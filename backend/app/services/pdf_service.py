"""
PDF generation service for Yield Trend Reports.

Branding configuration — swap these out for production:
  COMPANY_NAME  : displayed in the header logo area
  LOGO_PATH     : absolute path to a PNG/JPG logo file, or None to use mock
  CONFIDENTIAL  : set False to suppress the diagonal watermark
"""

import io
from datetime import date, timedelta
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.schemas import ProcessData

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
COMPANY_NAME: str = "Socionext"     
LOGO_PATH: str | None = str(Path(__file__).resolve().parents[3] / "assets" / "logo.png")  # ← project-root/assets/logo.png (backend/frontend 共通) | None = mock
CONFIDENTIAL: bool = True                     # ← False にすると透かし非表示

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

YIELD_LINE_COLOR = "#292929"
TEXT_COLOR = "#37352f"
SUBTEXT_COLOR = "#615d59"
FONT_FAMILY = "Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"

# PDF layout constants
MARGIN = 15 * mm
HEADER_H = 48 * mm           # header band 全体 (タイトル + 下線 + 余白)
HEADER_DIVIDER_OFFSET = 4 * mm  # ヘッダー底から下線までの距離 (タイトル + meta row の下に配置)
FOOTER_H = 10 * mm           # footer band


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
    # Yield scale fixed at 0-100 with a small top margin so points at 100 don't clip.
    y_range = [0, 102]

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
                line=dict(color=color, width=2),
                marker=dict(size=6, color=color),
                legendgroup=f"yield_{product}",
                hovertemplate=f"<b>{product}</b> @ %{{x}}<br>Yield: %{{y:.2f}}%<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_yaxes(
        title_text="Fail Bin (%)",
        range=[0, 102],  # 0-100 fixed + margin
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
    _draw_logo(c, MARGIN, logo_y, logo_h)

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
    chip_x = MARGIN + c.stringWidth(product, "Helvetica-Bold", 18) + 3 * mm
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


def _draw_footer(
    c: canvas.Canvas,
    page_width: float,
    current_page: int,
    total_pages: int,
) -> None:
    """Draw footer with generated date, page number, and confidential mark."""
    y = FOOTER_H - 3 * mm

    # Left: generated date (moved from header right)
    c.saveState()
    c.setFont("Helvetica", 7.5)
    c.setFillColorRGB(0.63, 0.61, 0.60)
    c.drawString(MARGIN, y, f"Generated  {date.today().isoformat()}")

    # Center: page number
    c.drawCentredString(
        page_width / 2, y,
        f"Page {current_page} of {total_pages}",
    )

    # Right: CONFIDENTIAL — red text only (no fill background)
    if CONFIDENTIAL:
        c.setFillColorRGB(0.78, 0.0, 0.0)
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(page_width - MARGIN, y, "SOCIONEXT CONFIDENTIAL")
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

    # データがある工程のみ対象。全工程データ無しの場合は空 PDF を避けるため
    # リクエスト工程をそのまま使い、データ無しならプレースホルダ表示する。
    processes = [
        p for p, prod_dict in data.items()
        if any(d.lots for d in prod_dict.values())
    ]
    if not processes:
        processes = list(data.keys()) or ["CP"]
    total_pages = len(processes)

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
                if multi:
                    chart_bytes = _create_multi_chart_image(process_name, products, prod_dict)
                else:
                    chart_bytes = _create_chart_image(process_name, prod_dict[products[0]])
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
        _draw_footer(c, page_width, page_num, total_pages)

        c.showPage()

    c.save()
    return buf.getvalue()
