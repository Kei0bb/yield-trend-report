from fastapi import APIRouter, Query

from app.services.summary_service import build_summary
from app.services.ttl_cache import get_or_compute

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard_summary(
    months: int = Query(6, ge=1, le=24),
    process: str = Query("all"),
    force: bool = Query(False),
) -> dict:
    return get_or_compute(
        f"summary:{months}:{process}",
        lambda: build_summary(months=months, process=process),
        force=force,
    )
