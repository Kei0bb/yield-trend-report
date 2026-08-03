"""Branding and page furniture shared by every PDF this app generates.

Both the landscape yield report (pdf_service) and the portrait PCM/WAT
report (wat_pdf_service) draw the same logo, footer, and margins. Keeping
one copy here means a branding change lands on both.

Swap these out for production:
  COMPANY_NAME  : displayed in the header logo area
  LOGO_PATH     : absolute path to a PNG/JPG logo file, or None to use mock
  CONFIDENTIAL  : set False to suppress the confidential mark
"""

import re
from datetime import date
from pathlib import Path
from urllib.parse import quote

from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
COMPANY_NAME: str = "Socionext"
LOGO_PATH: str | None = str(Path(__file__).resolve().parents[3] / "assets" / "logo.png")
CONFIDENTIAL: bool = True

# ---------------------------------------------------------------------------
# Shared type tokens
# ---------------------------------------------------------------------------
TEXT_COLOR = "#37352f"
SUBTEXT_COLOR = "#615d59"
FONT_FAMILY = "Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
MARGIN = 15 * mm
HEADER_H = 48 * mm              # header band (title + rule + padding)
HEADER_DIVIDER_OFFSET = 4 * mm  # header base → divider distance
FOOTER_H = 10 * mm


# ---------------------------------------------------------------------------
# Download filename
# ---------------------------------------------------------------------------

def content_disposition(raw_name: str) -> str:
    """Build a safe `Content-Disposition` header value for a PDF download.

    `raw_name` is built from free-form, ultimately DB-sourced strings (a
    lot_id or display_name) and may contain non-ASCII characters (garden
    variety in a Japanese-language fab tool) or quote characters. Putting it
    straight into the header either raises UnicodeEncodeError (HTTP headers
    are latin-1) or, if it contains a `"`, lets it inject a second
    `filename=` parameter that some clients prefer over the real one.

    This returns an ASCII-only `filename=` fallback (non-ASCII/unsafe chars
    replaced with `_`) plus an RFC 5987 `filename*=UTF-8''...` parameter
    carrying the real, percent-encoded name — the same pattern browsers
    already expect for non-ASCII downloads.
    """
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name)[:120] or "download"
    encoded = quote(raw_name + ".pdf", safe="")
    return f"attachment; filename=\"{safe}.pdf\"; filename*=UTF-8''{encoded}"


def draw_logo(c: canvas.Canvas, x: float, y: float, h: float) -> None:
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


def draw_footer(
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
