import logging
from datetime import datetime, timezone

from app.models.schemas import DashboardSummaryResponse, SparkPoint, SummaryRow
from app.services.lot_service import SUPPORTED_PROCESSES, get_lots, period_months
from app.services.product_config import (
    primary_product_id,
    resolve_display_name,
    resolve_major_process,
    resolve_sub_processes,
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

    Uses ``raw_bins=True`` so anomaly bin-surge alerts are computed on the raw DB
    bin names (no CSV bin-map dependency), consistent with the Explore page.
    """
    lots = get_lots(nickname, process, months, raw_bins=True, process_values=process_values)
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

    For each nickname × major process, emits rows according to the process config:
    - **Major row** (level=0): present when ``resolve_major_process`` returns a
      non-None value; queries exactly that single DB PROCESS value (no stacking).
    - **Sub rows** (level=1): one per value from ``resolve_sub_processes``, each
      querying that single DB PROCESS value, shown indented under the major.
    - **Subs-only** (no major row): when the config has ``subs`` but no ``major``
      (e.g. ``cp: {subs: [CP1, CP2]}``), only the sub rows are emitted.
    - **Key absent**: defaults to a single major row querying the literal process
      name (e.g. "CP"), with no sub rows — preserves prior behavior.
    """
    start, end = period_months(months)
    nicknames = get_products()
    processes = _target_processes(process)

    rows: list[SummaryRow] = []
    for nickname in nicknames:
        for proc in processes:
            # Major row: queries exactly its single major DB PROCESS value.
            major = resolve_major_process(nickname, proc)
            if major is not None:
                major_row = _build_row(
                    nickname, proc, months,
                    level=0,
                    process_label=proc,
                    process_values=[major],
                )
                if major_row is not None:
                    rows.append(major_row)

            # Sub rows: one per sub-process value, each queried individually.
            for value in resolve_sub_processes(nickname, proc):
                sub_row = _build_row(
                    nickname, proc, months,
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
