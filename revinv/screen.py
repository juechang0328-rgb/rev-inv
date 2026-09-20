"""Screen a single month's cross-section of companies by revenue momentum.

Ranks companies by YoY revenue growth relative to their own industry's
YoY growth baseline for the same month, since the same YoY number means
different things in an industry upswing vs. a downswing.

The baseline is the industry's median YoY, not its mean. Some industries
(construction/real estate especially, due to lumpy revenue recognition,
but also small biotech names) routinely have individual companies post
YoY swings in the thousands of percent off a near-zero prior-year base.
A mean lets one such company drag the whole industry's baseline with it,
distorting every other company's relative strength; the median is far
less sensitive to that.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Optional


@dataclass
class ScreenResult:
    company_id: str
    company_name: Optional[str]
    industry: str
    data_ym: str
    market: Optional[str]
    revenue: Optional[float]
    yoy_pct: float
    mom_pct: Optional[float]
    industry_median_yoy: Optional[float]
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
    industry_median_yoy = {ind: median(vals) for ind, vals in by_industry.items() if vals}

    results: list[ScreenResult] = []
    for r in records:
        yoy = r.get("yoy_pct")
        if yoy is None or yoy < min_yoy_pct:
            continue
        mom = r.get("mom_pct")
        if require_positive_mom and (mom is None or mom <= 0):
            continue
        industry = r.get("industry") or ""
        baseline = industry_median_yoy.get(industry)
        relative_strength = None if baseline is None else yoy - baseline
        results.append(
            ScreenResult(
                company_id=r["company_id"],
                company_name=r.get("company_name"),
                industry=industry,
                data_ym=r.get("data_ym"),
                market=r.get("market"),
                revenue=r.get("revenue"),
                yoy_pct=yoy,
                mom_pct=mom,
                industry_median_yoy=baseline,
                relative_strength=relative_strength,
            )
        )

    results.sort(key=lambda x: (x.relative_strength is None, -(x.relative_strength or 0.0)))
    return results
