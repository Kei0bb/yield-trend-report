import logging
from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.models.schemas import BinBreakdown, LotData, Warning
from app.services.anomaly_service import evaluate, load_anomaly_config, resolve_config
from app.services.bin_mapping import apply_bin_groups
from app.services.lot_queries import LOT_COLUMNS, query_lot_data
from app.services.mock_data import mock_lot_dataframe
from app.services.product_config import (
    resolve_bin_group,
    resolve_process_filter,
    resolve_product_ids,
)

logger = logging.getLogger(__name__)

SUPPORTED_PROCESSES = {"CP", "FT", "SLT"}


def period_months(months: int) -> tuple[str, str]:
    """Return (start_month, end_month) as 'YYYY-MM' spanning the last `months` months."""
    today = date.today()
    end = f"{today.year:04d}-{today.month:02d}"
    start_date = today - timedelta(days=months * 30)
    start = f"{start_date.year:04d}-{start_date.month:02d}"
    return start, end


def _load_dataframe(
    nickname: str,
    process: str,
    months: int,
    process_values: list[str] | None = None,
) -> pd.DataFrame:
    """Load raw lot data for a nickname + process.

    When *process_values* is provided it overrides ``resolve_process_filter``
    and queries exactly those DB PROCESS values (used by sub-process rows).
    """
    if process.upper() not in SUPPORTED_PROCESSES:
        return pd.DataFrame(columns=LOT_COLUMNS)
    if settings.USE_MOCK_DATA:
        # In mock mode, use the first explicit process value as the seed string
        # so different sub-processes produce distinct series.
        mock_process = process_values[0] if process_values else process.upper()
        return mock_lot_dataframe(nickname, mock_process, months)
    product_ids = resolve_product_ids(nickname, process)
    if not product_ids:
        return pd.DataFrame(columns=LOT_COLUMNS)
    start, end = period_months(months)
    resolved = process_values if process_values is not None else resolve_process_filter(nickname, process)
    return query_lot_data(process, product_ids, start, end, resolved)


def _aggregate(
    df: pd.DataFrame,
    bin_group: str,
    process: str,
    *,
    raw_bins: bool = False,
) -> list[LotData]:
    """Aggregate a raw DataFrame into a list of LotData.

    When *raw_bins* is True, skip the bin-group CSV mapping and use the DB
    ``bin_name`` column directly as the bin category.
    """
    if df.empty:
        return []
    if raw_bins:
        # Use the DB bin_name directly as the category column; skip CSV mapping.
        df = df.copy()
        df["bin_code"] = df["bin_name"]
    else:
        df = apply_bin_groups(df, bin_group, process)  # adds 'bin_code' = group name

    lots: list[LotData] = []
    for lot_id, g in df.groupby("lot_id", sort=False):
        wafer_count = int(g["wafer_id"].nunique())
        lot_yield = round(float(g.groupby("wafer_id")["yield_pct"].first().mean()), 2)
        total_gross = float(g.groupby("wafer_id")["gross_die"].first().sum())

        breakdown: list[BinBreakdown] = []
        for bin_name, bg in g.groupby("bin_code", sort=False):
            count = int(bg["bin_fail_count"].sum())
            percent = round(count / total_gross * 100, 3) if total_gross else 0.0
            raw_codes = sorted({int(c) for c in bg["raw_bin_code"].tolist()})
            breakdown.append(BinBreakdown(
                bin_name=str(bin_name), bin_codes=raw_codes,
                count=count, percent=percent,
            ))
        lots.append(LotData(
            lot_id=str(lot_id),
            lot_date=str(g["lot_date"].iloc[0]),
            wafer_count=wafer_count,
            yield_pct=lot_yield,
            bin_breakdown=breakdown,
            warnings=[],
        ))

    lots.sort(key=lambda l: (l.lot_date, l.lot_id))
    return lots


def get_lots(
    nickname: str,
    process: str,
    months: int = 6,
    *,
    raw_bins: bool = False,
    process_values: list[str] | None = None,
) -> list[LotData]:
    """Return lot-granular data for a product+process, oldest→newest, with
    anomaly warnings attached to the latest lot.

    Args:
        nickname: Internal product nickname.
        process: Major process name ("CP", "FT", "SLT").
        months: How many months of history to include.
        raw_bins: When True, skip the bin-group CSV mapping and use raw DB bin
            names directly as categories. Anomaly evaluation still runs on the
            full raw breakdown.
        process_values: When provided, bypass ``resolve_process_filter`` and
            query exactly these DB PROCESS values. Used to build sub-process
            rows on the dashboard.
    """
    df = _load_dataframe(nickname, process, months, process_values=process_values)
    bin_group = resolve_bin_group(nickname, process)
    lots = _aggregate(df, bin_group, process, raw_bins=raw_bins)
    if lots:
        cfg = resolve_config(nickname, load_anomaly_config())
        warns = evaluate(lots, cfg)
        lots[-1].warnings = [Warning(**w) for w in warns]
    return lots
