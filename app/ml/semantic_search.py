from __future__ import annotations

import logging
import torch
from PIL import Image
import numpy as np

from app.config import settings

log = logging.getLogger("ml_chege_photos.semantic_search")

_clip_model = None
_clip_processor = None
_loaded_model_name = None

def load_clip_model(force: bool = False):
    global _clip_model, _clip_processor, _loaded_model_name
    if _clip_model is None or force or _loaded_model_name != settings.clip_model_name:
        try:
            from transformers import CLIPModel, CLIPProcessor
            log.info("Loading CLIP model: %s ...", settings.clip_model_name)
            _clip_model = CLIPModel.from_pretrained(settings.clip_model_name)
            _clip_processor = CLIPProcessor.from_pretrained(settings.clip_model_name)
            _loaded_model_name = settings.clip_model_name
            log.info("CLIP model loaded successfully")
        except Exception as exc:
            log.error("Failed to load CLIP model: %s", exc)
            raise

def get_clip_model_and_processor():
    if _clip_model is None:
        load_clip_model()
    return _clip_model, _clip_processor

def encode_text(text: str) -> list[float]:
    model, processor = get_clip_model_and_processor()
    inputs = processor(text=[text], return_tensors="pt", padding=True)
    with torch.no_grad():
        features = model.get_text_features(**inputs)
        if hasattr(features, "pooler_output"):
            features = features.pooler_output
    # L2 normalize the embedding
    features = features / features.norm(dim=-1, keepdim=True)
    return features[0].cpu().numpy().tolist()

def encode_image(image_path: str) -> list[float]:
    model, processor = get_clip_model_and_processor()
    try:
        image = Image.open(image_path)
        inputs = processor(images=image, return_tensors="pt")
        with torch.no_grad():
            features = model.get_image_features(**inputs)
            if hasattr(features, "pooler_output"):
                features = features.pooler_output
        # L2 normalize the embedding
        features = features / features.norm(dim=-1, keepdim=True)
        return features[0].cpu().numpy().tolist()
    except Exception as exc:
        log.error("Failed to generate CLIP embedding for image %s: %s", image_path, exc)
        raise
