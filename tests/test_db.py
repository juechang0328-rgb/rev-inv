from revinv import db


def make_record(company_id, data_ym):
    return {
        "company_id": company_id,
        "company_name": f"公司{company_id}",
        "industry": "電子",
        "data_ym": data_ym,
        "market": "TWSE",
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


def test_list_data_ym_returns_empty_list_for_new_db(tmp_path):
    conn = db.connect(str(tmp_path / "revinv.sqlite3"))
    assert db.list_data_ym(conn) == []


def test_list_data_ym_returns_distinct_months_most_recent_first(tmp_path):
    conn = db.connect(str(tmp_path / "revinv.sqlite3"))
    db.upsert_monthly_revenue(
        conn,
        [
            make_record("1101", "11401"),
            make_record("1101", "11403"),
            make_record("2330", "11403"),
            make_record("2330", "11402"),
        ],
    )
    assert db.list_data_ym(conn) == ["11403", "11402", "11401"]
