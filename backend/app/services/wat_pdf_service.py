"""PCM/WAT lot report PDF (A4 portrait).

Layout: lot header + summary, then the full item table across as many pages
as it needs, then the scatter plots 2x2 per page, then a wafer-trend chart
for every item judged red or yellow.
"""

import io
import logging
import math

import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.schemas import WatItemStats, WatScatterPlot, WatSummaryResponse
from app.services.pdf_common import FOOTER_H, MARGIN, SUBTEXT_COLOR, draw_footer, draw_logo
from app.services.wat_pdf_common import (
    PAGE_BREAK_MARGIN, STATUS_RGB, axis, base_layout, draw_item_row,
    draw_table_header, render_batch, rows_per_page,
)

logger = logging.getLogger(__name__)

# Single-hue ramp for wafer number: light -> dark. A rainbow would imply an
# order the eye reads wrongly, and 25 discrete legend entries are unreadable.
WAFER_COLORSCALE = [[0.0, "#f0d9cf"], [0.5, "#cc785c"], [1.0, "#5c2f1e"]]

PLOT_TITLES = {
    "vth_np": "Vth  n/p",
    "idsat_np": "Idsat  n/p",
    "ion_vt_n": "Ion-Vt  (N)",
    "ion_vt_p": "Ion-Vt  (P)",
}


# ---------------------------------------------------------------------------
# Chart images
#
# Every figure a report needs is known before any drawing starts (count_pages
# already relies on that). So figures are only *built* here; rendering them
# to PNG happens once, for the whole batch, in render_batch below — kaleido
# pays a ~1.8s subprocess/IPC cost per call regardless of what it's
# rendering, so N separate fig.to_image() calls cost N x that overhead where
# one batched plotly.io.write_images() call pays it once.
# ---------------------------------------------------------------------------

def _scatter_figure(plot: WatScatterPlot, width: int = 620, height: int = 820) -> go.Figure:
    title = PLOT_TITLES.get(plot.kind, plot.kind)
    fig = go.Figure()

    if plot.points:
        fig.add_trace(go.Scatter(
            x=[p.x for p in plot.points],
            y=[p.y for p in plot.points],
            mode="markers",
            marker=dict(
                size=8,
                color=[p.wafer_id for p in plot.points],
                colorscale=WAFER_COLORSCALE,
                colorbar=dict(title=dict(text="Wafer", font=dict(size=9)),
                              thickness=10, len=0.8),
                line=dict(width=1, color="#ffffff"),   # ring separates overlaps
            ),
        ))
        # Spec box: a rectangle is read instantly, four lines are not.
        x_lo, x_hi = plot.x_spec
        y_lo, y_hi = plot.y_spec
        if None not in (x_lo, x_hi, y_lo, y_hi):
            fig.add_shape(type="rect", x0=x_lo, x1=x_hi, y0=y_lo, y1=y_hi,
                          line=dict(color="rgba(198,69,69,0.45)", width=1, dash="dash"),
                          fillcolor="rgba(198,69,69,0.05)", layer="below")
    else:
        fig.add_annotation(text="No data", showarrow=False,
                           font=dict(size=12, color=SUBTEXT_COLOR))

    x_label = f"{plot.x_item} [{plot.x_unit}]" if plot.x_unit else plot.x_item
    y_label = f"{plot.y_item} [{plot.y_unit}]" if plot.y_unit else plot.y_item
    fig.update_layout(**base_layout(width, height, title),
                      xaxis=axis(x_label), yaxis=axis(y_label))
    return fig


def _trend_figure(item: WatItemStats, width: int = 1000, height: int = 647) -> go.Figure:
    series = item.wafer_series
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[w.wafer_id for w in series],
        y=[w.mean for w in series],
        mode="lines+markers",
        line=dict(color="#141413", width=2),
        marker=dict(size=8, color="#141413"),
        error_y=dict(
            type="data",
            array=[(w.sigma * 3 if w.sigma is not None else 0) for w in series],
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
                      xaxis=axis("Wafer #"), yaxis=axis(""))
    return fig


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------

