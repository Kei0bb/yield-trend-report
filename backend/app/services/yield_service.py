import logging

from app.config import settings
from app.models.schemas import ProcessData
from app.services.bin_mapping import apply_bin_groups
from app.services.mock_data import mock_products, mock_yield_dataframe
from app.services.product_config import (
    load_product_config,
    resolve_bin_group,
    resolve_display_name,
    resolve_process_filter,
    resolve_product_ids,
)
from app.services.yield_aggregator import (
    aggregate_lot_data,
    anchor_from_end_month,
    latest_iso_weeks,
)
from app.services.yield_queries import query_yield_data

FIXED_WEEK_COUNT = 12

logger = logging.getLogger(__name__)


def get_products() -> list[str]:
    """Return the product list for the UI.

    Priority:
    1. product_config.csv nicknames (mock and real DB)
    2. DB SEMI_CP_HEADER.PRODUCT_ID enumeration (real DB only)
    3. Hard-coded mock list (mock mode, no config)
    """
    config = load_product_config()
    if config is not None:
        return list(config.keys())

    if settings.USE_MOCK_DATA:
        return mock_products()

    from app.database import get_connection, release_connection
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT PRODUCT_ID FROM SEMI_CP_HEADER WHERE DEL_FLAG = 0 ORDER BY PRODUCT_ID"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        release_connection(conn)


def get_yield_data_merged(
    nicknames: list[str],
    start_month: str,
    end_month: str,
    process: str,
) -> ProcessData:
    """Fetch and aggregate yield data for one or more nicknames as a single series.

    All nicknames are resolved to PRODUCT_IDs, which are queried together in one
    SQL statement. Nicknames sharing the same display_name represent revision variants
    of the same product and should be merged this way.
    """
    target_lots = latest_iso_weeks(anchor_from_end_month(end_month), FIXED_WEEK_COUNT)

    if not nicknames:
        return ProcessData(
            lots=target_lots,
            yield_avg=[None] * len(target_lots),
            fail_bins={},
        )

    bin_group = resolve_bin_group(nicknames[0], process)

    if settings.USE_MOCK_DATA:
        display = resolve_display_name(nicknames[0])
        df = mock_yield_dataframe(display, start_month, end_month, process)
    else:
        all_pids: list[str] = []
        for nickname in nicknames:
            for pid in resolve_product_ids(nickname, process):
                if pid not in all_pids:
                    all_pids.append(pid)

        logger.info(
            "Fetching yield data: process=%s nicknames=%s resolved_ids=%s period=%s..%s",
            process, nicknames, all_pids, start_month, end_month,
        )

        if not all_pids:
            logger.warning(
                "No PRODUCT_IDs resolved for nicknames=%s process=%s — check product_config.csv",
                nicknames, process,
            )
            return ProcessData(
                lots=target_lots,
                yield_avg=[None] * len(target_lots),
                fail_bins={},
            )

        # Resolve sub-process filter (e.g. ft_processes="FT1" → only query PROCESS=FT1)
        process_values = resolve_process_filter(nicknames[0], process)

        df = query_yield_data(process, all_pids, start_month, end_month, process_values=process_values)

    if df.empty:
        return ProcessData(
            lots=target_lots,
            yield_avg=[None] * len(target_lots),
            fail_bins={},
        )

    df = apply_bin_groups(df, bin_group=bin_group, process=process)
    return aggregate_lot_data(df, target_lots=target_lots)
