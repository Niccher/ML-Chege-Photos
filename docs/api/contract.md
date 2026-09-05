# REST API Contract — ML Chege Photos

This document provides the formal API specification for the ML Chege Photos microservice. All endpoints (except public health checks) require the `X-API-KEY` header.

---

## Global Headers & Security

| Header | Required | Example | Description |
|---|---|---|---|
| `X-API-KEY` | **Yes** (unless public) | `shared_token_key_123` | Master inter-service credential matching `ML_API_KEY`. |
| `X-Webapp-Url` | Recommended | `http://chege-photos-webapp:80` | Origin URL for on-demand photo streaming. |
| `Content-Type` | Optional | `application/json` | Required for JSON request bodies. |

---

## 1. Health & Diagnostics

### `GET /health`
* **Auth**: Public
* **Description**: Liveness probe for Docker and Railway container management.
* **Response `200 OK`**:
  ```json
  {
    "status": "ok",
    "service": "ML Chege Photos"
  }
  ```

### `GET /api/v1/health/diagnostics`
* **Auth**: `X-API-KEY` required
* **Description**: Deep diagnostic check inspecting database connection, Qdrant collection readiness, and model loading state.
* **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "database": true,
    "qdrant": true,
    "models_loaded": true,
    "models": {
      "face_analysis": "buffalo_l",
      "clip": "openai/clip-vit-base-patch32"
    }
  }
  ```

---

## 2. Face Detection & Recognition

### `POST /api/v1/faces/detect`
* **Description**: Detect faces, bounding boxes, 5-point landmarks, and demographic attributes in an uploaded image.
* **Content-Type**: `multipart/form-data` (form field: `file`)
* **Response `200 OK`**:
  ```json
  {
    "faces_count": 1,
    "faces": [
      {
        "face_index": 0,
        "bbox": { "x": 120.5, "y": 84.0, "w": 189.5, "h": 191.0 },
        "detection_score": 0.94,
        "landmarks": {
          "left_eye": { "x": 165.2, "y": 140.1 },
          "right_eye": { "x": 245.0, "y": 139.8 },
          "nose": { "x": 204.5, "y": 182.3 }
        },
        "attributes": {
          "age": 28,
          "gender": "M"
        }
      }
    ]
  }
  ```

### `POST /api/v1/faces/search`
* **Description**: Search for visually similar faces across Qdrant vector storage.
* **Body**:
  ```json
  {
    "photo_id": 142,
    "face_index": 0,
    "limit": 20,
    "threshold": 0.65
  }
  ```
* **Response `200 OK`**:
  ```json
  {
    "query_face_id": 412,
    "matches": [
      {
        "face_id": 901,
        "photo_id": 185,
        "similarity": 0.892,
        "person_name": "Alice"
      }
    ]
  }
  ```

### `POST /api/v1/faces/cluster`
* **Description**: Triggers HDBSCAN identity clustering across all unclustered face embeddings.
* **Response `200 OK`**:
  ```json
  {
    "status": "success",
    "clusters_formed": 14,
    "faces_clustered": 182,
    "noise_faces": 12
  }
  ```

---

## 3. Photo Scanning & Ingestion

### `POST /api/v1/scan/{photo_id}`
* **Status**: `202 Accepted`
* **Description**: Asynchronously enqueue face detection, object detection, and CLIP embedding for a single photo.
* **Response `202 Accepted`**:
  ```json
  {
    "status": "queued",
    "photo_id": 142
  }
  ```

### `POST /api/v1/scan`
* **Status**: `202 Accepted`
* **Description**: Enqueue a batch of photos for processing.
* **Body**:
  ```json
  {
    "photo_ids": [142, 143, 144, 145],
    "webapp_url": "http://chege-photos-webapp:80"
  }
  ```
* **Response `202 Accepted`**:
  ```json
  {
    "job_id": "8f399ab7-6a1e-450f-90db-3b567d1219b1",
    "total_photos": 4,
    "status": "queued"
  }
  ```

### `GET /api/v1/scan/batch/{job_id}/status`
* **Description**: Query real-time progress of a batch scan job.
* **Response `200 OK`**:
  ```json
  {
    "job_id": "8f399ab7-6a1e-450f-90db-3b567d1219b1",
    "status": "running",
    "total": 4,
    "processed": 2,
    "progress_percent": 50.0
  }
  ```

---

## 4. Semantic Search

### `GET /api/v1/search/semantic?q={query}`
* **Description**: Natural language photo search using 512-d CLIP vector similarity.
* **Parameters**: `q` (string, e.g. `"golden retriever playing in snow"`)
* **Response `200 OK`**:
  ```json
  {
    "query": "golden retriever playing in snow",
    "results": [
      {
        "photo_id": 98,
        "score": 0.812
      }
    ]
  }
  ```

---

## Related Documentation

* [Architecture Overview](../architecture/overview.md)
* [Inter-Service Communication](../architecture/communication.md)
* [Data & Storage Models](../architecture/data-and-storage.md)
* [FastAPI Implementation](../services/fastapi.md)