def _draw_header(c: canvas.Canvas, page_width: float, page_height: float,
                 summary: WatSummaryResponse) -> float:
    """Draws the header band; returns the y coordinate where content starts."""
    top = page_height - MARGIN
    logo_h = 10 * mm
    draw_logo(c, MARGIN, top - logo_h, logo_h)

    c.saveState()
    c.setFillColorRGB(0.216, 0.208, 0.184)
    c.setFont("Helvetica-Bold", 13)
    title = f"PCM / WAT  —  {summary.product_id}"
    if summary.display_name and summary.display_name != summary.product_id:
        title += f"  ({summary.display_name})"
    c.drawString(MARGIN, top - logo_h - 7 * mm, title)

    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(0.38, 0.36, 0.35)
    meta = (f"Lot {summary.lot_id}    Measured {summary.measured_date or '—'}    "
            f"{summary.wafer_count} wafers    {len(summary.items)} items")
    c.drawString(MARGIN, top - logo_h - 12 * mm, meta)

    reds = sum(1 for i in summary.items if i.status == "red")
    yellows = sum(1 for i in summary.items if i.status == "yellow")
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def count_pages(summary: WatSummaryResponse, content_top: float) -> int:
    """Total page count, known before drawing.

    ReportLab cannot revisit a finished page, so "Page n of N" needs N up
    front. Every section's length is a pure function of the summary, so the
    count is computed rather than guessed.
    """
    per_page = rows_per_page(content_top)
    table_pages = max(1, math.ceil(len(summary.items) / per_page))
    scatter = sum(len(pair.plots) for pair in summary.scatter_pairs)
    scatter_pages = math.ceil(scatter / 4)
    flagged = sum(1 for i in summary.items if i.status in ("red", "yellow"))
    trend_pages = math.ceil(flagged / 2)
    return table_pages + scatter_pages + trend_pages


def generate_wat_pdf(summary: WatSummaryResponse) -> bytes:
    """A4 portrait PCM/WAT lot report."""
    buf = io.BytesIO()
    page_width, page_height = A4
    c = canvas.Canvas(buf, pagesize=A4)

    flagged = [i for i in summary.items if i.status in ("red", "yellow")]
    scatter_plots = [p for pair in summary.scatter_pairs for p in pair.plots]

    # Every figure this report needs is known right now, before any page is
    # drawn — so build them all up front and render the whole batch in one
    # kaleido call (see render_batch) instead of one call per figure.
    scatter_figs = [_scatter_figure(p) for p in scatter_plots]
    trend_figs = [_trend_figure(i) for i in flagged]
    rendered = render_batch(scatter_figs + trend_figs)
    scatter_images = rendered[:len(scatter_figs)]
    trend_images = rendered[len(scatter_figs):]

    # Draw one header to learn where content starts, then discard the canvas
    # state — the value only depends on constants, so it is stable.
    probe_top = _draw_header(c, page_width, page_height, summary)
    total_pages = count_pages(summary, probe_top)
    logger.info(
        "WAT PDF: lot=%s items=%d flagged=%d scatter=%d pages=%d",
        summary.lot_id, len(summary.items), len(flagged),
        len(scatter_plots), total_pages,
    )

    page_no = 1

    def end_page() -> float:
        """Footer the current page, start the next, return its content top."""
        nonlocal page_no
        draw_footer(c, page_width, page_no, total_pages)
        c.showPage()
        page_no += 1
        return _draw_header(c, page_width, page_height, summary)

    # --- Item table ---------------------------------------------------------
    y = draw_table_header(c, probe_top)
    if not summary.items:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(*STATUS_RGB["gray"])
        c.drawString(MARGIN, y, "No WAT data for this lot.")
    for item in summary.items:
        if y < PAGE_BREAK_MARGIN:
            y = draw_table_header(c, end_page())
        y = draw_item_row(c, y, item)

    # --- Scatter plots, 2x2 per page ----------------------------------------
    for i in range(0, len(scatter_images), 4):
        top = end_page()
        chunk = scatter_images[i:i + 4]
        cell_w = (page_width - 2 * MARGIN) / 2
        cell_h = (top - FOOTER_H - 4 * mm) / 2
        for j, img_bytes in enumerate(chunk):
            col, row = j % 2, j // 2
            img = ImageReader(io.BytesIO(img_bytes))
            c.drawImage(
                img,
                MARGIN + col * cell_w,
                top - (row + 1) * cell_h,
                width=cell_w - 2 * mm, height=cell_h - 2 * mm,
                preserveAspectRatio=True, anchor="n", mask="auto",
            )

    # --- Trend charts for flagged items -------------------------------------
    for i in range(0, len(trend_images), 2):
        top = end_page()
        chunk = trend_images[i:i + 2]
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
