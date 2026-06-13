from fastapi import APIRouter, Query

from app.models.schemas import ExploreLotsResponse
from app.services.explore_service import build_explore
from app.services.lot_service import period_months
from app.services.product_config import nickname_for_product_id, resolve_display_name

router = APIRouter()


@router.get("/explore/lots", response_model=ExploreLotsResponse)
def explore_lots(
    product_id: str = Query(...),
    process: str = Query(...),
    months: int = Query(6, ge=1, le=24),
) -> ExploreLotsResponse:
    # Resolve the UI-facing product_id back to its internal nickname (used for
    # bin_group / query resolution). Falls back to the value itself when the
    # product_id is not configured (mock / plain-nickname compatibility).
    nickname = nickname_for_product_id(product_id) or product_id
    lots, available_bins = build_explore(nickname, process, months)
    start, end = period_months(months)
    return ExploreLotsResponse(
        product_id=product_id,
        display_name=resolve_display_name(nickname),
        process=process,
        period={"months": months, "start": start, "end": end},
        lots=lots,
        available_bins=available_bins,
    )
