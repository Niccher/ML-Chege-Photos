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
from app.api.search import router as search_router
from app.ml.loader import load_models, get_model_status
from app.ml.semantic_search import load_clip_model
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

    # ── Background initialization (prevents blocking Uvicorn port binding) ──
    async def init_services_background():
        # ── DB tables ───────────────────────────────────────────
        try:
            await asyncio.to_thread(init_db)
            log.info("Database tables ensured")
            app.state.db_ready = True
        except Exception as exc:
            log.warning("Could not init DB tables: %s", exc)

        # ── Qdrant collections ──────────────────────────────────
        try:
            await asyncio.to_thread(ensure_qdrant_collection)
            await asyncio.to_thread(ml_clustering.ensure_collections)
            log.info("Qdrant collections ready (main + centroids)")
            app.state.qdrant_ready = True
        except Exception as exc:
            log.warning("Qdrant not available on startup: %s", exc)

        # ── Models ──────────────────────────────────────────────
        try:
            await asyncio.to_thread(load_models)
            app.state.models_loaded = get_model_status()
            log.info("Face analysis models loaded: %s", app.state.models_loaded)
        except Exception as exc:
            log.warning("Models not loaded on startup: %s", exc)

    asyncio.create_task(init_services_background())


    # ── Stale cleanup task ───────────────────────────────────────
    async def stale_cleanup_loop():
        while True:
            await asyncio.sleep(60)
            try:
                cleanup_stale_scans(max_age_sec=settings.scan_stale_timeout_sec)
            except Exception as exc:
                log.warning("Stale cleanup error: %s", exc)

    task = asyncio.create_task(stale_cleanup_loop())

    from app.ml.queue import ml_job_queue
    await ml_job_queue.start()

    yield

    await ml_job_queue.stop()
    task.cancel()
    log.info("Shutting down ML Chege Photos service ...")


from fastapi import Depends, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header_value: str = Depends(api_key_header)):
    if api_key_header_value != settings.ml_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing X-API-KEY credential header"
        )

app = FastAPI(
    title="ML Chege Photos",
    description="Face detection, embedding, clustering, and attribute classification service.",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(health_router, dependencies=[Depends(get_api_key)])
app.include_router(faces_router, dependencies=[Depends(get_api_key)])
app.include_router(scan_router, dependencies=[Depends(get_api_key)])
app.include_router(clusters_router, dependencies=[Depends(get_api_key)])
app.include_router(search_router, dependencies=[Depends(get_api_key)])
