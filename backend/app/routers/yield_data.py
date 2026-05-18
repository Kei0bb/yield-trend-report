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
