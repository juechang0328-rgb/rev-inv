from revinv.screen import screen_snapshot


def make_record(company_id, industry, yoy, mom, revenue=1000.0):
    return {
        "company_id": company_id,
        "company_name": f"公司{company_id}",
        "industry": industry,
        "data_ym": "11408",
        "revenue": revenue,
        "yoy_pct": yoy,
        "mom_pct": mom,
    }


def test_screen_filters_out_companies_below_min_yoy():
    records = [
        make_record("A", "電子", 30.0, 5.0),
        make_record("B", "電子", 2.0, -1.0),
    ]
    results = screen_snapshot(records, min_yoy_pct=10.0)
    assert [r.company_id for r in results] == ["A"]


def test_screen_computes_relative_strength_vs_industry_average():
    records = [
        make_record("A", "電子", 30.0, 5.0),
        make_record("B", "電子", 10.0, 1.0),
    ]
    results = screen_snapshot(records, min_yoy_pct=0.0)
    by_id = {r.company_id: r for r in results}
    assert by_id["A"].industry_avg_yoy == 20.0
    assert by_id["A"].relative_strength == 10.0
    assert by_id["B"].relative_strength == -10.0


def test_screen_requires_positive_mom_when_flag_set():
    records = [
        make_record("A", "電子", 30.0, -5.0),
        make_record("B", "電子", 15.0, 2.0),
    ]
    results = screen_snapshot(records, min_yoy_pct=0.0, require_positive_mom=True)
    assert [r.company_id for r in results] == ["B"]


def test_screen_sorts_by_relative_strength_descending():
    records = [
        make_record("A", "電子", 15.0, 1.0),
        make_record("B", "電子", 40.0, 1.0),
        make_record("C", "電子", 25.0, 1.0),
    ]
    results = screen_snapshot(records, min_yoy_pct=0.0)
    assert [r.company_id for r in results] == ["B", "C", "A"]


def test_screen_skips_records_without_yoy_data():
    records = [
        make_record("A", "電子", None, 1.0),
        make_record("B", "電子", 20.0, 1.0),
    ]
    results = screen_snapshot(records, min_yoy_pct=0.0)
    assert [r.company_id for r in results] == ["B"]
