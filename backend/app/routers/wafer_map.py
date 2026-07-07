from fastapi import APIRouter, Query

from app.models.schemas import (
    WaferMapLotInfo,
    WaferMapLotsResponse,
    WaferMapRequest,
    WaferMapResponse,
)
from app.services.lot_service import _load_dataframe
from app.services.map_service import get_wafer_maps
from app.services.product_config import nickname_for_product_id

router = APIRouter()


@router.get("/wafermap/lots", response_model=WaferMapLotsResponse)
def wafermap_lots(
    product_id: str = Query(...),
    process: str = Query(...),
    months: int = Query(6, ge=1, le=6),
    sub: str | None = Query(None),
) -> WaferMapLotsResponse:
    nickname = nickname_for_product_id(product_id) or product_id
    process_values = [sub] if sub else None
    df = _load_dataframe(nickname, process, months, process_values=process_values)

    lots: list[WaferMapLotInfo] = []
    if not df.empty:
        g = df.groupby("lot_id", sort=False).agg(
            lot_date=("lot_date", "max"),
            wafer_count=("wafer_id", "nunique"),
            test_program_rev=("test_program_rev", lambda s: ", ".join(
                sorted({str(v).strip() for v in s.dropna() if str(v).strip()})
            )),
        ).reset_index().sort_values("lot_date")
        lots = [
            WaferMapLotInfo(
                lot_id=str(r.lot_id), lot_date=str(r.lot_date),
                wafer_count=int(r.wafer_count), test_program_rev=str(r.test_program_rev),
            )
            for r in g.itertuples()
        ]
    return WaferMapLotsResponse(product_id=product_id, process=sub or process, lots=lots)


@router.post("/wafermap", response_model=WaferMapResponse)
def wafermap(req: WaferMapRequest) -> WaferMapResponse:
    nickname = nickname_for_product_id(req.product_id) or req.product_id
    lot_ids = list(dict.fromkeys(req.lot_ids))
    return get_wafer_maps(nickname, req.process, lot_ids, months=req.months, sub=req.sub)
