from __future__ import annotations

import uuid
import logging
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from qdrant_client.models import PointStruct

from sqlalchemy import text
from app.database import get_db, get_qdrant, FaceEncoding, Person
from app.models.db import PhotoScan, FaceCluster, FaceAnnotation
from app.config import settings
from app.ml.loader import get_face_analysis, get_model_status
from app.ml.attributes import extract_attributes
from app.ml import clustering as ml_clustering
from app.services.face import reclassify_face

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
    attrs = extract_attributes(face)
    d["age"] = attrs["age"]
    d["gender"] = attrs["gender"]
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


def calculate_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBAArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    unionArea = float(boxAArea + boxBAArea - interArea)
    if unionArea == 0:
        return 0.0
    return interArea / unionArea


def process_photo_pipeline_sync(
    photo_id: int,
    scan_faces: bool,
    scan_tags: bool,
    scan_clip: bool,
    db: Session,
) -> dict:
    model = _require_models()

    photo = db.execute(
        text("SELECT id, path, user_id FROM db_chege_photos.tbl_photos WHERE id = :pid"),
        {"pid": photo_id},
    ).fetchone()
    if not photo:
        raise HTTPException(404, "Photo not found")
    user_id = photo.user_id if hasattr(photo, "user_id") else (photo[2] if len(photo) > 2 else None)

    rel = photo.path.removeprefix("uploads/")
    uploads_base = Path(settings.uploads_dir)
    photo_path = uploads_base / rel
    if not photo_path.exists() and settings.webapp_url:
        import urllib.request
        download_url = f"{settings.webapp_url.rstrip('/')}/uploads/{rel}"
        try:
            photo_path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(download_url, str(photo_path))
        except Exception as err:
            log.warning("Could not download photo %s from %s: %s", photo_id, download_url, err)

    if not photo_path.exists():
        raise HTTPException(404, f"Photo file not found at {photo_path}")

    img = cv2.imread(str(photo_path))
    if img is None:
        raise HTTPException(400, "Could not read photo file")

    results = []

    # 1. Faces Scan
    if scan_faces:
        all_faces = model.get(img)

        # Non-face filtering: skip low-confidence detections and tiny crops
        # that are likely false positives (patterns, paintings, icons).
        MIN_DET_SCORE = settings.face_det_thresh
        MIN_FACE_PX   = 30  # minimum face width/height in pixels
        faces = []
        for f in all_faces:
            w = float(f.bbox[2] - f.bbox[0])
            h = float(f.bbox[3] - f.bbox[1])
            if float(f.det_score) >= MIN_DET_SCORE and w >= MIN_FACE_PX and h >= MIN_FACE_PX:
                faces.append(f)
            else:
                log.debug(
                    "Skipping false-positive face: score=%.3f w=%.0f h=%.0f",
                    float(f.det_score), w, h
                )

        qdrant = get_qdrant()

        # Load existing FaceEncoding records for this photo
        existing_encodings = db.query(FaceEncoding).filter(FaceEncoding.photo_id == photo_id).all()

        matched_existing_ids = set()

        for i, face in enumerate(faces):
            new_box = [float(face.bbox[0]), float(face.bbox[1]), float(face.bbox[2]), float(face.bbox[3])]

            best_iou = 0.0
            best_match = None

            for old_fe in existing_encodings:
                if old_fe.id in matched_existing_ids:
                    continue
                old_box = [
                    old_fe.bbox_x,
                    old_fe.bbox_y,
                    old_fe.bbox_x + old_fe.bbox_w,
                    old_fe.bbox_y + old_fe.bbox_h
                ]
                iou = calculate_iou(new_box, old_box)
                if iou > best_iou:
                    best_iou = iou
                    best_match = old_fe

            # Matching threshold 0.50
            if best_match and best_iou >= 0.50:
                fe = best_match
                matched_existing_ids.add(fe.id)
                point_id = fe.qdrant_point_id
            else:
                point_id = str(uuid.uuid4())
                fe = FaceEncoding(
                    photo_id=photo_id,
                    qdrant_point_id=point_id
                )
                db.add(fe)

            fe.bbox_x = float(face.bbox[0])
            fe.bbox_y = float(face.bbox[1])
            fe.bbox_w = float(face.bbox[2] - face.bbox[0])
            fe.bbox_h = float(face.bbox[3] - face.bbox[1])

            fe.landmark_left_eye_x = float(face.kps[0, 0]) if face.kps is not None else None
            fe.landmark_left_eye_y = float(face.kps[0, 1]) if face.kps is not None else None
            fe.landmark_right_eye_x = float(face.kps[1, 0]) if face.kps is not None else None
            fe.landmark_right_eye_y = float(face.kps[1, 1]) if face.kps is not None else None
            fe.landmark_nose_x = float(face.kps[2, 0]) if face.kps is not None else None
            fe.landmark_nose_y = float(face.kps[2, 1]) if face.kps is not None else None
            fe.landmark_left_mouth_x = float(face.kps[3, 0]) if face.kps is not None else None
            fe.landmark_left_mouth_y = float(face.kps[3, 1]) if face.kps is not None else None
            fe.landmark_right_mouth_x = float(face.kps[4, 0]) if face.kps is not None else None
            fe.landmark_right_mouth_y = float(face.kps[4, 1]) if face.kps is not None else None
            fe.detection_score = float(face.det_score)
            fe.model_version    = settings.face_model_pack  # track which model produced this embedding

            attrs = extract_attributes(face)
            if not fe.id or not fe.gender:
                fe.gender = attrs["gender"]
            if not fe.id or not fe.age:
                fe.age = attrs["age"]

            db.flush()

            # Upsert vector
            qdrant.upsert(
                collection_name=settings.qdrant_collection,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=face.embedding.astype(float).tolist(),
                        payload={
                            "photo_id": photo_id,
                            "user_id": int(user_id) if user_id is not None else None,
                            "face_index": i,
                            "bbox": _face_to_dict(face, i)["bbox"],
                            "detection_score": float(face.det_score),
                        },
                    )
                ],
            )

            results.append({
                "face_id": fe.id,
                "qdrant_point_id": point_id,
                "bbox": _face_to_dict(face, i)["bbox"],
                "detection_score": float(face.det_score),
                "embedding": face.embedding.astype(float).tolist(),
            })

        # Delete any old FaceEncoding records that were NOT matched
        for old_fe in existing_encodings:
            if old_fe.id not in matched_existing_ids:
                db.delete(old_fe)
                try:
                    qdrant.delete(
                        collection_name=settings.qdrant_collection,
                        points_selector=[old_fe.qdrant_point_id]
                    )
                except Exception as q_exc:
                    log.warning(f"Could not delete point {old_fe.qdrant_point_id} from Qdrant: {q_exc}")

        db.execute(
            text("UPDATE db_chege_photos.tbl_photos SET scanned_face = 1 WHERE id = :pid"),
            {"pid": photo_id}
        )

    # 2. Object Detection (YOLOv8)
    if scan_tags:
        try:
            from app.ml import object_detection
            from app.database import PhotoTag
            tags = object_detection.detect_objects(str(photo_path))
            db.query(PhotoTag).filter(PhotoTag.photo_id == photo_id).delete()
            for t in tags:
                pt = PhotoTag(
                    photo_id=photo_id,
                    tag=t["tag"],
                    confidence=t["confidence"]
                )
                db.add(pt)
            db.execute(
                text("UPDATE db_chege_photos.tbl_photos SET scanned_tag = 1 WHERE id = :pid"),
                {"pid": photo_id}
            )
        except Exception as exc:
            log.error("Object detection failed for photo %d: %s", photo_id, exc)

    # 3. Semantic Search (CLIP)
    if scan_clip:
        try:
            from app.ml import semantic_search
            clip_emb = semantic_search.encode_image(str(photo_path))
            qdrant = get_qdrant()
            qdrant.upsert(
                collection_name=settings.qdrant_photo_collection,
                points=[PointStruct(
                    id=str(uuid.uuid4()),
                    vector=clip_emb,
                    payload={
                        "photo_id": photo_id,
                        "user_id": int(user_id) if user_id is not None else None,
                    }
                )]
            )
            db.execute(
                text("UPDATE db_chege_photos.tbl_photos SET scanned_clip = 1 WHERE id = :pid"),
                {"pid": photo_id}
            )
        except Exception as exc:
            log.error("CLIP embedding failed for photo %d: %s", photo_id, exc)

    db.commit()
    return {"photo_id": photo_id, "face_count": len(results), "faces": results}


