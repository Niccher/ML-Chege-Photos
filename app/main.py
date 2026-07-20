from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import ensure_qdrant_collection, get_db
from sqlalchemy import text
from app.api.health import router as health_router

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("ml_chege_photos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown logic."""
    log.info("Starting ML Chege Photos service ...")

    # ── Qdrant collection ───────────────────────────────────────
    try:
        ensure_qdrant_collection()
        log.info("Qdrant collection '%s' ready", settings.qdrant_collection)
    except Exception as exc:
        log.warning("Qdrant not available on startup: %s", exc)

    # ── DB connection check ─────────────────────────────────────
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        log.info("Database connection OK")
        db.close()
    except Exception as exc:
        log.warning("Database not available on startup: %s", exc)

    # ── Models (loaded lazily in Phase 2) ───────────────────────
    app.state.models_loaded = False
    app.state.qdrant_ready = False
    app.state.db_ready = False

    yield

    log.info("Shutting down ML Chege Photos service ...")


app = FastAPI(
    title="ML Chege Photos",
    description="Face detection, embedding, clustering, and attribute classification service.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
