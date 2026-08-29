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
#
# CP and FT read the CP schema (SEMI_CP_*): one row per wafer, keyed by
# SUBSTRATE_ID + WAFER_ID and distinguished by the PROCESS column value
# (e.g. 'cFT1'). SLT has no data in that schema — it is read from the FT schema
# (SEMI_FT_*), keyed by the assembly lot (ASSY_LOT_ID + PRODUCT_ID).
#
# The per-process PROCESS filter is supplied by product_config (cp/ft/slt
# processes, or a Report unit's explicit `values`), so the PROCESS values a
# product uses under SEMI_FT_* are a config change, not a code change.
#
# Spec fields:
#   lot_key        column holding the real lot identifier; selected AS
#                  substrate_id so yield_aggregator can dedupe each physical
#                  wafer's gross_die exactly once.
#   wafer_expr     SELECT expression for wafer_id. FT/SLT is a package process
#                  where WAFER_ID may be NULL, and a NULL group key makes pandas
#                  drop the row entirely (shrinking the gross-die denominator),
#                  so it is coalesced to a placeholder there.
#   rework_tables  aliases the REWORK_NEW = 0 filter is applied to.
_CP_SPEC: dict = {
    "header": "SEMI_CP_HEADER",
    "bin_sum": "SEMI_CP_BIN_SUM",
    "join_keys": ["SUBSTRATE_ID", "WAFER_ID", "PROCESS"],
    "join_type": "JOIN",
    "date_col": "MODIFIED_DATE",
    "lot_key": "SUBSTRATE_ID",
    "wafer_expr": "h.WAFER_ID",
    "rework_tables": ("h", "b"),
}

_FT_SPEC: dict = {
    "header": "SEMI_FT_HEADER",
    "bin_sum": "SEMI_FT_BIN_SUM",
    "join_keys": ["ASSY_LOT_ID", "PRODUCT_ID", "PROCESS"],
    # LEFT OUTER so a lot with zero fail bins still contributes its yield to its
    # week bucket instead of vanishing from the trend. Those rows arrive with a
    # NULL bin code; apply_bin_groups tolerates that (see bin_mapping).
    "join_type": "LEFT OUTER JOIN",
    "date_col": "MODIFIED_DATE",
    "lot_key": "ASSY_LOT_ID",
    "wafer_expr": "COALESCE(TO_CHAR(h.WAFER_ID), '0')",
    # REWORK_NEW must be filtered on BOTH tables or the join fans out and
    # double-counts fail bins (see CLAUDE.md). If SEMI_FT_BIN_SUM turns out to
    # have no REWORK_NEW column (ORA-00904 on b.REWORK_NEW), drop "b" here.
    "rework_tables": ("h", "b"),
}

_PROCESS_SPEC: dict[str, dict] = {
    "CP": _CP_SPEC,
    "FT": _CP_SPEC,
    "SLT": _FT_SPEC,
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


def build_yield_query(
    process: str,
    product_ids: list[str],
    process_values: list[str] | None = None,
) -> tuple[str, dict]:
    """Build the week-rollup yield + bin SQL and its bind dict.

    Returns ("", {}) for a process with no table spec. Split out from
    ``query_yield_data`` so the generated SQL can be asserted on without a DB.
    """
    spec = _PROCESS_SPEC.get(process.upper())
    if spec is None:
        return "", {}

    pid_where, pid_binds = build_product_id_where(product_ids)
    join_clause = " AND ".join(f"h.{k} = b.{k}" for k in spec["join_keys"])

    # Build PROCESS filter: use IN clause when specific sub-processes are requested,
    # otherwise fall back to exact match on the selected process.
    pv_list = process_values or [process]
    pv_names = [f"pv{i}" for i in range(len(pv_list))]
    pv_binds = dict(zip(pv_names, pv_list))
    process_where = f"h.PROCESS IN ({', '.join(f':{n}' for n in pv_names)})"

    # bin_sum-side predicates. Under a LEFT OUTER JOIN they MUST live in the ON
    # clause: in the WHERE clause an unmatched row's NULL fails `= 0` and the
    # outer join silently collapses into an inner one, dropping exactly the
    # zero-fail lots the outer join exists to keep. For an inner join both
    # placements are equivalent, so CP/FT keep their existing WHERE form.
    b_preds: list[str] = []
    if "b" in spec["rework_tables"]:
        b_preds.append("b.REWORK_NEW = 0")
    b_preds += [
        "UPPER(TRIM(COALESCE(b.BIN_QUALITY, ''))) <> 'PASS'",
        "UPPER(TRIM(COALESCE(b.BIN_NAME,    ''))) NOT IN ('PASS', 'PASSED', 'OK', 'GOOD')",
    ]
    is_outer = "OUTER" in spec["join_type"].upper()
    join_extra = "".join(f"\n         AND {p}" for p in b_preds) if is_outer else ""
    where_bin = "" if is_outer else "".join(f"\n          AND {p}" for p in b_preds)
    where_rework = "\n          AND h.REWORK_NEW = 0" if "h" in spec["rework_tables"] else ""

    date_col = spec["date_col"]
    query = f"""
        SELECT
            TO_CHAR(h.{date_col}, 'IYYY"W"IW')            AS lot_id,
            {spec['wafer_expr']}                           AS wafer_id,
            CASE
                WHEN h.EFFECTIVE_NUM > 0
                THEN ROUND(h.PASS_CHIP / h.EFFECTIVE_NUM * 100, 3)
                ELSE 0
            END                                            AS yield_pct,
            h.EFFECTIVE_NUM                                AS gross_die,
            b.BIN_CODE                                     AS raw_bin_code,
            b.BIN_NAME                                     AS bin_name,
            b.BIN_COUNT                                    AS bin_fail_count,
            h.{spec['lot_key']}                            AS substrate_id
        FROM {spec['header']} h
        {spec['join_type']} {spec['bin_sum']} b
          ON {join_clause}{join_extra}
        WHERE {pid_where}
          AND {process_where}{where_rework}
          AND h.{date_col}  >= TO_DATE(:start_month || '-01', 'YYYY-MM-DD')
          AND h.{date_col}   < ADD_MONTHS(
                                  TO_DATE(:end_month || '-01', 'YYYY-MM-DD'), 1){where_bin}
        ORDER BY lot_id, wafer_id
    """
    return query, {**pid_binds, **pv_binds}


def query_yield_data(
    process: str,
    product_ids: list[str],
    start_month: str,
    end_month: str,
    process_values: list[str] | None = None,
) -> pd.DataFrame:
    """Execute the yield + bin query for a given process and return a DataFrame.

    Supports CP/FT (CP schema) and SLT (FT schema); returns an empty DataFrame
    for unrecognised processes.
    """
    query, binds = build_yield_query(process, product_ids, process_values)
    if not query:
        logger.debug("No DB spec for process %r — returning empty DataFrame", process)
        return pd.DataFrame(columns=COMMON_COLUMNS)

    params = {**binds, "start_month": start_month, "end_month": end_month}
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
