# ML Chege Photos

Face detection, embedding, clustering, and attribute classification service for the Chege Photos ecosystem.

---

## Project Overview

ML Chege Photos is a FastAPI-based microservice that provides ML-powered face analysis to the Chege Photos web and Android applications. It performs:

- **Face detection** — locating faces within images using RetinaFace
- **Face embedding** — extracting 512-dimensional feature vectors via Insightface Buffalo-L (ArcFace)
- **Similarity search** — querying Qdrant for the most similar faces in sub-second time
- **Face clustering** — grouping unassigned embeddings into person clusters via HDBSCAN
- **Attribute classification** — age and gender estimation (optional; sensitive-attribute flag guarded by `.env`)
- **Person management** — naming, merging, and listing persons derived from clusters

The service replaces a purely heuristic/EXIF-based approach to photo organisation with learned representations that generalise across varied poses, lighting conditions, and occlusions.

---

## Tech Stack

| Component               | Technology                                      |
| ----------------------- | ----------------------------------------------- |
| API framework           | FastAPI (Python 3.12)                           |
| ASGI server             | Uvicorn                                         |
| ORM                     | SQLAlchemy 2.0 + PyMySQL                        |
| Vector database         | Qdrant                                          |
| Face model              | Insightface Buffalo-L (ResNet-100 backbone)     |
| Clustering              | HDBSCAN (via scikit-learn)                      |
| Attribute estimation    | Insightface (age / gender)                      |
| Containerisation        | Docker + Docker Compose                         |

Full dependencies are split into `requirements-core.txt` (API, DB, Qdrant client) and `requirements-ml.txt` (ML libraries). The combined `requirements.txt` includes both. Wheels are vendored under `wheels/` for offline builds.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         hosts / Docker                              │
│                                                                      │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │  Chege Photos │───▶│  ML Chege Photos │───▶│     Qdrant        │  │
│  │  Web App      │    │  (FastAPI)       │    │  (Vector DB)      │  │
│  │  (CI4 PHP)    │    │  port 9051       │    │  HTTP 9052        │  │
│  │  port 9005    │    │                  │    │  gRPC 9053        │  │
│  └──────┬───────┘    └────────┬─────────┘    └───────────────────┘  │
│         │                     │                                      │
│         │           ┌─────────▼─────────┐                           │
│         │           │     MySQL 8.4      │                           │
│         └──────────▶│   (Shared DB)     │                           │
│                     │   port 9306       │                           │
│                     └───────────────────┘                           │
│                                                                      │
│  ┌────────────────┐                                                  │
│  │  Android App   │───▶  ML Chege Photos API                        │
│  └────────────────┘                                                  │
└──────────────────────────────────────────────────────────────────────┘
```

The service sits in a shared Docker network (`hosts-shared-network`) alongside the Chege Photos CI4 web app (codeigniter 4, PHP), MySQL, and Qdrant. The Android app also communicates with the ML API directly.

- The CI4 web app or Android app sends a photo to `POST /api/v1/faces/encode`
- The service reads the photo file from a read-only mount of the web app's `public/uploads` directory
- Detected faces get embeddings stored in Qdrant and metadata (bbox, landmarks, age, gender) stored in MySQL (`face_encoding` table)
- The `/cluster` endpoint runs HDBSCAN over all embeddings to auto-discover persons
- The web app queries `/by-photo/{id}` to display face thumbnails and `/search` for "find similar faces"

---

## Why ML Over Heuristics

Traditional heuristic/EXIF-based approaches sort photos by timestamp, camera model, GPS location, or manual album assignment. These fail when:

- The **same person** appears in different lighting, angles, or with occlusions (sunglasses, masks, hats)
- **Multiple people** appear in a single photo that needs to be indexed per-face
- **Grouping** requires human effort — ML clustering automates it
- **Search** needs to find "photos of person X" across thousands of photos without manual tagging

ML-based face recognition solves these:

| Capability                | Heuristic / EXIF       | ML (this service)                          |
| ------------------------- | ---------------------- | ------------------------------------------ |
| Works across poses        | No                     | Yes — ArcFace is pose-invariant            |
| Works across lighting     | No                     | Yes — trained on MS1MV3 (5.8M images)      |
| Handles occlusions        | No                     | Yes — robust embeddings                    |
| Automatic grouping        | Manual albums          | HDBSCAN unsupervised clustering            |
| Similarity search         | Not possible           | Sub-second cosine search in Qdrant         |
| Per-face granularity      | Photo-level tags only  | Per-face bounding box and embedding        |
| Age / gender estimation   | Not possible           | Insightface attribute heads                |

Embeddings are 512-dimensional vectors learned via ArcFace loss. Cosine distance between embeddings reflects facial similarity — similar faces have near-zero distance, different faces approach 2.0.

---

## How Each Container Is Used

### `ml-chege-photos`

The primary FastAPI application container. Built from `Dockerfile` (Python 3.12-slim), it:
- Loads Insightface Buffalo-L models on startup (GPU with CUDA fallback to CPU)
- Connects to MySQL for relational data and Qdrant for vector storage
- Serves the REST API on port 8000 (mapped to host 9051)
- Mounts the web app's uploads directory read-only for photo access
- Stores downloaded model weights in a named volume (`insightface_models`) to avoid re-downloading on restart

### `ml-qdrant`

A stock `qdrant/qdrant:latest` container that holds all face embeddings in a single collection (`face_embeddings`). It:
- Exposes HTTP API on port 6333 (mapped to host 9052) and gRPC on port 6334 (mapped to host 9053)
- Persists data to a named volume (`qdrant_data`)
- Performs cosine-similarity ANN search; 512-d vectors indexed with default Qdrant config

---

## Usefulness of Docker

- **Reproducible builds** — The vendored `wheels/` directory combined with `pip install --no-index --find-links /wheels` ensures deterministic, offline builds regardless of network conditions
- **Consistent environment** — Python 3.12, ONNX Runtime, OpenCV, and system libs (`libgl1`, `libgomp1`) are identical across dev and production
- **Service isolation** — ML service, Qdrant, MySQL, and the web app each run in separate containers with their own lifecycle and resource limits
- **Portability** — The entire stack (including the shared network) can be deployed on any Docker host with a single `docker compose up`
- **Graceful degradation** — The service starts even when MySQL or Qdrant is temporarily unavailable; health checks report degraded status

---

## How to Set Up

### Prerequisites

- Docker ≥ 24.0
- Docker Compose ≥ 2.20
- A shared `.env` file at the `hosts/` root (or the service-level `.env`)

### Shared `.env` (at `hosts/.env`)

```ini
# Network
NETWORK_NAME=hosts-shared-network

