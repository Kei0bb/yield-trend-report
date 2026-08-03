"""PCM/WAT lot report PDF (A4 portrait).

Layout: lot header + summary, then the full item table across as many pages
as it needs, then the scatter plots 2x2 per page, then a wafer-trend chart
for every item judged red or yellow.
"""

import io
import logging
import math
import tempfile
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.schemas import WatItemStats, WatScatterPlot, WatSummaryResponse
from app.services.pdf_common import (
    FONT_FAMILY, FOOTER_H, MARGIN, SUBTEXT_COLOR, TEXT_COLOR,
    draw_footer, draw_logo,
)

logger = logging.getLogger(__name__)

STATUS_MARK: dict[str, str] = {"red": "●", "yellow": "▲",
                               "gray": "–", "ok": ""}

STATUS_RGB: dict[str, tuple[float, float, float]] = {
    "red": (0.776, 0.271, 0.271),
    "yellow": (0.831, 0.627, 0.090),
    "gray": (0.557, 0.545, 0.510),
    "ok": (0.216, 0.208, 0.184),
}

# Single-hue ramp for wafer number: light -> dark. A rainbow would imply an
# order the eye reads wrongly, and 25 discrete legend entries are unreadable.
WAFER_COLORSCALE = [[0.0, "#f0d9cf"], [0.5, "#cc785c"], [1.0, "#5c2f1e"]]

PLOT_TITLES = {
    "vth_np": "Vth  n/p",
    "idsat_np": "Idsat  n/p",
    "ion_vt_n": "Ion-Vt  (N)",
    "ion_vt_p": "Ion-Vt  (P)",
}

# 12 columns: mark, item, unit, low, high, N, mean, sigma, min, max, cpk, oos.
# Widths sum to the printable width of A4 portrait (210mm - 2 * 15mm).
COL_WIDTHS = [6, 40, 15, 16, 16, 12, 17, 15, 16, 16, 12, 11]
COL_HEADERS = ["", "Item", "Unit", "Low", "High", "N",
               "Mean", "Sigma", "Min", "Max", "Cpk", "OOS"]

ROW_H = 4.4 * mm
TABLE_FONT = 6.6

# Bottom margin reserved for the footer + breathing room, below which no new
# table row is drawn. Shared by _rows_per_page (page-count prediction) and
# the drawing loop's page-break check so the two cannot drift apart again.
PAGE_BREAK_MARGIN = FOOTER_H + 12 * mm


def fmt_value(v) -> str:
    """Four significant digits, so 0.4021 and 1043 read at the same width."""
    if v is None:
        return "—"
    return f"{v:.4g}"


def fmt_cpk(cpk, cpk_state: str) -> str:
    if cpk_state == "infinite":
        return "∞"
    if cpk_state == "value" and cpk is not None:
        return f"{cpk:.2f}"
    return "—"


# ---------------------------------------------------------------------------
# Chart images
#
# Every figure a report needs is known before any drawing starts (count_pages
# already relies on that). So figures are only *built* here; rendering them
# to PNG happens once, for the whole batch, in _render_batch below — kaleido
# pays a ~1.8s subprocess/IPC cost per call regardless of what it's
# rendering, so N separate fig.to_image() calls cost N x that overhead where
# one batched plotly.io.write_images() call pays it once.
# ---------------------------------------------------------------------------

def _base_layout(width: int, height: int, title: str) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=13, color=TEXT_COLOR, family=FONT_FAMILY)),
        font=dict(family=FONT_FAMILY, size=10, color=TEXT_COLOR),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        showlegend=False,
        width=width,
        height=height,
        margin=dict(l=62, r=24, t=42, b=48),
    )


def _axis(title: str) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=10, color=SUBTEXT_COLOR)),
        tickfont=dict(size=9, color=SUBTEXT_COLOR),
        gridcolor="rgba(0,0,0,0.05)",
        linecolor="rgba(0,0,0,0.12)",
        zeroline=False,
    )


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
    fig.update_layout(**_base_layout(width, height, title),
                      xaxis=_axis(x_label), yaxis=_axis(y_label))
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
    fig.update_layout(**_base_layout(width, height, f"{item.item_name}{unit}"),
                      xaxis=_axis("Wafer #"), yaxis=_axis(""))
    return fig


