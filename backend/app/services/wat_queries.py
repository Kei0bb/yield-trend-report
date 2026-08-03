"""PCM/WAT queries against WAT_MEASURE_DETAIL.

Single-table reads. This process has no rework operation, so neither
REWORK_NEW nor DEL_FLAG is filtered here — unlike the SEMI_CP_* pair, where
REWORK_NEW = 0 must be applied on BOTH tables (see CLAUDE.md).
"""

import logging
from datetime import date

import pandas as pd

from app.database import get_connection, release_connection

logger = logging.getLogger(__name__)

WAT_TABLE = "WAT_MEASURE_DETAIL"

# Column names in the SAME order as the SELECT below (pandas labels
# positionally — keep aligned).
WAT_LOT_COLUMNS = ["lot_id", "last_measured", "wafer_count"]

# start_time rides along on every detail row so the summary can report the
# lot's measured date without issuing a second GROUP BY query.
WAT_DETAIL_COLUMNS = [
    "wafer_id", "site_no", "item_name", "item_unit",
    "spec_low", "spec_high", "meas_data", "start_time",
]


def build_wat_lots_query(product_id: str, start: date, end: date) -> tuple[str, dict]:
    """Lots measured in [start, end). The upper bound is exclusive so the
    caller can pass tomorrow's date and still include everything measured
    today."""
    if not product_id:
        return "", {}
    sql = f"""
        SELECT LOT_ID                   AS lot_id,
               MAX(START_TIME)          AS last_measured,
               COUNT(DISTINCT WAFER_ID) AS wafer_count
        FROM {WAT_TABLE}
        WHERE PRODUCT_ID = :pid
          AND START_TIME >= :start
          AND START_TIME <  :end
        GROUP BY LOT_ID
        ORDER BY MAX(START_TIME)
    """
    return sql, {"pid": product_id, "start": start, "end": end}


def build_wat_detail_query(product_id: str, lot_id: str) -> tuple[str, dict]:
    """Every measurement of one lot. Aggregation happens in pandas."""
    if not product_id or not lot_id:
        return "", {}
    sql = f"""
        SELECT WAFER_ID   AS wafer_id,
               SITE_NO    AS site_no,
               ITEM_NAME  AS item_name,
               ITEM_UNIT  AS item_unit,
               SPEC_LOW   AS spec_low,
               SPEC_HIGH  AS spec_high,
               MEAS_DATA  AS meas_data,
               START_TIME AS start_time
        FROM {WAT_TABLE}
        WHERE PRODUCT_ID = :pid
          AND LOT_ID = :lot
        ORDER BY item_name, wafer_id, site_no
    """
    return sql, {"pid": product_id, "lot": lot_id}


def _run(sql: str, binds: dict, columns: list[str], what: str) -> pd.DataFrame:
    if not sql:
        return pd.DataFrame(columns=columns)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, binds)
        rows = cursor.fetchall()
        logger.info("WAT %s query returned %d rows", what, len(rows))
        return pd.DataFrame(rows, columns=columns)
    finally:
        release_connection(conn)


def query_wat_lots(product_id: str, start: date, end: date) -> pd.DataFrame:
    sql, binds = build_wat_lots_query(product_id, start, end)
    return _run(sql, binds, WAT_LOT_COLUMNS, "lots")


def query_wat_detail(product_id: str, lot_id: str) -> pd.DataFrame:
    sql, binds = build_wat_detail_query(product_id, lot_id)
    return _run(sql, binds, WAT_DETAIL_COLUMNS, "detail")
