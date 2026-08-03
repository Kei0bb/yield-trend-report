import time

import pytest

from app.models.schemas import WatItemStats, WatSummaryResponse
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


_TWO_FLAVOR_WAT_PAIRS = [
    {"label": "Core RVT", "vth_n": "VTHN_RVT", "vth_p": "VTHP_RVT",
     "idsat_n": "IDSATN_RVT", "idsat_p": "IDSATP_RVT"},
    {"label": "Core LVT", "vth_n": "VTHN_LVT", "vth_p": "VTHP_LVT",
     "idsat_n": "IDSATN_LVT", "idsat_p": "IDSATP_LVT"},
]


def test_page_count_matches_with_scatter_plots_present(monkeypatch):
    """This environment's product_config.yaml has no wat: block for
    product_a, so the un-monkeypatched tests above never exercise the 2x2
    scatter grid (build_scatter_pairs / _scatter_figure / the col-row
    drawImage placement). Force a small (2-flavor, 8-plot) wat: config here
    so that path actually runs, following the pattern already used in
    test_wat_service_integration.py."""
    import io
    from pypdf import PdfReader
    import app.services.wat_service as ws
    from app.services.wat_pdf_service import count_pages

    monkeypatch.setattr(ws, "resolve_wat_pairs", lambda nickname: _TWO_FLAVOR_WAT_PAIRS)

    lot = mock_wat_lots("P12345-A", 3)["lot_id"].iloc[-1]
    summary = ws.get_wat_summary("product_a", "P12345-A", lot)

    scatter_count = sum(len(pair.plots) for pair in summary.scatter_pairs)
    assert scatter_count == 8, "2 flavors x 4 plot kinds"

    out = generate_wat_pdf(summary)
    reader = PdfReader(io.BytesIO(out))

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _canvas
    from app.services.wat_pdf_service import _draw_header

    probe = _canvas.Canvas(io.BytesIO(), pagesize=A4)
    top = _draw_header(probe, A4[0], A4[1], summary)
    predicted = count_pages(summary, top)

    assert len(reader.pages) == predicted


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


def _make_table_only_summary(n_items: int) -> WatSummaryResponse:
    """A summary with only the item table (no scatter, nothing flagged), so
    `count_pages`'s table_pages term is isolated from the scatter/trend terms."""
    items = [
        WatItemStats(
            item_name=f"ITEM_{i:03d}", unit="V", spec_low=0.0, spec_high=1.0,
            n=5, mean=0.5, sigma=0.05, min=0.4, max=0.6, cpk=2.0,
            cpk_state="value", oos_count=0, oos_pct=0.0, status="ok",
            wafer_series=[],
        )
        for i in range(n_items)
    ]
    return WatSummaryResponse(
        product_id="P12345-A", display_name="P12345-A", lot_id="LOT-1",
        measured_date="2026-01-01", wafer_count=1, items=items, scatter_pairs=[],
    )


@pytest.mark.parametrize("n_items", [30, 51, 52, 53, 103])
def test_page_count_matches_actual_across_item_counts(n_items):
    """Regression for the _rows_per_page off-by-one: the drawing loop fits
    one more row per page than the old formula predicted, so a real ~60-item
    lot printed 'Page 1 of 4' on a 3-page report."""
    import io
    from pypdf import PdfReader
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _canvas
    from app.services.wat_pdf_service import _draw_header, count_pages

    summary = _make_table_only_summary(n_items)
    probe = _canvas.Canvas(io.BytesIO(), pagesize=A4)
    top = _draw_header(probe, A4[0], A4[1], summary)
    predicted = count_pages(summary, top)

    actual = len(PdfReader(io.BytesIO(generate_wat_pdf(summary))).pages)
    assert actual == predicted, f"items={n_items} predicted={predicted} actual={actual}"


def test_page_count_matches_at_52_items():
    """The specific count called out in review: 52 items filled exactly one
    page in the drawing loop while the old formula predicted 2."""
    import io
    from pypdf import PdfReader
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _canvas
    from app.services.wat_pdf_service import _draw_header, count_pages

    summary = _make_table_only_summary(52)
    probe = _canvas.Canvas(io.BytesIO(), pagesize=A4)
    top = _draw_header(probe, A4[0], A4[1], summary)
    predicted = count_pages(summary, top)

    actual = len(PdfReader(io.BytesIO(generate_wat_pdf(summary))).pages)
    assert predicted == 1
    assert actual == 1
    assert actual == predicted
