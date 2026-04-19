from fastapi import APIRouter

from app.models.schemas import YieldRequest, YieldResponse
from app.services.yield_service import get_products, get_yield_data

router = APIRouter()


@router.get("/products")
def list_products() -> list[str]:
    return get_products()


@router.post("/yield-data")
def fetch_yield_data(req: YieldRequest) -> YieldResponse:
    data = {}
    for process in req.processes:
        data[process] = get_yield_data(
            product=req.product,
            start_month=req.start_month,
            end_month=req.end_month,
            process=process,
        )
    return YieldResponse(data=data)
