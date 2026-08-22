<div align="center">

# ML Chege Photos

Face detection, embedding, clustering, and attribute classification service for the Chege Photos ecosystem.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009688?style=for-the-badge&logo=fastapi)
![Insightface](https://img.shields.io/badge/Insightface-1.0.1-FF6F00?style=for-the-badge)
![Qdrant](https://img.shields.io/badge/Qdrant-1.13.2-FF6600?style=for-the-badge&logo=qdrant)
![MySQL](https://img.shields.io/badge/MySQL-8.4-4479A1?style=for-the-badge&logo=mysql)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

</div>

---

## About the Project

ML Chege Photos is a FastAPI microservice that provides ML-powered face analysis — detection, 512-dimensional embedding extraction, age/gender estimation, and HDBSCAN clustering — to the Chege Photos web and Android applications. It uses Insightface (Buffalo-L / ResNet-100 backbone) for detection and embedding, stores vectors in Qdrant for sub-second cosine-similarity search, and persists face metadata in a shared MySQL database alongside the web app. It is one of three sibling repos: [Chege Photos WebApp](https://github.com/niccher/Chege-Photos-WebApp) (PHP/CodeIgniter 4), [Chege Photos Android App](https://github.com/niccher/Chege-Photos-Android), and this ML service.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          Docker  (hosts-shared-network)                     │
│                                                                            │
│  ┌────────────────┐   HTTPS/JSON    ┌──────────────────┐   gRPC/HTTP      │
│  │  Chege Photos  │ ───────────────▶│  ML Chege Photos │ ────────────────▶│
│  │  Web App       │                 │  (FastAPI)        │                  │
│  │  (CI4, PHP)    │ ◀───────────────│  port 9051        │                  │
│  │  port 9005     │   JSON response │                   │                  │
│  └───────┬────────┘                 └────────┬─────────┘                  │
│          │                                    │                            │
│          │                          ┌─────────▼─────────┐                 │
│          │                          │  MySQL 8.4         │                 │
│          └─────────────────────────▶│  (Shared DB)       │                 │
│                                     │  db_chege_photos   │                 │
│                                     │  port 3306         │                 │
│  ┌────────────────┐    HTTPS/JSON   └───────────────────┘                 │
│  │  Android App   │ ───────────────▶  ML Chege Photos                      │
│  │  (Kotlin)      │ ◀───────────────  (same endpoints)                     │
│  └────────────────┘                                                        │
└────────────────────────────────────────────────────────────────────────────┘

      ┌──────────────┐     🔁 scroll + upsert      ┌──────────────────┐
      │  Qdrant       │ ◀──────────────────────────▶│  ML Chege Photos │
      │  (Vector DB)  │    POST /cluster, /encode   │                  │
      │  HTTP 9052    │                              │                  │
      │  gRPC 9053    │                              │                  │
      └──────────────┘                              └──────────────────┘
```

**Data flow:**

1. User uploads a photo via the web or Android app → the app calls `POST /api/v1/faces/encode` with the `photo_id`
2. The ML service reads the photo file from a read-only mount of the web app's `public/uploads` directory
3. Insightface detects faces and extracts 512-d embeddings (Buffalo-L / ArcFace)
4. Embeddings are stored in **Qdrant** (for similarity search); face metadata (bbox, landmarks, age, gender) is stored in **MySQL** (`face_encoding` table)
5. A periodic scan pipeline (`POST /api/v1/scan`) processes un-scanned photos in batch with progress tracking
6. At any point, `POST /api/v1/faces/cluster` runs HDBSCAN across all embeddings to auto-discover persons and populate the `person` table
7. The web/Android app queries `/api/v1/faces/by-photo/{id}` for face thumbnails or `/api/v1/faces/search` for similarity search

---

## Machine Learning / Algorithms

### Detection & Classification Categories

| Feature | What is detected / estimated | Used for |
|---|---|---|
| Face detection | Bounding boxes + 5 landmarks (eyes, nose, mouth corners) | Cropping face thumbnails, overlay on photo viewer |
| Face embedding | 512-dimensional vector (ArcFace loss) | Similarity search, clustering, person identification |
| Age (optional) | Regression value (integer years) | Display on face cards, filtering |
| Gender (optional) | Binary (Male / Female) | Display on face cards, filtering |

### Algorithms

| Algorithm | Library / Method | Mechanism |
|---|---|---|
| Face detection | Insightface `RetinaFace` (MobileNet0.25 backbone) | Single-shot dense detector; threshold configurable via `FACE_DET_THRESH` (default 0.5) |
| Embedding generation | Insightface `Buffalo-L` (ResNet-100 + ArcFace) | 512-d embedding via ArcFace additive angular margin loss; trained on MS1MV3 (5.8M images, 93K IDs) |
| Clustering | `sklearn.cluster.HDBSCAN` | Hierarchical density-based clustering; parameters: `min_cluster_size=2`, `min_samples=1`, `metric=cosine` |
| Similarity search | Qdrant `cosine` distance + ANN index | Sub-second approximate nearest neighbour search; scores range 0.0 (identical) to 2.0 (orthogonal) |
| Centroid computation | NumPy `mean` per cluster | Arithmetic mean of all face embeddings assigned to a cluster; stored in separate `_centroids` Qdrant collection |
| Age / gender (optional) | Insightface attribute heads | Gated by `INCLUDE_SENSITIVE_ATTRIBUTES` env var |

### ML vs Heuristic

| Capability | Heuristic / EXIF-only | ML (this service) |
|---|---|---|
| Works across varied poses, occlusion, lighting | No | Yes — ArcFace is pose/illumination-invariant |
| Automatic person grouping | Manual albums only | HDBSCAN unsupervised clustering |
| Similarity search ("find this face") | Not possible | Sub-second cosine ANN search in Qdrant |
| Per-face granularity | Photo-level tags | Per-bbox embedding and metadata |
| Age / gender estimation | Not possible | Insightface attribute heads |
| Group photo handling | Single tag per photo | All faces indexed independently |

---

## Features

### Face Detection & Encoding
- **Detect faces** — RetinaFace detector with configurable confidence threshold; returns bounding boxes, 5-point landmarks, and detection scores
- **Extract embeddings** — 512-dimensional vectors via ArcFace (Buffalo-L) for each detected face
- **Bulk encode** — Single-endpoint call (`POST /encode`) that detects, embeds, and persists to both Qdrant and MySQL for a given `photo_id`
- **Re-classify** — `POST /faces/{id}/reclassify` re-runs HDBSCAN for a single face, reassigning it to the best-matching cluster

### Similarity Search
- **Search by example** — Upload a query image; returns top-N most similar faces from the entire Qdrant index, annotated with person name and photo ID
- **Per-photo listing** — `GET /by-photo/{id}` returns all faces for a given photo with bounding boxes, attributes, and person assignment

### Clustering & Person Management
- **Auto-cluster** — `POST /cluster` scrolls all embeddings from Qdrant, runs HDBSCAN, creates `person` rows, and assigns faces to persons
- **Merge persons** — Combine two persons into one; all source faces reassigned to target, centroid recomputed
- **Split cluster** — Re-cluster faces within a single person to split into sub-persons
- **Centroid storage** — Cluster centroids stored in a dedicated Qdrant `face_embeddings_centroids` collection for fast person-level similarity

### Scan Orchestration
- **Single scan** — `POST /scan/{photo_id}` triggers immediate scan of one photo, runs in background thread, with status tracking
- **Batch scan** — `POST /scan` accepts optional list of `photo_ids`; creates a `ScanJob` and processes photos asynchronously with progress counters
- **Stale cleanup** — Background task runs every 60 seconds, automatically fails scans stuck in "processing" state beyond `SCAN_STALE_TIMEOUT_SEC`

### Health & Observability
- **Health endpoint** — `GET /health` reports DB, Qdrant, and model-loading status in a single JSON response
- **Graceful degradation** — Service starts even if MySQL or Qdrant is temporarily unavailable; degraded status reported via health check
- **GPU fallback** — Attempts CUDA execution provider first; falls back to CPU if GPU is unavailable

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.115.6 (Python 3.12) |
| ASGI server | Uvicorn 0.34.0 |
| ORM | SQLAlchemy 2.0.36 + PyMySQL 1.1.1 |
| Vector database | Qdrant 1.13.2 (client) / `qdrant/qdrant:latest` (server) |
| Face model | Insightface 1.0.1 (Buffalo-L, ResNet-100 + ArcFace + RetinaFace) |
| Clustering | scikit-learn 1.9.0 (HDBSCAN) |
| Image processing | OpenCV 5.0.0, Pillow 12.3.0, NumPy 2.5.1 |
| Containerization | Docker + Compose (Python 3.12-slim base) |
| Migrations | Alembic |

---

## Prerequisites

- Docker ≥ 24.0
- Docker Compose ≥ 2.20
- A shared Docker network `hosts-shared-network` (created once via `docker network create hosts-shared-network`)

---

## Installation & Setup

### Docker (recommended)

```bash
# From the hosts/ root (alongside sibling repos):
docker compose up --build -d ml-service ml-qdrant

# Or standalone from this directory:
docker compose up --build -d
```

The Compose file defines two services:

| Service | Container name | Host port | Purpose |
|---|---|---|---|
| `ml-service` | `ml-chege-photos` | 9051 | FastAPI app (container port 8000) |
| `ml-qdrant` | `ml-qdrant` | 9052 (HTTP), 9053 (gRPC) | Qdrant vector database |

The ML service mounts the web app's uploads directory read-only (`../Chege Photos WebApp/public/uploads:/app/uploads:ro`) for direct file access. Model weights are cached in a named volume (`insightface_models`) to avoid re-downloading on container restart.

### Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env with your DB credentials, Qdrant host, and model settings
```

### Verification

```bash
curl http://localhost:9051/health
```

Expected response:
```json
{
  "status": "healthy",
  "db_connected": true,
  "qdrant_connected": true,
  "models_loaded": true
}
```

---

## Database Configuration

### MySQL (`db_chege_photos`)

#### `face_encoding` — one row per detected face instance

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK) | Auto-increment |
| `photo_id` | INT (indexed) | FK to `db_chege_photos.photos` (shared web app DB) |
| `person_id` | INT (FK → `person.id`, nullable, indexed) | Assigned person; null until clustering |
| `qdrant_point_id` | VARCHAR(36) (unique) | UUID linking to Qdrant point |
| `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h` | FLOAT | Bounding box in pixels |
| `landmark_*` | FLOAT (×10) | 5 facial landmarks: left/right eye, nose, left/right mouth corner |
| `detection_score` | FLOAT | RetinaFace confidence score |
| `face_image_path` | VARCHAR(500) | Cropped face thumbnail path |
| `age` | INT (nullable) | Estimated age (gated by `INCLUDE_SENSITIVE_ATTRIBUTES`) |
| `gender` | VARCHAR(10) (nullable) | "Male" / "Female" |
| `created_at` | DATETIME | Server default `now()` |

#### `person` — one row per discovered person

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK) | Auto-increment |
| `name` | VARCHAR(255) (nullable) | User-assigned name |
| `thumbnail_face_id` | INT (FK → `face_encoding.id`, nullable) | Representative face for thumbnails |
| `cluster_label` | INT (nullable) | HDBSCAN cluster label |
| `created_at` | DATETIME | Server default `now()` |
| `updated_at` | DATETIME | Auto-updates on change |

#### `photo_scan` — per-photo scan status (via `app/api/scan.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK) | Auto-increment |
| `photo_id` | INT (unique, indexed) | FK to `db_chege_photos.photos` |
| `status` | VARCHAR(20) | `pending`, `processing`, `completed`, `failed` |
| `started_at` | DATETIME (nullable) | When scan began |
| `completed_at` | DATETIME (nullable) | When scan finished |
| `error_message` | TEXT (nullable) | Error details on failure |
| `face_count` | INT (nullable) | Number of faces detected |
| `created_at` | DATETIME | Server default `now()` |

#### `scan_job` — batch scan jobs

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK) | Auto-increment |
| `status` | VARCHAR(20) | `pending`, `running`, `completed`, `failed` |
| `total_photos` | INT | Number of photos to scan |
| `processed` | INT | Completed so far |
| `failed` | INT | Failed so far |
| `created_at` | DATETIME | Server default `now()` |
| `completed_at` | DATETIME (nullable) | When the job finished |
| `error_message` | TEXT (nullable) | Overall error if job failed |

#### `face_cluster` — centroid storage and lineage

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK) | Auto-increment |
| `person_id` | INT (FK → `person.id`, indexed) | Associated person |
| `centroid_point_id` | VARCHAR(36) (unique, nullable) | Qdrant point ID in `_centroids` collection |
| `merged_from` | JSON (nullable) | Array of source cluster IDs if this cluster was created by a merge |
| `split_from` | INT (nullable) | Source cluster ID if this cluster was created by a split |
| `created_at` | DATETIME | Server default `now()` |

