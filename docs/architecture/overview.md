# Architecture Overview — ML Chege Photos

ML Chege Photos is a Python-based computer vision microservice designed to perform facial recognition, object detection, semantic image embeddings, and face clustering for the Chege Photos ecosystem.

---

## System Context & C4 Container Architecture

```mermaid
graph TD
    subgraph Client["Clients"]
        WebBrowser["Web Browser (User / Admin)"]
        AndroidApp["Android Companion App"]
    end

    subgraph CoreBackend["Core WebApp (PHP 8.3 / CodeIgniter 4)"]
        WebApp["Chege Photos WebApp<br/>(Port 80 / 8080)"]
        AppDB[("MySQL Database<br/>(Core Schema)")]
    end

    subgraph MLService["ML Microservice (Python 3.12 / FastAPI)"]
        FastAPI["FastAPI API Server<br/>(Port 8000)"]
        MLWorker["Async Job Queue &<br/>Background Workers"]
        MLDB[("MySQL Database<br/>(ML Metadata & Scan Jobs)")]
    end

    subgraph VectorEngine["Vector Search Engine"]
        Qdrant[("Qdrant Vector DB<br/>(REST 6333 / gRPC 6334)")]
    end

    WebBrowser -->|HTTP / HTML / REST| WebApp
    AndroidApp -->|REST API / Okio Stream| WebApp
    WebApp -->|SQL Queries| AppDB

    WebApp -->|HTTP / JSON + X-API-KEY| FastAPI
    FastAPI -->|On-Demand Image Fetch| WebApp
    FastAPI -->|Enqueue Scan / Cluster Jobs| MLWorker
    MLWorker -->|Store Metadata / Clusters| MLDB
    MLWorker -->|Upsert & Search 512-d Vectors| Qdrant
    FastAPI -->|Vector Similarity Queries| Qdrant
```

---

## Component Responsibilities

| Component | Technology | Responsibility |
|---|---|---|
| **FastAPI Gateway** | FastAPI, Uvicorn, Pydantic v2 | Ingests requests, validates tokens (`X-API-KEY`), routes face detection, search, and clustering tasks. |
| **InsightFace Pipeline** | InsightFace (`buffalo_l`), ONNX Runtime | Detects face bounding boxes, 5-point landmarks, age/gender, and extracts **512-dimensional ArcFace** embeddings. |
| **Object Detection** | Ultralytics YOLOv8 | Detects objects, scenes, and tags in uploaded photographs. |
| **Semantic Search** | OpenAI CLIP (`clip-vit-base-patch32`) | Generates **512-dimensional text and image embeddings** for natural language search queries. |
| **Clustering Engine** | HDBSCAN + Cosine Centroids | Performs identity clustering and incremental face assignment against existing centroid prototypes. |
| **Vector Database** | Qdrant | Stores and indexes high-dimensional vectors (`face_embeddings`, `centroids`, `photo_embeddings`) with HNSW cosine indexes. |
| **Metadata Database** | MySQL (SQLAlchemy + Alembic) | Tracks scan jobs, face detections, identities, and cluster assignments. |

---

## Machine Learning Pipeline Lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant WA as WebApp (PHP)
    participant FA as FastAPI (/api/v1/scan)
    participant Q as Background Queue
    participant ML as InsightFace / YOLO / CLIP
    participant QD as Qdrant Vector DB
    participant DB as ML Database

    WA->>FA: POST /api/v1/scan/jobs (photo_urls, dynamic_webapp_url)
    FA->>DB: Insert ScanJob (Status: QUEUED)
    FA-->>WA: 202 Accepted (job_id)
    FA->>Q: Enqueue Job Task

    loop Async Image Processing
        Q->>WA: HTTP GET photo binary (Media Rehydration)
        WA-->>Q: 200 OK (image bytes)
        Q->>ML: Run InsightFace (buffalo_l)
        ML-->>Q: Detected Faces + 512-d ArcFace Embeddings
        Q->>QD: Upsert vectors into `face_embeddings`
        Q->>ML: Run YOLOv8 & CLIP
        ML-->>Q: Object Tags + 512-d CLIP Embedding
        Q->>QD: Upsert vector into `photo_embeddings`
        Q->>DB: Save FaceDetections & ObjectTags
    end

    Q->>DB: Update ScanJob (Status: COMPLETED)
    WA->>FA: GET /api/v1/scan/jobs/{job_id} (Poll Status)
    FA-->>WA: 200 OK (status: completed, detections: count)
```

---

## Related Documentation

* [Inter-Service Communication](communication.md)
* [Data & Storage (Qdrant & MySQL)](data-and-storage.md)
* [Deployment Architecture](deployment.md)
* [ML Models & Pipelines](../services/ml.md)
