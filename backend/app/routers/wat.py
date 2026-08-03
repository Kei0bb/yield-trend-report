import logging
import traceback

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.models.schemas import WatExportRequest, WatLotsResponse, WatSummaryResponse
from app.services.product_config import nickname_for_product_id
from app.services.wat_pdf_service import generate_wat_pdf
from app.services.wat_service import get_wat_lots, get_wat_summary

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/wat/lots", response_model=WatLotsResponse)
def wat_lots(
    product_id: str = Query(...),
    months: int = Query(3, ge=1, le=6),
) -> WatLotsResponse:
    nickname = nickname_for_product_id(product_id) or product_id
    return get_wat_lots(nickname, product_id, months)


@router.get("/wat/summary", response_model=WatSummaryResponse)
def wat_summary(
    product_id: str = Query(...),
    lot_id: str = Query(...),
) -> WatSummaryResponse:
    nickname = nickname_for_product_id(product_id) or product_id
    return get_wat_summary(nickname, product_id, lot_id)


@router.post("/wat/export-pdf")
def wat_export_pdf(req: WatExportRequest) -> Response:
    nickname = nickname_for_product_id(req.product_id) or req.product_id
    summary = get_wat_summary(nickname, req.product_id, req.lot_id)
    try:
        pdf_bytes = generate_wat_pdf(summary)
    except Exception as e:
        logger.error("generate_wat_pdf failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    filename = f"WAT_{req.product_id}_{req.lot_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