# MySQL (shared across all services)
MYSQL_PORT=9306
MYSQL_ROOT_PASSWORD=root_password

# Chege Photos Web App
CHEGE_PHOTOS_PORT=9005

# ML Chege Photos
CONTAINER_ML_CHEGE_PHOTOS=ml-chege-photos
ML_CHEGE_PHOTOS_API_PORT=9051

# Qdrant
CONTAINER_QDRANT=ml-qdrant
ML_CHEGE_PHOTOS_QDRANT_HTTP=9052
ML_CHEGE_PHOTOS_QDRANT_GRPC=9053

# ML service .env (also copied to ML Chege Photos/.env)
DB_HOST=mysql
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root_password
DB_NAME=ml_chege_photos
QDRANT_HOST=ml-qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION=face_embeddings
FACE_MODEL_PACK=buffalo_l
FACE_DET_THRESH=0.5
INCLUDE_SENSITIVE_ATTRIBUTES=false
HDBSCAN_MIN_CLUSTER_SIZE=2
HDBSCAN_MIN_SAMPLES=1
CLUSTER_METRIC=cosine
SCAN_STALE_TIMEOUT_SEC=300
LOG_LEVEL=info
```

### Building and Running

From the `hosts/` root directory:

```bash
# Create the shared Docker network (one-time)
docker network create hosts-shared-network

# Build and start all services
docker compose up --build -d

# Or run only the ML stack
docker compose up --build -d ml-chege-photos ml-qdrant
```

From the `ML Chege Photos/` directory (standalone):

```bash
docker compose up --build -d
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

## API Endpoints

All endpoints prefixed with `/api/v1/faces` unless noted.

