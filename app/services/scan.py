from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from threading import Lock
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from qdrant_client.models import PointStruct

from app.config import settings
from app.database import get_db, get_qdrant, FaceEncoding, Person
from app.models.db import PhotoScan, ScanJob, FaceCluster
from app.ml.loader import get_face_analysis, get_model_status
from app.ml.attributes import extract_attributes
from app.ml import clustering as ml_clustering

log = logging.getLogger("ml_chege_photos.scan")

UPLOADS_DIR = Path("/app/uploads")

_scan_lock = Lock()


def _require_models():
    if not get_model_status():
        raise RuntimeError("Models not loaded")
    return get_face_analysis()


def _read_photo(photo_path: str) -> np.ndarray:
    img = cv2.imread(str(photo_path))
    if img is None:
        raise ValueError(f"Could not read photo at {photo_path}")
    return img


def process_single_photo(photo_id: int, db: Session) -> dict:
    from app.ml.manifest import ensure_all_models_ready
    ensure_all_models_ready()
    model = _require_models()

    photo = db.execute(
        text("SELECT id, path FROM db_chege_photos.tbl_photos WHERE id = :pid"),
        {"pid": photo_id},
    ).fetchone()
    if not photo:
        raise ValueError(f"Photo {photo_id} not found")

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
        raise ValueError(f"Photo file not found at {photo_path}")

    img = _read_photo(str(photo_path))
    faces = model.get(img)

    qdrant = get_qdrant()
    results = []

    for i, face in enumerate(faces):
        point_id = str(uuid.uuid4())
        embedding = face.embedding.astype(float).tolist()

        qdrant.upsert(
            collection_name=settings.qdrant_collection,
            points=[PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "photo_id": photo_id,
                    "face_index": i,
                    "bbox": {
                        "x": float(face.bbox[0]),
                        "y": float(face.bbox[1]),
                        "w": float(face.bbox[2] - face.bbox[0]),
                        "h": float(face.bbox[3] - face.bbox[1]),
                    },
                    "detection_score": float(face.det_score),
                },
            )],
        )

        attrs = extract_attributes(face)
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
            age=attrs["age"],
            gender=attrs["gender"],
        )
        db.add(fe)
        db.flush()
        results.append({
            "face_id": fe.id,
            "qdrant_point_id": point_id,
            "detection_score": float(face.det_score),
        })

    # ── Semantic Search (CLIP) ──
    try:
        from app.ml import semantic_search
        clip_emb = semantic_search.encode_image(str(photo_path))
        qdrant.upsert(
            collection_name=settings.qdrant_photo_collection,
            points=[PointStruct(
                id=str(uuid.uuid4()),
                vector=clip_emb,
                payload={"photo_id": photo_id}
            )]
        )
    except Exception as exc:
        log.warning("CLIP embedding failed for photo %d: %s. Re-verifying model...", photo_id, exc)
        try:
            ensure_all_models_ready()
            from app.ml import semantic_search
            clip_emb = semantic_search.encode_image(str(photo_path))
            qdrant.upsert(
                collection_name=settings.qdrant_photo_collection,
                points=[PointStruct(
                    id=str(uuid.uuid4()),
                    vector=clip_emb,
                    payload={"photo_id": photo_id}
                )]
            )
            log.info("CLIP embedding succeeded on retry for photo %d", photo_id)
        except Exception as retry_exc:
            log.error("CLIP embedding retry failed for photo %d: %s", photo_id, retry_exc)

    # ── Object Detection (YOLOv8) ──
    try:
        from app.ml import object_detection
        from app.database import PhotoTag
        tags = object_detection.detect_objects(str(photo_path))
        # Clear old tags first
        db.query(PhotoTag).filter(PhotoTag.photo_id == photo_id).delete()
        for t in tags:
            pt = PhotoTag(
                photo_id=photo_id,
                tag=t["tag"],
                confidence=t["confidence"]
            )
            db.add(pt)
    except Exception as exc:
        log.warning("Object detection failed for photo %d: %s. Re-verifying model...", photo_id, exc)
        try:
            ensure_all_models_ready()
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
            log.info("Object detection succeeded on retry for photo %d", photo_id)
        except Exception as retry_exc:
            log.error("Object detection retry failed for photo %d: %s", photo_id, retry_exc)

    db.commit()
    return {"face_count": len(results), "faces": results}