def process_photo_pipeline_queued(photo_id: int, scan_faces: bool, scan_tags: bool, scan_clip: bool):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        process_photo_pipeline_sync(
            photo_id=photo_id,
            scan_faces=scan_faces,
            scan_tags=scan_tags,
            scan_clip=scan_clip,
            db=db
        )
    except Exception as e:
        log.error(f"Failed to run queued photo pipeline for photo {photo_id}: {e}", exc_info=True)
    finally:
        db.close()


@router.post("/encode")
async def encode_photo(
    photo_id: int = Form(...),
    scan_faces: bool = Form(True),
    scan_tags: bool = Form(True),
    scan_clip: bool = Form(True),
    async_task: bool = Form(False),
    db: Session = Depends(get_db),
):
    if async_task:
        from app.ml.queue import ml_job_queue
        await ml_job_queue.add_job(
            process_photo_pipeline_queued,
            photo_id=photo_id,
            scan_faces=scan_faces,
            scan_tags=scan_tags,
            scan_clip=scan_clip
        )
        return {"status": "queued", "photo_id": photo_id}
    else:
        return process_photo_pipeline_sync(
            photo_id=photo_id,
            scan_faces=scan_faces,
            scan_tags=scan_tags,
            scan_clip=scan_clip,
            db=db
        )


