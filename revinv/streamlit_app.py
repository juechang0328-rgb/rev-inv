"""Interactive browser for revinv screening results.

Run with:
    streamlit run revinv/streamlit_app.py

If a local SQLite database populated by `python -m revinv.cli fetch`
exists, this reads live from it with fully adjustable filters (same
screening logic as the CLI, including a toggle between TEJ's finer
sub-industry classification and TWSE/TPEx's own broader 產業別 — see
revinv.tej_industry). Otherwise it falls back to browsing the repo's own
results/latest.csv (produced daily by .github/workflows/daily-screen.yml)
in read-only mode, since that already has fixed screening thresholds
baked in.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import streamlit as st

from revinv import db, screen, tej_industry

st.set_page_config(page_title="rev-inv 營收篩選", layout="wide")
st.title("台股營收轉強篩選")

REPO_ROOT = Path(__file__).resolve().parent.parent
FALLBACK_CSV = REPO_ROOT / "results" / "latest.csv"


def _round(value):
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return value


def _render_table(table: list[dict], data_ym: str) -> None:
    st.dataframe(table, use_container_width=True, hide_index=True)
    if not table:
        return
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(table[0].keys()))
    writer.writeheader()
    writer.writerows(table)
    st.download_button(
        "下載 CSV",
        data=buf.getvalue(),
        file_name=f"revinv_screen_{data_ym}.csv",
        mime="text/csv",
    )


def render_live_mode(conn) -> None:
    available_ym = db.list_data_ym(conn)
    data_ym = st.sidebar.selectbox("資料年月", available_ym, index=0)
    min_yoy = st.sidebar.number_input("最低 YoY 成長 (%)", value=15.0, step=5.0)
    positive_mom = st.sidebar.checkbox("同時要求 MoM 為正", value=True)
    industry_source = st.sidebar.radio(
        "產業分類",
        ["tej", "twse"],
        format_func=lambda v: "TEJ 子產業（較細）" if v == "tej" else "TWSE/TPEx 產業別（較粗）",
    )

    rows = db.load_snapshot(conn, data_ym)
    if industry_source == "tej":
        rows = tej_industry.enrich_with_tej_industry(rows)
    results = screen.screen_snapshot(rows, min_yoy_pct=min_yoy, require_positive_mom=positive_mom)

    market_options = sorted({r.market for r in results if r.market})
    selected_markets = st.sidebar.multiselect("市場", market_options, default=market_options)
    industry_options = sorted({r.industry for r in results})
    selected_industries = st.sidebar.multiselect("產業別", industry_options, default=industry_options)
    search = st.sidebar.text_input("搜尋代號/名稱")

    filtered = screen.filter_results(
        results,
        markets=set(selected_markets) if selected_markets else None,
        industries=set(selected_industries) if selected_industries else None,
        search=search,
    )

    st.caption(f"資料年月 {data_ym}，符合條件 {len(filtered)} / {len(results)} 家")

    table = [
        {
            "代號": r.company_id,
            "名稱": r.company_name,
            "市場": r.market,
            "產業別": r.industry,
            "YoY%": _round(r.yoy_pct),
            "MoM%": _round(r.mom_pct),
            "產業中位YoY%": _round(r.industry_median_yoy),
            "同業家數": r.peer_count,
            "相對強度": _round(r.relative_strength),
        }
        for r in filtered
    ]
    _render_table(table, data_ym)


def render_fallback_mode(csv_path: Path) -> None:
    st.info(
        "本機資料庫還沒有資料（還沒執行過 `python -m revinv.cli fetch`），"
        f"改用 repo 裡每天自動更新的 `{csv_path.relative_to(REPO_ROOT)}` 瀏覽——"
        "門檻已經固定在 YoY ≥ 15%、MoM 為正、前 50 名，要調整門檻請先在本機執行 fetch。"
    )
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        st.warning("目前沒有資料可以顯示。")
        return

    market_options = sorted({r["市場"] for r in rows if r.get("市場")})
    selected_markets = st.sidebar.multiselect("市場", market_options, default=market_options)
    industry_options = sorted({r["產業別"] for r in rows if r.get("產業別")})
    selected_industries = st.sidebar.multiselect("產業別", industry_options, default=industry_options)
    search = st.sidebar.text_input("搜尋代號/名稱").strip().lower()

    filtered = [
        r
        for r in rows
        if (not selected_markets or r.get("市場") in selected_markets)
        and (not selected_industries or r.get("產業別") in selected_industries)
        and (not search or search in r.get("代號", "").lower() or search in r.get("名稱", "").lower())
    ]
    data_ym = rows[0].get("資料年月", "")
    st.caption(f"資料年月 {data_ym}，符合條件 {len(filtered)} / {len(rows)} 家")
    _render_table(filtered, data_ym)


def main() -> None:
    db_path = st.sidebar.text_input("資料庫路徑", value=str(db.DEFAULT_DB_PATH))
    conn = db.connect(db_path)

    if db.list_data_ym(conn):
        render_live_mode(conn)
    elif FALLBACK_CSV.exists():
        render_fallback_mode(FALLBACK_CSV)
    else:
        st.warning(
            "本機資料庫是空的，repo 裡也還沒有 `results/latest.csv`。請先執行：\n\n"
            "```\npython -m revinv.cli fetch\n```"
        )


main()
