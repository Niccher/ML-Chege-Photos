from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func

from app.database import Base


class PhotoScan(Base):
    __tablename__ = "tbl_photo_scan"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, nullable=False, index=True, unique=True)
    status = Column(String(20), nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    face_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ScanJob(Base):
    __tablename__ = "tbl_scan_job"

    id = Column(Integer, primary_key=True)
    status = Column(String(20), nullable=False, default="pending")
    total_photos = Column(Integer, nullable=False, default=0)
    processed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class FaceCluster(Base):
    __tablename__ = "tbl_face_cluster"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("tbl_person.id"), nullable=False, index=True)
    centroid_point_id = Column(String(36), nullable=True, unique=True)
    merged_from = Column(JSON, nullable=True)
    split_from = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class FaceAnnotation(Base):
    """Human-in-the-loop refinement: a user's confirmed or rejected assignment
    of a face to a person. Rows with action='confirm' act as hard constraints
    during clustering (the face is pinned to that person and never moved).
    Rows with action='reject' prevent the face from being re-assigned to that
    person by future HDBSCAN runs.
    """
    __tablename__ = "tbl_face_annotation"

    id = Column(Integer, primary_key=True)
    face_encoding_id = Column(
        Integer, ForeignKey("tbl_face_encoding.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    person_id = Column(
        Integer, ForeignKey("tbl_person.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # 'confirm' — user says this face IS this person (pin)
    # 'reject'  — user says this face is NOT this person
    action = Column(String(10), nullable=False)
    annotated_by = Column(Integer, nullable=True)   # webapp user_id
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

