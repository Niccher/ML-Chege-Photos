from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import FaceCluster
from app.models.schemas import FaceClusterOut, MergeClustersRequest, SplitClusterRequest
from app.services.face import merge_clusters, split_cluster

log = logging.getLogger("ml_chege_photos.api_clusters")
router = APIRouter(prefix="/api/v1/clusters", tags=["clusters"])


@router.get("")
def list_clusters(db: Session = Depends(get_db)):
    clusters = db.query(FaceCluster).order_by(FaceCluster.id).all()
    return {
        "clusters": [FaceClusterOut.model_validate(c).model_dump() for c in clusters],
    }


@router.get("/{cluster_id}")
def get_cluster(cluster_id: int, db: Session = Depends(get_db)):
    cluster = db.query(FaceCluster).filter(FaceCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(404, f"FaceCluster {cluster_id} not found")
    return FaceClusterOut.model_validate(cluster).model_dump()


@router.post("/{cluster_id}/merge")
def merge_clusters_endpoint(
    cluster_id: int,
    body: MergeClustersRequest,
    db: Session = Depends(get_db),
):
    if body.source_cluster_id == body.target_cluster_id:
        raise HTTPException(400, "Cannot merge a cluster with itself")

    try:
        result = merge_clusters(body.source_cluster_id, body.target_cluster_id, db)
        return {"status": "success", "data": result}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/{cluster_id}/split")
def split_cluster_endpoint(
    cluster_id: int,
    body: Optional[SplitClusterRequest] = None,
    db: Session = Depends(get_db),
):
    try:
        result = split_cluster(cluster_id, db)
        return {"status": "success", "data": result}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
