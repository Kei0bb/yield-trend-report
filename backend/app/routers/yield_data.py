import logging

from fastapi import APIRouter

from app.models.schemas import YieldRequest, YieldResponse
from app.services.bin_mapping import load_bin_mapping
from app.services.product_config import (
    group_by_display_name,
    list_products as list_products_with_ids,
    load_product_config,
    resolve_bin_group,
    resolve_display_name,
    resolve_process_filter,
    resolve_product_ids,
    to_nicknames,
)
from app.services.yield_service import get_products, get_yield_data_merged
from app.utils.csv_loader import BIN_MAPPINGS_DIR

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/products")
def list_products() -> list[dict[str, str]]:
    """Product list for the UI: {product_id, display_name} per product.

    When product_config.csv is absent we fall back to DB/mock enumeration,
    using the enumerated id as both product_id and display_name.
    """
    configured = list_products_with_ids()
    if configured:
        return configured
    return [{"product_id": p, "display_name": p} for p in get_products()]


@router.get("/debug/config")
def debug_config(nickname: str | None = None) -> dict:
    """Inspect product config and bin mapping resolution.

    Usage: GET /api/debug/config?nickname=Phoenix
    """
    config = load_product_config()
    result: dict = {
        "bin_mappings_dir": str(BIN_MAPPINGS_DIR),
        "bin_mappings_files": sorted(
            p.name for p in BIN_MAPPINGS_DIR.glob("*.csv")
        ) if BIN_MAPPINGS_DIR.exists() else [],
        "product_config_loaded": config is not None,
        "product_config_nicknames": list(config.keys()) if config else [],
    }
    if nickname:
        bin_group = resolve_bin_group(nickname)
        result["resolved"] = {
            "nickname": nickname,
            "display_name": resolve_display_name(nickname),
            "bin_group": bin_group,
            "product_ids": resolve_product_ids(nickname),
            "process_filters": {
                proc: resolve_process_filter(nickname, proc) for proc in ("CP", "FT", "SLT")
            },
            "bin_mapping": {
                proc: dict(m) for proc, m in load_bin_mapping(bin_group).items()
            },
        }
    return result


@router.get("/debug/probe")
def debug_probe(nickname: str, process: str, start_month: str, end_month: str) -> dict:
    """Run a real DB query and return row counts for diagnosis.

    Usage: GET /api/debug/probe?nickname=Phoenix&process=FT&start_month=2025-01&end_month=2025-05
    Useful for diagnosing empty data issues (wrong PRODUCT_ID, SQL returning 0 rows, etc.)
    """
    import traceback

    from app.config import settings

    out: dict = {
        "input": {
            "nickname": nickname,
            "process": process,
            "start_month": start_month,
            "end_month": end_month,
        },
        "use_mock_data": settings.USE_MOCK_DATA,
        "resolved_product_ids": resolve_product_ids(nickname, process),
        "resolved_bin_group": resolve_bin_group(nickname),
    }
    try:
        proc_data = get_yield_data_merged(
            nicknames=[nickname],
            start_month=start_month,
            end_month=end_month,
            process=process,
        )
        out["lots_count"] = len(proc_data.lots)
        out["lots_sample"] = proc_data.lots[:5]
        out["yield_avg_sample"] = proc_data.yield_avg[:5]
        out["fail_bin_names"] = list(proc_data.fail_bins.keys())
    except Exception as e:
        out["error"] = str(e)
        out["traceback"] = traceback.format_exc()
    return out


@router.post("/yield-data")
def fetch_yield_data(req: YieldRequest) -> YieldResponse:
    """Fetch yield + bin data, merging nicknames that share the same display_name."""
    groups = group_by_display_name(to_nicknames(req.products))

    data: dict = {}
    for process in req.processes:
        data[process] = {}
        for display_name, nicknames in groups.items():
            data[process][display_name] = get_yield_data_merged(
                nicknames=nicknames,
                start_month=req.start_month,
                end_month=req.end_month,
                process=process,
            )
    return YieldResponse(data=data)
