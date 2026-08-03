from fastapi.testclient import TestClient

from app.main import app
from app.services.mock_data import mock_wat_lots

client = TestClient(app)


def test_lots_endpoint_returns_newest_first():
    res = client.get("/api/wat/lots", params={"product_id": "P12345-A", "months": 3})
    assert res.status_code == 200
    lots = res.json()["lots"]
    assert lots
    assert [l["last_measured"] for l in lots] == sorted(
        [l["last_measured"] for l in lots], reverse=True
    )


def test_lots_endpoint_rejects_out_of_range_months():
    res = client.get("/api/wat/lots", params={"product_id": "P12345-A", "months": 12})
    assert res.status_code == 422


def test_summary_endpoint_returns_items_and_scatter():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    res = client.get("/api/wat/summary",
                     params={"product_id": "P12345-A", "lot_id": lot})
    assert res.status_code == 200
    body = res.json()
    assert body["lot_id"] == lot
    assert len(body["items"]) == 30
    assert body["items"] == sorted(body["items"], key=lambda i: i["item_name"])


def test_summary_endpoint_unknown_lot_is_empty_not_500():
    res = client.get("/api/wat/summary",
                     params={"product_id": "P12345-A", "lot_id": "nope"})
    assert res.status_code == 200
    assert res.json()["items"] == []


def test_summary_response_is_json_serialisable_without_nan():
    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    res = client.get("/api/wat/summary",
                     params={"product_id": "P12345-A", "lot_id": lot})
    assert "NaN" not in res.text, "NaN is not valid JSON"
