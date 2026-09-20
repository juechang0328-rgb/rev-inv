"""Command line interface: fetch TWSE/TPEx monthly revenue and screen it."""

from __future__ import annotations

import argparse
import csv
import io
import logging
import sys
from pathlib import Path
from typing import Optional

from . import db, screen, tej_industry, tpex, twse

logger = logging.getLogger(__name__)

_COLUMN_HEADERS = {
    "data_ym": "資料年月",
    "company_id": "代號",
    "company_name": "名稱",
    "market": "市場",
    "industry": "產業別",
    "yoy_pct": "YoY%",
    "mom_pct": "MoM%",
    "industry_median_yoy": "產業中位YoY%",
    "peer_count": "同業家數",
    "relative_strength": "相對強度",
}
_COLUMN_ORDER = list(_COLUMN_HEADERS)

_MARKET_FETCHERS = {
    "twse": ("TWSE", twse.fetch_monthly_revenue),
    "tpex": ("TPEx", tpex.fetch_monthly_revenue),
}


def cmd_fetch(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    markets = _MARKET_FETCHERS if args.market == "all" else {args.market: _MARKET_FETCHERS[args.market]}

    total = 0
    failures = []
    for market_code, (market_label, fetch_fn) in markets.items():
        try:
            records = fetch_fn()
        except Exception:
            logger.exception("Failed to fetch %s monthly revenue", market_label)
            failures.append(market_code)
            continue
        for r in records:
            r["market"] = market_label
        count = db.upsert_monthly_revenue(conn, records)
        logger.info("Stored %d %s monthly revenue records", count, market_label)
        total += count

    if failures and len(failures) == len(markets):
        return 1
    logger.info("Stored %d monthly revenue records in total", total)
    return 0


def cmd_screen(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    data_ym = args.data_ym or db.fetch_latest_ym(conn)
    if not data_ym:
        logger.error("No data available. Run 'revinv fetch' first.")
        return 1
    stored_rows = db.load_snapshot(conn, data_ym)
    if args.industry_source == "tej":
        stored_rows = tej_industry.enrich_with_tej_industry(stored_rows)
    results = screen.screen_snapshot(
        stored_rows, min_yoy_pct=args.min_yoy, require_positive_mom=args.positive_mom
    )
    if args.top > 0:
        results = results[: args.top]

    rows = _results_to_rows(results)
    if args.format == "csv":
        output = _format_csv(rows)
    elif args.format == "markdown":
        output = _format_markdown(rows, data_ym)
    else:
        output = _format_text(rows, data_ym)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        logger.info("Wrote %d rows to %s", len(rows), out_path)
    else:
        print(output, end="")
    return 0


def _results_to_rows(results: list[screen.ScreenResult]) -> list[dict]:
    return [
        {
            "data_ym": r.data_ym,
            "company_id": r.company_id,
            "company_name": r.company_name or "",
            "market": r.market or "",
            "industry": r.industry,
            "yoy_pct": r.yoy_pct,
            "mom_pct": r.mom_pct,
            "industry_median_yoy": r.industry_median_yoy,
            "peer_count": r.peer_count,
            "relative_strength": r.relative_strength,
        }
        for r in results
    ]


def _fmt(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.1f}"


def _format_text(rows: list[dict], data_ym: str) -> str:
    if not rows:
        return f"No companies matched the criteria for {data_ym}.\n"
    lines = [
        f"{data_ym} 篩選結果 (共 {len(rows)} 家)",
        f"{'代號':<6}{'名稱':<10}{'市場':<6}{'產業別':<16}"
        f"{'YoY%':>8}{'MoM%':>8}{'產業中位YoY%':>14}{'同業家數':>8}{'相對強度':>10}",
    ]
    for row in rows:
        lines.append(
            f"{row['company_id']:<6}{row['company_name']:<10}{row['market']:<6}{row['industry']:<16}"
            f"{_fmt(row['yoy_pct']):>8}{_fmt(row['mom_pct']):>8}"
            f"{_fmt(row['industry_median_yoy']):>14}{row['peer_count']:>8}{_fmt(row['relative_strength']):>10}"
        )
    return "\n".join(lines) + "\n"


def _format_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_COLUMN_ORDER)
    writer.writerow(_COLUMN_HEADERS)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _format_markdown(rows: list[dict], data_ym: str) -> str:
    header = f"# {data_ym} 篩選結果 (共 {len(rows)} 家)\n\n"
    if not rows:
        return header + "_No companies matched the criteria._\n"
    headers = [_COLUMN_HEADERS[c] for c in _COLUMN_ORDER]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        cells = []
        for c in _COLUMN_ORDER:
            value = row[c]
            if isinstance(value, float):
                value = f"{value:.1f}"
            cells.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return header + "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="revinv", description=__doc__)
    parser.add_argument("--db", default=str(db.DEFAULT_DB_PATH), help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_p = sub.add_parser("fetch", help="Fetch latest TWSE/TPEx monthly revenue and store it")
    fetch_p.add_argument(
        "--market",
        choices=["all", "twse", "tpex"],
        default="all",
        help="Which market to fetch (default: all)",
    )
    fetch_p.set_defaults(func=cmd_fetch)

    screen_p = sub.add_parser("screen", help="Screen stored monthly revenue for momentum")
    screen_p.add_argument("--data-ym", help="Data year-month (e.g. 11408); defaults to latest stored")
    screen_p.add_argument("--min-yoy", type=float, default=10.0, help="Minimum YoY revenue growth %%")
    screen_p.add_argument("--positive-mom", action="store_true", help="Also require positive MoM growth")
    screen_p.add_argument(
        "--industry-source",
        choices=["tej", "twse"],
        default="tej",
        help=(
            "Industry classification to group peers by: 'tej' (TEJ's finer "
            "sub-industry, default) or 'twse' (TWSE/TPEx's own broader 產業別)"
        ),
    )
    screen_p.add_argument(
        "--top", type=int, default=20, help="Number of companies to show (0 = no limit)"
    )
    screen_p.add_argument(
        "--format", choices=["text", "csv", "markdown"], default="text", help="Output format"
    )
    screen_p.add_argument("--output", help="Write output to this file instead of stdout")
    screen_p.set_defaults(func=cmd_screen)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
