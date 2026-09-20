from revinv.screen import screen_snapshot


def make_record(company_id, industry, yoy, mom, revenue=1000.0, market="TWSE"):
    return {
        "company_id": company_id,
        "company_name": f"公司{company_id}",
        "industry": industry,
        "data_ym": "11408",
        "market": market,
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


def test_screen_computes_relative_strength_vs_industry_median():
    records = [
        make_record("A", "電子", 30.0, 5.0),
        make_record("B", "電子", 10.0, 1.0),
    ]
    results = screen_snapshot(records, min_yoy_pct=0.0)
    by_id = {r.company_id: r for r in results}
    assert by_id["A"].industry_median_yoy == 20.0
    assert by_id["A"].relative_strength == 10.0
    assert by_id["B"].relative_strength == -10.0


def test_screen_median_baseline_resists_a_single_extreme_outlier():
    # A construction/biotech-style base-effect blowout (thousands of %)
    # must not drag the whole industry's baseline with it the way a mean
    # would; the median should stay anchored near the typical company.
    records = [
        make_record("A", "電子", 41420.6, 5.0),  # extreme outlier
        make_record("B", "電子", 12.0, 1.0),
        make_record("C", "電子", 8.0, 1.0),
    ]
    results = screen_snapshot(records, min_yoy_pct=0.0)
    by_id = {r.company_id: r for r in results}
    assert by_id["B"].industry_median_yoy == 12.0
    assert by_id["C"].industry_median_yoy == 12.0


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


def test_screen_computes_industry_median_across_markets_combined():
    # Same industry classification is shared by TWSE and TPEx, so the peer
    # group (and the resulting relative strength) should mix both markets.
    records = [
        make_record("1101", "電子", 30.0, 5.0, market="TWSE"),
        make_record("6488", "電子", 10.0, 5.0, market="TPEx"),
    ]
    results = screen_snapshot(records, min_yoy_pct=0.0)
    by_id = {r.company_id: r for r in results}
    assert by_id["1101"].market == "TWSE"
    assert by_id["6488"].market == "TPEx"
    assert by_id["1101"].industry_median_yoy == 20.0
    assert by_id["6488"].industry_median_yoy == 20.0
