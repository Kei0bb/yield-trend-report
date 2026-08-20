"""
PDF generation service for Yield Trend Reports.

Branding configuration (COMPANY_NAME / LOGO_PATH / CONFIDENTIAL) lives in
pdf_common.py — shared with the PCM/WAT report — not here.
"""

import io
from datetime import date, timedelta

import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.schemas import ProcessData
from app.services.pdf_common import (
    COMPANY_NAME, CONFIDENTIAL, FONT_FAMILY, FOOTER_H, HEADER_DIVIDER_OFFSET,
    HEADER_H, LOGO_PATH, MARGIN, SUBTEXT_COLOR, TEXT_COLOR,
    draw_footer, draw_logo,
)

# ---------------------------------------------------------------------------
# Design tokens (Notion-inspired)
# ---------------------------------------------------------------------------
# Categorical fail-bin palette. Mirrors frontend/src/theme.ts BIN_COLORS —
# keep the two lists identical so screen and PDF agree.
# The ORDER is the colorblind-safety mechanism, not cosmetic: this sequence was
# validated for adjacent stacked segments on a white surface (worst adjacent
# CVD dE 9.1, normal-vision dE 19.6). Reordering or inserting a hue voids that.
BIN_COLORS = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]

YIELD_LINE_COLOR = "#292929"


# ---------------------------------------------------------------------------
# Chart rendering
# ---------------------------------------------------------------------------

def _create_chart_image(
    process_name: str,
    proc_data: ProcessData,
    width: int = 1000,
    height: int = 460,
    color_map: dict[str, str] | None = None,
) -> bytes:
    """単一品種: Bin stacked bar + Yield line"""
    fig = go.Figure()

    bin_names = list(proc_data.fail_bins.keys())
    for i, bin_name in enumerate(bin_names):
        fig.add_trace(go.Bar(
            x=proc_data.lots,
            y=proc_data.fail_bins[bin_name],
            name=bin_name,
            marker_color=(color_map or {}).get(bin_name, BIN_COLORS[i % len(BIN_COLORS)]),
            yaxis="y",
        ))

    fig.add_trace(go.Scatter(
        x=proc_data.lots,
        y=proc_data.yield_avg,
        name="Yield (%)",
        mode="lines+markers",
        line=dict(color=YIELD_LINE_COLOR, width=2),
        marker=dict(size=7, color=YIELD_LINE_COLOR),
        yaxis="y2",
    ))

    fig.update_layout(
        barmode="stack",
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR),
        xaxis=dict(
            title=dict(text="Week", font=dict(size=11, color=SUBTEXT_COLOR)),
            tickangle=-30,
            tickfont=dict(size=11, color=SUBTEXT_COLOR),
            gridcolor="rgba(0,0,0,0.04)",
            linecolor="rgba(0,0,0,0.1)",
        ),
        yaxis=dict(
            title=dict(text="Fail Bin (%)", font=dict(size=11, color=SUBTEXT_COLOR)),
            side="left",
            range=[0, 102],  # 0-100 fixed + margin
            tickfont=dict(size=11, color=SUBTEXT_COLOR),
            showticklabels=False,
            gridcolor="rgba(0,0,0,0.04)",
            zerolinecolor="rgba(0,0,0,0.08)",
        ),
        yaxis2=dict(
            title=dict(text="Yield (%)", font=dict(size=11, color=SUBTEXT_COLOR)),
            side="right",
            overlaying="y",
            range=[0, 102],  # 0-100 fixed; +2 margin so points at 100 aren't clipped
            tickfont=dict(size=11, color=SUBTEXT_COLOR),
            showticklabels=False,
            showgrid=False,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.38,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color=SUBTEXT_COLOR, family=FONT_FAMILY),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=60, r=60, t=20, b=110),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        width=width,
        height=height,
    )

    return fig.to_image(format="png", scale=2)


# ---------------------------------------------------------------------------
# Page components
# ---------------------------------------------------------------------------

