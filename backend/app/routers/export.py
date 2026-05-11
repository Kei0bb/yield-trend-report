from fastapi import APIRouter
from fastapi.responses import Response

from app.models.schemas import YieldRequest
from app.services.yield_service import get_yield_data
from app.services.pdf_service import generate_pdf

router = APIRouter()


@router.post("/export-pdf")
def export_pdf(req: YieldRequest) -> Response:
    # data[process][product] = ProcessData
    data: dict = {}
    for process in req.processes:
        data[process] = {}
        for product in req.products:
            data[process][product] = get_yield_data(
                product=product,
                start_month=req.start_month,
                end_month=req.end_month,
                process=process,
            )

    products_label = "_vs_".join(req.products)
    pdf_bytes = generate_pdf(
        products=req.products,
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
