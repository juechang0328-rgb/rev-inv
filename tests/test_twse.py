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
    assert record["revenue"] == 5123456.0
    assert record["yoy_pct"] == 13.85


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
