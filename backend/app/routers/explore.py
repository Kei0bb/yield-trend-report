from fastapi import APIRouter, Query

from app.models.schemas import ExploreLotsResponse
from app.services.explore_service import build_explore
from app.services.lot_service import clear_lot_df_cache, period_months
from app.services.product_config import (
    nickname_for_product_id,
    resolve_display_name,
    resolve_target,
)
from app.services.ttl_cache import get_or_compute

router = APIRouter()


@router.get("/explore/lots", response_model=ExploreLotsResponse)
def explore_lots(
    product_id: str = Query(...),
    process: str = Query(...),
    months: int = Query(6, ge=1, le=24),
    sub: str | None = Query(None),
    force: bool = Query(False),
) -> ExploreLotsResponse:
    # Resolve the UI-facing product_id back to its internal nickname (used for
    # bin_group / query resolution). Falls back to the value itself when the
    # product_id is not configured (mock / plain-nickname compatibility).
    nickname = nickname_for_product_id(product_id) or product_id
    # `sub` (a single DB PROCESS value) drills into one sub-process; without it
    # the process's full merged set is queried.
    process_values = [sub] if sub else None

    def _compute() -> ExploreLotsResponse:
        lots, available_bins = build_explore(nickname, process, months, process_values=process_values)
        start, end = period_months(months)
        return ExploreLotsResponse(
            product_id=product_id,
            display_name=resolve_display_name(nickname),
            process=sub or process,
            period={"months": months, "start": start, "end": end},
            lots=lots,
            available_bins=available_bins,
            target=resolve_target(nickname, sub or process),
        )

    if force:
        clear_lot_df_cache()
    return get_or_compute(
        f"explore:{product_id}:{process}:{months}:{sub or ''}",
        _compute,
        force=force,
    )