### Qdrant Collections

| Collection | Vector size | Distance | Purpose |
|---|---|---|---|
| `face_embeddings` | 512 | Cosine | All face embeddings |
| `face_embeddings_centroids` | 512 | Cosine | Cluster centroids (one per person) |

---

## Usage / Routes / API Reference

All endpoints prefixed with `/api/v1/faces` unless noted.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness / readiness check (DB, Qdrant, models) |
| `POST` | `/api/v1/faces/detect` | Detect faces in uploaded image (no persistence) |
| `POST` | `/api/v1/faces/embed` | Extract 512-d embedding from uploaded face crop |
| `POST` | `/api/v1/faces/encode` | Detect + embed + persist to Qdrant + MySQL for a `photo_id` |
| `POST` | `/api/v1/faces/search` | Upload query image, return top-N similar faces |
| `POST` | `/api/v1/faces/cluster` | HDBSCAN cluster all embeddings, create persons |
| `GET` | `/api/v1/faces/by-photo/{photo_id}` | List faces for a photo (bbox, attributes, person) |
| `GET` | `/api/v1/faces/persons` | List all persons with face count and thumbnail |
| `PUT` | `/api/v1/faces/persons/{person_id}` | Update person name / thumbnail |
| `POST` | `/api/v1/faces/persons/merge` | Merge two persons into one |
| `GET` | `/api/v1/faces/unassigned` | List unassigned faces |
| `POST` | `/api/v1/faces/delete-by-photo-ids` | Bulk delete faces by photo IDs (cleans encodings, Qdrant points, persons, clusters, centroids, scans) |
| `POST` | `/api/v1/faces/{face_id}/reclassify` | Re-run HDBSCAN for a single face |
| `DELETE` | `/api/v1/faces/reset` | Wipe all face data and recreate Qdrant collection |
| `POST` | `/api/v1/scan/{photo_id}` | Trigger single-photo scan (async) |
| `GET` | `/api/v1/scan/{photo_id}/status` | Poll scan status for a photo |
| `POST` | `/api/v1/scan` | Start batch scan (with optional photo_ids filter) |
| `GET` | `/api/v1/scan/batch/{job_id}/status` | Poll batch scan job status |
| `GET` | `/api/v1/clusters` | Get all face clusters |
| `GET` | `/api/v1/clusters/{id}` | Get cluster details |
| `POST` | `/api/v1/clusters/{id}/merge` | Merge source cluster into target |
| `POST` | `/api/v1/clusters/{id}/split` | Split cluster into sub-clusters |
| `POST` | `/models/reload` | Dynamically reload model pack weights in memory without container restarts |
| `GET` | `/api/v1/search/semantic` | Query photos using natural language text search (CLIP) |

