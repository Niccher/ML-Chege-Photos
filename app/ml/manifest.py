from __future__ import annotations

import os
import logging
from pathlib import Path
from datetime import datetime

from app.config import settings

log = logging.getLogger("ml_chege_photos.manifest")

INSIGHTFACE_ROOT = Path("/app/models/insightface_models/models")
YOLO_MODEL_PATH = Path("/app/models/yolov8n.onnx")
YOLO_DOWNLOAD_URL = "https://huggingface.co/Kalray/yolov8/resolve/main/yolov8n.onnx"
HF_CACHE_ROOT = Path(os.path.expanduser("~/.cache/huggingface/hub"))


def format_bytes(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_huggingface_model_dir(model_name: str) -> Path:
    folder_name = "models--" + model_name.replace("/", "--")
    return HF_CACHE_ROOT / folder_name


def get_directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp):
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    return total


def get_model_inventory() -> list[dict]:
    pack = settings.face_model_pack
    pack_dir = INSIGHTFACE_ROOT / pack

    from app.ml.loader import get_model_status
    from app.ml import object_detection, semantic_search

    face_loaded = get_model_status()
    yolo_loaded = object_detection._net is not None
    clip_loaded = semantic_search._clip_model is not None

    items = [
        {
            "id": "det_10g",
            "name": f"RetinaFace Detector ({pack})",
            "category": "Face Detection",
            "pack": pack,
            "filename": "det_10g.onnx",
            "path": str(pack_dir / "det_10g.onnx"),
            "purpose": "Detects facial bounding boxes and 5 primary landmark anchors (eyes, nose, mouth).",
            "is_loaded": face_loaded,
            "download_group": "insightface",
        },
        {
            "id": "w600k_r50",
            "name": f"ArcFace Recognition ({pack})",
            "category": "Face Recognition",
            "pack": pack,
            "filename": "w600k_r50.onnx",
            "path": str(pack_dir / "w600k_r50.onnx"),
            "purpose": "Extracts identity-defining 512-dimensional facial embedding vectors for Qdrant.",
            "is_loaded": face_loaded,
            "download_group": "insightface",
        },
        {
            "id": "genderage",
            "name": f"Gender & Age Estimator ({pack})",
            "category": "Sensitive Attributes",
            "pack": pack,
            "filename": "genderage.onnx",
            "path": str(pack_dir / "genderage.onnx"),
            "purpose": "Predicts age group and gender classification for smart people categorization.",
            "is_loaded": face_loaded,
            "download_group": "insightface",
        },
        {
            "id": "2d106det",
            "name": f"2D 106-Point Landmarks ({pack})",
            "category": "Face Alignment",
            "pack": pack,
            "filename": "2d106det.onnx",
            "path": str(pack_dir / "2d106det.onnx"),
            "purpose": "Dense 106-point facial contour tracking for high-precision pose estimation.",
            "is_loaded": face_loaded,
            "download_group": "insightface",
        },
        {
            "id": "1k3d68",
            "name": f"3D Landmark Pose ({pack})",
            "category": "Face Alignment",
            "pack": pack,
            "filename": "1k3d68.onnx",
            "path": str(pack_dir / "1k3d68.onnx"),
            "purpose": "Estimates 3D head pitch, yaw, and roll angles to identify profile vs frontal shots.",
            "is_loaded": face_loaded,
            "download_group": "insightface",
        },
        {
            "id": "yolov8n",
            "name": "YOLOv8 Nano Objects",
            "category": "Object & Scene Tagging",
            "pack": "yolov8",
            "filename": "yolov8n.onnx",
            "path": str(YOLO_MODEL_PATH),
            "purpose": "Auto-tags photos with 80 COCO objects (vehicles, animals, food, appliances, outdoors).",
            "is_loaded": yolo_loaded,
            "download_group": "yolov8n",
        },
        {
            "id": "clip_model",
            "name": f"CLIP Transformer ({settings.clip_model_name})",
            "category": "Semantic Search",
            "pack": "clip",
            "filename": "model.safetensors / pytorch_model.bin",
            "path": str(get_huggingface_model_dir(settings.clip_model_name)),
            "purpose": "Projects images and text queries into a shared 512-d vector space for natural language search.",
            "is_loaded": clip_loaded,
            "download_group": "clip",
        },
    ]

    inventory = []
    for item in items:
        p = Path(item["path"])
        exists = p.exists()
        size_bytes = get_directory_size(p) if exists else 0
        last_modified = None
        if exists:
            try:
                mtime = p.stat().st_mtime
                last_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            except OSError:
                pass

        status = "missing"
        if exists and size_bytes > 0:
            status = "loaded" if item["is_loaded"] else "on_disk"

        inventory.append({
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "filename": item["filename"],
            "path": item["path"],
            "purpose": item["purpose"],
            "download_group": item["download_group"],
            "exists": exists,
            "size_bytes": size_bytes,
            "size_formatted": format_bytes(size_bytes),
            "is_loaded": item["is_loaded"],
            "status": status,
            "last_modified": last_modified,
        })

    return inventory
