from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_trend_endpoint_returns_items_and_lots():
    res = client.get("/api/wat/trend", params={"product_id": "P12345-A", "months": 3})
    assert res.status_code == 200
    body = res.json()
    assert body["months"] == 3
    assert body["start_date"] < body["end_date"]
    assert len(body["items"]) == 30
    assert body["lots"]


def test_trend_endpoint_defaults_to_three_months():
    res = client.get("/api/wat/trend", params={"product_id": "P12345-A"})
    assert res.status_code == 200
    assert res.json()["months"] == 3


def test_trend_endpoint_rejects_out_of_range_months():
    for months in (0, 7):
        res = client.get("/api/wat/trend",
                         params={"product_id": "P12345-A", "months": months})
        assert res.status_code == 422, months


def test_trend_endpoint_items_carry_a_lot_series():
    res = client.get("/api/wat/trend", params={"product_id": "P12345-A", "months": 3})
    item = res.json()["items"][0]
    assert item["lot_series"]
    point = item["lot_series"][0]
    assert set(point) == {
        "lot_id", "measured_date", "n", "mean", "sigma",
        "cpk", "cpk_state", "status",
    }


def test_trend_endpoint_survives_an_unconfigured_product_id():
    """Mock mode fabricates data for any product id, so this checks the
    unconfigured-nickname path returns 200 rather than 500 — not emptiness."""
    res = client.get("/api/wat/trend",
                     params={"product_id": "nope-nope", "months": 3})
    assert res.status_code == 200
    assert res.json()["product_id"]


def test_export_trend_pdf_returns_a_pdf_attachment():
    res = client.post("/api/wat/export-trend-pdf",
                      json={"product_id": "P12345-A", "months": 3})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment" in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF")
