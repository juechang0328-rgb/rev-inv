"""Client for the TPEx (Taipei Exchange) OpenAPI monthly revenue dataset.

Dataset: mopsfin_t187ap05_O (上櫃公司每月營業收入彙總表)
https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O

TPEx's OpenAPI reuses the exact same field names as TWSE's t187ap05_L —
both are sourced from the 公開資訊觀測站 (MOPS) format — so this module
reuses revinv.twse's FIELD_MAP and normalization logic and only supplies
the TPEx URL.
"""

from __future__ import annotations

from typing import Any

import requests

from .twse import normalize_records

MONTHLY_REVENUE_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"


def fetch_monthly_revenue(timeout: float = 30.0) -> list[dict[str, Any]]:
    """Fetch and normalize the latest OTC-listed company monthly revenue summary.

    Requires outbound network access to www.tpex.org.tw, which is not
    reachable from every sandboxed environment (see README).
    """
    response = requests.get(MONTHLY_REVENUE_URL, timeout=timeout)
    response.raise_for_status()
    return normalize_records(response.json())
