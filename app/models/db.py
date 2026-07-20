from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func

from app.database import Base


class PhotoScan(Base):
    __tablename__ = "photo_scan"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, nullable=False, index=True, unique=True)
    status = Column(String(20), nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    face_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ScanJob(Base):
    __tablename__ = "scan_job"

    id = Column(Integer, primary_key=True)
    status = Column(String(20), nullable=False, default="pending")
    total_photos = Column(Integer, nullable=False, default=0)
    processed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class FaceCluster(Base):
    __tablename__ = "face_cluster"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False, index=True)
    centroid_point_id = Column(String(36), nullable=True, unique=True)
    merged_from = Column(JSON, nullable=True)
    split_from = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
