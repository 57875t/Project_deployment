from fastapi.testclient import TestClient

from qrdesk_gateway.app import app


def test_root_is_read_only():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["readOnly"] is True


def test_bundle_rejects_range_interval_mismatch_before_sdk_query():
    client = TestClient(app)
    response = client.get(
        "/v1/market/bundle",
        params={"instrument": "US.AAPL", "symbol": "AAPL", "range": "1d", "interval": "1d"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "RANGE_INTERVAL_MISMATCH"
