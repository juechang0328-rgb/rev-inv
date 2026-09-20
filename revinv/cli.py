"""Command line interface: fetch TWSE/TPEx monthly revenue and screen it."""

from __future__ import annotations

import argparse
import csv
import io
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

from . import db, quarterly, screen, tej_industry, tpex, twse

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

_INDUSTRY_COLUMN_HEADERS = {
    "data_ym": "資料年月",
    "industry": "產業別",
    "peer_count": "公司家數",
    "median_yoy": "YoY中位數%",
}
_INDUSTRY_COLUMN_ORDER = list(_INDUSTRY_COLUMN_HEADERS)

_MARKET_FETCHERS = {
    "twse": ("TWSE", twse.fetch_monthly_revenue),
    "tpex": ("TPEx", tpex.fetch_monthly_revenue),
}

_CONFIRM_COLUMN_HEADERS = {
    "data_ym": "資料年月",
    "company_id": "代號",
    "company_name": "名稱",
    "market": "市場",
    "industry": "產業別",
    "yoy_pct": "YoY%",
    "relative_strength": "相對強度",
    "quarter": "季報期別",
    "dio": "存貨周轉天期",
    "dio_prior": "存貨周轉天期(上季)",
    "dso": "應收帳款收現天期",
    "dso_prior": "應收帳款收現天期(上季)",
    "note": "二次確認",
}
_CONFIRM_COLUMN_ORDER = list(_CONFIRM_COLUMN_HEADERS)


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


def _get_screened_results(
    args: argparse.Namespace,
) -> tuple[Optional[str], list[screen.ScreenResult]]:
    conn = db.connect(args.db)
    data_ym = args.data_ym or db.fetch_latest_ym(conn)
    if not data_ym:
        return None, []
    stored_rows = db.load_snapshot(conn, data_ym)
    if args.industry_source == "tej":
        stored_rows = tej_industry.enrich_with_tej_industry(stored_rows)
    results = screen.screen_snapshot(
        stored_rows, min_yoy_pct=args.min_yoy, require_positive_mom=args.positive_mom
    )
    if args.industry:
        results = screen.filter_results(results, industries=set(args.industry))
    if args.top > 0:
        results = results[: args.top]
    return data_ym, results


def cmd_screen(args: argparse.Namespace) -> int:
    data_ym, results = _get_screened_results(args)
    if data_ym is None:
        logger.error("No data available. Run 'revinv fetch' first.")
        return 1

    rows = _results_to_rows(results)
    if args.format == "csv":
        output = _generic_csv(rows, _COLUMN_ORDER, _COLUMN_HEADERS)
    elif args.format == "markdown":
        output = _generic_markdown(rows, data_ym, "篩選結果", _COLUMN_ORDER, _COLUMN_HEADERS)
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


