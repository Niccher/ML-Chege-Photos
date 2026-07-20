from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import ensure_qdrant_collection, init_db, get_db
from sqlalchemy import text
import asyncio

from app.api.health import router as health_router
from app.api.faces import router as faces_router
from app.api.scan import router as scan_router
from app.api.clusters import router as clusters_router
from app.ml.loader import load_models, get_model_status
from app.ml import clustering as ml_clustering
from app.services.scan import cleanup_stale_scans
import app.models.db  # noqa: F401 — register models on Base before init_db()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("ml_chege_photos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting ML Chege Photos service ...")

    app.state.models_loaded = False
    app.state.qdrant_ready = False
    app.state.db_ready = False

    # ── DB tables ───────────────────────────────────────────────
    try:
        init_db()
        log.info("Database tables ensured")
        app.state.db_ready = True
    except Exception as exc:
        log.warning("Could not init DB tables: %s", exc)

    # ── Qdrant collections ──────────────────────────────────────
    try:
        ensure_qdrant_collection()
        ml_clustering.ensure_collections()
        log.info("Qdrant collections ready (main + centroids)")
        app.state.qdrant_ready = True
    except Exception as exc:
        log.warning("Qdrant not available on startup: %s", exc)

    # ── Models ──────────────────────────────────────────────────
    try:
        load_models()
        app.state.models_loaded = get_model_status()
    except Exception as exc:
        log.warning("Models not loaded on startup: %s", exc)

    # ── Stale cleanup task ───────────────────────────────────────
    async def stale_cleanup_loop():
        while True:
            await asyncio.sleep(60)
            try:
                cleanup_stale_scans(max_age_sec=settings.scan_stale_timeout_sec)
            except Exception as exc:
                log.warning("Stale cleanup error: %s", exc)

    task = asyncio.create_task(stale_cleanup_loop())

    yield

    task.cancel()
    log.info("Shutting down ML Chege Photos service ...")


app = FastAPI(
    title="ML Chege Photos",
    description="Face detection, embedding, clustering, and attribute classification service.",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(faces_router)
app.include_router(scan_router)
app.include_router(clusters_router)
