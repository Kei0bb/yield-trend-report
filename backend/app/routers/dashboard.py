from fastapi import APIRouter, Query

from app.services.summary_service import build_summary

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard_summary(
    months: int = Query(6, ge=1, le=24),
    process: str = Query("all"),
) -> dict:
    return build_summary(months=months, process=process)