def cmd_industries(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    data_ym = args.data_ym or db.fetch_latest_ym(conn)
    if not data_ym:
        logger.error("No data available. Run 'revinv fetch' first.")
        return 1
    stored_rows = db.load_snapshot(conn, data_ym)
    if args.industry_source == "tej":
        stored_rows = tej_industry.enrich_with_tej_industry(stored_rows)
    summaries = screen.summarize_industries(stored_rows)
    if args.top > 0:
        summaries = summaries[: args.top]

    rows = [
        {
            "data_ym": data_ym,
            "industry": s.industry,
            "peer_count": s.peer_count,
            "median_yoy": s.median_yoy,
        }
        for s in summaries
    ]
    if args.format == "csv":
        output = _generic_csv(rows, _INDUSTRY_COLUMN_ORDER, _INDUSTRY_COLUMN_HEADERS)
    elif args.format == "markdown":
        output = _generic_markdown(
            rows, data_ym, "產業趨勢", _INDUSTRY_COLUMN_ORDER, _INDUSTRY_COLUMN_HEADERS
        )
    else:
        output = _format_industries_text(rows, data_ym)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        logger.info("Wrote %d industries to %s", len(rows), out_path)
    else:
        print(output, end="")
    return 0


def cmd_confirm(args: argparse.Namespace) -> int:
    data_ym, results = _get_screened_results(args)
    if data_ym is None:
        logger.error("No data available. Run 'revinv fetch' first.")
        return 1

    token = args.finmind_token or os.environ.get("FINMIND_TOKEN")
    rows = []
    for i, r in enumerate(results):
        if i > 0:
            time.sleep(args.request_delay)
        try:
            confirmation = quarterly.fetch_confirmation(r.company_id, token=token)
        except Exception:
            logger.warning(
                "Failed to fetch quarterly confirmation for %s", r.company_id, exc_info=True
            )
            confirmation = None
        rows.append(_confirm_row(r, confirmation))

    if args.format == "csv":
        output = _generic_csv(rows, _CONFIRM_COLUMN_ORDER, _CONFIRM_COLUMN_HEADERS)
    elif args.format == "markdown":
        output = _generic_markdown(rows, data_ym, "季報二次確認", _CONFIRM_COLUMN_ORDER, _CONFIRM_COLUMN_HEADERS)
    else:
        output = _format_confirm_text(rows, data_ym)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        logger.info("Wrote %d rows to %s", len(rows), out_path)
    else:
        print(output, end="")
    return 0


def _confirm_row(r: screen.ScreenResult, c: Optional[quarterly.QuarterlyConfirmation]) -> dict:
    return {
        "data_ym": r.data_ym,
        "company_id": r.company_id,
        "company_name": r.company_name or "",
        "market": r.market or "",
        "industry": r.industry,
        "yoy_pct": r.yoy_pct,
        "relative_strength": r.relative_strength,
        "quarter": c.period if c else "",
        "dio": c.dio if c else None,
        "dio_prior": c.dio_prior if c else None,
        "dso": c.dso if c else None,
        "dso_prior": c.dso_prior if c else None,
        "note": _confirmation_note(c),
    }


def _confirmation_note(c: Optional[quarterly.QuarterlyConfirmation]) -> str:
    if c is None:
        return "無季報資料（可能為金融股或近期上市）"
    parts = []
    if c.dio is not None and c.dio_prior is not None:
        if c.dio < c.dio_prior - 0.5:
            parts.append("存貨周轉加快")
        elif c.dio > c.dio_prior + 0.5:
            parts.append("存貨周轉轉慢")
        else:
            parts.append("存貨周轉持平")
    if c.dso is not None and c.dso_prior is not None:
        if c.dso < c.dso_prior - 0.5:
            parts.append("收現變快")
        elif c.dso > c.dso_prior + 0.5:
            parts.append("收現變慢")
        else:
            parts.append("收現持平")
    return "、".join(parts) if parts else "資料不足"


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


def _format_industries_text(rows: list[dict], data_ym: str) -> str:
    if not rows:
        return f"No industry data available for {data_ym}.\n"
    lines = [
        f"{data_ym} 產業趨勢 (共 {len(rows)} 個產業)",
        f"{'產業別':<20}{'公司家數':>8}{'YoY中位數%':>12}",
    ]
    for row in rows:
        lines.append(f"{row['industry']:<20}{row['peer_count']:>8}{_fmt(row['median_yoy']):>12}")
    return "\n".join(lines) + "\n"


def _format_confirm_text(rows: list[dict], data_ym: str) -> str:
    if not rows:
        return f"No companies matched the criteria for {data_ym}.\n"
    lines = [
        f"{data_ym} 季報二次確認 (共 {len(rows)} 家)",
        f"{'代號':<6}{'名稱':<10}{'產業別':<16}{'YoY%':>8}"
        f"{'存貨周轉':>10}{'(上季)':>10}{'收現天期':>10}{'(上季)':>10}  二次確認",
    ]
    for row in rows:
        lines.append(
            f"{row['company_id']:<6}{row['company_name']:<10}{row['industry']:<16}{_fmt(row['yoy_pct']):>8}"
            f"{_fmt(row['dio']):>10}{_fmt(row['dio_prior']):>10}"
            f"{_fmt(row['dso']):>10}{_fmt(row['dso_prior']):>10}  {row['note']}"
        )
    return "\n".join(lines) + "\n"


def _generic_csv(rows: list[dict], column_order: list[str], column_headers: dict[str, str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=column_order)
    writer.writerow(column_headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _generic_markdown(
    rows: list[dict],
    data_ym: str,
    title: str,
    column_order: list[str],
    column_headers: dict[str, str],
) -> str:
    header = f"# {data_ym} {title} (共 {len(rows)} 筆)\n\n"
    if not rows:
        return header + "_No data available._\n"
    headers = [column_headers[c] for c in column_order]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        cells = []
        for c in column_order:
            value = row[c]
            if value is None:
                text = "-"
            elif isinstance(value, float):
                text = f"{value:.1f}"
            else:
                text = str(value)
            cells.append(text.replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return header + "\n".join(lines) + "\n"


def _add_screen_filter_args(parser: argparse.ArgumentParser, top_default: int) -> None:
    parser.add_argument("--data-ym", help="Data year-month (e.g. 11408); defaults to latest stored")
    parser.add_argument("--min-yoy", type=float, default=10.0, help="Minimum YoY revenue growth %%")
    parser.add_argument("--positive-mom", action="store_true", help="Also require positive MoM growth")
    parser.add_argument(
        "--industry-source",
        choices=["tej", "twse"],
        default="tej",
        help=(
            "Industry classification to group peers by: 'tej' (TEJ's 96-category "
            "industry, default) or 'twse' (TWSE/TPEx's own broader 產業別)"
        ),
    )
    parser.add_argument(
        "--industry",
        action="append",
        help=(
            "Only include this industry (repeatable for multiple); matches the "
            "value exactly as shown by 'revinv industries'. Useful for looking at "
            "industry trends first (see the industries command) and then drilling "
            "into strong companies within one."
        ),
    )
    parser.add_argument(
        "--top", type=int, default=top_default, help="Number of companies to show (0 = no limit)"
    )


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
    _add_screen_filter_args(screen_p, top_default=20)
    screen_p.add_argument(
        "--format", choices=["text", "csv", "markdown"], default="text", help="Output format"
    )
    screen_p.add_argument("--output", help="Write output to this file instead of stdout")
    screen_p.set_defaults(func=cmd_screen)

    industries_p = sub.add_parser(
        "industries", help="Summarize industry-level YoY trend before drilling into companies"
    )
    industries_p.add_argument("--data-ym", help="Data year-month (e.g. 11408); defaults to latest stored")
    industries_p.add_argument(
        "--industry-source",
        choices=["tej", "twse"],
        default="tej",
        help=(
            "Industry classification to group by: 'tej' (TEJ's 96-category "
            "industry, default) or 'twse' (TWSE/TPEx's own broader 產業別)"
        ),
    )
    industries_p.add_argument(
        "--top", type=int, default=30, help="Number of industries to show (0 = no limit)"
    )
    industries_p.add_argument(
        "--format", choices=["text", "csv", "markdown"], default="text", help="Output format"
    )
    industries_p.add_argument("--output", help="Write output to this file instead of stdout")
    industries_p.set_defaults(func=cmd_industries)

    confirm_p = sub.add_parser(
        "confirm",
        help=(
            "Quarterly confirmation (存貨周轉天期/應收帳款收現天期) for the same "
            "shortlist 'screen' would produce, via FinMind"
        ),
    )
    _add_screen_filter_args(confirm_p, top_default=20)
    confirm_p.add_argument(
        "--finmind-token",
        help="FinMind API token for a higher rate limit (or set the FINMIND_TOKEN env var)",
    )
    confirm_p.add_argument(
        "--request-delay",
        type=float,
        default=0.5,
        help="Seconds to wait between companies' FinMind requests (default: 0.5)",
    )
    confirm_p.add_argument(
        "--format", choices=["text", "csv", "markdown"], default="text", help="Output format"
    )
    confirm_p.add_argument("--output", help="Write output to this file instead of stdout")
    confirm_p.set_defaults(func=cmd_confirm)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
