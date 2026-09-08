"""Parts shared by the two PCM/WAT PDFs (single-lot and trend).

The item table is the reason this module exists: it was drawn identically by
both reports, and a copy would drift the moment one of them gained a column.
"""

import tempfile
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.pdf_common import (
    FONT_FAMILY, FOOTER_H, MARGIN, SUBTEXT_COLOR, TEXT_COLOR,
)

STATUS_MARK: dict[str, str] = {"red": "●", "yellow": "▲",
                               "gray": "–", "ok": ""}

STATUS_RGB: dict[str, tuple[float, float, float]] = {
    "red": (0.776, 0.271, 0.271),
    "yellow": (0.831, 0.627, 0.090),
    "gray": (0.557, 0.545, 0.510),
    "ok": (0.216, 0.208, 0.184),
}

# Plotly needs hex; ReportLab needs float triples. Same colors, both forms.
STATUS_HEX: dict[str, str] = {
    "red": "#c64545", "yellow": "#d4a017", "gray": "#8e8b82", "ok": "#141413",
}

# 12 columns: mark, item, unit, low, high, N, mean, sigma, min, max, cpk, oos.
# Widths sum to the printable width of A4 portrait (210mm - 2 * 15mm).
COL_WIDTHS = [6, 40, 15, 16, 16, 12, 17, 15, 16, 16, 12, 11]
COL_HEADERS = ["", "Item", "Unit", "Low", "High", "N",
               "Mean", "Sigma", "Min", "Max", "Cpk", "OOS"]

ROW_H = 4.4 * mm
TABLE_FONT = 6.6

# Bottom margin reserved for the footer + breathing room, below which no new
# table row is drawn. Shared by rows_per_page (page-count prediction) and
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


def base_layout(width: int, height: int, title: str) -> dict:
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


def axis(title: str) -> dict:
    return dict(
        title=dict(text=title, font=dict(size=10, color=SUBTEXT_COLOR)),
        tickfont=dict(size=9, color=SUBTEXT_COLOR),
        gridcolor="rgba(0,0,0,0.05)",
        linecolor="rgba(0,0,0,0.12)",
        zeroline=False,
    )


def render_batch(figs: list[go.Figure]) -> list[bytes]:
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


def draw_table_header(c: canvas.Canvas, y: float) -> float:
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


def draw_item_row(c: canvas.Canvas, y: float, item) -> float:
    """One table row. `item` is any object carrying the scalar stats columns —
    WatItemStats or WatTrendItemStats; the series field is never read here."""
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


def rows_per_page(content_top: float) -> int:
    """How many item rows fit between the header rule and the footer.

    The column header itself is drawn at `content_top` (row 0); item k is
    drawn at content_top - k * ROW_H. The last item that still fits satisfies
    content_top - k * ROW_H >= PAGE_BREAK_MARGIN, i.e. its own slot already
    accounts for the header's row — no extra ROW_H subtraction needed here.
    """
    usable = content_top - PAGE_BREAK_MARGIN
    return max(1, int(usable // ROW_H))
