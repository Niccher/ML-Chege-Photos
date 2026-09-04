from __future__ import annotations

from pydantic_settings import BaseSettings

_ACTIVE_DYNAMIC_WEBAPP_URL: str | None = None


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
        import os
        return (
            self.mysqlhost
            or os.getenv("MYSQLHOST")
            or ("mysql.railway.internal" if (os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID")) else self.db_host)
        )

    @property
    def effective_db_port(self) -> int:
        import os
        return self.mysqlport or (int(os.getenv("MYSQLPORT")) if os.getenv("MYSQLPORT") else self.db_port)

    @property
    def effective_db_user(self) -> str:
        import os
        return self.mysqluser or os.getenv("MYSQLUSER") or self.db_user

    @property
    def effective_db_password(self) -> str:
        import os
        return self.mysqlpassword or os.getenv("MYSQLPASSWORD") or self.db_password

    @property
    def effective_db_name(self) -> str:
        import os
        return (
            self.mysqldatabase
            or os.getenv("MYSQLDATABASE")
            or ("railway" if (os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID")) else self.db_name)
        )

    @property
    def database_url(self) -> str:
        import os
        raw_url = os.getenv("MYSQL_URL") or os.getenv("DATABASE_URL")
        if raw_url:
            if raw_url.startswith("mysql://"):
                raw_url = "mysql+pymysql://" + raw_url[len("mysql://"):]
            if "?" not in raw_url:
                raw_url += "?charset=utf8mb4"
            return raw_url

        return (
            f"mysql+pymysql://{self.effective_db_user}:{self.effective_db_password}"
            f"@{self.effective_db_host}:{self.effective_db_port}/{self.effective_db_name}?charset=utf8mb4"
        )

    # ── Storage & Inter-service ─────────────────────────────────
    uploads_dir: str = "/app/uploads"
    webapp_url: str | None = None
    ml_concurrent_workers: int = 4

    def set_dynamic_webapp_url(self, url: str | None) -> None:
        """Dynamically record the WebApp URL passed via request headers or body."""
        global _ACTIVE_DYNAMIC_WEBAPP_URL
        if not url:
            return
        clean = str(url).strip().rstrip("/")
        if clean and not clean.startswith(("http://", "https://")):
            clean = "https://" + clean
        if clean:
            _ACTIVE_DYNAMIC_WEBAPP_URL = clean

    @property
    def effective_webapp_url(self) -> str | None:
        """Return the webapp URL to download photos from, with dynamic & Railway auto-discovery."""
        import os
        import socket

        # 1. Dynamically learned URL from incoming request header/body (highest priority)
        global _ACTIVE_DYNAMIC_WEBAPP_URL
        if _ACTIVE_DYNAMIC_WEBAPP_URL:
            return _ACTIVE_DYNAMIC_WEBAPP_URL

        # 2. Explicit config or environment variable (supports Railway ${{...}} reference)
        raw_url = self.webapp_url or os.getenv("WEBAPP_URL")
        if raw_url:
            clean = raw_url.strip().rstrip("/")
            if not clean.startswith(("http://", "https://")):
                clean = "https://" + clean
            return clean

        # 3. Railway private mesh DNS candidate discovery
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"):
            candidates = [
                "chege-photos-webapp.railway.internal",
                "chege-photos-webapp",
                "webapp.railway.internal",
                "web.railway.internal",
            ]
            for host in candidates:
                try:
                    socket.getaddrinfo(host, 80)
                    return f"http://{host}:80"
                except Exception:
                    pass

            # 4. Fallback to default known production URL on Railway
            return "https://chege-photos-webapp-production.up.railway.app"

        return None

    # ── Qdrant ──────────────────────────────────────────────────
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "face_embeddings"

    @property
    def effective_qdrant_host(self) -> str:
        import os
        import socket
        from urllib.parse import urlparse

        q_url = os.getenv("QDRANT_URL")
        if q_url:
            parsed = urlparse(q_url)
            if parsed.hostname:
                return parsed.hostname

        if os.getenv("QDRANT_HOST"):
            return os.getenv("QDRANT_HOST")

        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"):
            candidates = [
                "ml-qdrant.railway.internal",
                "qdrant.railway.internal",
                "ml-qdrant",
                "qdrant"
            ]
            for host in candidates:
                try:
                    socket.getaddrinfo(host, 6333)
                    return host
                except Exception:
                    pass
            return "ml-qdrant.railway.internal"

        return self.qdrant_host

    @property
    def effective_qdrant_port(self) -> int:
        import os
        from urllib.parse import urlparse

        q_url = os.getenv("QDRANT_URL")
        if q_url:
            parsed = urlparse(q_url)
            if parsed.port:
                return parsed.port

        return int(os.getenv("QDRANT_PORT") or self.qdrant_port)

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.effective_qdrant_host}:{self.effective_qdrant_port}"

    # ── Model pack ──────────────────────────────────────────────
    face_model_pack: str = "buffalo_l"
    face_det_thresh: float = 0.5

    # ── CLIP / Semantic Search ──────────────────────────────────
    clip_model_name: str = "openai/clip-vit-base-patch32"
    qdrant_photo_collection: str = "photo_embeddings"

    # ── Object Detection ────────────────────────────────────────
    object_det_threshold: float = 0.5

    # ── Sensitive attributes ────────────────────────────────────
    include_sensitive_attributes: bool = True

    # ── Clustering ──────────────────────────────────────────────
    hdbscan_min_cluster_size: int = 2
    hdbscan_min_samples: int = 2
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
