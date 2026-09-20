"""Quarterly inventory-turnover / receivables-collection confirmation.

This is the "季報確認" stage from the original two-stage screening plan:
monthly revenue picks candidates, and inventory turnover days (存貨周轉天期)
plus receivables collection days (應收帳款收現天期) are a secondary check —
"存貨降但營收也降" (inventory shrinking because the business is shrinking,
not because it's running lean) is exactly the kind of false positive a
revenue-only screen can't tell apart on its own.

Two FinMind quirks make this easy to get quietly wrong, so they're
verified against real data rather than assumed:

1. Every line item is paired with a "_per" variant (percentage of total
   assets/liabilities/equity) that shares the *exact same* Chinese
   `origin_name` as the raw-amount row -- e.g. both "AccountsPayable" and
   "AccountsPayable_per" are labeled 應付帳款. `_extract()` drops any row
   whose `type` ends in "_per" before matching by name, so the raw
   amount is always what's used.
2. Unlike a raw MOPS filing (where the income statement is cumulative
   year-to-date -- the "Q2" report covers Jan-Jun, not just Apr-Jun),
   FinMind's `Revenue`/`CostOfGoodsSold` values are already single-quarter.
   This was verified against live data, not assumed: an earlier version
   of this module tried to de-cumulate them, which produced nonsense
   (including negative "single-quarter" values) once real data confirmed
   a company's own revenue could legitimately drop quarter-over-quarter --
   impossible for a truly cumulative series. So these fields are used
   directly, exactly like the point-in-time balance-sheet items.

Line items are matched by their Chinese `origin_name` (e.g. "存貨",
"營業收入") rather than FinMind's English `type` field, since origin_name
is what's actually documented/stable and some type codes vary by the
account template a company's industry uses (e.g. banks and insurers don't
report inventory or cost of goods sold at all — confirm_company() returns
None for those rather than a bogus zero).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Optional

from . import finmind

# Filings don't state an exact day count for the period; 91 is the
# conventional Taiwan-market approximation for a calendar quarter.
QUARTER_DAYS = 91

# How far back to pull: enough to comfortably cover the 3 consecutive
# quarters confirm_company() needs (current + prior, each needing the
# quarter before it for a two-point average).
LOOKBACK_DAYS = 730

_INVENTORY_LABELS = ["存貨"]
_ACCOUNTS_RECEIVABLE_LABELS = ["應收帳款淨額", "應收帳款"]
_REVENUE_LABELS = ["營業收入合計", "營業收入"]
_COGS_LABELS = ["營業成本合計", "營業成本"]


@dataclass
class QuarterPoint:
    date: str
    inventory: Optional[float]
    accounts_receivable: Optional[float]
    revenue: Optional[float]  # single-quarter, as FinMind reports it
    cogs: Optional[float]  # single-quarter, as FinMind reports it


@dataclass
class QuarterlyConfirmation:
    company_id: str
    period: str
    prior_period: str
    dio: Optional[float]  # 存貨周轉天期 (days), this quarter
    dio_prior: Optional[float]  # same, prior quarter -- for a trend
    dso: Optional[float]  # 應收帳款收現天期 (days), this quarter
    dso_prior: Optional[float]


def _extract(rows: list[dict[str, Any]], labels: list[str]) -> Optional[float]:
    # FinMind pairs many line items with a "_per" variant (percentage of
    # total assets/liabilities/equity) that shares the exact same Chinese
    # origin_name as the raw-amount row, e.g. both "AccountsPayable" and
    # "AccountsPayable_per" are labeled 應付帳款. Matching by origin_name
    # alone would silently pick whichever one happens to come last for
    # that name, so the percentage variants are excluded up front.
    by_name = {
        r.get("origin_name"): r.get("value")
        for r in rows
        if not str(r.get("type", "")).endswith("_per")
    }
    for label in labels:
        if label in by_name:
            try:
                return float(by_name[label])
            except (TypeError, ValueError):
                return None
    return None


def _group_by_date(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(r.get("date", ""), []).append(r)
    return grouped


def build_quarterly_series(
    balance_sheet_rows: list[dict[str, Any]],
    financial_statement_rows: list[dict[str, Any]],
) -> list[QuarterPoint]:
    bs_by_date = _group_by_date(balance_sheet_rows)
    fs_by_date = _group_by_date(financial_statement_rows)

    points = []
    for date in sorted(set(bs_by_date) | set(fs_by_date)):
        bs_rows = bs_by_date.get(date, [])
        fs_rows = fs_by_date.get(date, [])
        points.append(
            QuarterPoint(
                date=date,
                inventory=_extract(bs_rows, _INVENTORY_LABELS),
                accounts_receivable=_extract(bs_rows, _ACCOUNTS_RECEIVABLE_LABELS),
                revenue=_extract(fs_rows, _REVENUE_LABELS),
                cogs=_extract(fs_rows, _COGS_LABELS),
            )
        )
    return points


def _avg(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return None if a is None or b is None else (a + b) / 2


def _days(avg_balance: Optional[float], flow: Optional[float]) -> Optional[float]:
    if avg_balance is None or not flow:
        return None
    return avg_balance / flow * QUARTER_DAYS


def confirm_company(
    company_id: str, points: list[QuarterPoint]
) -> Optional[QuarterlyConfirmation]:
    """Derive a DIO/DSO trend confirmation from a company's quarterly series.

    Needs at least 3 consecutive quarter points -- the latest quarter's
    DIO/DSO plus the prior quarter's (for a trend) each need an average of
    two consecutive balance-sheet snapshots. Returns None when there isn't
    enough data (a very recent IPO) or when neither metric applies at all
    (e.g. a bank or insurer, which has no inventory/COGS concept).
    """
    points = sorted(points, key=lambda p: p.date)
    if len(points) < 3:
        return None
    latest, prior, before_prior = points[-1], points[-2], points[-3]

    dio = _days(_avg(prior.inventory, latest.inventory), latest.cogs)
    dio_prior = _days(_avg(before_prior.inventory, prior.inventory), prior.cogs)
    dso = _days(_avg(prior.accounts_receivable, latest.accounts_receivable), latest.revenue)
    dso_prior = _days(
        _avg(before_prior.accounts_receivable, prior.accounts_receivable), prior.revenue
    )

    if dio is None and dso is None:
        return None

    return QuarterlyConfirmation(
        company_id=company_id,
        period=latest.date,
        prior_period=prior.date,
        dio=dio,
        dio_prior=dio_prior,
        dso=dso,
        dso_prior=dso_prior,
    )


def fetch_confirmation(
    company_id: str, token: Optional[str] = None
) -> Optional[QuarterlyConfirmation]:
    """Fetch this company's recent quarterly filings from FinMind and
    derive its DIO/DSO trend confirmation. Requires outbound network
    access to api.finmindtrade.com, which is not reachable from every
    sandboxed environment (see README).
    """
    start_date = (datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)).isoformat()
    balance_sheet_rows = finmind.fetch_balance_sheet(company_id, start_date, token)
    financial_statement_rows = finmind.fetch_financial_statements(company_id, start_date, token)
    points = build_quarterly_series(balance_sheet_rows, financial_statement_rows)
    return confirm_company(company_id, points)