# ── Search ──────────────────────────────────────────────────────


@router.post("/search")
async def search_faces(
    file: UploadFile = File(...),
    limit: int = Query(20, ge=1, le=100),
    user_id: int | None = Query(None, description="Restrict results to this user's faces only"),
    min_det_score: float = Query(0.85, description="Minimum RetinaFace detection score to consider"),
    db: Session = Depends(get_db),
):
    model = _require_models()
    img = _read_image(file)
    faces = model.get(img)
    if not faces:
        raise HTTPException(404, "No face detected")

    # Non-face filtering: only accept high-confidence detections
    confident_faces = [f for f in faces if float(f.det_score) >= min_det_score]
    if not confident_faces:
        raise HTTPException(404, f"No face with detection score ≥ {min_det_score} found (got scores: {[round(float(f.det_score), 3) for f in faces]})")

    query_vec = confident_faces[0].embedding.astype(float).tolist()
    qdrant = get_qdrant()

    # Build optional user_id filter to ensure cross-user privacy
    query_filter = None
    if user_id is not None:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                )
            ]
        )

    hits = qdrant.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vec,
        query_filter=query_filter,
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
    mode: str = Query(
        "incremental",
        description="'incremental' = centroid fast-assign then HDBSCAN only if threshold exceeded; 'full' = always full HDBSCAN",
    ),
    min_cluster_size: int | None = Query(None, description="HDBSCAN min_cluster_size override"),
    min_samples: int | None = Query(None, description="HDBSCAN min_samples override"),
    db: Session = Depends(get_db),
):
    qdrant = get_qdrant()
    vectors, point_ids = ml_clustering.scroll_all_vectors(qdrant, settings.qdrant_collection)

    # ── Load pinned annotations (Human-in-the-Loop) ─────────────
    # 'confirm' annotations are hard constraints: the face stays pinned to its
    # person and is excluded from HDBSCAN re-assignment entirely.
    pinned_confirm_rows = db.execute(
        text(
            "SELECT fa.face_encoding_id, fa.person_id "
            "FROM face_annotation fa WHERE fa.action = 'confirm'"
        )
    ).fetchall()
    pinned_face_ids: dict[int, int] = {r[0]: r[1] for r in pinned_confirm_rows}

    # 'reject' annotations: face must NOT be assigned to a specific person.
    reject_rows = db.execute(
        text(
            "SELECT fa.face_encoding_id, fa.person_id "
            "FROM face_annotation fa WHERE fa.action = 'reject'"
        )
    ).fetchall()
    # Maps face_encoding_id -> set of forbidden person_ids
    rejected_persons: dict[int, set[int]] = {}
    for r in reject_rows:
        rejected_persons.setdefault(r[0], set()).add(r[1])

    # Apply confirmed pins first — set person_id directly, skip HDBSCAN for these
    pinned_qdrant_ids: set[str] = set()
    for fe_db_id, person_id in pinned_face_ids.items():
        fe = db.query(FaceEncoding).filter(FaceEncoding.id == fe_db_id).first()
        if fe:
            fe.person_id = person_id
            pinned_qdrant_ids.add(fe.qdrant_point_id)
    if pinned_face_ids:
        db.commit()

    # ── 1. Fetch unlocked faces (unassigned or with unnamed person, not pinned) ─
    unlocked_rows = db.execute(
        text(
            "SELECT fe.qdrant_point_id, fe.id FROM face_encoding fe "
            "LEFT JOIN person p ON fe.person_id = p.id "
            "WHERE (fe.person_id IS NULL OR p.name IS NULL OR p.name = '')"
        )
    ).fetchall()
    unlocked_ids = {r[0] for r in unlocked_rows if r[0] not in pinned_qdrant_ids}

    # ── 2. Incremental fast-assign via centroid proximity ────────
    incremental_assigned = 0
    if mode == "incremental":
        new_vectors = [v for v, pid in zip(vectors, point_ids) if pid in unlocked_ids]
        new_pids    = [pid for pid in point_ids if pid in unlocked_ids]

        if new_vectors:
            assignments = ml_clustering.assign_new_faces(
                qdrant, new_vectors, new_pids,
                confidence_threshold=settings.incremental_centroid_threshold,
            )
            for pid, person_id in assignments.items():
                if person_id is None:
                    continue
                fe = db.query(FaceEncoding).filter(
                    FaceEncoding.qdrant_point_id == pid
                ).first()
                if not fe:
                    continue
                # Honour reject annotations
                if fe.id in rejected_persons and person_id in rejected_persons[fe.id]:
                    continue
                fe.person_id = person_id
                unlocked_ids.discard(pid)   # no longer needs full HDBSCAN
                incremental_assigned += 1

            db.commit()

    # ── 3. Decide whether to run full HDBSCAN ────────────────────
    remaining_unlocked = len(unlocked_ids)
    run_full = (
        mode == "full"
        or remaining_unlocked >= settings.incremental_unassigned_trigger
    )

    if not run_full:
        return {
            "mode": mode,
            "total_faces": len(vectors),
            "incremental_assigned": incremental_assigned,
            "unassigned_remaining": remaining_unlocked,
            "full_hdbscan_run": False,
            "message": (
                f"Incremental assignment complete. "
                f"{remaining_unlocked} face(s) pending full sweep "
                f"(trigger={settings.incremental_unassigned_trigger})."
            ),
        }

    # ── 4. Full HDBSCAN on remaining unlocked faces ──────────────
    filtered_vectors  = [v for v, pid in zip(vectors, point_ids) if pid in unlocked_ids]
    filtered_pids     = [pid for pid in point_ids if pid in unlocked_ids]

    if not filtered_vectors:
        return {
            "mode": mode,
            "total_faces": len(vectors),
            "incremental_assigned": incremental_assigned,
            "unassigned_remaining": 0,
            "full_hdbscan_run": True,
            "clusters": 0,
            "noise": 0,
            "assigned": 0,
            "message": "No unlocked faces remain for HDBSCAN",
        }

    # Detach face encodings from unnamed persons before deleting them to satisfy foreign keys
    db.execute(text("UPDATE face_encoding fe JOIN person p ON fe.person_id = p.id SET fe.person_id = NULL WHERE p.name IS NULL OR p.name = ''"))
    db.execute(text("DELETE FROM person WHERE name IS NULL OR name = ''"))
    db.commit()

    result    = ml_clustering.run_hdbscan(filtered_vectors, min_cluster_size, min_samples)
    labels    = result["labels"]
    n_clusters = result["n_clusters"]
    noise      = result["noise"]

    if n_clusters == 0:
        return {
            "mode": mode,
            "total_faces": len(vectors),
            "incremental_assigned": incremental_assigned,
            "full_hdbscan_run": True,
            "clusters": 0,
            "noise": noise,
            "assigned": 0,
            "message": "Not enough faces to cluster" if noise == len(filtered_vectors) else "All faces are noise",
        }

    unique_labels = set(labels) - {-1}
    label_to_person: dict[int, int] = {}
    for lbl in unique_labels:
        person = Person(cluster_label=int(lbl))
        db.add(person)
        db.flush()
        label_to_person[lbl] = person.id

    hdbscan_assigned = 0
    for pid, lbl in zip(filtered_pids, labels):
        if lbl == -1:
            continue
        fe = db.query(FaceEncoding).filter(FaceEncoding.qdrant_point_id == pid).first()
        if not fe:
            continue
        candidate_person = label_to_person[lbl]
        # Honour reject annotations
        if fe.id in rejected_persons and candidate_person in rejected_persons[fe.id]:
            continue
        fe.person_id = candidate_person
        hdbscan_assigned += 1

    db.commit()

    centroids = ml_clustering.compute_centroids(filtered_vectors, labels)
    ml_clustering.store_centroids(centroids, label_to_person)

    return {
        "mode": mode,
        "total_faces": len(vectors),
        "pinned_faces": len(pinned_face_ids),
        "incremental_assigned": incremental_assigned,
        "full_hdbscan_run": True,
        "unlocked_faces": len(filtered_vectors),
        "clusters": n_clusters,
        "noise": noise,
        "assigned": hdbscan_assigned,
        "centroids_stored": len(centroids),
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


@router.post("/delete-by-photo-ids")
def delete_by_photo_ids(
    body: dict,
    db: Session = Depends(get_db),
):
    photo_ids = body.get("photo_ids", [])
    if not photo_ids:
        raise HTTPException(400, "photo_ids list required")

    faces = db.query(FaceEncoding).filter(
        FaceEncoding.photo_id.in_(photo_ids)
    ).all()

    qdrant_points = [f.qdrant_point_id for f in faces]
    person_ids = list({f.person_id for f in faces if f.person_id is not None})

    # Delete from Qdrant
    qdrant = get_qdrant()
    for pid in qdrant_points:
        try:
            qdrant.delete(
                collection_name=settings.qdrant_collection,
                points_selector=[pid],
            )
        except Exception:
            pass

    # Delete face encodings
    deleted_faces = db.query(FaceEncoding).filter(
        FaceEncoding.photo_id.in_(photo_ids)
    ).delete(synchronize_session=False)

    # Delete orphaned persons (and their clusters)
    deleted_persons = 0
    centroid_points_removed = 0
    for pid in person_ids:
        remaining = db.query(FaceEncoding).filter(
            FaceEncoding.person_id == pid
        ).count()
        if remaining == 0:
            clusters = db.query(FaceCluster).filter(FaceCluster.person_id == pid).all()
            for c in clusters:
                if c.centroid_point_id:
                    try:
                        qdrant.delete(
                            collection_name=settings.qdrant_collection + "_centroids",
                            points_selector=[c.centroid_point_id],
                        )
                        centroid_points_removed += 1
                    except Exception:
                        pass
            db.query(FaceCluster).filter(FaceCluster.person_id == pid).delete()
            db.query(Person).filter(Person.id == pid).delete()
            deleted_persons += 1

    # Delete photo tags
    try:
        from app.database import PhotoTag
        db.query(PhotoTag).filter(PhotoTag.photo_id.in_(photo_ids)).delete(synchronize_session=False)
    except Exception as exc:
        log.warning("Failed to delete photo tags: %s", exc)

    # Delete photo embeddings
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchAny
        qdrant.delete(
            collection_name=settings.qdrant_photo_collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="photo_id",
                        match=MatchAny(any=photo_ids)
                    )
                ]
            )
        )
    except Exception:
        pass

    # Delete photo scans
    deleted_scans = db.query(PhotoScan).filter(
        PhotoScan.photo_id.in_(photo_ids)
    ).delete(synchronize_session=False)

    db.commit()

    return {
        "deleted_faces": deleted_faces,
        "deleted_persons": deleted_persons,
        "deleted_scans": deleted_scans,
        "qdrant_points_removed": len(qdrant_points),
        "centroid_points_removed": centroid_points_removed,
    }


