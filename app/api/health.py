from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.database import get_db, get_qdrant
from app.ml.loader import get_model_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Liveness / readiness check."""

    # ── Database ────────────────────────────────────────────────
    db_ok = False
    try:
        db = next(get_db())
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False

    # ── Qdrant ──────────────────────────────────────────────────
    qdrant_ok = False
    try:
        qdrant = get_qdrant()
        qdrant.get_collections()
        qdrant_ok = True
    except Exception:
        qdrant_ok = False

    # ── Models ──────────────────────────────────────────────────
    models_loaded = get_model_status()

    overall = db_ok and qdrant_ok

    return {
        "status": "healthy" if overall else "degraded",
        "db_connected": db_ok,
        "qdrant_connected": qdrant_ok,
        "models_loaded": models_loaded,
    }
