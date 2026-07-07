import logging

import pandas as pd

from app.database import get_connection, release_connection

logger = logging.getLogger(__name__)

DIE_TABLE = "SEMI_CP_BIN_DETAL"

# Column names for query_die_map results, in the SAME order as the SELECT
# below (pandas labels positionally — keep aligned).
DIE_COLUMNS = ["lot_id", "wafer_id", "x", "y", "bin_code", "bin_quality"]


def build_die_map_query(
    lot_ids: list[str],
    process_values: list[str],
) -> tuple[str, dict]:
    """Single-table die query: product/date filtering already happened at lot
    selection, so we only need lot ids + PROCESS values. No header join, hence
    REWORK_NEW on this table alone is correct."""
    if not lot_ids or not process_values:
        return "", {}

    lot_names = [f"lot{i}" for i in range(len(lot_ids))]
    pv_names = [f"pv{i}" for i in range(len(process_values))]
    sql = f"""
        SELECT
            SUBSTRATE_ID   AS lot_id,
            WAFER_ID       AS wafer_id,
            X              AS x,
            Y              AS y,
            BIN_CODE       AS bin_code,
            BIN_QUALITY    AS bin_quality
        FROM {DIE_TABLE}
        WHERE SUBSTRATE_ID IN ({', '.join(f':{n}' for n in lot_names)})
          AND PROCESS IN ({', '.join(f':{n}' for n in pv_names)})
          AND REWORK_NEW = 0
        ORDER BY lot_id, wafer_id, y, x
    """
    binds = {**dict(zip(lot_names, lot_ids)), **dict(zip(pv_names, process_values))}
    return sql, binds


def query_die_map(lot_ids: list[str], process_values: list[str]) -> pd.DataFrame:
    sql, binds = build_die_map_query(lot_ids, process_values)
    if not sql:
        return pd.DataFrame(columns=DIE_COLUMNS)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, binds)
        rows = cursor.fetchall()
        logger.info("Die map query returned %d rows (%d lots)", len(rows), len(lot_ids))
        return pd.DataFrame(rows, columns=DIE_COLUMNS)
    finally:
        release_connection(conn)
