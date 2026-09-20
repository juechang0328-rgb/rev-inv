"""TEJ's industry classification, more granular than TWSE/TPEx's own
"產業別" (36 broad categories market-wide vs. TEJ's 96 mid-level "TEJ產業名"
categories) — e.g. TWSE's single "半導體業" splits under TEJ into IC design,
IC manufacturing, packaging & testing, etc., which matters for the
peer-group comparison in revinv.screen: comparing a company only against
its actual industry peers is a more meaningful baseline than comparing it
against every company TWSE lumps into the same broad sector.

TEJ also has an even finer 231-category "TEJ子產業名" (sub_industry), but
that's too granular for everyday screening — many sub-industries end up
with only 1-2 peer companies, which makes the median baseline unreliable.
The 96-category "TEJ產業名" (industry) is the default; sub_industry is
still available via enrich_with_tej_industry(records, level="sub_industry")
for anyone who wants to drill in further.

This is a static reference table (data/tej_industry.csv), not something
fetched live: TEJ's classification is proprietary/paid data with no free
public API, so the mapping was exported once from a TEJ dataset snapshot.
Refresh it manually (re-export from TEJ and overwrite the CSV) when it
goes stale — new IPOs and reclassified companies won't be in an old
snapshot, which is why lookup() returns None for unknown company_ids
rather than raising, so callers can fall back to the official industry.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple, Optional

_DATA_PATH = Path(__file__).resolve().parent / "data" / "tej_industry.csv"


class TejIndustry(NamedTuple):
    industry: str
    sub_industry: str


@lru_cache(maxsize=1)
def _load(data_path: Path = _DATA_PATH) -> dict[str, TejIndustry]:
    mapping: dict[str, TejIndustry] = {}
    with data_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mapping[row["company_id"]] = TejIndustry(
                industry=row["tej_industry"], sub_industry=row["tej_sub_industry"]
            )
    return mapping


def lookup(company_id: str) -> Optional[TejIndustry]:
    """The TEJ (industry, sub_industry) for a company_id, or None if unknown."""
    return _load().get(company_id)


def enrich_with_tej_industry(records: list[dict], level: str = "industry") -> list[dict]:
    """Copy `records`, replacing each `industry` with its TEJ classification.

    `level` is "industry" (the default 96-category TEJ產業名) or
    "sub_industry" (the finer 231-category TEJ子產業名). Companies not
    found in the TEJ mapping (e.g. a very recent IPO not yet in the
    snapshot) keep their original `industry` value unchanged.
    """
    if level not in ("industry", "sub_industry"):
        raise ValueError(f"level must be 'industry' or 'sub_industry', got {level!r}")
    enriched = []
    for r in records:
        tej = lookup(r.get("company_id", ""))
        row = dict(r)
        if tej is not None:
            row["industry"] = getattr(tej, level)
        enriched.append(row)
    return enriched
