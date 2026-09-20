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
