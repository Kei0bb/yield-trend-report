"""PCM/WAT trend report PDF (A4 portrait).

Layout: period header + the full item table, then a lot-trend chart for
EVERY item, two per page. The single-lot report charts only its flagged
items; this one is the period's record, so nothing is dropped.
"""

import io
import logging
import math

import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.schemas import WatTrendItemStats, WatTrendResponse
from app.services.pdf_common import FOOTER_H, MARGIN, draw_footer, draw_logo
from app.services.wat_pdf_common import (
    PAGE_BREAK_MARGIN, STATUS_HEX, STATUS_RGB, axis, base_layout,
    draw_item_row, draw_table_header, render_batch, rows_per_page,
)

logger = logging.getLogger(__name__)


def _lot_trend_figure(item: WatTrendItemStats,
                      width: int = 1000, height: int = 647) -> go.Figure:
    """Lot means with +/-3 sigma whiskers against the period's spec lines.

    Marker color carries each lot's own judgement, so a reader can see which
    lot went out without cross-referencing the table.
    """
    series = item.lot_series
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[p.lot_id for p in series],
        y=[p.mean for p in series],
        mode="lines+markers",
        line=dict(color="#141413", width=2),
        marker=dict(
            size=8,
            color=[STATUS_HEX.get(p.status, STATUS_HEX["ok"]) for p in series],
        ),
        error_y=dict(
            type="data",
            array=[(p.sigma * 3 if p.sigma is not None else 0) for p in series],
            visible=True, color="rgba(20,20,19,0.35)", thickness=1.2, width=3,
        ),
    ))
    for limit, label in ((item.spec_low, "LSL"), (item.spec_high, "USL")):
        if limit is not None:
            fig.add_hline(y=limit, line=dict(color="#c64545", width=1, dash="dash"),
                          annotation_text=label,
                          annotation_font=dict(size=9, color="#c64545"))

    unit = f" [{item.unit}]" if item.unit else ""
    fig.update_layout(**base_layout(width, height, f"{item.item_name}{unit}"),
                      xaxis=dict(**axis("Lot"), type="category"),
                      yaxis=axis(""))
    return fig


def _draw_header(c: canvas.Canvas, page_width: float, page_height: float,
                 trend: WatTrendResponse) -> float:
    """Draws the header band; returns the y coordinate where content starts."""
    top = page_height - MARGIN
    logo_h = 10 * mm
    draw_logo(c, MARGIN, top - logo_h, logo_h)

    c.saveState()
    c.setFillColorRGB(0.216, 0.208, 0.184)
    c.setFont("Helvetica-Bold", 13)
    title = f"PCM / WAT Trend  —  {trend.product_id}"
    if trend.display_name and trend.display_name != trend.product_id:
        title += f"  ({trend.display_name})"
    c.drawString(MARGIN, top - logo_h - 7 * mm, title)

    latest = trend.lots[0].last_measured if trend.lots else "—"
    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(0.38, 0.36, 0.35)
    meta = (f"{trend.start_date} — {latest}    Last {trend.months} months    "
            f"{len(trend.lots)} lots    {len(trend.items)} items")
    c.drawString(MARGIN, top - logo_h - 12 * mm, meta)

    reds = sum(1 for i in trend.items if i.status == "red")
    yellows = sum(1 for i in trend.items if i.status == "yellow")
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColorRGB(*STATUS_RGB["red"])
    c.drawRightString(page_width - MARGIN - 18 * mm, top - logo_h - 12 * mm,
                      f"● {reds}")
    c.setFillColorRGB(*STATUS_RGB["yellow"])
    c.drawRightString(page_width - MARGIN, top - logo_h - 12 * mm, f"▲ {yellows}")

    rule_y = top - logo_h - 15 * mm
    c.setStrokeColorRGB(0, 0, 0, alpha=0.12)
    c.setLineWidth(0.6)
    c.line(MARGIN, rule_y, page_width - MARGIN, rule_y)
    c.restoreState()
    return rule_y - 6 * mm


def count_pages(trend: WatTrendResponse, content_top: float) -> int:
    """Total page count, known before drawing — ReportLab cannot revisit a
    finished page, so "Page n of N" needs N up front."""
    per_page = rows_per_page(content_top)
    table_pages = max(1, math.ceil(len(trend.items) / per_page))
    chart_pages = math.ceil(len(trend.items) / 2)
    return table_pages + chart_pages


def generate_wat_trend_pdf(trend: WatTrendResponse) -> bytes:
    """A4 portrait PCM/WAT trend report."""
    buf = io.BytesIO()
    page_width, page_height = A4
    c = canvas.Canvas(buf, pagesize=A4)

    # Every figure is known before any page is drawn, so the whole batch goes
    # through one kaleido call instead of one call per figure.
    chart_images = render_batch([_lot_trend_figure(i) for i in trend.items])

    probe_top = _draw_header(c, page_width, page_height, trend)
    total_pages = count_pages(trend, probe_top)
    logger.info(
        "WAT trend PDF: product=%s months=%d lots=%d items=%d pages=%d",
        trend.product_id, trend.months, len(trend.lots), len(trend.items),
        total_pages,
    )

    page_no = 1

    def end_page() -> float:
        """Footer the current page, start the next, return its content top."""
        nonlocal page_no
        draw_footer(c, page_width, page_no, total_pages)
        c.showPage()
        page_no += 1
        return _draw_header(c, page_width, page_height, trend)

    # --- Item table ---------------------------------------------------------
    y = draw_table_header(c, probe_top)
    if not trend.items:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(*STATUS_RGB["gray"])
        c.drawString(MARGIN, y, "No WAT data for this period.")
    for item in trend.items:
        if y < PAGE_BREAK_MARGIN:
            y = draw_table_header(c, end_page())
        y = draw_item_row(c, y, item)

    # --- Lot trend charts, 2 per page ---------------------------------------
    for i in range(0, len(chart_images), 2):
        top = end_page()
        chunk = chart_images[i:i + 2]
        cell_h = (top - FOOTER_H - 4 * mm) / 2
        for j, img_bytes in enumerate(chunk):
            img = ImageReader(io.BytesIO(img_bytes))
            c.drawImage(
                img,
                MARGIN, top - (j + 1) * cell_h,
                width=page_width - 2 * MARGIN, height=cell_h - 2 * mm,
                preserveAspectRatio=True, anchor="n", mask="auto",
            )

    draw_footer(c, page_width, page_no, total_pages)
    c.save()
    return buf.getvalue()