### `GET /health`

Liveness and readiness check. Returns status of DB connection, Qdrant connection, and model loading.

### `POST /api/v1/faces/detect`

Upload an image file. Returns detected face bounding boxes, landmarks, and detection scores — without storing anything.

**Request:** `multipart/form-data` with `file` (image)

**Response:**
```json
{
  "face_count": 2,
  "faces": [
    {
      "face_index": 0,
      "bbox": { "x": 100, "y": 50, "w": 80, "h": 100 },
      "detection_score": 0.99,
      "landmarks": { "left_eye": { "x": 120, "y": 80 }, ... },
      "embedding": null
    }
  ]
}
```

### `POST /api/v1/faces/embed`

Upload a face crop. Returns the 512-d embedding of the first detected face.

**Response:**
```json
{ "embedding": [0.012, -0.034, ...] }
```

### `POST /api/v1/faces/encode`

Detect faces in a photo referenced by `photo_id` (from the `db_chege_photos.photos` table), generate embeddings, store them in Qdrant and MySQL. This is the primary ingestion endpoint.

**Request:** `application/x-www-form-urlencoded` with `photo_id`

**Response:**
```json
{
  "photo_id": 42,
  "face_count": 3,
  "faces": [
    {
      "face_id": 1,
      "qdrant_point_id": "uuid-string",
      "bbox": { "x": 10, "y": 20, "w": 60, "h": 70 },
      "detection_score": 0.97,
      "embedding": [0.012, ...]
    }
  ]
}
```

### `POST /api/v1/faces/search`

Upload a query image. Returns the top `limit` most similar faces from Qdrant, annotated with person name if assigned.

**Parameters:** `file` (multipart), `limit` (query, default 20, max 100)

**Response:**
```json
{
  "query_embedding": [0.012, ...],
  "results": [
    { "score": 0.95, "qdrant_point_id": "...", "photo_id": 42, "bbox": {...}, "person_name": "Alice" }
  ]
}
```

### `POST /api/v1/faces/cluster`

Scrolls all embeddings from Qdrant, runs HDBSCAN clustering, creates `person` rows for each cluster, and assigns `face_encoding` rows to their corresponding person. Faces labelled as noise (`label == -1`) remain unassigned.

**Response:**
```json
{
  "total_faces": 500,
  "clusters": 12,
  "noise": 23,
  "assigned": 477
}
```

### `GET /api/v1/faces/by-photo/{photo_id}`

Returns all face records for a given photo, including bounding boxes, landmarks, attributes, and assigned person info.

### `GET /api/v1/faces/persons`

Lists all persons with face count, name, and thumbnail reference.

### `PUT /api/v1/faces/persons/{person_id}`

Update a person's name or thumbnail face ID.

**Request:** `application/x-www-form-urlencoded` with optional `name` and `thumbnail_face_id`

### `POST /api/v1/faces/persons/merge`

Merge two persons into one. All faces from `source_person_id` are reassigned to `target_person_id`, and the source person is deleted.

**Request:** `application/x-www-form-urlencoded` with `source_person_id` and `target_person_id`

### `GET /api/v1/faces/faces/unassigned`

Returns all face encodings that have no `person_id` assigned.

---

## Model Details

### Insightface Buffalo-L

| Property             | Value                              |
| -------------------- | ---------------------------------- |
| Backbone             | ResNet-100                         |
| Training data        | MS1MV3 (5.8M images, 93K IDs)     |
| Loss function        | ArcFace (Additive Angular Margin)  |
| Embedding dimension  | 512                                |
| Detector             | RetinaFace (MobilNet0.25 backbone) |
| Landmarks            | 5-point (eyes, nose, mouth corners)|
| Attribute heads      | Age (regression), Gender (binary)  |

### Initialisation

On container start, `app/ml/loader.py` attempts to load the model with CUDA execution provider. If GPU is unavailable, it falls back to CPU:

```python
providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
```

A dummy inference (`np.zeros((480, 640, 3), dtype=np.uint8)`) is run to warm up the model and confirm it loaded successfully.

### License Notice

The Buffalo-L model weights distributed with Insightface are licensed for **non-commercial research only**. For production use, replace `FACE_MODEL_PACK` with a commercially-licensed model pack (e.g., `buffalo_sc` or a fine-tuned alternative).

