from __future__ import annotations

import io
import uuid
import logging
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from qdrant_client.http import models as qdrant_models

from sqlalchemy import text
from app.database import get_db, get_qdrant, FaceEncoding, Person
from app.config import settings
from app.ml.loader import get_face_analysis, get_model_status

log = logging.getLogger("ml_chege_photos.faces")
router = APIRouter(prefix="/api/v1/faces", tags=["faces"])

UPLOADS_DIR = Path("/app/uploads")


def _require_models():
    if not get_model_status():
        raise HTTPException(503, "Models not loaded")
    return get_face_analysis()


def _read_image(file: UploadFile) -> np.ndarray:
    contents = file.file.read()
    arr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Could not decode image")
    return img


def _face_to_dict(face, idx: int) -> dict:
    d = {
        "face_index": idx,
        "bbox": {
            "x": float(face.bbox[0]),
            "y": float(face.bbox[1]),
            "w": float(face.bbox[2] - face.bbox[0]),
            "h": float(face.bbox[3] - face.bbox[1]),
        },
        "detection_score": float(face.det_score),
        "landmarks": None,
        "embedding": None,
    }
    if face.kps is not None and face.kps.shape == (5, 2):
        d["landmarks"] = {
            "left_eye": {"x": float(face.kps[0, 0]), "y": float(face.kps[0, 1])},
            "right_eye": {"x": float(face.kps[1, 0]), "y": float(face.kps[1, 1])},
            "nose": {"x": float(face.kps[2, 0]), "y": float(face.kps[2, 1])},
            "left_mouth": {"x": float(face.kps[3, 0]), "y": float(face.kps[3, 1])},
            "right_mouth": {"x": float(face.kps[4, 0]), "y": float(face.kps[4, 1])},
        }
    if face.embedding is not None:
        d["embedding"] = face.embedding.astype(float).tolist()
    if settings.include_sensitive_attributes:
        d["age"] = int(face.age) if hasattr(face, "age") and face.age else None
        d["gender"] = str(face.gender) if hasattr(face, "gender") and face.gender is not None else None
    return d


# ── Detection ───────────────────────────────────────────────────


@router.post("/detect")
async def detect_faces(file: UploadFile = File(...)):
    model = _require_models()
    img = _read_image(file)
    faces = model.get(img)
    return {
        "face_count": len(faces),
        "faces": [_face_to_dict(f, i) for i, f in enumerate(faces)],
    }


# ── Embed (from a face crop) ────────────────────────────────────


@router.post("/embed")
async def embed_face(file: UploadFile = File(...)):
    model = _require_models()
    img = _read_image(file)
    faces = model.get(img)
    if not faces:
        raise HTTPException(404, "No face detected")
    return {"embedding": faces[0].embedding.astype(float).tolist()}


# ── Encode (detect + embed + store in Qdrant + DB) ──────────────


