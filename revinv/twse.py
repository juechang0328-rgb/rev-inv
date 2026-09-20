"""Client for the TWSE (Taiwan Stock Exchange) OpenAPI monthly revenue dataset.

Dataset: t187ap05_L (上市公司每月營業收入彙總表)
https://openapi.twse.com.tw/v1/opendata/t187ap05_L
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

import requests

logger = logging.getLogger(__name__)

MONTHLY_REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"

# Maps the API's Chinese column names to stable, English field names.
FIELD_MAP = {
    "出表日期": "report_date",
    "資料年月": "data_ym",
    "公司代號": "company_id",
    "公司名稱": "company_name",
    "產業別": "industry",
    "營業收入-當月營收": "revenue",
    "營業收入-上月營收": "revenue_prev_month",
    "營業收入-去年當月營收": "revenue_prev_year_month",
    "營業收入-上月比較增減(%)": "mom_pct",
    "營業收入-去年同月增減(%)": "yoy_pct",
    "累計營業收入-當月累計營收": "cumulative_revenue",
    "累計營業收入-去年累計營收": "cumulative_revenue_prev_year",
    "累計營業收入-前期比較增減(%)": "cumulative_yoy_pct",
    "備註": "remark",
}

# Monetary fields: the API reports these in NT$ thousands (仟元).
_AMOUNT_FIELDS = {
    "revenue",
    "revenue_prev_month",
    "revenue_prev_year_month",
    "cumulative_revenue",
    "cumulative_revenue_prev_year",
}

# Percentage fields: already a plain percentage number, no unit conversion.
_PERCENT_FIELDS = {
    "mom_pct",
    "yoy_pct",
    "cumulative_yoy_pct",
}

_NUMERIC_FIELDS = _AMOUNT_FIELDS | _PERCENT_FIELDS

# The API reports amounts in NT$ thousands; multiply by this to get NT$.
AMOUNT_UNIT_SCALE = 1000

_PLACEHOLDER_VALUES = {"", "N/A", "-", "--"}


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text in _PLACEHOLDER_VALUES:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        logger.warning("Could not parse numeric value: %r", value)
        return None


def normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert one raw TWSE JSON record into a flat dict with English keys.

    Percentage fields are parsed to float as-is. Amount fields are parsed
    to float and scaled from the API's native NT$ thousands (仟元) to NT$,
    so revenue figures are directly comparable to other data sources (e.g.
    quarterly financial statement line items) without a unit mismatch.
    """
    record: dict[str, Any] = {}
    for zh_key, en_key in FIELD_MAP.items():
        value = raw.get(zh_key)
        if en_key in _AMOUNT_FIELDS:
            amount = _to_float(value)
            record[en_key] = None if amount is None else amount * AMOUNT_UNIT_SCALE
        elif en_key in _PERCENT_FIELDS:
            record[en_key] = _to_float(value)
        else:
            record[en_key] = value
    return record


def normalize_records(raw_records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_record(r) for r in raw_records]


def fetch_monthly_revenue(timeout: float = 30.0) -> list[dict[str, Any]]:
    """Fetch and normalize the latest listed-company monthly revenue summary.

    Requires outbound network access to openapi.twse.com.tw, which is not
    reachable from every sandboxed environment (see README).
    """
    response = requests.get(MONTHLY_REVENUE_URL, timeout=timeout)
    response.raise_for_status()
    return normalize_records(response.json())
