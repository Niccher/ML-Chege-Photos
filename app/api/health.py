from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.database import get_db, get_qdrant
from app.ml.loader import get_model_status

router = APIRouter(prefix="/api/v1", tags=["health"])


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

    # ── CLIP Health ─────────────────────────────────────────────
    clip_ok = False
    try:
        from app.ml import semantic_search
        clip_ok = (semantic_search._clip_model is not None)
    except Exception:
        clip_ok = False

    # ── YOLOv8 Health ───────────────────────────────────────────
    yolo_ok = False
    try:
        from app.ml import object_detection
        yolo_ok = (object_detection._net is not None)
    except Exception:
        yolo_ok = False

    overall = db_ok and qdrant_ok

    return {
        "status": "healthy" if overall else "degraded",
        "db_connected": db_ok,
        "qdrant_connected": qdrant_ok,
        "models_loaded": models_loaded,
        "clip_loaded": clip_ok,
        "yolo_loaded": yolo_ok,
    }


@router.post("/models/reload")
def reload_models_endpoint(
    model_pack: str | None = None,
    face_det_thresh: float | None = None,
    clip_model_name: str | None = None,
    object_det_threshold: float | None = None,
    include_sensitive: str | bool | None = None,
):
    """Reload models and configurations dynamically."""
    from app.config import settings
    from app.ml.loader import load_models
    from app.ml.semantic_search import load_clip_model

    should_reload_face = False
    should_reload_clip = False

    if model_pack is not None:
        if model_pack not in ["buffalo_l", "buffalo_m", "buffalo_s", "buffalo_sc"]:
            return {"status": "error", "message": "Invalid model pack name."}
        if settings.face_model_pack != model_pack:
            settings.face_model_pack = model_pack
            should_reload_face = True

    if face_det_thresh is not None:
        if settings.face_det_thresh != face_det_thresh:
            settings.face_det_thresh = face_det_thresh
            should_reload_face = True

    if clip_model_name is not None:
        if settings.clip_model_name != clip_model_name:
            settings.clip_model_name = clip_model_name
            should_reload_clip = True

    if object_det_threshold is not None:
        settings.object_det_threshold = object_det_threshold

    if include_sensitive is not None:
        if isinstance(include_sensitive, str):
            settings.include_sensitive_attributes = include_sensitive.lower() in ("true", "1", "yes")
        else:
            settings.include_sensitive_attributes = bool(include_sensitive)

    if should_reload_face:
        load_models()

    if should_reload_clip:
        try:
            load_clip_model(force=True)
        except Exception as exc:
            return {"status": "error", "message": f"Failed to reload CLIP: {exc}"}

    return {
        "status": "success",
        "face_model_pack": settings.face_model_pack,
        "face_det_thresh": settings.face_det_thresh,
        "clip_model_name": settings.clip_model_name,
        "object_det_threshold": settings.object_det_threshold,
        "include_sensitive_attributes": settings.include_sensitive_attributes,
        "models_loaded": get_model_status()
    }
