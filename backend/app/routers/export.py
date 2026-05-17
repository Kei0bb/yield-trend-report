from fastapi import APIRouter
from fastapi.responses import Response

from app.models.schemas import YieldRequest
from app.services.yield_service import (
    get_yield_data_merged,
    group_by_display_name,
)
from app.services.pdf_service import generate_pdf

router = APIRouter()


@router.post("/export-pdf")
def export_pdf(req: YieldRequest) -> Response:
    """display_name でグループ化してマージ後のデータで PDF を生成。"""
    groups = group_by_display_name(req.products)
    display_names = list(groups.keys())

    # data[process][display_name] = ProcessData
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

    products_label = "_vs_".join(display_names)
    pdf_bytes = generate_pdf(
        products=display_names,
        start_month=req.start_month,
        end_month=req.end_month,
        data=data,
    )

    filename = f"YieldTrend_{products_label}_{req.start_month}_to_{req.end_month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