@router.post("/encode")
async def encode_photo(
    photo_id: int = Form(...),
    db: Session = Depends(get_db),
):
    model = _require_models()

    photo = db.execute(
        text("SELECT id, path FROM db_chege_photos.photos WHERE id = :pid"),
        {"pid": photo_id},
    ).fetchone()
    if not photo:
        raise HTTPException(404, "Photo not found")

    # DB stores path as "uploads/filename"; mount is already at /app/uploads
    rel = photo.path.removeprefix("uploads/")
    photo_path = UPLOADS_DIR / rel
    if not photo_path.exists():
        raise HTTPException(404, f"Photo file not found at {photo_path}")

    img = cv2.imread(str(photo_path))
    if img is None:
        raise HTTPException(400, "Could not read photo file")

    faces = model.get(img)
    if not faces:
        return {"photo_id": photo_id, "face_count": 0, "faces": []}

    qdrant = get_qdrant()
    results = []

    for i, face in enumerate(faces):
        point_id = str(uuid.uuid4())

        qdrant.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=face.embedding.astype(float).tolist(),
                    payload={
                        "photo_id": photo_id,
                        "face_index": i,
                        "bbox": _face_to_dict(face, i)["bbox"],
                        "detection_score": float(face.det_score),
                    },
                )
            ],
        )

        fe = FaceEncoding(
            photo_id=photo_id,
            qdrant_point_id=point_id,
            bbox_x=float(face.bbox[0]),
            bbox_y=float(face.bbox[1]),
            bbox_w=float(face.bbox[2] - face.bbox[0]),
            bbox_h=float(face.bbox[3] - face.bbox[1]),
            landmark_left_eye_x=float(face.kps[0, 0]) if face.kps is not None else None,
            landmark_left_eye_y=float(face.kps[0, 1]) if face.kps is not None else None,
            landmark_right_eye_x=float(face.kps[1, 0]) if face.kps is not None else None,
            landmark_right_eye_y=float(face.kps[1, 1]) if face.kps is not None else None,
            landmark_nose_x=float(face.kps[2, 0]) if face.kps is not None else None,
            landmark_nose_y=float(face.kps[2, 1]) if face.kps is not None else None,
            landmark_left_mouth_x=float(face.kps[3, 0]) if face.kps is not None else None,
            landmark_left_mouth_y=float(face.kps[3, 1]) if face.kps is not None else None,
            landmark_right_mouth_x=float(face.kps[4, 0]) if face.kps is not None else None,
            landmark_right_mouth_y=float(face.kps[4, 1]) if face.kps is not None else None,
            detection_score=float(face.det_score),
            age=int(face.age) if hasattr(face, "age") and face.age else None,
            gender=str(face.gender) if hasattr(face, "gender") and face.gender is not None else None,
        )
        db.add(fe)
        db.flush()

        results.append({
            "face_id": fe.id,
            "qdrant_point_id": point_id,
            "bbox": _face_to_dict(face, i)["bbox"],
            "detection_score": float(face.det_score),
            "embedding": face.embedding.astype(float).tolist(),
        })

    db.commit()
    return {"photo_id": photo_id, "face_count": len(results), "faces": results}


# ── Search ──────────────────────────────────────────────────────


@router.post("/search")
async def search_faces(
    file: UploadFile = File(...),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    model = _require_models()
    img = _read_image(file)
    faces = model.get(img)
    if not faces:
        raise HTTPException(404, "No face detected")

    query_vec = faces[0].embedding.astype(float).tolist()
    qdrant = get_qdrant()
    hits = qdrant.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vec,
        limit=limit,
        with_payload=True,
    )

    results = []
    for hit in hits:
        payload = hit.payload or {}
        fe = db.query(FaceEncoding).filter(
            FaceEncoding.qdrant_point_id == hit.id
        ).first()
        person_name = None
        if fe and fe.person and fe.person.name:
            person_name = fe.person.name

        results.append({
            "score": hit.score,
            "qdrant_point_id": hit.id,
            "photo_id": payload.get("photo_id"),
            "bbox": payload.get("bbox"),
            "person_name": person_name,
        })

    return {"query_embedding": query_vec, "results": results}


# ── Clustering ──────────────────────────────────────────────────


@router.post("/cluster")
async def cluster_faces(
    db: Session = Depends(get_db),
):
    from sklearn.cluster import HDBSCAN

    qdrant = get_qdrant()

    offset: int | None = None
    vectors = []
    point_ids = []
    while True:
        points, next_offset = qdrant.scroll(
            collection_name=settings.qdrant_collection,
            limit=100,
            offset=offset,
            with_vectors=True,
            with_payload=False,
        )
        for p in points:
            vectors.append(p.vector)
            point_ids.append(p.id)
        if next_offset is None:
            break
        offset = next_offset

    if len(vectors) < settings.hdbscan_min_cluster_size:
        return {"clusters": 0, "noise": len(vectors), "message": "Not enough faces to cluster"}

    X = np.array(vectors)
    clusterer = HDBSCAN(
        min_cluster_size=settings.hdbscan_min_cluster_size,
        min_samples=settings.hdbscan_min_samples,
        metric=settings.cluster_metric,
    )
    labels = clusterer.fit_predict(X)

    label_to_person = {}
    unique_labels = set(labels) - {-1}
    for lbl in unique_labels:
        person = Person(cluster_label=int(lbl))
        db.add(person)
        db.flush()
        label_to_person[lbl] = person.id

    assigned = 0
    for point_id, lbl in zip(point_ids, labels):
        if lbl == -1:
            continue
        fe = db.query(FaceEncoding).filter(
            FaceEncoding.qdrant_point_id == point_id
        ).first()
        if fe:
            fe.person_id = label_to_person[lbl]
            assigned += 1

    db.commit()

    return {
        "total_faces": len(vectors),
        "clusters": len(unique_labels),
        "noise": int((labels == -1).sum()),
        "assigned": assigned,
    }


