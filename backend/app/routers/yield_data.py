from fastapi import APIRouter

from app.models.schemas import YieldRequest, YieldResponse
from app.services.yield_service import (
    get_products,
    get_yield_data_merged,
    group_by_display_name,
)

router = APIRouter()


@router.get("/products")
def list_products() -> list[str]:
    return get_products()


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
