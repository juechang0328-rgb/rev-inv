"""Client for FinMind's quarterly financial statement data.

Used only as a secondary confirmation step on the shortlist of companies
that already passed the monthly-revenue screen (see revinv.quarterly),
never on the full market: FinMind's API is per-company (one HTTP call per
stock per dataset), so a full-market quarterly pull (~2000 companies x 2
datasets) would take hours against typical free-tier rate limits, whereas
confirming a few dozen shortlisted companies only costs a few dozen calls.

FinMind has no free public API for TWSE/TPEx-style "give me everyone at
once" fundamental data; this is the community package the original
brainstorm suggested to avoid hand-parsing MOPS' own XBRL/HTML quarterly
report pages.
"""

from __future__ import annotations

from typing import Any, Optional

import requests

BASE_URL = "https://api.finmindtrade.com/api/v4/data"

BALANCE_SHEET_DATASET = "TaiwanStockBalanceSheet"
FINANCIAL_STATEMENTS_DATASET = "TaiwanStockFinancialStatements"


def fetch_dataset(
    dataset: str,
    company_id: str,
    start_date: str,
    token: Optional[str] = None,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Fetch raw rows for one FinMind dataset/company/date range.

    Each row is {"date", "stock_id", "type", "value", "origin_name"}; a
    single report date has many rows (one per line item).
    """
    params = {"dataset": dataset, "data_id": company_id, "start_date": start_date}
    if token:
        params["token"] = token
    response = requests.get(BASE_URL, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if payload.get("msg") not in (None, "success", ""):
        raise RuntimeError(f"FinMind API error for {dataset}/{company_id}: {payload.get('msg')}")
    return payload.get("data", [])


def fetch_balance_sheet(
    company_id: str, start_date: str, token: Optional[str] = None, timeout: float = 30.0
) -> list[dict[str, Any]]:
    return fetch_dataset(BALANCE_SHEET_DATASET, company_id, start_date, token, timeout)


def fetch_financial_statements(
    company_id: str, start_date: str, token: Optional[str] = None, timeout: float = 30.0
) -> list[dict[str, Any]]:
    return fetch_dataset(FINANCIAL_STATEMENTS_DATASET, company_id, start_date, token, timeout)