# ── Get faces by photo ──────────────────────────────────────────


@router.get("/by-photo/{photo_id}")
def get_faces_by_photo(
    photo_id: int,
    db: Session = Depends(get_db),
):
    faces = db.query(FaceEncoding).filter(
        FaceEncoding.photo_id == photo_id
    ).order_by(FaceEncoding.id).all()

    results = []
    for fe in faces:
        person_name = fe.person.name if fe.person and fe.person.name else None
        results.append({
            "face_id": fe.id,
            "photo_id": fe.photo_id,
            "person_id": fe.person_id,
            "person_name": person_name,
            "qdrant_point_id": fe.qdrant_point_id,
            "bbox": {
                "x": fe.bbox_x,
                "y": fe.bbox_y,
                "w": fe.bbox_w,
                "h": fe.bbox_h,
            },
            "landmarks": {
                "left_eye": {"x": fe.landmark_left_eye_x, "y": fe.landmark_left_eye_y},
                "right_eye": {"x": fe.landmark_right_eye_x, "y": fe.landmark_right_eye_y},
                "nose": {"x": fe.landmark_nose_x, "y": fe.landmark_nose_y},
                "left_mouth": {"x": fe.landmark_left_mouth_x, "y": fe.landmark_left_mouth_y},
                "right_mouth": {"x": fe.landmark_right_mouth_x, "y": fe.landmark_right_mouth_y},
            } if fe.landmark_left_eye_x else None,
            "detection_score": fe.detection_score,
            "age": fe.age,
            "gender": fe.gender,
            "created_at": str(fe.created_at) if fe.created_at else None,
        })

    return {"photo_id": photo_id, "face_count": len(results), "faces": results}


# ── Persons ─────────────────────────────────────────────────────


@router.get("/persons")
def list_persons(
    db: Session = Depends(get_db),
):
    persons = db.query(Person).order_by(Person.id).all()
    results = []
    for p in persons:
        face_count = db.query(FaceEncoding).filter(
            FaceEncoding.person_id == p.id
        ).count()
        results.append({
            "id": p.id,
            "name": p.name,
            "cluster_label": p.cluster_label,
            "face_count": face_count,
            "thumbnail_face_id": p.thumbnail_face_id,
            "created_at": str(p.created_at) if p.created_at else None,
        })
    return {"persons": results}


@router.put("/persons/{person_id}")
def update_person(
    person_id: int,
    name: str = Form(None),
    thumbnail_face_id: int = Form(None),
    db: Session = Depends(get_db),
):
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(404, "Person not found")
    if name is not None:
        person.name = name
    if thumbnail_face_id is not None:
        face = db.query(FaceEncoding).filter(
            FaceEncoding.id == thumbnail_face_id,
            FaceEncoding.person_id == person_id,
        ).first()
        if not face:
            raise HTTPException(400, "Face does not belong to this person")
        person.thumbnail_face_id = thumbnail_face_id
    db.commit()
    return {"id": person.id, "name": person.name, "thumbnail_face_id": person.thumbnail_face_id}


@router.post("/persons/merge")
def merge_persons(
    source_person_id: int = Form(...),
    target_person_id: int = Form(...),
    db: Session = Depends(get_db),
):
    if source_person_id == target_person_id:
        raise HTTPException(400, "Cannot merge a person with itself")
    source = db.query(Person).filter(Person.id == source_person_id).first()
    target = db.query(Person).filter(Person.id == target_person_id).first()
    if not source or not target:
        raise HTTPException(404, "Person not found")

    db.query(FaceEncoding).filter(
        FaceEncoding.person_id == source_person_id
    ).update({"person_id": target_person_id})
    db.delete(source)
    db.commit()
    return {"merged_into": target_person_id, "deleted_person": source_person_id}


@router.get("/faces/unassigned")
def unassigned_faces(
    db: Session = Depends(get_db),
):
    faces = db.query(FaceEncoding).filter(
        FaceEncoding.person_id.is_(None)
    ).order_by(FaceEncoding.id).all()
    return {
        "face_count": len(faces),
        "faces": [
            {
                "face_id": f.id,
                "photo_id": f.photo_id,
                "bbox": {"x": f.bbox_x, "y": f.bbox_y, "w": f.bbox_w, "h": f.bbox_h},
                "detection_score": f.detection_score,
            }
            for f in faces
        ],
    }
