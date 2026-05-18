from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import logging_config
from app.config import settings
from app.database import close_pool, init_pool
from app.routers import export, yield_data

logging_config.setup(settings.LOG_LEVEL)


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
