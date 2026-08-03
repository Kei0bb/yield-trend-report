import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
from app.routers import anomaly_config, dashboard, explore, export, wafer_map, wat, yield_data


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
app.include_router(dashboard.router, prefix="/api")
app.include_router(explore.router, prefix="/api")
app.include_router(anomaly_config.router, prefix="/api")
app.include_router(wafer_map.router, prefix="/api")
app.include_router(wat.router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "mock": settings.USE_MOCK_DATA}


# Shared logo (used by PDF + frontend). Served as /logo.png from project-root/assets.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_LOGO = PROJECT_ROOT / "assets" / "logo.png"


@app.get("/logo.png")
def serve_logo():
    if SHARED_LOGO.is_file():
        return FileResponse(SHARED_LOGO, media_type="image/png")
    raise HTTPException(status_code=404, detail="logo not found")


# ---------------------------------------------------------------------------
# Frontend (SPA) — serve the built React app from frontend/dist
# Build with: cd frontend && npm run build
# ---------------------------------------------------------------------------
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Reject API/health requests that fell through (they should be handled above)
        if full_path.startswith(("api/", "health")):
            raise HTTPException(status_code=404, detail="Not found")
        # Serve real files (favicon.ico, vite.svg, etc.) if they exist at dist root
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        # Otherwise return index.html so React Router can handle the route
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    logging.getLogger("app").warning(
        "Frontend not built: %s not found. Run 'cd frontend && npm run build' to enable SPA serving.",
        FRONTEND_DIST,
    )
