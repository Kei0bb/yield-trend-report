"""
PDF generation service for Yield Trend Reports.

Branding configuration — swap these out for production:
  COMPANY_NAME  : displayed in the header logo area
  LOGO_PATH     : absolute path to a PNG/JPG logo file, or None to use mock
  CONFIDENTIAL  : set False to suppress the diagonal watermark
"""

import io
import math
from datetime import date
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.schemas import ProcessData

# ---------------------------------------------------------------------------
# Branding  ← production で差し替えてください
# ---------------------------------------------------------------------------
COMPANY_NAME: str = "Acme Semiconductor"          # ← 企業名
LOGO_PATH: str | None = None                       # ← ロゴ画像の絶対パス (PNG/JPG) | None = mock
CONFIDENTIAL: bool = True                          # ← False にすると透かし非表示

# ---------------------------------------------------------------------------
# Design tokens (Notion-inspired)
# ---------------------------------------------------------------------------
BIN_COLORS = [
    "#2a9d99",  # teal
    "#1aae39",  # green
    "#dd5b00",  # orange
    "#ff64c8",  # pink
    "#391c57",  # purple
    "#e9b949",  # yellow
    "#e03e3e",  # red
    "#0075de",  # notion blue
    "#a39e98",  # gray
    "#37352f",  # warm dark
    "#097fe8",  # focus blue
    "#005bab",  # active blue
]

YIELD_LINE_COLOR = "#0075de"
TEXT_COLOR = "#37352f"
SUBTEXT_COLOR = "#615d59"
FONT_FAMILY = "Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"

# PDF layout constants
MARGIN = 15 * mm
HEADER_H = 38 * mm   # height of the header band
FOOTER_H = 10 * mm   # height of the footer band


# 品種ごとの色（複数品種比較用）
PRODUCT_COLORS = [
    "#0075de",  # notion blue
    "#e03e3e",  # red
    "#1aae39",  # green
    "#dd5b00",  # orange
    "#391c57",  # purple
    "#e9b949",  # yellow
    "#097fe8",  # focus blue
    "#ff64c8",  # pink
]

# ---------------------------------------------------------------------------
# Chart rendering
# ---------------------------------------------------------------------------

