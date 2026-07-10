from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_wafermap_lots_returns_lot_list():
    r = client.get("/api/wafermap/lots", params={"product_id": "P12345-A", "process": "CP"})
    assert r.status_code == 200
    body = r.json()
    assert body["lots"], "mock mode should list lots"
    first = body["lots"][0]
    assert {"lot_id", "lot_date", "wafer_count", "test_program_rev"} <= set(first)


def test_wafermap_lots_accepts_explicit_start_end():
    start = (date.today() - timedelta(days=30)).isoformat()
    end = date.today().isoformat()
    r = client.get(
        "/api/wafermap/lots",
        params={"product_id": "P12345-A", "process": "CP", "start": start, "end": end},
    )
    assert r.status_code == 200
    body = r.json()
    assert "lots" in body


def test_wafermap_post_returns_maps():
    lots = client.get("/api/wafermap/lots", params={"product_id": "P12345-A", "process": "CP"}).json()["lots"]
    lot_ids = [l["lot_id"] for l in lots[:2]]
    r = client.post("/api/wafermap", json={"product_id": "P12345-A", "process": "CP", "lot_ids": lot_ids})
    assert r.status_code == 200
    body = r.json()
    assert body["wafers"] and body["legend"]
    w = body["wafers"][0]
    assert len(w["x"]) == len(w["y"]) == len(w["bin"])


def test_wafermap_post_rejects_over_12_lots():
    r = client.post("/api/wafermap", json={
        "product_id": "P12345-A", "process": "CP",
        "lot_ids": [f"L{i}" for i in range(13)],
    })
    assert r.status_code == 422


def test_wafermap_post_rejects_months_over_6():
    r = client.post("/api/wafermap", json={
        "product_id": "P12345-A", "process": "CP",
        "lot_ids": ["LOT-A"], "months": 12,
    })
    assert r.status_code == 422


def test_wafermap_process_subs_returns_cp_ft_slt_keys():
    r = client.get("/api/wafermap/process-subs", params={"product_id": "P12345-A"})
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"CP", "FT", "SLT"}
    for v in body.values():
        assert isinstance(v, list)
        assert v == []  # mock mode: no product_config.yaml → all empty


def test_wafermap_post_dedupes_lot_ids():
    lots = client.get("/api/wafermap/lots", params={"product_id": "P12345-A", "process": "CP"}).json()["lots"]
    lot_id = lots[0]["lot_id"]
    r = client.post("/api/wafermap", json={
        "product_id": "P12345-A", "process": "CP",
        "lot_ids": [lot_id, lot_id],
    })
    assert r.status_code == 200
    body = r.json()
    wafer_keys = [(w["lot_id"], w["wafer_id"]) for w in body["wafers"]]
    assert len(wafer_keys) == len(set(wafer_keys))
