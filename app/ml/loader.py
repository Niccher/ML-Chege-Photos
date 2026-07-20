from __future__ import annotations

import logging
import os

import numpy as np

from app.config import settings

log = logging.getLogger("ml_chege_photos.models")

_models_loaded: bool = False
_face_analysis = None

MODEL_DIR = "/app/models/insightface_models"


def load_models():
    global _models_loaded, _face_analysis

    os.makedirs(MODEL_DIR, exist_ok=True)

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    try:
        from insightface.app import FaceAnalysis

        _face_analysis = FaceAnalysis(
            name=settings.face_model_pack,
            root=MODEL_DIR,
            providers=providers,
        )
        _face_analysis.prepare(ctx_id=0, det_thresh=settings.face_det_thresh)

        dummy = np.zeros((480, 640, 3), dtype=np.uint8)
        _face_analysis.get(dummy)
        _models_loaded = True
        log.info("Insightface models loaded (GPU)")
    except Exception:
        log.warning("GPU unavailable, falling back to CPU")
        try:
            from insightface.app import FaceAnalysis

            _face_analysis = FaceAnalysis(
                name=settings.face_model_pack,
                root=MODEL_DIR,
                providers=["CPUExecutionProvider"],
            )
            _face_analysis.prepare(ctx_id=-1, det_thresh=settings.face_det_thresh)
            _models_loaded = True
            log.info("Insightface models loaded (CPU)")
        except Exception as exc:
            log.error("Failed to load insightface models: %s", exc)
            _models_loaded = False


def get_model_status() -> bool:
    return _models_loaded


def get_face_analysis():
    return _face_analysis