@router.post("/{face_id}/reclassify")
def reclassify_face_endpoint(
    face_id: int,
    db: Session = Depends(get_db),
):
    try:
        result = reclassify_face(face_id, db)
        return {"status": "success", "data": result}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/reset")
def reset_faces(
    db: Session = Depends(get_db),
):
    db.query(FaceEncoding).delete()
    db.query(Person).delete()
    db.commit()

    qdrant = get_qdrant()
    collections = qdrant.get_collections().collections
    existing = {c.name for c in collections}
    if settings.qdrant_collection in existing:
        qdrant.delete_collection(collection_name=settings.qdrant_collection)

    from qdrant_client.models import VectorParams, Distance
    qdrant.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE),
    )

    ml_clustering.clear_centroids()
    return {"status": "success", "message": "All face data deleted, Qdrant collection recreated"}


@router.get("/unassigned")
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


# ── Human-in-the-Loop Refinements ────────────────────────────────

@router.post("/{face_id}/annotate")
def annotate_face(
    face_id: int,
    person_id: int = Form(...),
    action: str = Form(..., description="'confirm' to lock face to person; 'reject' to disallow the assignment"),
    annotated_by: int | None = Form(None),
    db: Session = Depends(get_db),
):
    if action not in ("confirm", "reject"):
        raise HTTPException(400, "Action must be either 'confirm' or 'reject'")

    fe = db.query(FaceEncoding).filter(FaceEncoding.id == face_id).first()
    if not fe:
        raise HTTPException(404, "FaceEncoding not found")

    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(404, "Person not found")

    # Check if this annotation already exists
    ann = db.query(FaceAnnotation).filter(
        FaceAnnotation.face_encoding_id == face_id,
        FaceAnnotation.person_id == person_id
    ).first()

    if not ann:
        ann = FaceAnnotation(
            face_encoding_id=face_id,
            person_id=person_id,
            action=action,
            annotated_by=annotated_by
        )
        db.add(ann)
    else:
        ann.action = action
        ann.annotated_by = annotated_by

    # For confirm, immediately update the face's person_id mapping
    if action == "confirm":
        fe.person_id = person_id
    elif action == "reject" and fe.person_id == person_id:
        # If rejected, unassign it if it was assigned to this person
        fe.person_id = None

    db.commit()
    return {
        "status": "success",
        "face_id": face_id,
        "person_id": person_id,
        "action": action,
        "assigned_person_id": fe.person_id,
    }


@router.delete("/{face_id}/annotate/{person_id}")
def remove_annotation(
    face_id: int,
    person_id: int,
    db: Session = Depends(get_db),
):
    ann = db.query(FaceAnnotation).filter(
        FaceAnnotation.face_encoding_id == face_id,
        FaceAnnotation.person_id == person_id
    ).first()

    if not ann:
        raise HTTPException(404, "Annotation not found")

    db.delete(ann)
    db.commit()
    return {"status": "success", "message": "Annotation removed successfully"}


@router.get("/{face_id}/annotations")
def get_face_annotations(
    face_id: int,
    db: Session = Depends(get_db),
):
    annotations = db.query(FaceAnnotation).filter(FaceAnnotation.face_encoding_id == face_id).all()
    return {
        "face_id": face_id,
        "annotations": [
            {
                "person_id": a.person_id,
                "action": a.action,
                "annotated_by": a.annotated_by,
                "created_at": str(a.created_at) if a.created_at else None,
            }
            for a in annotations
        ]
    }

