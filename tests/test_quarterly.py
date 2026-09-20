import pytest

from revinv.quarterly import (
    QuarterPoint,
    _extract,
    build_quarterly_series,
    confirm_company,
    dequarterize,
)


def test_dequarterize_converts_cumulative_to_single_quarter():
    cumulative = {"2025-03-31": 100.0, "2025-06-30": 220.0, "2025-09-30": 345.0}
    single = dequarterize(cumulative)
    assert single == {"2025-03-31": 100.0, "2025-06-30": 120.0, "2025-09-30": 125.0}


def test_dequarterize_drops_quarters_missing_their_predecessor():
    # No Q1 for this fiscal year, so Q2/Q3 can't be safely de-cumulated.
    cumulative = {"2025-06-30": 220.0, "2025-09-30": 345.0}
    assert dequarterize(cumulative) == {}


def test_dequarterize_resets_at_each_fiscal_year():
    # 2024 only has its annual (Q4) figure, with no Q1-Q3 to de-cumulate
    # against, so it's dropped -- but that must not affect 2025 at all.
    cumulative = {"2024-12-31": 400.0, "2025-03-31": 100.0, "2025-06-30": 220.0}
    single = dequarterize(cumulative)
    assert single["2025-03-31"] == 100.0
    assert single["2025-06-30"] == 120.0
    assert "2024-12-31" not in single


def test_dequarterize_a_full_prior_year_does_not_leak_into_the_next():
    cumulative = {
        "2024-03-31": 90.0,
        "2024-06-30": 200.0,
        "2024-09-30": 310.0,
        "2024-12-31": 430.0,
        "2025-03-31": 100.0,
    }
    single = dequarterize(cumulative)
    assert single["2024-12-31"] == pytest.approx(120.0)  # 430 - 310
    assert single["2025-03-31"] == 100.0  # not reduced by 2024's baseline


def _row(date, origin_name, value, type_="x"):
    return {"date": date, "stock_id": "2330", "type": type_, "value": value, "origin_name": origin_name}


def test_extract_ignores_the_per_percentage_variant_sharing_the_same_name():
    # FinMind reports both the raw amount and a "_per" (% of total)
    # variant under the identical Chinese origin_name -- e.g. real
    # responses pair "AccountsPayable": 7.84e9 with "AccountsPayable_per":
    # 2.15, both labeled 應付帳款. Matching on origin_name alone must not
    # pick the percentage row.
    rows = [
        _row("2025-03-31", "存貨", 50_000_000.0, type_="Inventories"),
        _row("2025-03-31", "存貨", 4.2, type_="Inventories_per"),
    ]
    assert _extract(rows, ["存貨"]) == 50_000_000.0


def test_extract_ignores_the_per_variant_regardless_of_row_order():
    rows = [
        _row("2025-03-31", "存貨", 4.2, type_="Inventories_per"),
        _row("2025-03-31", "存貨", 50_000_000.0, type_="Inventories"),
    ]
    assert _extract(rows, ["存貨"]) == 50_000_000.0


def test_build_quarterly_series_extracts_and_dequarterizes_from_raw_rows():
    balance_sheet_rows = [
        _row("2025-03-31", "存貨", 50.0),
        _row("2025-03-31", "應收帳款淨額", 40.0),
        _row("2025-06-30", "存貨", 55.0),
        _row("2025-06-30", "應收帳款淨額", 45.0),
        _row("2025-09-30", "存貨", 60.0),
        _row("2025-09-30", "應收帳款淨額", 42.0),
    ]
    financial_statement_rows = [
        _row("2025-03-31", "營業收入", 100.0),
        _row("2025-03-31", "營業成本", 60.0),
        _row("2025-06-30", "營業收入", 220.0),
        _row("2025-06-30", "營業成本", 130.0),
        _row("2025-09-30", "營業收入", 345.0),
        _row("2025-09-30", "營業成本", 200.0),
    ]

    points = build_quarterly_series(balance_sheet_rows, financial_statement_rows)

    assert [p.date for p in points] == ["2025-03-31", "2025-06-30", "2025-09-30"]
    q3 = points[-1]
    assert q3.inventory == 60.0
    assert q3.accounts_receivable == 42.0
    assert q3.revenue == 125.0  # de-cumulated: 345 - 220
    assert q3.cogs == 70.0  # de-cumulated: 200 - 130


def test_confirm_company_computes_dio_dso_and_prior_quarter_trend():
    points = [
        QuarterPoint("2025-03-31", inventory=50.0, accounts_receivable=40.0, revenue=100.0, cogs=60.0),
        QuarterPoint("2025-06-30", inventory=55.0, accounts_receivable=45.0, revenue=120.0, cogs=70.0),
        QuarterPoint("2025-09-30", inventory=60.0, accounts_receivable=42.0, revenue=125.0, cogs=70.0),
    ]
    result = confirm_company("2330", points)

    assert result is not None
    assert result.period == "2025-09-30"
    assert result.prior_period == "2025-06-30"
    assert result.dio == pytest.approx(74.75)  # avg(55,60)/70*91
    assert result.dio_prior == pytest.approx(68.25)  # avg(50,55)/70*91
    assert result.dso == pytest.approx(31.668)  # avg(45,42)/125*91
    assert result.dso_prior == pytest.approx(32.229166, rel=1e-4)  # avg(40,45)/120*91


def test_confirm_company_returns_none_with_fewer_than_three_quarters():
    points = [
        QuarterPoint("2025-06-30", inventory=55.0, accounts_receivable=45.0, revenue=120.0, cogs=70.0),
        QuarterPoint("2025-09-30", inventory=60.0, accounts_receivable=42.0, revenue=125.0, cogs=70.0),
    ]
    assert confirm_company("2330", points) is None


def test_confirm_company_handles_a_bank_with_no_inventory_concept():
    # Banks/insurers report no inventory or cost of goods sold at all.
    points = [
        QuarterPoint("2025-03-31", inventory=None, accounts_receivable=40.0, revenue=100.0, cogs=None),
        QuarterPoint("2025-06-30", inventory=None, accounts_receivable=45.0, revenue=120.0, cogs=None),
        QuarterPoint("2025-09-30", inventory=None, accounts_receivable=42.0, revenue=125.0, cogs=None),
    ]
    result = confirm_company("2880", points)

    assert result is not None
    assert result.dio is None
    assert result.dio_prior is None
    assert result.dso == pytest.approx(31.668)


def test_confirm_company_returns_none_when_nothing_is_computable():
    points = [
        QuarterPoint("2025-03-31", None, None, None, None),
        QuarterPoint("2025-06-30", None, None, None, None),
        QuarterPoint("2025-09-30", None, None, None, None),
    ]
    assert confirm_company("0000", points) is None
