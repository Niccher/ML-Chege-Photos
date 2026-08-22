from __future__ import annotations

import logging
import os
import urllib.request
import cv2
import numpy as np

from app.config import settings

log = logging.getLogger("ml_chege_photos.object_detection")

MODEL_URL = "https://huggingface.co/Kalray/yolov8/resolve/main/yolov8n.onnx"
MODEL_PATH = "/app/models/yolov8n.onnx"

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush"
]

_net = None

def download_yolov8_model():
    if not os.path.exists(MODEL_PATH):
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        log.info("Downloading YOLOv8n ONNX model from %s ...", MODEL_URL)
        try:
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
            log.info("YOLOv8n ONNX model downloaded successfully")
        except Exception as exc:
            log.error("Failed to download YOLOv8n ONNX model: %s", exc)
            raise

def load_yolo_model():
    global _net
    if _net is None:
        download_yolov8_model()
        try:
            _net = cv2.dnn.readNetFromONNX(MODEL_PATH)
            _net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            _net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            log.info("YOLOv8n ONNX model loaded into OpenCV DNN")
        except Exception as exc:
            log.error("Failed to load YOLOv8n ONNX model: %s", exc)
            raise

def detect_objects(img_path: str, conf_threshold: float | None = None) -> list[dict]:
    if conf_threshold is None:
        conf_threshold = settings.object_det_threshold
        
    try:
        load_yolo_model()
        image = cv2.imread(img_path)
        if image is None:
            log.warning("Could not read image for object detection: %s", img_path)
            return []
        
        # YOLOv8 expects 640x640 input shape
        blob = cv2.dnn.blobFromImage(image, 1/255.0, (640, 640), swapRB=True, crop=False)
        _net.setInput(blob)
        outputs = _net.forward() # shape: [1, 84, 8400]
        
        # Post-process outputs
        rows = outputs[0].T # transpose to shape [8400, 84]
        
        seen_tags = {}
        for row in rows:
            classes_scores = row[4:]
            class_id = np.argmax(classes_scores)
            confidence = float(classes_scores[class_id])
            if confidence >= conf_threshold:
                label = COCO_CLASSES[class_id]
                if label not in seen_tags or confidence > seen_tags[label]:
                    seen_tags[label] = confidence
                    
        return [{"tag": label, "confidence": conf} for label, conf in seen_tags.items()]
    except Exception as exc:
        log.error("Object detection failed for %s: %s", img_path, exc)
        return []
