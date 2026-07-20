from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from qdrant_client import QdrantClient

from app.config import settings

# ── SQLAlchemy ──────────────────────────────────────────────────

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a session, closes on teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Qdrant ──────────────────────────────────────────────────────

_qdrant_client: QdrantClient | None = None


def get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            prefer_grpc=False,
        )
    return _qdrant_client


def ensure_qdrant_collection():
    """Create the face_embeddings collection on startup if it doesn't exist."""
    client = get_qdrant()
    collections = client.get_collections().collections
    existing = {c.name for c in collections}

    if settings.qdrant_collection not in existing:
        from qdrant_client.models import VectorParams, Distance

        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=512, distance=Distance.COSINE),
        )