---

## Database Schema

### `face_encoding`

| Column                | Type        | Notes                              |
| --------------------- | ----------- | ---------------------------------- |
| `id`                  | INT (PK)    | Auto-increment                     |
| `photo_id`            | INT         | FK to `db_chege_photos.photos`     |
| `person_id`           | INT (FK)    | Nullable; FK to `person.id`        |
| `qdrant_point_id`     | VARCHAR(36) | UUID; unique, links to Qdrant      |
| `bbox_x`              | FLOAT       | Bounding box left                  |
| `bbox_y`              | FLOAT       | Bounding box top                   |
| `bbox_w`              | FLOAT       | Bounding box width                 |
| `bbox_h`              | FLOAT       | Bounding box height                |
| `landmark_*`          | FLOAT (x10) | 5 facial landmarks (nullable)      |
| `detection_score`     | FLOAT       | RetinaFace confidence              |
| `face_image_path`     | VARCHAR(500)| Cropped face thumbnail path        |
| `age`                 | INT         | Estimated age (nullable)           |
| `gender`              | VARCHAR(10) | "Male" / "Female" (nullable)       |
| `created_at`          | DATETIME    | Server default now()               |

### `person`

| Column              | Type        | Notes                              |
| ------------------- | ----------- | ---------------------------------- |
| `id`                | INT (PK)    | Auto-increment                     |
| `name`              | VARCHAR(255)| User-assigned name (nullable)      |
| `thumbnail_face_id` | INT (FK)    | References `face_encoding.id`      |
| `cluster_label`     | INT         | HDBSCAN cluster label              |
| `created_at`        | DATETIME    | Server default now()               |
| `updated_at`        | DATETIME    | Auto-updates on change             |

### Relationships

```
person 1───* face_encoding
```

A person may have many face encodings (one per detected face across different photos). The `thumbnail_face_id` field optionally points to a single face encoding used as the person's representative thumbnail.

---

## Port Mapping

| Service           | Container Port | Default Host Port | Protocol |
| ----------------- | -------------- | ----------------- | -------- |
| ML FastAPI        | 8000           | 9051              | HTTP     |
| Qdrant HTTP       | 6333           | 9052              | HTTP     |
| Qdrant gRPC       | 6334           | 9053              | gRPC     |

Ports are configurable via environment variables (`ML_CHEGE_PHOTOS_API_PORT`, `ML_CHEGE_PHOTOS_QDRANT_HTTP`, `ML_CHEGE_PHOTOS_QDRANT_GRPC`). The host-side ports follow a harmonised scheme across the `hosts` monorepo: web apps use ports 90xx and their corresponding ML backends use 9{xx}n (e.g., Chege Photos is 9005, so its ML component uses 905{1..3}).

---

## Network

All containers connect to a shared external Docker network named `hosts-shared-network` (configurable via `NETWORK_NAME`). This enables:

- **Service discovery** by container name — `ml-chege-photos` resolves to the FastAPI container, `ml-qdrant` to Qdrant, `mysql` to the shared MySQL instance
- **Cross-stack communication** — the Chege Photos web app (CI4 PHP) and the Android app both reach the ML API at `http://ml-chege-photos:8000` over the internal network
- **Isolation** — the ML stack does not need to expose ports to the host for inter-service communication; only the API port is published for external clients

---

## Volume Mounts

| Mount Point in Container             | Host Source                                    | Purpose                                      |
| ------------------------------------ | ---------------------------------------------- | -------------------------------------------- |
| `/app/uploads`                       | `../Chege Photos WebApp/public/uploads` (ro)   | Read-only access to uploaded photos          |
| `/app/models/insightface_models`     | `insightface_models` (named volume)            | Persist downloaded model weights             |
| `/qdrant/storage`                    | `qdrant_data` (named volume)                   | Persist Qdrant vector index and payload      |

The photo uploads mount is **read-only** (`:ro`) — the ML service never writes to the upload directory. The `insightface_models` volume prevents re-downloading the Buffalo-L model weights (hundreds of MB) on every container restart. The `qdrant_data` volume ensures embeddings survive container recreation.
