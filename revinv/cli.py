"""Command line interface: fetch TWSE monthly revenue and screen it."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from . import db, screen, twse

logger = logging.getLogger(__name__)


def cmd_fetch(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    try:
        records = twse.fetch_monthly_revenue()
    except Exception:
        logger.exception("Failed to fetch TWSE monthly revenue")
        return 1
    count = db.upsert_monthly_revenue(conn, records)
    logger.info("Stored %d monthly revenue records", count)
    return 0


def cmd_screen(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    data_ym = args.data_ym or db.fetch_latest_ym(conn)
    if not data_ym:
        logger.error("No data available. Run 'revinv fetch' first.")
        return 1
    rows = db.load_snapshot(conn, data_ym)
    results = screen.screen_snapshot(
        rows, min_yoy_pct=args.min_yoy, require_positive_mom=args.positive_mom
    )
    results = results[: args.top]
    if not results:
        print(f"No companies matched the criteria for {data_ym}.")
        return 0

    print(f"{data_ym} 篩選結果 (共 {len(results)} 家)")
    print(f"{'代號':<6}{'名稱':<10}{'產業別':<12}{'YoY%':>8}{'MoM%':>8}{'產業均YoY%':>12}{'相對強度':>10}")
    for r in results:
        print(
            f"{r.company_id:<6}{r.company_name or '':<10}{r.industry:<12}"
            f"{_fmt(r.yoy_pct):>8}{_fmt(r.mom_pct):>8}"
            f"{_fmt(r.industry_avg_yoy):>12}{_fmt(r.relative_strength):>10}"
        )
    return 0


def _fmt(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.1f}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="revinv", description=__doc__)
    parser.add_argument("--db", default=str(db.DEFAULT_DB_PATH), help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser("fetch", help="Fetch latest TWSE monthly revenue and store it")
    fetch_p.set_defaults(func=cmd_fetch)

    screen_p = sub.add_parser("screen", help="Screen stored monthly revenue for momentum")
    screen_p.add_argument("--data-ym", help="Data year-month (e.g. 11408); defaults to latest stored")
    screen_p.add_argument("--min-yoy", type=float, default=10.0, help="Minimum YoY revenue growth %%")
    screen_p.add_argument("--positive-mom", action="store_true", help="Also require positive MoM growth")
    screen_p.add_argument("--top", type=int, default=20, help="Number of companies to show")
    screen_p.set_defaults(func=cmd_screen)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
