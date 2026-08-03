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


def test_export_pdf_with_japanese_lot_id_returns_200_with_usable_header():
    """Regression: a raw non-ASCII lot_id in Content-Disposition used to raise
    UnicodeEncodeError after the PDF was already generated, surfacing as an
    opaque 500."""
    res = client.post("/api/wat/export-pdf",
                      json={"product_id": "P12345-A", "lot_id": "ロット1"})
    assert res.status_code == 200
    cd = res.headers["content-disposition"]
    assert "filename*=UTF-8''" in cd


def test_export_pdf_lot_id_with_quote_does_not_inject_second_filename():
    """Regression: an unescaped '\"' in lot_id let the effective download
    filename become attacker-chosen (a second filename= parameter)."""
    res = client.post(
        "/api/wat/export-pdf",
        json={"product_id": "P12345-A", "lot_id": 'x" ; filename="evil.exe'},
    )
    assert res.status_code == 200
    cd = res.headers["content-disposition"]
    ascii_part = cd.split("; filename*=", 1)[0]
    assert ascii_part.count('filename="') == 1


def test_get_endpoints_log_and_return_503_on_db_failure(monkeypatch, caplog):
    """A real-DB failure must be logged with traceback and surfaced as a
    503 with an actionable detail, not a bare unlogged 500."""
    import app.services.wat_queries as wat_queries
    import app.services.wat_service as wat_service

    monkeypatch.setattr(wat_service.settings, "USE_MOCK_DATA", False)

    def _boom():
        raise RuntimeError("ORA-12541: TNS:no listener")

    monkeypatch.setattr(wat_queries, "get_connection", _boom)

    with caplog.at_level("ERROR"):
        res = client.get("/api/wat/lots", params={"product_id": "P12345-A", "months": 3})
    assert res.status_code == 503
    assert res.json()["detail"] == "WAT data source unavailable"
    assert "ORA-12541" in caplog.text

    caplog.clear()
    with caplog.at_level("ERROR"):
        res2 = client.get("/api/wat/summary",
                          params={"product_id": "P12345-A", "lot_id": "L1"})
    assert res2.status_code == 503
    assert res2.json()["detail"] == "WAT data source unavailable"
    assert "ORA-12541" in caplog.text
