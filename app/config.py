from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────
    db_host: str = "mysql"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "root_password"
    db_name: str = "ml_chege_photos"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    # ── Qdrant ──────────────────────────────────────────────────
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "face_embeddings"

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    # ── Model pack ──────────────────────────────────────────────
    face_model_pack: str = "buffalo_l"
    face_det_thresh: float = 0.5

    # ── CLIP / Semantic Search ──────────────────────────────────
    clip_model_name: str = "openai/clip-vit-base-patch32"
    qdrant_photo_collection: str = "photo_embeddings"

    # ── Object Detection ────────────────────────────────────────
    object_det_threshold: float = 0.5

    # ── Sensitive attributes ────────────────────────────────────
    include_sensitive_attributes: bool = False

    # ── Clustering ──────────────────────────────────────────────
    hdbscan_min_cluster_size: int = 2
    hdbscan_min_samples: int = 1
    cluster_metric: str = "cosine"

    # Incremental clustering
    # Confidence (cosine similarity) required to immediately assign a new face
    # to an existing centroid without waiting for a full HDBSCAN run.
    incremental_centroid_threshold: float = 0.80
    # When the number of unassigned faces exceeds this, trigger a full sweep.
    incremental_unassigned_trigger: int = 50

    # ── Scan timeouts ───────────────────────────────────────────
    scan_stale_timeout_sec: int = 300

    # ── Server ──────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    # ── Security ────────────────────────────────────────────────
    ml_api_key: str = "my_super_secret_shared_token_key_123!"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