---

## Project Structure

```
ML Chege Photos/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, lifespan, router registration
│   ├── config.py            # Pydantic Settings (reads .env)
│   ├── database.py          # SQLAlchemy engine, Qdrant client, FaceEncoding + Person models
│   ├── api/
│   │   ├── health.py        # GET /health endpoint
│   │   ├── faces.py         # 13 face endpoints (detect, embed, encode, search, cluster, ...)
│   │   ├── scan.py          # Scan orchestration endpoints
│   │   ├── clusters.py      # Cluster CRUD + merge/split endpoints
│   │   └── search.py        # Semantic search endpoints (CLIP)
│   ├── ml/
│   │   ├── loader.py        # Insightface model loading (GPU → CPU fallback)
│   │   ├── attributes.py    # Age / gender extraction
│   │   ├── clustering.py    # HDBSCAN, centroid compute/store/clear
│   │   ├── object_detection.py # YOLOv8 object detection via OpenCV DNN
│   │   ├── semantic_search.py # CLIP model text/image embedding generator
│   │   └── queue.py         # JobQueue async background execution runner
│   ├── models/
│   │   ├── db.py            # PhotoScan, ScanJob, FaceCluster ORM models
│   │   └── schemas.py       # Pydantic request/response models
│   ├── services/
│   │   ├── scan.py          # Single/batch scan orchestration, stale cleanup
│   │   └── face.py          # Reclassify, merge clusters, split cluster
│   └── migrations/
│       ├── env.py           # Alembic env
│       ├── script.py.mako   # Alembic template
│       └── versions/
│           └── 001_initial.py  # Creates photo_scan, scan_job, face_cluster
├── Dockerfile               # Python 3.12-slim, offline wheel install
├── docker-compose.yml       # ml-service + ml-qdrant
├── requirements.txt         # Combined core + ML dependencies
├── requirements-core.txt    # API, DB, Qdrant client
├── requirements-ml.txt      # NumPy, Insightface, HDBSCAN, scikit-learn
├── alembic.ini              # Alembic configuration
├── wheels/                  # Vendored .whl files (offline builds)
├── .env.example             # Documented environment template
└── .env                     # Runtime configuration (git-ignored)
```

