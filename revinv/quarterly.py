"""Quarterly inventory-turnover / receivables-collection confirmation.

This is the "季報確認" stage from the original two-stage screening plan:
monthly revenue picks candidates, and inventory turnover days (存貨周轉天期)
plus receivables collection days (應收帳款收現天期) are a secondary check —
"存貨降但營收也降" (inventory shrinking because the business is shrinking,
not because it's running lean) is exactly the kind of false positive a
revenue-only screen can't tell apart on its own.

Two things about Taiwan's quarterly filings make this easy to get quietly
wrong, so they're handled explicitly rather than assumed away:

1. Income-statement line items (revenue, cost of goods sold) are reported
   CUMULATIVE year-to-date, not per-quarter: the "Q2" filing covers
   Jan-Jun, "Q3" covers Jan-Sep, and the annual filing covers all 12
   months. Only Q1 is already a standalone quarter. dequarterize() derives
   single-quarter figures by subtracting the prior quarter's cumulative
   value within the same fiscal year, and drops any quarter whose earlier
   siblings are missing rather than guessing.
2. Balance-sheet items (inventory, accounts receivable) are point-in-time
   snapshots, not cumulative — used as reported, no de-cumulation needed.

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

# How far back to pull: enough for the current quarter, the prior quarter
# (for a trend), and the earlier quarter each of those needs to
# de-cumulate against -- with slack for a fiscal-year boundary in between.
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
    revenue: Optional[float]  # single-quarter (already de-cumulated)
    cogs: Optional[float]  # single-quarter (already de-cumulated)


@dataclass
class QuarterlyConfirmation:
    company_id: str
    period: str
    prior_period: str
    dio: Optional[float]  # 存貨周轉天期 (days), this quarter
    dio_prior: Optional[float]  # same, prior quarter -- for a trend
    dso: Optional[float]  # 應收帳款收現天期 (days), this quarter
    dso_prior: Optional[float]


def _quarter_of(date_str: str) -> Optional[int]:
    return {"03": 1, "06": 2, "09": 3, "12": 4}.get(date_str[5:7])


def dequarterize(cumulative_by_date: dict[str, float]) -> dict[str, float]:
    """Cumulative year-to-date values -> single-quarter values.

    A quarter is only converted if every earlier quarter of the same
    fiscal year is present in `cumulative_by_date`; otherwise it (and any
    later quarter in that year) is left out rather than estimated.
    """
    by_year_quarter: dict[tuple[int, int], tuple[str, float]] = {}
    for date_str, value in cumulative_by_date.items():
        quarter = _quarter_of(date_str)
        if quarter is None:
            continue
        by_year_quarter[(int(date_str[:4]), quarter)] = (date_str, value)

    result: dict[str, float] = {}
    years = {year for year, _ in by_year_quarter}
    for year in years:
        prior_cumulative = 0.0
        for quarter in (1, 2, 3, 4):
            key = (year, quarter)
            if key not in by_year_quarter:
                break
            date_str, cumulative_value = by_year_quarter[key]
            result[date_str] = cumulative_value - prior_cumulative
            prior_cumulative = cumulative_value
    return result


def _extract(rows: list[dict[str, Any]], labels: list[str]) -> Optional[float]:
    by_name = {r.get("origin_name"): r.get("value") for r in rows}
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

    revenue_cumulative = {}
    cogs_cumulative = {}
    for date, rows in fs_by_date.items():
        revenue = _extract(rows, _REVENUE_LABELS)
        if revenue is not None:
            revenue_cumulative[date] = revenue
        cogs = _extract(rows, _COGS_LABELS)
        if cogs is not None:
            cogs_cumulative[date] = cogs
    revenue_by_date = dequarterize(revenue_cumulative)
    cogs_by_date = dequarterize(cogs_cumulative)

    points = []
    for date in sorted(set(bs_by_date) | set(fs_by_date)):
        bs_rows = bs_by_date.get(date, [])
        points.append(
            QuarterPoint(
                date=date,
                inventory=_extract(bs_rows, _INVENTORY_LABELS),
                accounts_receivable=_extract(bs_rows, _ACCOUNTS_RECEIVABLE_LABELS),
                revenue=revenue_by_date.get(date),
                cogs=cogs_by_date.get(date),
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
