import pytest

from revinv import tej_industry


def test_lookup_known_company_returns_tej_classification():
    result = tej_industry.lookup("1101")
    assert result is not None
    assert result.industry == "M11A 水泥製造"
    assert result.sub_industry == "M11A 水泥製造"


def test_lookup_distinguishes_sub_industry_from_industry():
    # 1301 台塑: TEJ's mid-level industry is the broader "M13A 石化", but the
    # sub-industry is the finer "M13A1 泛用塑膠" -- this extra split relative
    # to TWSE's own single "塑膠工業" bucket is the whole point of using it.
    result = tej_industry.lookup("1301")
    assert result is not None
    assert result.industry == "M13A 石化"
    assert result.sub_industry == "M13A1 泛用塑膠"


def test_lookup_unknown_company_returns_none():
    assert tej_industry.lookup("0000") is None


def test_enrich_defaults_to_the_mid_level_tej_industry():
    # The 231-category sub-industry is too fine for everyday screening
    # (many groups end up with 1-2 peers), so the default is the coarser
    # 96-category "TEJ產業名".
    records = [{"company_id": "1301", "industry": "塑膠工業"}]
    enriched = tej_industry.enrich_with_tej_industry(records)
    assert enriched[0]["industry"] == "M13A 石化"
    assert records[0]["industry"] == "塑膠工業"  # original left untouched


def test_enrich_can_opt_into_the_finer_sub_industry_level():
    records = [{"company_id": "1301", "industry": "塑膠工業"}]
    enriched = tej_industry.enrich_with_tej_industry(records, level="sub_industry")
    assert enriched[0]["industry"] == "M13A1 泛用塑膠"


def test_enrich_rejects_an_unknown_level():
    records = [{"company_id": "1301", "industry": "塑膠工業"}]
    with pytest.raises(ValueError):
        tej_industry.enrich_with_tej_industry(records, level="bogus")


def test_enrich_falls_back_to_original_industry_for_unknown_company():
    records = [{"company_id": "0000", "industry": "未知產業"}]
    enriched = tej_industry.enrich_with_tej_industry(records)
    assert enriched[0]["industry"] == "未知產業"
