from __future__ import annotations

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, create_engine, Text,
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.sql import func
from qdrant_client import QdrantClient

from app.config import settings

# ── SQLAlchemy ──────────────────────────────────────────────────

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)


# ── Models ──────────────────────────────────────────────────────


class FaceEncoding(Base):
    __tablename__ = "face_encoding"

    id = Column(Integer, primary_key=True)
    photo_id = Column(Integer, nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=True, index=True)
    qdrant_point_id = Column(String(36), unique=True, nullable=False)
    bbox_x = Column(Float, nullable=False)
    bbox_y = Column(Float, nullable=False)
    bbox_w = Column(Float, nullable=False)
    bbox_h = Column(Float, nullable=False)
    landmark_left_eye_x = Column(Float, nullable=True)
    landmark_left_eye_y = Column(Float, nullable=True)
    landmark_right_eye_x = Column(Float, nullable=True)
    landmark_right_eye_y = Column(Float, nullable=True)
    landmark_nose_x = Column(Float, nullable=True)
    landmark_nose_y = Column(Float, nullable=True)
    landmark_left_mouth_x = Column(Float, nullable=True)
    landmark_left_mouth_y = Column(Float, nullable=True)
    landmark_right_mouth_x = Column(Float, nullable=True)
    landmark_right_mouth_y = Column(Float, nullable=True)
    detection_score = Column(Float, nullable=True)
    face_image_path = Column(String(500), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    person = relationship("Person", back_populates="faces",
                          foreign_keys=[person_id])


class Person(Base):
    __tablename__ = "person"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=True)
    thumbnail_face_id = Column(Integer, ForeignKey("face_encoding.id"), nullable=True)
    cluster_label = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    faces = relationship("FaceEncoding", back_populates="person",
                         foreign_keys=[FaceEncoding.person_id])


# ── Qdrant ──────────────────────────────────────────────────────

_qdrant_client: QdrantClient | None = None


def get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _qdrant_client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                prefer_grpc=False,
            )
    return _qdrant_client


def ensure_qdrant_collection():
    client = get_qdrant()
    collections = client.get_collections().collections
    existing = {c.name for c in collections}

    if settings.qdrant_collection not in existing:
        from qdrant_client.models import VectorParams, Distance

        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=512, distance=Distance.COSINE),
        )
