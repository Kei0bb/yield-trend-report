from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_export_pdf_failure_returns_500_without_exception_text(monkeypatch, caplog):
    """generate_pdf failures must be logged server-side (with traceback) but
    the response body must not leak the exception message."""
    import app.routers.export as export_router

    def _boom(**kwargs):
        raise RuntimeError("distinctive export pdf failure xyz")

    monkeypatch.setattr(export_router, "generate_pdf", _boom)

    with caplog.at_level("ERROR"):
        res = client.post("/api/export-pdf", json={
            "products": ["Product-A"], "start_month": "2026-01",
            "end_month": "2026-05", "processes": ["CP"],
        })
    assert res.status_code == 500
    assert res.json()["detail"] == "PDF generation failed"
    assert "distinctive export pdf failure xyz" not in res.text
    assert "distinctive export pdf failure xyz" in caplog.text
