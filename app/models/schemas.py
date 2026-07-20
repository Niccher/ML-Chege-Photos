from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── PhotoScan ────────────────────────────────────────────────────


class PhotoScanCreate(BaseModel):
    photo_id: int


class PhotoScanOut(BaseModel):
    id: int
    photo_id: int
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    face_count: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── ScanJob ──────────────────────────────────────────────────────


class ScanJobCreate(BaseModel):
    photo_ids: Optional[list[int]] = None


class ScanJobOut(BaseModel):
    id: int
    status: str
    total_photos: int
    processed: int
    failed: int
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Face Cluster ─────────────────────────────────────────────────


class FaceClusterOut(BaseModel):
    id: int
    person_id: int
    centroid_point_id: Optional[str] = None
    merged_from: Optional[list[int]] = None
    split_from: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MergeClustersRequest(BaseModel):
    source_cluster_id: int
    target_cluster_id: int


class SplitClusterRequest(BaseModel):
    new_cluster_label: Optional[int] = None


# ── Reclassify ───────────────────────────────────────────────────


class ReclassifyResponse(BaseModel):
    face_id: int
    previous_cluster_id: Optional[int] = None
    new_cluster_id: Optional[int] = None
    message: str
