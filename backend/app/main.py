from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
