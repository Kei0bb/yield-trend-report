import logging
from datetime import datetime, timezone

from app.models.schemas import DashboardSummaryResponse, SparkPoint, SummaryRow
from app.services.lot_service import SUPPORTED_PROCESSES, get_lots, period_months
from app.services.product_config import primary_product_id, resolve_display_name
from app.services.yield_service import get_products

logger = logging.getLogger(__name__)


def _target_processes(process: str) -> list[str]:
    if process.lower() == "all":
        return ["CP", "FT"]            # SLT shares FT tables; CP+FT cover the dashboard
    p = process.upper()
    return [p] if p in SUPPORTED_PROCESSES else []


def _build_row(nickname: str, process: str, months: int) -> SummaryRow | None:
    lots = get_lots(nickname, process, months)
    if not lots:
        return None
    latest = lots[-1]
    yields = [l.yield_pct for l in lots]
    avg = round(sum(yields) / len(yields), 2)
    return SummaryRow(
        nickname=nickname,
        product_id=primary_product_id(nickname),
        display_name=resolve_display_name(nickname),
        process=process,
        latest_yield=latest.yield_pct,
        latest_lot_id=latest.lot_id,
        latest_lot_date=latest.lot_date,
        avg_yield_6m=avg,
        delta=round(latest.yield_pct - avg, 2),
        sparkline=[SparkPoint(lot_id=l.lot_id, lot_date=l.lot_date, yield_pct=l.yield_pct)
                   for l in lots],
        warnings=latest.warnings,
    )


def build_summary(months: int = 6, process: str = "all") -> dict:
    """Build the dashboard summary for every configured product × target process."""
    start, end = period_months(months)
    nicknames = get_products()
    processes = _target_processes(process)

    rows: list[SummaryRow] = []
    for nickname in nicknames:
        for proc in processes:
            row = _build_row(nickname, proc, months)
            if row is not None:
                rows.append(row)

    resp = DashboardSummaryResponse(
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        period={"months": months, "start": start, "end": end},
        rows=rows,
    )
    return resp.model_dump()
