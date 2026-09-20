import pytest

from revinv.quarterly import (
    QuarterPoint,
    _extract,
    build_quarterly_series,
    confirm_company,
)


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


def test_build_quarterly_series_uses_revenue_and_cogs_as_reported():
    # FinMind's Revenue/CostOfGoodsSold are already single-quarter (see
    # module docstring) -- unlike a raw MOPS filing, they must NOT be
    # treated as cumulative year-to-date and reduced. A real company can
    # legitimately have Q2 revenue lower than Q1 (impossible for a truly
    # cumulative series), which is exactly what this fixture checks isn't
    # misinterpreted as a data error and "fixed" by subtraction.
    balance_sheet_rows = [
        _row("2025-03-31", "存貨", 50.0),
        _row("2025-03-31", "應收帳款淨額", 40.0),
        _row("2025-06-30", "存貨", 55.0),
        _row("2025-06-30", "應收帳款淨額", 45.0),
    ]
    financial_statement_rows = [
        _row("2025-03-31", "營業收入", 100.0),
        _row("2025-03-31", "營業成本", 60.0),
        _row("2025-06-30", "營業收入", 70.0),  # lower than Q1 -- fine if not cumulative
        _row("2025-06-30", "營業成本", 45.0),
    ]

    points = build_quarterly_series(balance_sheet_rows, financial_statement_rows)

    assert [p.date for p in points] == ["2025-03-31", "2025-06-30"]
    q1, q2 = points
    assert q1.revenue == 100.0
    assert q1.cogs == 60.0
    assert q2.inventory == 55.0
    assert q2.accounts_receivable == 45.0
    assert q2.revenue == 70.0
    assert q2.cogs == 45.0


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


def test_confirm_company_matches_hand_calculation_on_real_finmind_data():
    # Captured from a live `revinv confirm` debugging session against
    # company 3631: its Revenue/CostOfGoodsSold visibly drop
    # quarter-over-quarter within a fiscal year (e.g. 2025-06-30's
    # 6,755,000 < 2025-03-31's 10,568,000), which is only possible if
    # these are already single-quarter figures, not cumulative -- this
    # is the real data that first exposed the incorrect de-cumulation
    # this module used to apply. Locking in the resulting DIO/DSO here
    # against a hand calculation.
    balance_sheet_rows = [
        _row("2025-12-31", "應收帳款淨額", 5721000.0, type_="AccountsReceivableNet"),
        _row("2025-12-31", "存貨", 219054000.0, type_="Inventories"),
        _row("2026-03-31", "應收帳款淨額", 8782000.0, type_="AccountsReceivableNet"),
        _row("2026-03-31", "存貨", 224528000.0, type_="Inventories"),
        _row("2026-06-30", "應收帳款淨額", 9532000.0, type_="AccountsReceivableNet"),
        _row("2026-06-30", "存貨", 226655000.0, type_="Inventories"),
    ]
    financial_statement_rows = [
        _row("2025-12-31", "營業成本", 4770000.0, type_="CostOfGoodsSold"),
        _row("2025-12-31", "營業收入", 6295000.0, type_="Revenue"),
        _row("2026-03-31", "營業成本", 7365000.0, type_="CostOfGoodsSold"),
        _row("2026-03-31", "營業收入", 8997000.0, type_="Revenue"),
        _row("2026-06-30", "營業成本", 7688000.0, type_="CostOfGoodsSold"),
        _row("2026-06-30", "營業收入", 9075000.0, type_="Revenue"),
    ]

    points = build_quarterly_series(balance_sheet_rows, financial_statement_rows)
    result = confirm_company("3631", points)

    assert result is not None
    assert result.period == "2026-06-30"
    assert result.dio == pytest.approx(2670.24, rel=1e-4)  # avg(224528000,226655000)/7688000*91
    assert result.dio_prior == pytest.approx(2740.39, rel=1e-4)
    assert result.dso == pytest.approx(91.82, rel=1e-3)  # avg(8782000,9532000)/9075000*91
    assert result.dso_prior == pytest.approx(73.35, rel=1e-3)
    # None of these must ever be negative -- a negative DIO/DSO is a
    # sure sign of a scale/sign bug (e.g. reintroducing de-cumulation).
    assert result.dio > 0
    assert result.dio_prior > 0
    assert result.dso > 0
    assert result.dso_prior > 0
