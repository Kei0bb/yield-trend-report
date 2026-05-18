from fastapi import APIRouter

from app.models.schemas import YieldRequest, YieldResponse
from app.services.yield_service import (
    _BIN_MAPPINGS_DIR,
    _load_bin_mapping,
    _load_product_config,
    _resolve_bin_group,
    _resolve_product_ids,
    get_products,
    get_yield_data_merged,
    group_by_display_name,
    resolve_display_name,
)

router = APIRouter()


@router.get("/products")
def list_products() -> list[str]:
    return get_products()


@router.get("/debug/config")
def debug_config(nickname: str | None = None) -> dict:
    """
    設定ファイルの読み込み状況を確認するためのデバッグエンドポイント。
    `?nickname=Phoenix` のように指定すると、その nickname の
    bin_group / PRODUCT_ID / bin_mapping 読み込み結果まで全て表示。
    """
    config = _load_product_config()
    result: dict = {
        "bin_mappings_dir": str(_BIN_MAPPINGS_DIR),
        "bin_mappings_files": sorted(
            p.name for p in _BIN_MAPPINGS_DIR.glob("*.csv")
        ) if _BIN_MAPPINGS_DIR.exists() else [],
        "product_config_loaded": config is not None,
        "product_config_nicknames": list(config.keys()) if config else [],
    }
    if nickname:
        bin_group = _resolve_bin_group(nickname)
        result["resolved"] = {
            "nickname": nickname,
            "display_name": resolve_display_name(nickname),
            "bin_group": bin_group,
            "cp_product_ids": _resolve_product_ids(nickname, "CP"),
            "ft_product_ids": _resolve_product_ids(nickname, "FT"),
            "bin_mapping": {
                proc: dict(m) for proc, m in _load_bin_mapping(bin_group).items()
            },
        }
    return result


@router.get("/debug/probe")
def debug_probe(nickname: str, process: str, start_month: str, end_month: str) -> dict:
    """
    実 DB クエリを叩いて何件返るかをそのまま返す診断エンドポイント。
    例: /api/debug/probe?nickname=Phoenix&process=FT&start_month=2025-01&end_month=2025-05
    PDF が空になる原因 (PRODUCT_ID 解決失敗 / SQL 0 行 / 例外) を直接確認。
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
        "resolved_product_ids": _resolve_product_ids(nickname, process),
        "resolved_bin_group": _resolve_bin_group(nickname),
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
    """
    リクエストの nicknames を display_name でグループ化し、同じ display_name に
    属する nicknames は 1 つの ProcessData にマージして返す。

    レスポンス構造:
        data[process][display_name] = ProcessData
    """
    groups = group_by_display_name(req.products)

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
