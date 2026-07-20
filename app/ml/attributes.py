from __future__ import annotations

import logging

import numpy as np

from app.config import settings

log = logging.getLogger("ml_chege_photos.attributes")

EMOTION_LABELS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]


def extract_attributes(face) -> dict:
    result = {}

    if settings.include_sensitive_attributes:
        result["age"] = int(face.age) if hasattr(face, "age") and face.age is not None else None
        result["gender"] = str(face.gender) if hasattr(face, "gender") and face.gender is not None else None
    else:
        result["age"] = None
        result["gender"] = None

    return result


def extract_aligned_crop(img: np.ndarray, face, size: tuple[int, int] = (112, 112)) -> np.ndarray | None:
    try:
        from insightface.utils import face_align

        crop = face_align.norm_crop(img, face.kps, image_size=size[0])
        return crop
    except Exception as exc:
        log.warning("Failed to extract aligned crop: %s", exc)
        return None