---

## Configuration / Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `mysql` | MySQL hostname (Docker service name) |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | `root_password` | MySQL password |
| `DB_NAME` | `db_chege_photos` | MySQL database name (shared with the web app) |
| `QDRANT_HOST` | `qdrant` | Qdrant hostname (Docker service name) |
| `QDRANT_PORT` | `6333` | Qdrant gRPC/HTTP port |
| `QDRANT_COLLECTION` | `face_embeddings` | Qdrant collection name |
| `FACE_MODEL_PACK` | `buffalo_l` | Insightface model pack (e.g. `buffalo_l`, `buffalo_sc`) |
| `FACE_DET_THRESH` | `0.5` | Detection confidence threshold (0.0–1.0) |
| `INCLUDE_SENSITIVE_ATTRIBUTES` | `false` | Enable age/gender estimation |
| `HDBSCAN_MIN_CLUSTER_SIZE` | `2` | Minimum cluster size for HDBSCAN |
| `HDBSCAN_MIN_SAMPLES` | `1` | Minimum samples parameter for HDBSCAN |
| `CLUSTER_METRIC` | `cosine` | Distance metric for clustering |
| `SCAN_STALE_TIMEOUT_SEC` | `300` | Seconds before a "processing" scan is considered stale |
| `HOST` | `0.0.0.0` | Uvicorn bind address |
| `PORT` | `8000` | Uvicorn listen port (container) |
| `LOG_LEVEL` | `info` | Logging level |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

All new pip dependencies must have a matching wheel placed in `wheels/` and listed in the appropriate `requirements-*.txt` file.

---

## License

MIT License. See `LICENSE` file in this repository.

---

## Support / Contact

For issues and feature requests, please open an issue on the [GitHub repository](https://github.com/niccher/Chege-Photos-ML/issues).
