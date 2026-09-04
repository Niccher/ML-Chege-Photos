from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import text

from app.database import get_db, get_qdrant
from app.ml.loader import get_model_status

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def health_check(x_webapp_url: str | None = Header(None, alias="X-Webapp-Url")):
    """Liveness / readiness check."""
    if x_webapp_url:
        from app.config import settings
        settings.set_dynamic_webapp_url(x_webapp_url)

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

    # ── Job Queue ────────────────────────────────────────────────
    queue_size = 0
    is_processing = False
    workers_count = 1
    total_processed = 0
    total_failed = 0
    last_error = None
    last_error_time = None
    try:
        from app.ml.queue import ml_job_queue
        queue_size = ml_job_queue.queue.qsize()
        is_processing = ml_job_queue.is_running and (queue_size > 0 or ml_job_queue._current_task is not None)
        workers_count = len(ml_job_queue.worker_tasks) or ml_job_queue.num_workers
        total_processed = ml_job_queue.total_processed
        total_failed = ml_job_queue.total_failed
        last_error = ml_job_queue.last_error
        last_error_time = ml_job_queue.last_error_time
    except Exception:
        pass

    return {
        "status": "healthy" if overall else "degraded",
        "db_connected": db_ok,
        "qdrant_connected": qdrant_ok,
        "models_loaded": models_loaded,
        "clip_loaded": clip_ok,
        "yolo_loaded": yolo_ok,
        "queue_size": queue_size,
        "is_processing": is_processing,
        "concurrent_workers": workers_count,
        "total_processed": total_processed,
        "total_failed": total_failed,
        "last_error": last_error,
        "last_error_time": last_error_time,
    }


@router.get("/health/diagnostics")
def health_diagnostics(x_webapp_url: str | None = Header(None, alias="X-Webapp-Url")):
    """Deep diagnostics endpoint: inspects failure reasons, photo reachability, and pipeline health."""
    from app.config import settings
    if x_webapp_url:
        settings.set_dynamic_webapp_url(x_webapp_url)
    from app.models.db import PhotoScan

    recent_errors = []
    try:
        db = next(get_db())
        failed_scans = db.query(PhotoScan).filter(
            PhotoScan.status == "failed"
        ).order_by(PhotoScan.completed_at.desc()).limit(15).all()

        for s in failed_scans:
            recent_errors.append({
                "photo_id": s.photo_id,
                "error": s.error_message,
                "failed_at": str(s.completed_at) if s.completed_at else None,
            })
        db.close()
    except Exception as exc:
        recent_errors.append({"error": f"Failed to query failure logs: {exc}"})

    # Test photo reachability probe
    photo_access_test = {
        "configured_webapp_url": settings.effective_webapp_url,
        "accessible": False,
        "status_code": None,
        "message": None,
    }
    if settings.effective_webapp_url:
        import urllib.request
        try:
            req = urllib.request.Request(
                settings.effective_webapp_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ChegePhotosML/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                photo_access_test["accessible"] = (resp.status == 200)
                photo_access_test["status_code"] = resp.status
                photo_access_test["message"] = "Connected successfully to WebApp"
        except Exception as probe_err:
            photo_access_test["message"] = str(probe_err)

    return {
        "status": "success",
        "webapp_url": settings.effective_webapp_url,
        "photo_access_test": photo_access_test,
        "recent_errors": recent_errors,
        "queue": {
            "num_workers": settings.ml_concurrent_workers,
        },
    }


@router.post("/models/reload")
def reload_models_endpoint(
    model_pack: str | None = None,
    face_det_thresh: float | None = None,
    clip_model_name: str | None = None,
    object_det_threshold: float | None = None,
    include_sensitive: str | bool | None = None,
    x_api_key: str | None = Header(None, alias="X-API-KEY"),
):
    """Reload models and configurations dynamically."""
    from app.config import settings
    if x_api_key != settings.ml_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing X-API-KEY credential header",
        )
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