def _create_chart_image(
    process_name: str,
    proc_data: ProcessData,
    width: int = 1000,
    height: int = 460,
) -> bytes:
    """単一品種: Bin stacked bar + Yield line"""
    fig = go.Figure()

    bin_names = list(proc_data.fail_bins.keys())
    for i, bin_name in enumerate(bin_names):
        fig.add_trace(go.Bar(
            x=proc_data.lots,
            y=proc_data.fail_bins[bin_name],
            name=bin_name,
            marker_color=BIN_COLORS[i % len(BIN_COLORS)],
            opacity=0.9,
            yaxis="y",
        ))

    fig.add_trace(go.Scatter(
        x=proc_data.lots,
        y=proc_data.yield_avg,
        name="Yield (%)",
        mode="lines+markers",
        line=dict(color=YIELD_LINE_COLOR, width=2.5, shape="spline"),
        marker=dict(size=7, color=YIELD_LINE_COLOR),
        yaxis="y2",
    ))

    fig.update_layout(
        barmode="stack",
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR),
        xaxis=dict(
            title=dict(text="Work Week", font=dict(size=11, color=SUBTEXT_COLOR)),
            tickangle=-30,
            tickfont=dict(size=11, color=SUBTEXT_COLOR),
            gridcolor="rgba(0,0,0,0.04)",
            linecolor="rgba(0,0,0,0.1)",
        ),
        yaxis=dict(
            title=dict(text="Fail Bin (%)", font=dict(size=11, color=SUBTEXT_COLOR)),
            side="left",
            rangemode="tozero",
            tickfont=dict(size=11, color=SUBTEXT_COLOR),
            gridcolor="rgba(0,0,0,0.04)",
            zerolinecolor="rgba(0,0,0,0.08)",
        ),
        yaxis2=dict(
            title=dict(text="Yield (%)", font=dict(size=11, color=SUBTEXT_COLOR)),
            side="right",
            overlaying="y",
            range=[80, 100],
            tickfont=dict(size=11, color=SUBTEXT_COLOR),
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


def _create_multi_chart_image(
    process_name: str,
    products: list[str],
    product_data: dict[str, ProcessData],
    width: int = 1100,
    height: int = 500,
) -> bytes:
    """
    複数（改版）品種: 同一チャートに grouped stacked bar + 品種別 Yield line
    Work Week ごとに品種別 Bin stack を横に並べ、Yield ラインを重ね描き。
    """
    # 共通 yield スケール
    all_yields = [v for p in products for v in product_data[p].yield_avg]
    y_min = min(all_yields) if all_yields else 80
    y_max = max(all_yields) if all_yields else 100
    y_pad = max((y_max - y_min) * 0.5, 2)
    y_range = [max(0, y_min - y_pad), min(100, y_max + y_pad)]

    # 全 bin 名のユニオン
    all_bin_names: list[str] = []
    for p in products:
        for b in product_data[p].fail_bins.keys():
            if b not in all_bin_names:
                all_bin_names.append(b)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Bar traces: product × bin
    for p_idx, product in enumerate(products):
        proc_data = product_data[product]
        for b_idx, bin_name in enumerate(all_bin_names):
            y_vals = proc_data.fail_bins.get(bin_name, [0] * len(proc_data.lots))
            fig.add_trace(
                go.Bar(
                    x=proc_data.lots,
                    y=y_vals,
                    name=bin_name,
                    marker_color=BIN_COLORS[b_idx % len(BIN_COLORS)],
                    opacity=0.9,
                    offsetgroup=product,        # 同じ product のbinsは積み上げ
                    legendgroup=bin_name,
                    showlegend=(p_idx == 0),    # 凡例は最初の品種のみ
                    hovertemplate=f"<b>{product}</b> @ %{{x}}<br>{bin_name}: %{{y:.3f}}%<extra></extra>",
                ),
                secondary_y=False,
            )

    # Yield line: 品種別
    for i, product in enumerate(products):
        proc_data = product_data[product]
        color = PRODUCT_COLORS[i % len(PRODUCT_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=proc_data.lots,
                y=proc_data.yield_avg,
                name=f"Yield · {product}",
                mode="lines+markers",
                line=dict(color=color, width=2.5, shape="spline"),
                marker=dict(size=6, color=color),
                legendgroup=f"yield_{product}",
                hovertemplate=f"<b>{product}</b> @ %{{x}}<br>Yield: %{{y:.2f}}%<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_yaxes(
        title_text="Fail Bin (%)",
        rangemode="tozero",
        tickfont=dict(size=11, color=SUBTEXT_COLOR),
        gridcolor="rgba(0,0,0,0.04)",
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Yield (%)",
        range=y_range,
        tickfont=dict(size=11, color=SUBTEXT_COLOR),
        showgrid=False,
        secondary_y=True,
    )
    fig.update_xaxes(
        title_text="Work Week",
        tickangle=-30,
        tickfont=dict(size=11, color=SUBTEXT_COLOR),
        gridcolor="rgba(0,0,0,0.04)",
    )

    fig.update_layout(
        barmode="stack",
        bargap=0.25,
        bargroupgap=0.08,
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR),
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


def _create_comparison_chart_image(
    process_name: str,
    product_data: dict[str, ProcessData],
    width: int = 1000,
    height: int = 460,
) -> bytes:
    """複数品種比較: 品種ごとの Yield line を重ね描き"""
    # Y 軸範囲を動的計算（余白 ±2%）
    all_yields = [v for d in product_data.values() for v in d.yield_avg]
    y_min = min(all_yields) if all_yields else 80
    y_max = max(all_yields) if all_yields else 100
    y_pad = max((y_max - y_min) * 0.5, 2)
    y_range = [max(0, y_min - y_pad), min(100, y_max + y_pad)]

    fig = go.Figure()

    for i, (product, proc_data) in enumerate(product_data.items()):
        color = PRODUCT_COLORS[i % len(PRODUCT_COLORS)]
        fig.add_trace(go.Scatter(
            x=proc_data.lots,
            y=proc_data.yield_avg,
            name=product,
            mode="lines+markers",
            line=dict(color=color, width=2.5, shape="spline"),
            marker=dict(size=7, color=color),
        ))

    fig.update_layout(
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_COLOR),
        xaxis=dict(
            title=dict(text="Work Week", font=dict(size=11, color=SUBTEXT_COLOR)),
            tickangle=-30,
            tickfont=dict(size=11, color=SUBTEXT_COLOR),
            gridcolor="rgba(0,0,0,0.05)",
            linecolor="rgba(0,0,0,0.1)",
        ),
        yaxis=dict(
            title=dict(text="Yield (%)", font=dict(size=11, color=SUBTEXT_COLOR)),
            range=y_range,
            tickfont=dict(size=11, color=SUBTEXT_COLOR),
            gridcolor="rgba(0,0,0,0.05)",
            zerolinecolor="rgba(0,0,0,0.08)",
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

def _draw_logo(c: canvas.Canvas, x: float, y: float, h: float) -> None:
    """Draw company logo. Replace with c.drawImage(LOGO_PATH, ...) in production."""
    if LOGO_PATH and Path(LOGO_PATH).exists():
        # --- Production: real logo image ---
        w = h * 3  # assume ~3:1 aspect ratio; adjust as needed
        c.drawImage(
            ImageReader(LOGO_PATH),
            x, y,
            width=w, height=h,
            preserveAspectRatio=True,
            anchor="sw",
            mask="auto",
        )
    else:
        # --- Mock: styled placeholder box ---
        box_w = 44 * mm
        box_h = h
        # Box outline
        c.saveState()
        c.setStrokeColorRGB(0.0, 0.46, 0.87, alpha=0.4)
        c.setFillColorRGB(0.95, 0.97, 1.0)
        c.setLineWidth(0.8)
        c.roundRect(x, y, box_w, box_h, 3, stroke=1, fill=1)
        # Company name inside
        c.setFillColorRGB(0.0, 0.46, 0.87)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x + box_w / 2, y + box_h / 2 + 1.5, COMPANY_NAME.upper())
        c.setFont("Helvetica", 6)
        c.setFillColorRGB(0.38, 0.36, 0.35)
        c.drawCentredString(x + box_w / 2, y + box_h / 2 - 5, "LOGO PLACEHOLDER")
        c.restoreState()


def _draw_confidential_watermark(
    c: canvas.Canvas, page_width: float, page_height: float
) -> None:
    """Draw a diagonal CONFIDENTIAL watermark across the center of the page."""
    if not CONFIDENTIAL:
        return
    c.saveState()
    c.setFillColorRGB(0.6, 0.0, 0.0, alpha=0.055)
    c.setFont("Helvetica-Bold", 72)
    c.translate(page_width / 2, page_height / 2)
    c.rotate(math.degrees(math.atan2(page_height, page_width)))  # diagonal angle
    c.drawCentredString(0, 0, "CONFIDENTIAL")
    c.restoreState()


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
    logo_h = 9 * mm
    logo_y = top - logo_h
    _draw_logo(c, MARGIN, logo_y, logo_h)

    # ── CONFIDENTIAL badge (right) ────────────────────────────────────────
    if CONFIDENTIAL:
        badge_w = 30 * mm
        badge_h = 5.5 * mm
        badge_x = page_width - MARGIN - badge_w
        badge_y = top - badge_h - 1 * mm
        c.saveState()
        c.setFillColorRGB(0.88, 0.0, 0.0, alpha=0.9)
        c.setLineWidth(0)
        c.roundRect(badge_x, badge_y, badge_w, badge_h, 2, stroke=0, fill=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(badge_x + badge_w / 2, badge_y + 1.8 * mm, "CONFIDENTIAL")
        c.restoreState()

    # Generated date (right, below badge)
    c.saveState()
    c.setFillColorRGB(0.47, 0.46, 0.45)
    c.setFont("Helvetica", 7.5)
    c.drawRightString(
        page_width - MARGIN,
        top - logo_h - 0.5 * mm,
        f"Generated  {date.today().isoformat()}",
    )
    c.restoreState()

    # ── Product title ─────────────────────────────────────────────────────
    title_y = top - logo_h - 7.5 * mm
    c.saveState()
    c.setFillColorRGB(0.13, 0.12, 0.11)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, title_y, product)
    c.restoreState()

    # Process chip
    chip_text = process_name
    chip_font_size = 7.5
    chip_padding_x = 3.5 * mm
    chip_h = 4.5 * mm
    c.saveState()
    c.setFont("Helvetica-Bold", chip_font_size)
    chip_w = c.stringWidth(chip_text, "Helvetica-Bold", chip_font_size) + chip_padding_x * 2
    chip_x = MARGIN + c.stringWidth(product, "Helvetica-Bold", 18) + 3 * mm
    chip_y = title_y + 1 * mm
    c.setFillColorRGB(0.95, 0.97, 1.0)
    c.setStrokeColorRGB(0.04, 0.46, 0.91, alpha=0.5)
    c.setLineWidth(0.6)
    c.roundRect(chip_x, chip_y, chip_w, chip_h, 2, stroke=1, fill=1)
    c.setFillColorRGB(0.04, 0.46, 0.91)
    c.drawString(chip_x + chip_padding_x, chip_y + 1.4 * mm, chip_text)
    c.restoreState()

    # ── Meta row ──────────────────────────────────────────────────────────
    meta_y = title_y - 5.5 * mm
    c.saveState()
    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(0.38, 0.36, 0.35)
    meta = (
        f"Product  {product}"
        f"   ·   Period  {start_month} → {end_month}"
        f"   ·   Process  {process_name}"
    )
    c.drawString(MARGIN, meta_y, meta)
    c.restoreState()

    # ── Divider ───────────────────────────────────────────────────────────
    div_y = page_height - HEADER_H
    c.saveState()
    c.setStrokeColorRGB(0, 0, 0, alpha=0.08)
    c.setLineWidth(0.5)
    c.line(MARGIN, div_y, page_width - MARGIN, div_y)
    c.restoreState()


def _draw_footer(
    c: canvas.Canvas,
    page_width: float,
    current_page: int,
    total_pages: int,
) -> None:
    """Draw footer with page number and company name."""
    y = FOOTER_H - 3 * mm

    # Left: company name
    c.saveState()
    c.setFont("Helvetica", 7.5)
    c.setFillColorRGB(0.63, 0.61, 0.60)
    c.drawString(MARGIN, y, COMPANY_NAME)

    # Center: page number
    c.drawCentredString(
        page_width / 2, y,
        f"Page {current_page} of {total_pages}",
    )

    # Right: report title
    c.drawRightString(page_width - MARGIN, y, "Yield Trend Report  ·  Internal Use Only")
    c.restoreState()

    # Thin top rule for footer
    c.saveState()
    c.setStrokeColorRGB(0, 0, 0, alpha=0.07)
    c.setLineWidth(0.4)
    c.line(MARGIN, FOOTER_H, page_width - MARGIN, FOOTER_H)
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

    multi = len(products) > 1
    title_label = " vs ".join(products) if multi else products[0]

    # データがある工程のみ対象
    processes = [
        p for p, prod_dict in data.items()
        if any(d.lots for d in prod_dict.values())
    ]
    total_pages = len(processes)

    for page_num, process_name in enumerate(processes, start=1):
        prod_dict = data[process_name]

        # 1. Watermark
        _draw_confidential_watermark(c, page_width, page_height)

        # 2. Header
        _draw_header(
            c, page_width, page_height,
            title_label, start_month, end_month, process_name,
        )

        # 3. Chart
        if multi:
            # 複数品種: 品種ごとに Bin chart を生成して横に並べた画像を返す
            chart_bytes = _create_multi_chart_image(process_name, products, prod_dict)
        else:
            chart_bytes = _create_chart_image(process_name, prod_dict[products[0]])

        img_reader = ImageReader(io.BytesIO(chart_bytes))
        chart_x = MARGIN
        chart_y = FOOTER_H + 2 * mm
        chart_w = page_width - 2 * MARGIN
        chart_h = page_height - HEADER_H - FOOTER_H - 4 * mm
        c.drawImage(
            img_reader,
            chart_x,
            chart_y,
            width=chart_w,
            height=chart_h,
            preserveAspectRatio=True,
            anchor="n",
        )

        # 4. Footer
        _draw_footer(c, page_width, page_num, total_pages)

        c.showPage()

    c.save()
    return buf.getvalue()
