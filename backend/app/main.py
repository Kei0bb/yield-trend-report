import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# uvicorn は自前の logger しか設定しないため、app 配下の
# logger 出力が表示されない場合がある。root logger に StreamHandler を追加し
# app.* の INFO 以上を必ず stderr に出すよう設定する。
_root = logging.getLogger()
if not any(isinstance(h, logging.StreamHandler) for h in _root.handlers):
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s [%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _root.addHandler(_handler)
_root.setLevel(logging.INFO)
logging.getLogger("app").setLevel(logging.INFO)

from app.config import settings
from app.database import close_pool, init_pool
from app.routers import export, yield_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_db_config()
    init_pool()
    yield
    close_pool()


app = FastAPI(
    title="Yield Trend Report Generator",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(yield_data.router, prefix="/api")
app.include_router(export.router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "mock": settings.USE_MOCK_DATA}
