from unittest.mock import Mock, patch

from revinv import finmind


def _mock_response(data):
    mock_response = Mock()
    mock_response.json.return_value = {"msg": "success", "data": data}
    mock_response.raise_for_status = Mock()
    return mock_response


def test_fetch_dataset_requests_expected_params_and_returns_data_rows():
    sample_rows = [{"date": "2025-03-31", "stock_id": "2330", "type": "x", "value": 1.0, "origin_name": "存貨"}]

    with patch("revinv.finmind.requests.get", return_value=_mock_response(sample_rows)) as mock_get:
        rows = finmind.fetch_dataset("TaiwanStockBalanceSheet", "2330", "2024-01-01")

    mock_get.assert_called_once_with(
        finmind.BASE_URL,
        params={"dataset": "TaiwanStockBalanceSheet", "data_id": "2330", "start_date": "2024-01-01"},
        timeout=30.0,
    )
    assert rows == sample_rows


def test_fetch_dataset_includes_token_when_provided():
    with patch("revinv.finmind.requests.get", return_value=_mock_response([])) as mock_get:
        finmind.fetch_dataset("TaiwanStockBalanceSheet", "2330", "2024-01-01", token="abc123")

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["token"] == "abc123"


def test_fetch_dataset_raises_on_api_error_message():
    mock_response = Mock()
    mock_response.json.return_value = {"msg": "Requests reach the upper limit", "data": []}
    mock_response.raise_for_status = Mock()

    with patch("revinv.finmind.requests.get", return_value=mock_response):
        try:
            finmind.fetch_dataset("TaiwanStockBalanceSheet", "2330", "2024-01-01")
        except RuntimeError as exc:
            assert "upper limit" in str(exc)
        else:
            raise AssertionError("expected RuntimeError for a FinMind API error message")


def test_fetch_balance_sheet_and_financial_statements_use_the_right_dataset():
    with patch("revinv.finmind.requests.get", return_value=_mock_response([])) as mock_get:
        finmind.fetch_balance_sheet("2330", "2024-01-01")
        finmind.fetch_financial_statements("2330", "2024-01-01")

    datasets_used = [call.kwargs["params"]["dataset"] for call in mock_get.call_args_list]
    assert datasets_used == ["TaiwanStockBalanceSheet", "TaiwanStockFinancialStatements"]
