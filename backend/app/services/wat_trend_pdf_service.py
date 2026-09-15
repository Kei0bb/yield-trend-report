"""PCM/WAT trend report PDF (A4 portrait).

Layout: period header + the full item table, then a lot-trend chart for
EVERY item, six per page. The single-lot report charts only its flagged
items; this one is the period's record, so nothing is dropped.
"""

import io
import logging
import math

import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.models.schemas import WatTrendItemStats, WatTrendResponse
from app.services.pdf_common import MARGIN, draw_footer
from app.services.wat_pdf_common import (
    CHART_H, CHART_W, STATUS_HEX, STATUS_RGB, axis, base_layout,
    chart_page_count, draw_chart_grid, draw_header_band, draw_table_header,
    draw_table_rows, paginate_table, render_batch, rows_per_page,
)

logger = logging.getLogger(__name__)

MAX_LOT_LABELS = 12


def _lot_trend_figure(item: WatTrendItemStats,
                      width: int = CHART_W, height: int = CHART_H) -> go.Figure:
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
        line=dict(color="#141413", width=1.5),
        marker=dict(
            size=6,
            color=[STATUS_HEX.get(p.status, STATUS_HEX["ok"]) for p in series],
        ),
        error_y=dict(
            type="data",
            array=[(p.sigma * 3 if p.sigma is not None else 0) for p in series],
            visible=True, color="rgba(20,20,19,0.35)", thickness=1, width=2,
        ),
    ))
    for limit, label in ((item.spec_low, "LSL"), (item.spec_high, "USL")):
        if limit is not None:
            fig.add_hline(y=limit, line=dict(color="#c64545", width=1, dash="dash"),
                          annotation_text=label,
                          annotation_font=dict(size=9, color="#c64545"))

    # In a six-per-page cell a 6-month period's lot ids, all printed upright,
    # would eat a third of the chart. Every lot keeps its point; only the
    # labels are thinned to at most MAX_LOT_LABELS.
    lot_ids = [p.lot_id for p in series]
    step = max(1, math.ceil(len(lot_ids) / MAX_LOT_LABELS))
    x_axis = axis("")
    x_axis["tickfont"] = dict(x_axis["tickfont"], size=8)
    x_axis.update(type="category", tickangle=-90, tickmode="array",
                  tickvals=lot_ids[::step], ticktext=lot_ids[::step])

    unit = f" [{item.unit}]" if item.unit else ""
    fig.update_layout(**base_layout(width, height, f"{item.item_name}{unit}"),
                      xaxis=x_axis, yaxis=axis(""))
    return fig


def _draw_header(c: canvas.Canvas, page_width: float, page_height: float,
                 trend: WatTrendResponse) -> float:
    """Builds this report's title/meta and delegates to the shared band —
    see draw_header_band's docstring for why the drawing itself is shared."""
    title = f"PCM / WAT Trend  —  {trend.product_id}"
    if trend.display_name and trend.display_name != trend.product_id:
        title += f"  ({trend.display_name})"

    latest = trend.lots[0].last_measured if trend.lots else "—"
    meta = (f"{trend.start_date} — {latest}    Last {trend.months} months    "
            f"{len(trend.lots)} lots    {len(trend.items)} items")

    reds = sum(1 for i in trend.items if i.status == "red")
    yellows = sum(1 for i in trend.items if i.status == "yellow")
    return draw_header_band(c, page_width, page_height, title, meta, reds, yellows)


def count_pages(trend: WatTrendResponse, content_top: float) -> int:
    """Total page count, known before drawing — ReportLab cannot revisit a
    finished page, so "Page n of N" needs N up front."""
    table_pages = len(paginate_table(trend.items, rows_per_page(content_top)))
    return table_pages + chart_page_count(len(trend.items))


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
    for k, rows in enumerate(paginate_table(trend.items, rows_per_page(probe_top))):
        if k > 0:
            y = draw_table_header(c, end_page())
        y = draw_table_rows(c, y, rows)

    # --- Lot trend charts, six per page -------------------------------------
    draw_chart_grid(c, chart_images, page_width, end_page)

    draw_footer(c, page_width, page_no, total_pages)
    c.save()
    return buf.getvalue()
