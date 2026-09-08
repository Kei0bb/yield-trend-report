"""PCM/WAT trend service: item statistics pooled over a period, plus a
per-lot series for each item.

The counterpart of wat_service, which is scoped to a single lot. Everything
here spans lots; the Cpk/OOS/judgement core itself is shared (_item_core), so
the two reports can never disagree about what a Cpk of 1.2 means.
"""

import logging
from datetime import date, timedelta

import pandas as pd

from app.config import settings
from app.models.schemas import (
    WatLotInfo, WatLotPoint, WatTrendItemStats, WatTrendResponse,
)
from app.services.mock_data import mock_wat_trend_dataframe
from app.services.product_config import primary_product_id, resolve_display_name
from app.services.wat_queries import WAT_TREND_COLUMNS, query_wat_trend
from app.services.wat_service import _item_core, resolve_spec

logger = logging.getLogger(__name__)


def _period(months: int) -> tuple[date, date]:
    """[start, end) for the window. The end is exclusive and one day ahead so
    today's measurements are included — the same contract as _load_lots()."""
    today = date.today()
    return today - timedelta(days=months * 30), today + timedelta(days=1)


def _load_trend(product_id: str, months: int) -> pd.DataFrame:
    if settings.USE_MOCK_DATA:
        return mock_wat_trend_dataframe(product_id, months)
    start, end = _period(months)
    return query_wat_trend(product_id, start, end)


def _measured_date(stamps: pd.Series) -> str:
    """A lot's date is its latest measurement, trimmed to YYYY-MM-DD."""
    clean = stamps.dropna()
    return str(clean.max())[:10] if not clean.empty else ""


def build_lot_series(group: pd.DataFrame, item_name: str,
                     spec_low: float | None,
                     spec_high: float | None) -> list[dict]:
    """One point per lot for a single item, oldest measured date first.

    The spec limits are passed in rather than re-resolved per lot: the chart
    draws one spec line for the whole period, so judging each lot against a
    different limit would put a red point under a line it never crossed.
    """
    points: list[dict] = []
    for lot_id, g in group.groupby("lot_id", sort=False):
        core = _item_core(g, item_name, spec_low, spec_high)
        points.append({
            "lot_id": str(lot_id),
            "measured_date": _measured_date(g["start_time"]),
            "n": core["n"],
            "mean": core["mean"],
            "sigma": core["sigma"],
            "cpk": core["cpk"],
            "cpk_state": core["cpk_state"],
            "status": core["status"],
        })
    points.sort(key=lambda p: (p["measured_date"], p["lot_id"]))
    return points


def _lot_infos(df: pd.DataFrame) -> list[WatLotInfo]:
    """Lot list for the header strip, newest measured date first."""
    rows: list[WatLotInfo] = []
    for lot_id, g in df.groupby("lot_id", sort=False):
        rows.append(WatLotInfo(
            lot_id=str(lot_id),
            last_measured=_measured_date(g["start_time"]),
            wafer_count=int(g["wafer_id"].nunique()),
        ))
    rows.sort(key=lambda r: (r.last_measured, r.lot_id), reverse=True)
    return rows


def get_wat_trend(nickname: str, product_id: str, months: int) -> WatTrendResponse:
    """Period-wide item statistics and per-lot series for one product."""
    df = _load_trend(product_id, months)
    if df.empty:
        df = pd.DataFrame(columns=WAT_TREND_COLUMNS)

    start, end = _period(months)
    items: list[WatTrendItemStats] = []

    for item_name, group in df.groupby("item_name", sort=True):
        name = str(item_name)
        # Resolved once over the whole period, then applied to every lot.
        spec_low = resolve_spec(group["spec_low"], name)
        spec_high = resolve_spec(group["spec_high"], name)
        core = _item_core(group, name, spec_low, spec_high)
        series = [WatLotPoint(**p)
                  for p in build_lot_series(group, name, spec_low, spec_high)]
        items.append(WatTrendItemStats(**core, lot_series=series))

    lots = _lot_infos(df) if not df.empty else []
    logger.info(
        "WAT trend: product=%s months=%d lots=%d items=%d",
        product_id, months, len(lots), len(items),
    )

    return WatTrendResponse(
        product_id=primary_product_id(nickname) or product_id,
        display_name=resolve_display_name(nickname),
        months=months,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        lots=lots,
        items=items,
    )
