import logging

import pandas as pd

from app.database import get_connection, release_connection

logger = logging.getLogger(__name__)

COMMON_COLUMNS = [
    "lot_id",
    "wafer_id",
    "yield_pct",
    "gross_die",
    "raw_bin_code",
    "bin_name",
    "bin_fail_count",
    "substrate_id",
]

# Per-process table and JOIN key definitions.
# FT/SLT data was migrated into the CP schema (SEMI_CP_*) and is now keyed by
# the same SUBSTRATE_ID/PRODUCT_ID as CP, distinguished only by the PROCESS
# column value (e.g. 'cFT1'). All processes therefore share one table spec; the
# per-process PROCESS filter is supplied by product_config (cp/ft/slt_processes).
_CP_SPEC: dict = {
    "header": "SEMI_CP_HEADER",
    "bin_sum": "SEMI_CP_BIN_SUM",
    "join_keys": ["SUBSTRATE_ID", "WAFER_ID", "PROCESS"],
    "join_type": "JOIN",
    "date_col": "MODIFIED_DATE",
}

_PROCESS_SPEC: dict[str, dict] = {
    "CP": _CP_SPEC,
    "FT": _CP_SPEC,
    "SLT": _CP_SPEC,
}


def build_product_id_where(product_ids: list[str]) -> tuple[str, dict[str, str]]:
    """Build a WHERE clause fragment and bind-variable dict for a list of PRODUCT_IDs.

    IDs containing '%' use LIKE (Oracle wildcard); others use IN (...).
    Mixed lists are joined with OR.

    Examples:
        ["SCT101A", "SCT101B"]      → "h.PRODUCT_ID IN (:pid0, :pid1)"
        ["SC0G29AP3%"]              → "h.PRODUCT_ID LIKE :like0"
        ["SCT101A", "SC0G29AP3%"]  → "(h.PRODUCT_ID IN (:pid0) OR h.PRODUCT_ID LIKE :like0)"
    """
    exacts = [pid for pid in product_ids if "%" not in pid]
    likes = [pid for pid in product_ids if "%" in pid]
    binds: dict[str, str] = {}
    conditions: list[str] = []

    if exacts:
        names = [f"pid{i}" for i in range(len(exacts))]
        conditions.append(f"h.PRODUCT_ID IN ({', '.join(f':{n}' for n in names)})")
        for n, pid in zip(names, exacts):
            binds[n] = pid

    for i, pat in enumerate(likes):
        bind_name = f"like{i}"
        conditions.append(f"h.PRODUCT_ID LIKE :{bind_name}")
        binds[bind_name] = pat

    if not conditions:
        return "1=0", {}
    if len(conditions) == 1:
        return conditions[0], binds
    return "(" + " OR ".join(conditions) + ")", binds


def query_yield_data(
    process: str,
    product_ids: list[str],
    start_month: str,
    end_month: str,
    process_values: list[str] | None = None,
) -> pd.DataFrame:
    """Execute the yield + bin query for a given process and return a DataFrame.

    Supports CP and FT; returns an empty DataFrame for unrecognised processes.
    """
    spec = _PROCESS_SPEC.get(process.upper())
    if spec is None:
        logger.debug("No DB spec for process %r — returning empty DataFrame", process)
        return pd.DataFrame(columns=COMMON_COLUMNS)

    pid_where, pid_binds = build_product_id_where(product_ids)
    join_clause = " AND ".join(f"h.{k} = b.{k}" for k in spec["join_keys"])

    # Build PROCESS filter: use IN clause when specific sub-processes are requested,
    # otherwise fall back to exact match on the selected process.
    pv_list = process_values or [process]
    pv_names = [f"pv{i}" for i in range(len(pv_list))]
    pv_binds = dict(zip(pv_names, pv_list))
    process_where = f"h.PROCESS IN ({', '.join(f':{n}' for n in pv_names)})"

    date_col = spec["date_col"]
    query = f"""
        SELECT
            TO_CHAR(h.{date_col}, 'IYYY"W"IW')            AS lot_id,
            h.WAFER_ID                                     AS wafer_id,
            CASE
                WHEN h.EFFECTIVE_NUM > 0
                THEN ROUND(h.PASS_CHIP / h.EFFECTIVE_NUM * 100, 3)
                ELSE 0
            END                                            AS yield_pct,
            h.EFFECTIVE_NUM                                AS gross_die,
            b.BIN_CODE                                     AS raw_bin_code,
            b.BIN_NAME                                     AS bin_name,
            b.BIN_COUNT                                    AS bin_fail_count,
            h.SUBSTRATE_ID                                 AS substrate_id
        FROM {spec['header']} h
        {spec['join_type']} {spec['bin_sum']} b
          ON {join_clause}
        WHERE {pid_where}
          AND {process_where}
          AND h.REWORK_NEW   = 0
          AND b.REWORK_NEW   = 0
          AND h.{date_col}  >= TO_DATE(:start_month || '-01', 'YYYY-MM-DD')
          AND h.{date_col}   < ADD_MONTHS(
                                  TO_DATE(:end_month || '-01', 'YYYY-MM-DD'), 1)
          AND UPPER(TRIM(COALESCE(b.BIN_QUALITY, ''))) <> 'PASS'
          AND UPPER(TRIM(COALESCE(b.BIN_NAME,    ''))) NOT IN ('PASS', 'PASSED', 'OK', 'GOOD')
        ORDER BY lot_id, h.WAFER_ID
    """
    params = {**pid_binds, **pv_binds, "start_month": start_month, "end_month": end_month}
    return _execute_query(query, params, process, product_ids)


def _execute_query(query: str, params: dict, process: str, product_ids: list[str]) -> pd.DataFrame:
    pid_binds = {k: v for k, v in params.items() if k.startswith("pid") or k.startswith("like")}
    logger.info(
        "DB query: process=%s period=%s..%s product_ids=%s",
        process, params.get("start_month"), params.get("end_month"), pid_binds,
    )
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
        except Exception:
            logger.exception(
                "DB query failed: process=%s product_ids=%s\n--- SQL ---\n%s",
                process, product_ids, query,
            )
            raise
        rows = cursor.fetchall()
        logger.info("DB query returned %d rows", len(rows))
        return pd.DataFrame(rows, columns=COMMON_COLUMNS)
    finally:
        release_connection(conn)
