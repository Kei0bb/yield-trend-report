import io
import math

from pypdf import PdfReader

from app.models.schemas import WatTrendResponse
from app.services.wat_pdf_common import rows_per_page
from app.services.wat_trend_pdf_service import count_pages, generate_wat_trend_pdf
from app.services.wat_trend_service import get_wat_trend


def _empty_trend() -> WatTrendResponse:
    return WatTrendResponse(
        product_id="P12345-A", display_name="Product A", months=3,
        start_date="2026-06-09", end_date="2026-09-08", lots=[], items=[],
    )


def test_count_pages_is_table_pages_plus_two_charts_per_page():
    trend = get_wat_trend("product_a", "P12345-A", 3)
    content_top = 700.0
    per_page = rows_per_page(content_top)
    expected = (max(1, math.ceil(len(trend.items) / per_page))
                + math.ceil(len(trend.items) / 2))
    assert count_pages(trend, content_top) == expected


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
