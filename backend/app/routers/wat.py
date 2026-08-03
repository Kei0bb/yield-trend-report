import logging

from fastapi import APIRouter, Query

from app.models.schemas import WatLotsResponse, WatSummaryResponse
from app.services.product_config import nickname_for_product_id
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