def _draw_header(
    c: canvas.Canvas,
    page_width: float,
    page_height: float,
    product: str,
    start_month: str,
    end_month: str,
    process_name: str,
) -> None:
    """Draw the page header band."""
    top = page_height - MARGIN

    # ── Logo (left) ──────────────────────────────────────────────────────
    logo_h = 12 * mm
    logo_y = top - logo_h + 3 * mm  # nudge upward into the top margin
    draw_logo(c, MARGIN, logo_y, logo_h)

    # ── Divider (header base) ────────────────────────────────────────────
    div_y = page_height - HEADER_H + HEADER_DIVIDER_OFFSET

    # ── Product title (left, baseline aligned just above the divider) ────
    title_y = div_y + 3.5 * mm
    c.saveState()
    c.setFillColorRGB(0.13, 0.12, 0.11)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(MARGIN, title_y, product)
    c.restoreState()

    # Process chip (right of title)
    chip_text = process_name
    chip_font_size = 7.5
    chip_padding_x = 3.5 * mm
    chip_h = 4.5 * mm
    c.saveState()
    c.setFont("Helvetica-Bold", chip_font_size)
    chip_w = c.stringWidth(chip_text, "Helvetica-Bold", chip_font_size) + chip_padding_x * 2
    chip_x = MARGIN + c.stringWidth(product, "Helvetica-Bold", 18) + 5 * mm
    chip_y = title_y
    c.setFillColorRGB(0.95, 0.97, 1.0)
    c.setStrokeColorRGB(0.04, 0.46, 0.91, alpha=0.5)
    c.setLineWidth(0.6)
    c.roundRect(chip_x, chip_y, chip_w, chip_h, 2, stroke=1, fill=1)
    c.setFillColorRGB(0.04, 0.46, 0.91)
    c.drawString(chip_x + chip_padding_x, chip_y + 1.4 * mm, chip_text)
    c.restoreState()

    # ── Meta row (right-aligned, same baseline as title) ─────────────────
    c.saveState()
    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(0.38, 0.36, 0.35)
    today = date.today()
    period_start = today - timedelta(days=90)
    meta = (
        f"Product  {product}"
        f"   ·   Period  {period_start.isoformat()} to {today.isoformat()}"
        f"   ·   Process  {process_name}"
    )
    c.drawRightString(page_width - MARGIN, title_y, meta)
    c.restoreState()

    # ── Draw divider line ────────────────────────────────────────────────
    c.saveState()
    c.setStrokeColorRGB(0, 0, 0, alpha=0.18)  # より濃く視認性アップ
    c.setLineWidth(0.8)
    c.line(MARGIN, div_y, page_width - MARGIN, div_y)
    c.restoreState()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_pdf(
    products: list[str],
    start_month: str,
    end_month: str,
    data: dict[str, dict[str, ProcessData]],  # process -> product -> ProcessData
) -> bytes:
    """
    複数品種対応 PDF 生成。
    - 1 品種: 工程ごとに Bin bar + Yield line のページ
    - 複数品種: 工程ごとに品種別 Yield line 比較ページ
    """
    buf = io.BytesIO()
    page_width, page_height = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    title_label = products[0]

    # データがある工程のみ対象。全工程データ無しの場合は空 PDF を避けるため
    # リクエスト工程をそのまま使い、データ無しならプレースホルダ表示する。
    processes = [
        p for p, prod_dict in data.items()
        if any(d.lots for d in prod_dict.values())
    ]
    if not processes:
        processes = list(data.keys()) or ["CP"]
    total_pages = len(processes)

    # Shared bin-name -> color map across ALL processes/products so the same
    # bin keeps one color on every page (first-appearance order over the
    # displayed processes, then products). Mirrors the web Report's ReportView.
    bin_order: list[str] = []
    for process_name in processes:
        prod_dict = data.get(process_name, {})
        for product in products:
            pdata = prod_dict.get(product)
            if not pdata:
                continue
            for b in pdata.fail_bins.keys():
                if b not in bin_order:
                    bin_order.append(b)
    color_map = {b: BIN_COLORS[i % len(BIN_COLORS)] for i, b in enumerate(bin_order)}

    for page_num, process_name in enumerate(processes, start=1):
        prod_dict = data[process_name]

        # 1. Header
        _draw_header(
            c, page_width, page_height,
            title_label, start_month, end_month, process_name,
        )

        # 2. Chart (データ無し / 画像生成失敗時はテキストで代替)
        has_data = any(prod_dict.get(p) and prod_dict[p].lots for p in products)
        chart_bytes: bytes | None = None
        if has_data:
            try:
                chart_bytes = _create_chart_image(process_name, prod_dict[products[0]], color_map=color_map)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    "chart image generation failed for %s: %s", process_name, e,
                )
                chart_bytes = None

        chart_x = MARGIN
        chart_y = FOOTER_H + 2 * mm
        chart_w = page_width - 2 * MARGIN
        chart_h = page_height - HEADER_H - FOOTER_H - 4 * mm

        if chart_bytes:
            img_reader = ImageReader(io.BytesIO(chart_bytes))
            c.drawImage(
                img_reader,
                chart_x,
                chart_y,
                width=chart_w,
                height=chart_h,
                preserveAspectRatio=True,
                anchor="n",
            )
        else:
            # プレースホルダ
            c.saveState()
            c.setFillColorRGB(0.55, 0.53, 0.52)
            c.setFont("Helvetica", 14)
            c.drawCentredString(
                chart_x + chart_w / 2,
                chart_y + chart_h / 2,
                f"No data available for {process_name}",
            )
            c.restoreState()

        # 3. Footer
        draw_footer(c, page_width, page_num, total_pages)

        c.showPage()

    c.save()
    return buf.getvalue()
