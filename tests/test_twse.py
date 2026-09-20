import json
from pathlib import Path

from revinv import twse

FIXTURE = Path(__file__).parent / "fixtures" / "twse_sample.json"


def load_fixture() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_normalize_record_maps_fields_and_parses_numbers():
    raw = load_fixture()[0]
    record = twse.normalize_record(raw)
    assert record["company_id"] == "1101"
    assert record["company_name"] == "台泥"
    assert record["industry"] == "水泥工業"
    # API reports 仟元 (NT$ thousands); normalize_record scales to 元 (NT$).
    assert record["revenue"] == 5123456.0 * 1000
    assert record["yoy_pct"] == 13.85


def test_normalize_record_scales_all_amount_fields_but_not_percent_fields():
    raw = load_fixture()[0]
    record = twse.normalize_record(raw)
    assert record["revenue_prev_month"] == 4987000.0 * 1000
    assert record["revenue_prev_year_month"] == 4500000.0 * 1000
    assert record["cumulative_revenue"] == 10110456.0 * 1000
    assert record["cumulative_revenue_prev_year"] == 9000000.0 * 1000
    # Percentage fields must not be scaled.
    assert record["mom_pct"] == 2.74
    assert record["cumulative_yoy_pct"] == 12.34


def test_normalize_record_treats_placeholders_as_none():
    raw = load_fixture()[2]
    record = twse.normalize_record(raw)
    assert record["revenue_prev_year_month"] is None
    assert record["mom_pct"] is None
    assert record["yoy_pct"] is None


def test_normalize_record_ignores_missing_keys():
    record = twse.normalize_record({"公司代號": "1234", "公司名稱": "殘缺資料"})
    assert record["company_id"] == "1234"
    assert record["revenue"] is None


def test_normalize_records_returns_one_record_per_input():
    records = twse.normalize_records(load_fixture())
    assert len(records) == 3
    assert {r["company_id"] for r in records} == {"1101", "2330", "9999"}
