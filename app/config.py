from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────
    db_host: str = "mysql"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "root_password"
    db_name: str = "ml_chege_photos"

    # Railway MySQL fallbacks
    mysqlhost: str | None = None
    mysqlport: int | None = None
    mysqluser: str | None = None
    mysqlpassword: str | None = None
    mysqldatabase: str | None = None

    @property
    def effective_db_host(self) -> str:
        return self.mysqlhost or self.db_host

    @property
    def effective_db_port(self) -> int:
        return self.mysqlport or self.db_port

    @property
    def effective_db_user(self) -> str:
        return self.mysqluser or self.db_user

    @property
    def effective_db_password(self) -> str:
        return self.mysqlpassword or self.db_password

    @property
    def effective_db_name(self) -> str:
        return self.mysqldatabase or self.db_name

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.effective_db_user}:{self.effective_db_password}"
            f"@{self.effective_db_host}:{self.effective_db_port}/{self.effective_db_name}?charset=utf8mb4"
        )

    # ── Storage & Inter-service ─────────────────────────────────
    uploads_dir: str = "/app/uploads"
    webapp_url: str | None = None

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
