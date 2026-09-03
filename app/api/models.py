from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.ml.manifest import get_model_inventory, format_bytes

log = logging.getLogger("ml_chege_photos.models_api")
router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("/inventory")
def get_inventory():
    """Returns real-time on-disk presence, size, location, and memory state of all models."""
    inv = get_model_inventory()
    total_bytes = sum(item["size_bytes"] for item in inv)

    return {
        "status": "success",
        "inventory": inv,
        "total_disk_usage": format_bytes(total_bytes),
        "total_disk_bytes": total_bytes,
        "active_face_pack": settings.face_model_pack,
        "active_clip_model": settings.clip_model_name,
    }


@router.post("/download")
def download_models(
    group: str = Query("all", description="Model group to download: insightface, yolov8n, clip, or all")
):
    """
    Forces download of missing model files and loads them into memory (RAM / GPU).
    Can be invoked on-demand from the WebApp admin interface.
    """
    from app.ml.loader import load_models
    from app.ml.semantic_search import load_clip_model
    from app.ml.object_detection import download_yolov8_model, load_yolo_model

    results = []

    # 1. InsightFace Pack
    if group in ("all", "insightface"):
        try:
            log.info("Downloading/verifying InsightFace model pack: %s", settings.face_model_pack)
            load_models()
            results.append({"group": "insightface", "status": "success", "message": "InsightFace models ready"})
        except Exception as exc:
            log.error("Failed downloading InsightFace: %s", exc)
            results.append({"group": "insightface", "status": "error", "message": str(exc)})

    # 2. YOLOv8 Objects
    if group in ("all", "yolov8n"):
        try:
            log.info("Downloading/verifying YOLOv8 model")
            download_yolov8_model()
            load_yolo_model()
            results.append({"group": "yolov8n", "status": "success", "message": "YOLOv8 model ready"})
        except Exception as exc:
            log.error("Failed downloading YOLOv8: %s", exc)
            results.append({"group": "yolov8n", "status": "error", "message": str(exc)})

    # 3. CLIP Transformer
    if group in ("all", "clip"):
        try:
            log.info("Downloading/verifying CLIP model: %s", settings.clip_model_name)
            load_clip_model(force=True)
            results.append({"group": "clip", "status": "success", "message": "CLIP model ready"})
        except Exception as exc:
            log.error("Failed downloading CLIP: %s", exc)
            results.append({"group": "clip", "status": "error", "message": str(exc)})

    updated_inv = get_model_inventory()
    total_bytes = sum(item["size_bytes"] for item in updated_inv)

    has_errors = any(r["status"] == "error" for r in results)

    return {
        "status": "partial_error" if has_errors else "success",
        "results": results,
        "inventory": updated_inv,
        "total_disk_usage": format_bytes(total_bytes),
        "total_disk_bytes": total_bytes,
    }
