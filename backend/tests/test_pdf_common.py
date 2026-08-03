from pathlib import Path

from app.services import pdf_common, pdf_service


def test_branding_constants_live_in_pdf_common():
    assert pdf_common.COMPANY_NAME == "Socionext"
    assert pdf_common.CONFIDENTIAL is True
    assert pdf_common.LOGO_PATH is None or Path(pdf_common.LOGO_PATH).name == "logo.png"


def test_layout_constants_are_unchanged():
    from reportlab.lib.units import mm
    assert pdf_common.MARGIN == 15 * mm
    assert pdf_common.HEADER_H == 48 * mm
    assert pdf_common.HEADER_DIVIDER_OFFSET == 4 * mm
    assert pdf_common.FOOTER_H == 10 * mm


def test_pdf_service_reuses_the_shared_constants():
    """The yield PDF must not keep a private copy that can drift."""
    assert pdf_service.MARGIN is pdf_common.MARGIN
    assert pdf_service.COMPANY_NAME is pdf_common.COMPANY_NAME
    assert pdf_service.FOOTER_H is pdf_common.FOOTER_H


def test_shared_drawing_helpers_are_callable():
    assert callable(pdf_common.draw_logo)
    assert callable(pdf_common.draw_footer)


def test_content_disposition_ascii_fallback_and_utf8_star():
    header = pdf_common.content_disposition("ロット1")
    fallback = header.split('filename="', 1)[1].split('"', 1)[0]
    fallback.encode("ascii")  # must not raise — this is the http-header-safe part
    assert "filename*=UTF-8''" in header
    assert "%E3%83%AD" in header  # percent-encoded UTF-8 for the first kana


def test_content_disposition_header_is_latin1_encodable():
    """Regression: raw non-ASCII in Content-Disposition raised
    UnicodeEncodeError ('latin-1' codec) — after the PDF was already
    generated."""
    header = pdf_common.content_disposition("ロット1")
    header.encode("latin-1")


def test_content_disposition_quote_does_not_inject_second_filename():
    """Regression: an unescaped '\"' in the raw name used to let
    `filename="x" ; filename="evil.exe.pdf"` through, so the effective
    download name became attacker-chosen."""
    header = pdf_common.content_disposition('x" ; filename="evil.exe')
    ascii_part = header.split("; filename*=", 1)[0]
    assert ascii_part.count('filename="') == 1
    # value is quote-delimited: exactly one opening and one closing '"'
    value = ascii_part.split('filename="', 1)[1]
    assert value.endswith('"')
    assert value.count('"') == 1


def test_yield_pdf_still_generates():
    from app.models.schemas import ProcessData
    data = {"CP": {"Product-A": ProcessData(
        lots=["2026W01", "2026W02"], yield_avg=[95.0, 94.0],
        fail_bins={"Leak": [2.0, 3.0]},
    )}}
    out = pdf_service.generate_pdf(["Product-A"], "2026-01", "2026-02", data)
    assert out[:4] == b"%PDF"
    assert len(out) > 1000
