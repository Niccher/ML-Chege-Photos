# Configuration Reference (ML Service)

Complete guide to environment variables controlling the FastAPI ML microservice, neural network weights, and Qdrant integration.

---

## 1. Core Service Settings

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `production` | Environment mode (`development` or `production`). |
| `API_KEY` | *None* | Shared secret key required in the `X-API-KEY` header for all requests. |
| `PORT` | `9051` | Port on which the Uvicorn ASGI server listens. |
| `LOG_LEVEL` | `info` | Logging verbosity (`debug`, `info`, `warning`, `error`). |

---

## 2. Database & Vector Store Settings

| Variable | Railway Mapping | Default | Description |
|---|---|---|---|
| `DB_HOST` | `MYSQLHOST` | `mysql` | Shared MySQL server hostname. |
| `DB_PORT` | `MYSQLPORT` | `3306` | MySQL port. |
| `DB_USER` | `MYSQLUSER` | `root` | MySQL user. |
| `DB_PASSWORD` | `MYSQLPASSWORD` | `root_password` | MySQL password. |
| `DB_NAME` | `MYSQLDATABASE` | `db_chege_photos` | MySQL database name. |
| `QDRANT_HOST` | `QDRANT_HOST` | `qdrant` | Qdrant server hostname. |
| `QDRANT_PORT` | `QDRANT_PORT` | `6333` | Qdrant REST port. |
| `QDRANT_COLLECTION` | *None* | `face_embeddings` | Name of the primary face vector collection. |

---

## 3. Model Inference & Thresholds

| Variable | Default | Description |
|---|---|---|
| `MODEL_NAME` | `buffalo_l` | InsightFace model pack (`buffalo_l`, `buffalo_m`, `buffalo_s`). |
| `DET_THRESH` | `0.5` | Minimum confidence score for RetinaFace bounding box detection. |
| `SIMILARITY_THRESHOLD` | `0.65` | Cosine similarity threshold for identity matching. |
| `ENABLE_CLIP` | `true` | Enables OpenAI CLIP semantic search and visual similarity indexing. |
| `ENABLE_YOLO` | `true` | Enables YOLOv8 automated object detection. |
| `UPLOADS_PATH` | `/var/www/html/public/uploads` | Path to shared photos directory on local container disk. |
