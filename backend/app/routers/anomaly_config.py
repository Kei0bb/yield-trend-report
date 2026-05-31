from fastapi import APIRouter

from app.services.anomaly_service import load_anomaly_config

router = APIRouter()


@router.get("/anomaly/config")
def anomaly_config() -> dict:
    return load_anomaly_config()
