import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# uvicorn は自前の logger しか設定しないため、app 配下の
# logger 出力が一切表示されない。root logger に StreamHandler を付け、
# app.* の INFO 以上を必ず stderr に出すよう設定する。
_root = logging.getLogger()
if not any(isinstance(h, logging.StreamHandler) for h in _root.handlers):
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter(
        "%(levelname)-8s %(name)s: %(message)s"
    ))
    _root.addHandler(_handler)
_root.setLevel(logging.INFO)
logging.getLogger("app").setLevel(logging.INFO)

from app.config import settings
from app.database import close_pool, init_pool
from app.routers import export, yield_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: DB 接続プールを初期化（USE_MOCK_DATA=false のときのみ実行）
    init_pool()
    yield
    # shutdown: DB 接続プールを解放
    close_pool()


app = FastAPI(
    title="Yield Trend Report Generator",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(yield_data.router, prefix="/api")
app.include_router(export.router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "mock": settings.USE_MOCK_DATA}
