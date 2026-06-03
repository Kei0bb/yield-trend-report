import logging
import traceback

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.models.schemas import ProcessData, YieldRequest
from app.services.product_config import group_by_display_name, to_nicknames
from app.services.yield_service import get_yield_data_merged
from app.services.pdf_service import generate_pdf

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/export-pdf")
def export_pdf(req: YieldRequest) -> Response:
    """display_name でグループ化してマージ後のデータで PDF を生成。"""
    logger.info(
        "export-pdf request: products=%s processes=%s period=%s..%s",
        req.products, req.processes, req.start_month, req.end_month,
    )
    groups = group_by_display_name(to_nicknames(req.products))
    display_names = list(groups.keys())

    # data[process][display_name] = ProcessData
    # 個別の process / product のデータ取得失敗で PDF 全体を 500 にしない
    data: dict = {}
    for process in req.processes:
        data[process] = {}
        for display_name, nicknames in groups.items():
            try:
                data[process][display_name] = get_yield_data_merged(
                    nicknames=nicknames,
                    start_month=req.start_month,
                    end_month=req.end_month,
                    process=process,
                )
            except Exception:
                logger.error(
                    "yield data fetch failed: process=%s display=%s nicknames=%s\n%s",
                    process, display_name, nicknames, traceback.format_exc(),
                )
                # 空データで埋めて他の process / product は処理継続
                data[process][display_name] = ProcessData(lots=[], yield_avg=[], fail_bins={})

    products_label = "_vs_".join(display_names)
    try:
        pdf_bytes = generate_pdf(
            products=display_names,
            start_month=req.start_month,
            end_month=req.end_month,
            data=data,
        )
    except Exception as e:
        logger.error("generate_pdf failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    filename = f"YieldTrend_{products_label}_{req.start_month}_to_{req.end_month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
