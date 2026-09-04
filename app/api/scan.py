from __future__ import annotations

import logging
from typing import Optional
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import PhotoScan, ScanJob
from app.models.schemas import PhotoScanOut, ScanJobOut, ScanJobCreate
from app.services.scan import scan_photo, create_scan_job, run_scan_job, cleanup_stale_scans

log = logging.getLogger("ml_chege_photos.api_scan")
router = APIRouter(prefix="/api/v1/scan", tags=["scan"])


@router.post("/{photo_id}", status_code=202)
def scan_single_photo(photo_id: int, db: Session = Depends(get_db)):
    existing = db.query(PhotoScan).filter(PhotoScan.photo_id == photo_id).first()
    if existing and existing.status == "completed":
        return {
            "status": "already_scanned",
            "photo_scan_id": existing.id,
            "face_count": existing.face_count,
        }

    thread = Thread(target=scan_photo, args=(photo_id,), daemon=True)
    thread.start()

    return {
        "status": "accepted",
        "photo_id": photo_id,
        "message": "Scan started",
    }


@router.get("/{photo_id}/status")
def scan_status(photo_id: int, db: Session = Depends(get_db)):
    scan = db.query(PhotoScan).filter(PhotoScan.photo_id == photo_id).first()
    if not scan:
        raise HTTPException(404, f"No scan found for photo {photo_id}")
    return PhotoScanOut.model_validate(scan).model_dump()


@router.post("", status_code=202)
def start_batch_scan(
    body: Optional[ScanJobCreate] = None,
    db: Session = Depends(get_db),
):
    photo_ids = body.photo_ids if body else None
    job = create_scan_job(photo_ids)

    thread = Thread(target=run_scan_job, args=(job.id,), daemon=True)
    thread.start()

    return {
        "status": "accepted",
        "scan_job_id": job.id,
        "total_photos": job.total_photos,
    }


@router.get("/batch/{job_id}/status")
def batch_scan_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(404, f"ScanJob {job_id} not found")
    return ScanJobOut.model_validate(job).model_dump()


@router.post("/reap-stale")
def reap_stale_scans_endpoint(max_age_sec: int = 300):
    """Reaps any scan tasks stuck in processing state for longer than max_age_sec."""
    result = cleanup_stale_scans(max_age_sec=max_age_sec)
    return {
        "status": "success",
        "message": f"Reaped {result['reaped_scans']} stale scans and {result['reaped_jobs']} stale jobs.",
        "data": result,
    }


@router.post("/retry-failed")
async def retry_failed_scans_endpoint(db: Session = Depends(get_db)):
    """Re-enqueues all failed photo scans into the background worker queue."""
    from app.ml.queue import ml_job_queue
    from app.api.faces import process_photo_pipeline_queued

    failed = db.query(PhotoScan).filter(PhotoScan.status == "failed").all()
    if not failed:
        return {"status": "success", "message": "No failed scans to retry", "retried": 0}

    count = 0
    for s in failed:
        s.status = "pending"
        s.error_message = None
        await ml_job_queue.add_job(
            process_photo_pipeline_queued,
            photo_id=s.photo_id,
            scan_faces=True,
            scan_tags=True,
            scan_clip=True,
        )
        count += 1
    db.commit()

    return {
        "status": "success",
        "retried": count,
        "message": f"Re-queued {count} failed scans for background processing.",
    }

