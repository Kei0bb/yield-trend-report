import logging

import pandas as pd

from app.database import get_connection, release_connection
from app.services.yield_queries import build_product_id_where, _PROCESS_SPEC

logger = logging.getLogger(__name__)

TEST_PROGRAM_COLUMN = "REV01"  # SEMI_CP_HEADER column holding the test program revision (e.g. 'REV01')

# Column names for query_lot_data results, in the SAME order as the SELECT in
# build_lot_query (lot_date is the 2nd column, not appended last). Keeping this
# aligned with the SELECT is essential: pandas labels positionally, so a wrong
# order silently mislabels every column after lot_date.
LOT_COLUMNS = [
    "lot_id",
    "lot_date",
    "wafer_id",
    "yield_pct",
    "gross_die",
    "raw_bin_code",
    "bin_name",
    "bin_fail_count",
    "test_program_rev",
]

# Real per-lot identifier column by process (vs. yield_queries' ISO-week rollup).
# FT/SLT now live in the CP schema and share CP's SUBSTRATE_ID lot identifier.
_LOT_COLUMN: dict[str, str] = {
    "CP": "SUBSTRATE_ID",
    "FT": "SUBSTRATE_ID",
    "SLT": "SUBSTRATE_ID",
}


def lot_column_for(process: str) -> str | None:
    return _LOT_COLUMN.get(process.upper())


def build_lot_query(
    process: str,
    product_ids: list[str],
    start_month: str,
    end_month: str,
    process_values: list[str] | None,
) -> tuple[str, dict]:
    """Build the lot-granular SQL and bind dict. Returns ("", {}) for unknown process."""
    spec = _PROCESS_SPEC.get(process.upper())
    lot_col = lot_column_for(process)
    if spec is None or lot_col is None:
        return "", {}

    pid_where, pid_binds = build_product_id_where(product_ids)
    join_clause = " AND ".join(f"h.{k} = b.{k}" for k in spec["join_keys"])

    pv_list = process_values or [process]
    pv_names = [f"pv{i}" for i in range(len(pv_list))]
    pv_binds = dict(zip(pv_names, pv_list))
    process_where = f"h.PROCESS IN ({', '.join(f':{n}' for n in pv_names)})"

    date_col = spec["date_col"]
    sql = f"""
        SELECT
            h.{lot_col}                                    AS lot_id,
            TO_CHAR(MAX(h.{date_col}) OVER (PARTITION BY h.{lot_col}, h.{TEST_PROGRAM_COLUMN}),
                    'YYYY-MM-DD')                          AS lot_date,
            h.WAFER_ID                                     AS wafer_id,
            CASE WHEN h.EFFECTIVE_NUM > 0
                 THEN ROUND(h.PASS_CHIP / h.EFFECTIVE_NUM * 100, 3)
                 ELSE 0 END                                AS yield_pct,
            h.EFFECTIVE_NUM                                AS gross_die,
            b.BIN_CODE                                     AS raw_bin_code,
            b.BIN_NAME                                     AS bin_name,
            b.BIN_COUNT                                    AS bin_fail_count,
            h.{TEST_PROGRAM_COLUMN}                          AS test_program_rev
        FROM {spec['header']} h
        {spec['join_type']} {spec['bin_sum']} b
          ON {join_clause}
        WHERE {pid_where}
          AND {process_where}
          AND h.REWORK_NEW = 0
          AND b.REWORK_NEW = 0
          AND h.{date_col} >= TO_DATE(:start_month || '-01', 'YYYY-MM-DD')
          AND h.{date_col}  < ADD_MONTHS(TO_DATE(:end_month || '-01', 'YYYY-MM-DD'), 1)
          AND UPPER(TRIM(COALESCE(b.BIN_QUALITY, ''))) <> 'PASS'
          AND UPPER(TRIM(COALESCE(b.BIN_NAME,    ''))) NOT IN ('PASS', 'PASSED', 'OK', 'GOOD')
        ORDER BY lot_date, lot_id, h.WAFER_ID
    """
    binds = {**pid_binds, **pv_binds, "start_month": start_month, "end_month": end_month}
    return sql, binds


def query_lot_data(
    process: str,
    product_ids: list[str],
    start_month: str,
    end_month: str,
    process_values: list[str] | None = None,
) -> pd.DataFrame:
    """Execute the lot-granular query and return a DataFrame (empty for unknown process)."""
    sql, binds = build_lot_query(process, product_ids, start_month, end_month, process_values)
    if not sql:
        return pd.DataFrame(columns=LOT_COLUMNS)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, binds)
        rows = cursor.fetchall()
        logger.info("Lot query returned %d rows (process=%s)", len(rows), process)
        return pd.DataFrame(rows, columns=LOT_COLUMNS)
    finally:
        release_connection(conn)
