"""
TipStar FastAPI backend entry point.
Run with: uvicorn backend.api.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.middleware import register_middleware
from backend.api.routes import posts, news, players, teams, matches, drama, analytics
from backend.database.db import init_db
from backend.embeddings.miniLM import _get_model

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise DB tables and pre-load MiniLM model
    logger.info("Starting TipStar backend...")
    await init_db()
    _get_model()  # Load MiniLM once at startup, not per request
    logger.info("TipStar backend ready")
    yield
    logger.info("TipStar backend shutting down")


app = FastAPI(
    title="TipStar Football Intelligence API",
    description="Backend for the TipStar football content platform",
    version="2.0.0",
    lifespan=lifespan,
)

register_middleware(app)

# Same-origin API path used by the React frontend.
app.include_router(posts.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(players.router, prefix="/api")
app.include_router(teams.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(drama.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")

# Legacy direct API paths kept for scripts and older local usage.
app.include_router(posts.router)
app.include_router(news.router)
app.include_router(players.router)
app.include_router(teams.router)
app.include_router(matches.router)
app.include_router(drama.router)
app.include_router(analytics.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "TipStar Football Intelligence API"}


@app.get("/api/health")
async def api_health():
    return await health()


if FRONTEND_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_ASSETS)), name="assets")


@app.get("/", include_in_schema=False)
async def serve_frontend_index():
    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend build not found. Run `npm run build` in frontend first.",
        )
    return FileResponse(index)


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    target = FRONTEND_DIST / full_path
    if target.is_file():
        return FileResponse(target)

    return await serve_frontend_index()
