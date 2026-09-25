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
    assert "defaults" in body and "bin_surge" in body["defaults"]


def test_existing_yield_data_endpoint_unchanged():
    r = client.post("/api/yield-data", json={
        "products": ["Product-A"], "start_month": "2026-01",
        "end_month": "2026-05", "processes": ["CP"],
    })
    assert r.status_code == 200
    assert "data" in r.json()


def test_debug_probe_logs_traceback_but_does_not_leak_it(monkeypatch, caplog):
    """A failure inside debug_probe must be logged server-side (with
    traceback) but the response body must only carry str(e), not the
    traceback text."""
    import app.routers.yield_data as yield_data

    def _boom(**kwargs):
        raise RuntimeError("boom: distinctive probe failure")

    monkeypatch.setattr(yield_data, "get_yield_data_merged", _boom)

    with caplog.at_level("ERROR"):
        r = client.get("/api/debug/probe", params={
            "nickname": "Product-A", "process": "CP",
            "start_month": "2026-01", "end_month": "2026-05",
        })
    assert r.status_code == 200
    body = r.json()
    assert body["error"] == "boom: distinctive probe failure"
    assert "traceback" not in body
    assert "boom: distinctive probe failure" in caplog.text
