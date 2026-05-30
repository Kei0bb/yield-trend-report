from fastapi import APIRouter, Query

from app.models.schemas import ExploreLotsResponse
from app.services.lot_service import get_lots, period_months

router = APIRouter()


@router.get("/explore/lots", response_model=ExploreLotsResponse)
def explore_lots(
    nickname: str = Query(...),
    process: str = Query(...),
    months: int = Query(6, ge=1, le=24),
) -> ExploreLotsResponse:
    lots = get_lots(nickname, process, months)
    start, end = period_months(months)
    available: list[str] = []
    for lot in lots:
        for b in lot.bin_breakdown:
            if b.bin_name not in available:
                available.append(b.bin_name)
    return ExploreLotsResponse(
        nickname=nickname,
        process=process,
        period={"months": months, "start": start, "end": end},
        lots=lots,
        available_bins=available,
    )
