from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_dashboard_summary_endpoint():
    r = client.get("/api/dashboard/summary?months=6&process=CP")
    assert r.status_code == 200
    body = r.json()
    assert body["period"]["months"] == 6
    assert isinstance(body["rows"], list) and body["rows"]
    assert all(row["process"] == "CP" for row in body["rows"])


def test_explore_lots_endpoint():
    # CP product_id for Product-A (resolved back to its nickname internally)
    r = client.get("/api/explore/lots?product_id=P12345-A&process=CP&months=6")
    assert r.status_code == 200
    body = r.json()
    assert body["product_id"] == "P12345-A"
    assert body["display_name"] == "Product-A"
    assert body["lots"]
    assert "available_bins" in body
    assert "yield_pct" in body["lots"][0]


def test_products_endpoint_returns_product_ids():
    r = client.get("/api/products")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and body
    assert {"product_id", "display_name"} <= set(body[0].keys())
    assert any(p["product_id"] == "P12345-A" for p in body)


def test_anomaly_config_endpoint():
    r = client.get("/api/anomaly/config")
    assert r.status_code == 200
    body = r.json()
    assert "defaults" in body and "yield_drop" in body["defaults"]


def test_existing_yield_data_endpoint_unchanged():
    r = client.post("/api/yield-data", json={
        "products": ["Product-A"], "start_month": "2026-01",
        "end_month": "2026-05", "processes": ["CP"],
    })
    assert r.status_code == 200
    assert "data" in r.json()