def scan_photo(photo_id: int) -> PhotoScan:
    db = next(get_db())
    try:
        scan = db.query(PhotoScan).filter(PhotoScan.photo_id == photo_id).first()
        if not scan:
            scan = PhotoScan(photo_id=photo_id, status="pending")
            db.add(scan)
            db.commit()
            db.refresh(scan)

        scan.status = "processing"
        scan.started_at = datetime.now(timezone.utc)
        db.commit()

        result = process_single_photo(photo_id, db)

        scan.status = "completed"
        scan.face_count = result["face_count"]
        scan.completed_at = datetime.now(timezone.utc)
        db.commit()

        return scan
    except Exception as exc:
        scan = db.query(PhotoScan).filter(PhotoScan.photo_id == photo_id).first()
        if scan:
            scan.status = "failed"
            scan.error_message = str(exc)
            scan.completed_at = datetime.now(timezone.utc)
            db.commit()
        log.error("Scan failed for photo %d: %s", photo_id, exc)
        raise
    finally:
        db.close()


def create_scan_job(photo_ids: Optional[list[int]] = None) -> ScanJob:
    db = next(get_db())
    try:
        if photo_ids:
            total = len(photo_ids)
        else:
            total = db.execute(
                text("SELECT COUNT(*) FROM db_chege_photos.tbl_photos WHERE type = 'image' AND deleted_at IS NULL")
            ).scalar()

        job = ScanJob(status="pending", total_photos=total)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def run_scan_job(job_id: int):
    with _scan_lock:
        db = next(get_db())
        try:
            job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
            if not job:
                log.error("ScanJob %d not found", job_id)
                return

            job.status = "processing"
            db.commit()

            photos = db.execute(
                text("SELECT id FROM db_chege_photos.tbl_photos WHERE type = 'image' AND deleted_at IS NULL ORDER BY id")
            ).fetchall()

            for row in photos:
                pid = row[0]
                existing = db.query(PhotoScan).filter(
                    PhotoScan.photo_id == pid, PhotoScan.status == "completed"
                ).first()
                if existing:
                    continue

                try:
                    scan_photo(pid)
                    job.processed += 1
                except Exception:
                    job.failed += 1

                db.commit()

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            log.info("ScanJob %d complete: %d processed, %d failed", job_id, job.processed, job.failed)

        except Exception as exc:
            job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
            log.error("ScanJob %d failed: %s", job_id, exc)
        finally:
            db.close()


def cleanup_stale_scans(max_age_sec: int = 300):
    db = next(get_db())
    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
        from sqlalchemy import func as sa_func
        stale = db.query(PhotoScan).filter(
            PhotoScan.status == "processing",
            PhotoScan.started_at.isnot(None),
        ).all()
        for s in stale:
            age = (cutoff - s.started_at).total_seconds() if s.started_at else 0
            if age > max_age_sec:
                s.status = "failed"
                s.error_message = "Stale — timed out after %ds" % max_age_sec
                s.completed_at = cutoff
                log.warning("Marked stale PhotoScan %d for photo %d", s.id, s.photo_id)
        db.commit()

        stale_jobs = db.query(ScanJob).filter(
            ScanJob.status == "processing",
            ScanJob.created_at.isnot(None),
        ).all()
        for j in stale_jobs:
            age = (cutoff - j.created_at).total_seconds() if j.created_at else 0
            if age > max_age_sec:
                j.status = "failed"
                j.error_message = "Stale — timed out after %ds" % max_age_sec
                j.completed_at = cutoff
                log.warning("Marked stale ScanJob %d", j.id)
        db.commit()
    finally:
        db.close()
