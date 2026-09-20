"""Screen a single month's cross-section of companies by revenue momentum.

Ranks companies by YoY revenue growth relative to their own industry's
average YoY growth for the same month, since the same YoY number means
different things in an industry upswing vs. a downswing.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Optional


@dataclass
class ScreenResult:
    company_id: str
    company_name: Optional[str]
    industry: str
    data_ym: str
    revenue: Optional[float]
    yoy_pct: float
    mom_pct: Optional[float]
    industry_avg_yoy: Optional[float]
    relative_strength: Optional[float]


def screen_snapshot(
    records: list[dict],
    min_yoy_pct: float = 0.0,
    require_positive_mom: bool = False,
) -> list[ScreenResult]:
    by_industry: dict[str, list[float]] = {}
    for r in records:
        yoy = r.get("yoy_pct")
        if yoy is None:
            continue
        by_industry.setdefault(r.get("industry") or "", []).append(yoy)
    industry_avg_yoy = {ind: mean(vals) for ind, vals in by_industry.items() if vals}

    results: list[ScreenResult] = []
    for r in records:
        yoy = r.get("yoy_pct")
        if yoy is None or yoy < min_yoy_pct:
            continue
        mom = r.get("mom_pct")
        if require_positive_mom and (mom is None or mom <= 0):
            continue
        industry = r.get("industry") or ""
        avg_yoy = industry_avg_yoy.get(industry)
        relative_strength = None if avg_yoy is None else yoy - avg_yoy
        results.append(
            ScreenResult(
                company_id=r["company_id"],
                company_name=r.get("company_name"),
                industry=industry,
                data_ym=r.get("data_ym"),
                revenue=r.get("revenue"),
                yoy_pct=yoy,
                mom_pct=mom,
                industry_avg_yoy=avg_yoy,
                relative_strength=relative_strength,
            )
        )

    results.sort(key=lambda x: (x.relative_strength is None, -(x.relative_strength or 0.0)))
    return results
