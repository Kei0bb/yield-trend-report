import logging
from datetime import datetime, timezone

from app.models.schemas import DashboardSummaryResponse, SparkPoint, SummaryRow
from app.services.lot_service import SUPPORTED_PROCESSES, get_lots, period_months
from app.services.product_config import (
    primary_product_id,
    resolve_display_name,
    resolve_process_filter,
)
from app.services.yield_service import get_products

logger = logging.getLogger(__name__)


def _target_processes(process: str) -> list[str]:
    if process.lower() == "all":
        return ["CP", "FT"]            # SLT shares FT tables; CP+FT cover the dashboard
    p = process.upper()
    return [p] if p in SUPPORTED_PROCESSES else []


def _build_row(
    nickname: str,
    process: str,
    months: int,
    *,
    level: int = 0,
    process_label: str = "",
    process_values: list[str] | None = None,
) -> SummaryRow | None:
    """Build a single SummaryRow for a nickname + major process.

    Args:
        nickname: Internal product nickname.
        process: Major process name (used for navigation; always the major name).
        months: History window in months.
        level: 0 for a major row, 1 for a sub-process row.
        process_label: Display label (major name for level 0; DB PROCESS value
            for level 1).
        process_values: When provided, passed through to ``get_lots`` to query
            exactly this set of DB PROCESS values (sub-process rows).
    """
    lots = get_lots(nickname, process, months, process_values=process_values)
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
        process_label=process_label or process,
        level=level,
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
    """Build the dashboard summary for every configured product × target process.

    For each nickname × major process, emits:
    - A **major row** (level=0) covering all sub-processes combined.
    - Sub rows (level=1) only when the process has **2 or more** configured DB
      PROCESS values — one per value, querying that single value. A process with
      a single value (or none) is shown as the major row alone, since a lone sub
      row would just duplicate the major row.
    """
    start, end = period_months(months)
    nicknames = get_products()
    processes = _target_processes(process)

    rows: list[SummaryRow] = []
    for nickname in nicknames:
        for proc in processes:
            # Major row (all sub-processes combined).
            major_row = _build_row(nickname, proc, months, level=0, process_label=proc)
            if major_row is None:
                continue
            rows.append(major_row)

            # Sub-process rows — only when there are 2+ values (a lone value
            # would merely duplicate the major row).
            sub_values = resolve_process_filter(nickname, proc)
            if sub_values and len(sub_values) >= 2:
                for value in sub_values:
                    sub_row = _build_row(
                        nickname,
                        proc,
                        months,
                        level=1,
                        process_label=value,
                        process_values=[value],
                    )
                    if sub_row is not None:
                        rows.append(sub_row)

    resp = DashboardSummaryResponse(
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        period={"months": months, "start": start, "end": end},
        rows=rows,
    )
    return resp.model_dump()
