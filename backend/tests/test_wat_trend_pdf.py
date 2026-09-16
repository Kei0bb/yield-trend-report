import io
import math

from pypdf import PdfReader

from app.models.schemas import WatTrendItemStats, WatTrendResponse
from app.services.wat_pdf_common import rows_per_page
from app.services.wat_trend_pdf_service import (
    chart_items, count_pages, generate_wat_trend_pdf,
)
from app.services.wat_trend_service import get_wat_trend


def _empty_trend() -> WatTrendResponse:
    return WatTrendResponse(
        product_id="P12345-A", display_name="Product A", months=3,
        start_date="2026-06-09", end_date="2026-09-08", lots=[], items=[],
    )


def _trend_item(item_name: str, section: str) -> WatTrendItemStats:
    return WatTrendItemStats(
        item_name=item_name, section=section, unit="V", spec_low=0.0, spec_high=1.0,
        n=2, mean=0.5, sigma=0.05, min=0.4, max=0.6, cpk=2.0,
        cpk_state="value", oos_count=0, oos_pct=0.0, status="ok", lot_series=[],
    )


def test_count_pages_is_table_pages_plus_six_charts_per_page():
    trend = get_wat_trend("product_a", "P12345-A", 3)
    content_top = 700.0
    per_page = rows_per_page(content_top)
    n_charts = len(chart_items(trend))
    expected = (max(1, math.ceil(len(trend.items) / per_page))
                + math.ceil(n_charts / 6))
    assert count_pages(trend, content_top) == expected


def test_chart_items_excludes_others():
    trend = WatTrendResponse(
        product_id="P12345-A", display_name="Product A", months=3,
        start_date="2026-06-09", end_date="2026-09-08", lots=[],
        items=[_trend_item("Vtl_N", "Vtl"), _trend_item("RS_POLY", "Others")],
    )
    assert [i.item_name for i in chart_items(trend)] == ["Vtl_N"]


def test_count_pages_charts_only_the_non_others_item():
    """A table-only-sized item list isolates the chart term of count_pages:
    with one normal item and one Others item, only the normal one charts."""
    trend = WatTrendResponse(
        product_id="P12345-A", display_name="Product A", months=3,
        start_date="2026-06-09", end_date="2026-09-08", lots=[],
        items=[_trend_item("Vtl_N", "Vtl"), _trend_item("RS_POLY", "Others")],
    )
    content_top = 700.0
    per_page = rows_per_page(content_top)
    table_pages = max(1, math.ceil(len(trend.items) / per_page))
    assert count_pages(trend, content_top) == table_pages + 1  # one chart page


def test_generate_trend_pdf_produces_a_portrait_pdf():
    trend = get_wat_trend("product_a", "P12345-A", 3)
    out = generate_wat_trend_pdf(trend)
    assert out.startswith(b"%PDF")

    reader = PdfReader(io.BytesIO(out))
    box = reader.pages[0].mediabox
    assert box.height > box.width, "A4 portrait"
    assert len(reader.pages) > 1, "30 items cannot fit on one page"


def test_generate_trend_pdf_with_no_items_does_not_raise():
    out = generate_wat_trend_pdf(_empty_trend())
    assert out.startswith(b"%PDF")
    assert len(PdfReader(io.BytesIO(out)).pages) == 1
