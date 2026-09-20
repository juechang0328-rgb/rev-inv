import json
from pathlib import Path
from unittest.mock import Mock, patch

from revinv import tpex

FIXTURE = Path(__file__).parent / "fixtures" / "tpex_sample.json"


def load_fixture() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fetch_monthly_revenue_requests_the_tpex_url_and_normalizes():
    mock_response = Mock()
    mock_response.json.return_value = load_fixture()
    mock_response.raise_for_status = Mock()

    with patch("revinv.tpex.requests.get", return_value=mock_response) as mock_get:
        records = tpex.fetch_monthly_revenue()

    mock_get.assert_called_once_with(tpex.MONTHLY_REVENUE_URL, timeout=30.0)
    mock_response.raise_for_status.assert_called_once()
    assert len(records) == 1
    record = records[0]
    assert record["company_id"] == "6488"
    assert record["company_name"] == "環球晶"
    assert record["industry"] == "半導體業"
    # Reuses revinv.twse's amount scaling (仟元 -> 元).
    assert record["revenue"] == 8_000_000.0 * 1000
    assert record["yoy_pct"] == 14.29