def _render_batch(figs: list[go.Figure]) -> list[bytes]:
    """Render many figures to PNG in a single kaleido batch call.

    plotly.io.write_images (kaleido >= 1.0, this repo pins 1.3.0) opens one
    browser session for the whole list instead of one per figure. Measured
    on this repo: 10 individually-rendered figures took 18.6s; the same 10
    through one write_images() call took 3.3s (0.33s/image) — the per-call
    cost that dominated was subprocess/IPC startup, not the render itself.

    write_images does NOT fall back to each figure's own layout width/height
    the way fig.to_image() does — it defaults to a global size — so width
    and height are passed explicitly per figure to preserve that behavior.
    """
    if not figs:
        return []
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = [Path(tmpdir) / f"{i}.png" for i in range(len(figs))]
        widths = [fig.layout.width for fig in figs]
        heights = [fig.layout.height for fig in figs]
        pio.write_images(figs, file=paths, format="png", scale=2,
                         width=widths, height=heights)
        return [p.read_bytes() for p in paths]


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


def _draw_table_header(c: canvas.Canvas, y: float) -> float:
    c.saveState()
    c.setFont("Helvetica-Bold", TABLE_FONT)
    c.setFillColorRGB(0.38, 0.36, 0.35)
    x = MARGIN
    for header, width in zip(COL_HEADERS, COL_WIDTHS):
        c.drawString(x, y, header)
        x += width * mm
    c.setStrokeColorRGB(0, 0, 0, alpha=0.12)
    c.setLineWidth(0.5)
    c.line(MARGIN, y - 1.5 * mm, MARGIN + sum(COL_WIDTHS) * mm, y - 1.5 * mm)
    c.restoreState()
    return y - ROW_H


def _draw_item_row(c: canvas.Canvas, y: float, item: WatItemStats) -> float:
    cells = [
        STATUS_MARK.get(item.status, ""),
        item.item_name,
        item.unit,
        fmt_value(item.spec_low),
        fmt_value(item.spec_high),
        str(item.n),
        fmt_value(item.mean),
        fmt_value(item.sigma),
        fmt_value(item.min),
        fmt_value(item.max),
        fmt_cpk(item.cpk, item.cpk_state),
        str(item.oos_count),
    ]
    c.saveState()
    c.setFont("Helvetica", TABLE_FONT)
    x = MARGIN
    for i, (text, width) in enumerate(zip(cells, COL_WIDTHS)):
        # The mark column carries the status color; every other cell stays ink
        # so a colored value never has to be read as a judgement.
        c.setFillColorRGB(*(STATUS_RGB.get(item.status, STATUS_RGB["ok"])
                            if i == 0 else STATUS_RGB["ok"]))
        avail = width * mm - 1.2 * mm
        while text and c.stringWidth(text, "Helvetica", TABLE_FONT) > avail:
            text = text[:-1]
        c.drawString(x, y, text)
        x += width * mm
    c.restoreState()
    return y - ROW_H


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _rows_per_page(content_top: float) -> int:
    """How many item rows fit between the header rule and the footer.

    The column header itself is drawn at `content_top` (row 0); item k is
    drawn at content_top - k * ROW_H. The last item that still fits satisfies
    content_top - k * ROW_H >= PAGE_BREAK_MARGIN, i.e. its own slot already
    accounts for the header's row — no extra ROW_H subtraction needed here.
    """
    usable = content_top - PAGE_BREAK_MARGIN
    return max(1, int(usable // ROW_H))


def count_pages(summary: WatSummaryResponse, content_top: float) -> int:
    """Total page count, known before drawing.

    ReportLab cannot revisit a finished page, so "Page n of N" needs N up
    front. Every section's length is a pure function of the summary, so the
    count is computed rather than guessed.
    """
    per_page = _rows_per_page(content_top)
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
    # kaleido call (see _render_batch) instead of one call per figure.
    scatter_figs = [_scatter_figure(p) for p in scatter_plots]
    trend_figs = [_trend_figure(i) for i in flagged]
    rendered = _render_batch(scatter_figs + trend_figs)
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
    y = _draw_table_header(c, probe_top)
    if not summary.items:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(*STATUS_RGB["gray"])
        c.drawString(MARGIN, y, "No WAT data for this lot.")
    for item in summary.items:
        if y < PAGE_BREAK_MARGIN:
            y = _draw_table_header(c, end_page())
        y = _draw_item_row(c, y, item)

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
