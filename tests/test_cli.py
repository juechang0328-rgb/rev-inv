import argparse
from unittest.mock import patch

from revinv import cli, db


def make_record(company_id):
    return {
        "company_id": company_id,
        "company_name": f"公司{company_id}",
        "industry": "電子",
        "data_ym": "11402",
        "revenue": 1000.0,
        "revenue_prev_month": None,
        "revenue_prev_year_month": None,
        "mom_pct": None,
        "yoy_pct": 10.0,
        "cumulative_revenue": None,
        "cumulative_revenue_prev_year": None,
        "cumulative_yoy_pct": None,
        "remark": "",
        "report_date": "1140310",
    }


def test_cmd_fetch_tags_and_stores_records_from_both_markets(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"
    fake_fetchers = {
        "twse": ("TWSE", lambda: [make_record("1101")]),
        "tpex": ("TPEx", lambda: [make_record("6488")]),
    }
    args = argparse.Namespace(db=str(db_path), market="all")

    with patch.object(cli, "_MARKET_FETCHERS", fake_fetchers):
        rc = cli.cmd_fetch(args)

    assert rc == 0
    conn = db.connect(str(db_path))
    rows = {row["company_id"]: row for row in db.load_snapshot(conn, "11402")}
    assert rows["1101"]["market"] == "TWSE"
    assert rows["6488"]["market"] == "TPEx"


def test_cmd_fetch_continues_when_one_market_fails(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"

    def failing():
        raise RuntimeError("boom")

    fake_fetchers = {
        "twse": ("TWSE", lambda: [make_record("1101")]),
        "tpex": ("TPEx", failing),
    }
    args = argparse.Namespace(db=str(db_path), market="all")

    with patch.object(cli, "_MARKET_FETCHERS", fake_fetchers):
        rc = cli.cmd_fetch(args)

    assert rc == 0
    conn = db.connect(str(db_path))
    rows = db.load_snapshot(conn, "11402")
    assert [r["company_id"] for r in rows] == ["1101"]


def test_cmd_fetch_returns_error_when_all_markets_fail(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"

    def failing():
        raise RuntimeError("boom")

    fake_fetchers = {
        "twse": ("TWSE", failing),
        "tpex": ("TPEx", failing),
    }
    args = argparse.Namespace(db=str(db_path), market="all")

    with patch.object(cli, "_MARKET_FETCHERS", fake_fetchers):
        rc = cli.cmd_fetch(args)

    assert rc == 1


def test_cmd_fetch_respects_market_filter(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"
    fake_fetchers = {
        "twse": ("TWSE", lambda: [make_record("1101")]),
        "tpex": ("TPEx", lambda: [make_record("6488")]),
    }
    args = argparse.Namespace(db=str(db_path), market="twse")

    with patch.object(cli, "_MARKET_FETCHERS", fake_fetchers):
        rc = cli.cmd_fetch(args)

    assert rc == 0
    conn = db.connect(str(db_path))
    rows = db.load_snapshot(conn, "11402")
    assert [r["company_id"] for r in rows] == ["1101"]


def _seed(db_path):
    conn = db.connect(str(db_path))
    records = [
        {**make_record("1101"), "market": "TWSE", "yoy_pct": 30.0},
        {**make_record("6488"), "market": "TPEx", "yoy_pct": 10.0},
    ]
    db.upsert_monthly_revenue(conn, records)


def test_cmd_screen_writes_markdown_table_to_file(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"
    _seed(db_path)
    out_path = tmp_path / "latest.md"
    args = argparse.Namespace(
        db=str(db_path), data_ym=None, min_yoy=0.0, positive_mom=False,
        top=20, format="markdown", output=str(out_path), industry_source="twse",
        industry=None,
    )

    rc = cli.cmd_screen(args)

    assert rc == 0
    content = out_path.read_text(encoding="utf-8")
    assert "# 11402 篩選結果" in content
    assert "1101" in content and "6488" in content
    assert "| 代號 | 名稱 |" in content


def test_cmd_screen_writes_csv_to_file(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"
    _seed(db_path)
    out_path = tmp_path / "latest.csv"
    args = argparse.Namespace(
        db=str(db_path), data_ym=None, min_yoy=0.0, positive_mom=False,
        top=20, format="csv", output=str(out_path), industry_source="twse",
        industry=None,
    )

    rc = cli.cmd_screen(args)

    assert rc == 0
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",")[:2] == ["資料年月", "代號"]
    assert len(lines) == 3  # header + 2 companies


def test_cmd_screen_top_zero_means_no_limit(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"
    _seed(db_path)
    out_path = tmp_path / "latest.csv"
    args = argparse.Namespace(
        db=str(db_path), data_ym=None, min_yoy=0.0, positive_mom=False,
        top=0, format="csv", output=str(out_path), industry_source="twse",
        industry=None,
    )

    rc = cli.cmd_screen(args)

    assert rc == 0
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3  # header + 2 companies, nothing truncated


def test_cmd_screen_tej_industry_source_regroups_by_tej_industry(tmp_path):
    # 1101 (水泥) and 6488 (半導體) share the fake "電子" industry in _seed(),
    # but TEJ's real classification puts them in different mid-level
    # industries -- selecting industry_source="tej" should reflect that.
    db_path = tmp_path / "revinv.sqlite3"
    _seed(db_path)
    out_path = tmp_path / "latest.csv"
    args = argparse.Namespace(
        db=str(db_path), data_ym=None, min_yoy=0.0, positive_mom=False,
        top=0, format="csv", output=str(out_path), industry_source="tej",
        industry=None,
    )

    rc = cli.cmd_screen(args)

    assert rc == 0
    content = out_path.read_text(encoding="utf-8")
    assert "M11A 水泥製造" in content
    assert "M23G 半導體" in content
    assert "電子" not in content


def test_cmd_screen_industry_filter_narrows_to_named_industries(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"
    _seed(db_path)
    out_path = tmp_path / "latest.csv"
    args = argparse.Namespace(
        db=str(db_path), data_ym=None, min_yoy=0.0, positive_mom=False,
        top=0, format="csv", output=str(out_path), industry_source="tej",
        industry=["M11A 水泥製造"],
    )

    rc = cli.cmd_screen(args)

    assert rc == 0
    content = out_path.read_text(encoding="utf-8")
    assert "1101" in content
    assert "6488" not in content


def test_cmd_industries_writes_markdown_sorted_by_median_yoy(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"
    _seed(db_path)
    out_path = tmp_path / "industries.md"
    args = argparse.Namespace(
        db=str(db_path), data_ym=None, top=0, format="markdown",
        output=str(out_path), industry_source="twse",
    )

    rc = cli.cmd_industries(args)

    assert rc == 0
    content = out_path.read_text(encoding="utf-8")
    assert "# 11402 產業趨勢" in content
    # _seed() puts both companies in the fake "電子" industry.
    assert "電子" in content


def test_cmd_industries_writes_csv(tmp_path):
    db_path = tmp_path / "revinv.sqlite3"
    _seed(db_path)
    out_path = tmp_path / "industries.csv"
    args = argparse.Namespace(
        db=str(db_path), data_ym=None, top=0, format="csv",
        output=str(out_path), industry_source="tej",
    )

    rc = cli.cmd_industries(args)

    assert rc == 0
    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == ["資料年月", "產業別", "公司家數", "YoY中位數%"]
    # With TEJ enrichment, 1101 and 6488 land in different industries.
    assert len(lines) == 3  # header + 2 industries
