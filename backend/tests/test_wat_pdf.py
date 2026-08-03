import time

from app.services.mock_data import mock_wat_lots
from app.services.wat_pdf_service import (
    STATUS_MARK, fmt_cpk, fmt_value, generate_wat_pdf,
)
from app.services.wat_service import get_wat_summary


def test_status_marks_cover_every_status():
    assert set(STATUS_MARK) == {"red", "yellow", "gray", "ok"}
    assert STATUS_MARK["red"] == "●"
    assert STATUS_MARK["yellow"] == "▲"
    assert STATUS_MARK["ok"] == ""


def test_fmt_value_uses_four_significant_digits():
    assert fmt_value(0.4021456) == "0.4021"
    assert fmt_value(1042.637) == "1043"
    assert fmt_value(None) == "—"


def test_fmt_cpk_renders_each_state():
    assert fmt_cpk(1.234, "value") == "1.23"
    assert fmt_cpk(None, "infinite") == "∞"
    assert fmt_cpk(None, "undefined") == "—"


def test_generate_wat_pdf_produces_a_portrait_pdf():
    from pypdf import PdfReader
    import io

    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    summary = get_wat_summary("product_a", "P12345-A", lot)

    started = time.monotonic()
    out = generate_wat_pdf(summary)
    elapsed = time.monotonic() - started

    assert out[:4] == b"%PDF"
    reader = PdfReader(io.BytesIO(out))
    assert len(reader.pages) >= 2
    box = reader.pages[0].mediabox
    assert box.height > box.width, "WAT report must be A4 portrait"
    print(f"\nWAT PDF: {len(reader.pages)} pages in {elapsed:.1f}s")


def test_generate_wat_pdf_handles_empty_summary():
    summary = get_wat_summary("product_a", "P12345-A", "__no_such_lot__")
    out = generate_wat_pdf(summary)
    assert out[:4] == b"%PDF"


def test_page_count_matches_the_precomputed_total():
    """Page n of N is written before drawing, so the prediction must hold."""
    from pypdf import PdfReader
    import io as _io
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _canvas
    from app.services.wat_pdf_service import _draw_header, count_pages

    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    summary = get_wat_summary("product_a", "P12345-A", lot)

    probe = _canvas.Canvas(_io.BytesIO(), pagesize=A4)
    top = _draw_header(probe, A4[0], A4[1], summary)
    predicted = count_pages(summary, top)

    actual = len(PdfReader(_io.BytesIO(generate_wat_pdf(summary))).pages)
    assert actual == predicted
