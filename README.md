# ML Chege Photos

FastAPI computer vision microservice powering face detection, 512-dimensional ArcFace embeddings, HDBSCAN clustering, YOLOv8 object tagging, and OpenAI CLIP semantic search for the Chege Photos platform.

**Stack**: Python 3.12 / FastAPI, InsightFace, YOLOv8, OpenAI CLIP, Qdrant, MySQL, PyTorch, Docker Compose.  
**Audience**: If you only need to run or test the ML service, this page is enough. Software & ML engineers: [docs/README.md](docs/README.md).

---

## What “Running” Looks Like

| Service / Endpoint | URL / How to open | Port | Purpose / Default Status |
|---|---|---|---|
| **Liveness Health** | [http://localhost:8000/health](http://localhost:8000/health) | `8000` | Returns `{"status":"ok","service":"ML Chege Photos"}` |
| **Interactive Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | `8000` | OpenAPI Swagger UI for all ML endpoints |
| **Prometheus Metrics**| [http://localhost:8000/metrics](http://localhost:8000/metrics) | `8000` | Real-time scan and inference metrics |
| **Qdrant Vector DB** | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | `6333` | Vector engine dashboard & collections |

---

## Prerequisites

* **Docker Engine 24.0+ & Docker Compose v2** (Recommended) or **Python 3.12+**
* **Qdrant Vector Database** (Port 6333)
* **MySQL 8.0+** (Port 3306)
* **Memory**: Minimum **2048 MB RAM** (Recommended: **4096 MB**) to prevent OOM termination (exit code 137)

---

## Setup and Run

### Option A — Docker Compose (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/niccher/Chege-Photos-ML.git
cd Chege-Photos-ML

# 2. Configure environment
cp .env.example .env

# 3. Launch full stack (FastAPI, Qdrant, MySQL)
docker compose up -d --build

# 4. Verify service health
curl http://localhost:8000/health
```

### Option B — Bare-Metal Python Development

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run FastAPI development server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | HTTP port for FastAPI service. |
| `LOG_LEVEL` | `info` | Logging verbosity (`debug`, `info`, `warning`, `error`). |
| `ML_API_KEY` | *(Required)* | Shared secret token matching WebApp `X-API-KEY`. |
| `WEBAPP_URL` | `http://chege-photos-webapp:80` | URL for on-demand photo streaming. |
| `QDRANT_HOST` | `qdrant` | Hostname or IP of Qdrant vector database. |
| `QDRANT_PORT` | `6333` | HTTP REST port for Qdrant. |
| `DB_HOST` | `mysql` | MySQL hostname for metadata tables. |
| `DB_PORT` | `3306` | MySQL port. |
| `DB_NAME` | `ml_chege_photos` | MySQL database name. |
| `ML_CONCURRENT_WORKERS` | `4` | Parallel photo processing worker limit. |

For the complete configuration reference, see [docs/user/configuration.md](docs/user/configuration.md).

---

## Troubleshooting

* **Process Killed / Exit Code 137**: Out-of-memory error. Ensure the container has at least 2048 MB RAM allocated.
* **Photo Download 404**: Verify `WEBAPP_URL` or `X-Webapp-Url` header matches the reachable WebApp host.
* **Qdrant Connection Refused**: Ensure Qdrant is running on port 6333 (`curl http://localhost:6333/collections`).

Detailed diagnostic steps and recovery procedures: [docs/user/troubleshooting.md](docs/user/troubleshooting.md).

---

## Engineering Documentation

For architecture, database schemas, API contracts, and development workflows, see the **[Engineering Handbook](docs/README.md)**:

* [Architecture Overview](docs/architecture/overview.md)
* [Inter-Service Communication](docs/architecture/communication.md)
* [Data & Storage Models (Qdrant & MySQL)](docs/architecture/data-and-storage.md)
* [Deployment Architecture](docs/architecture/deployment.md)
* [REST API Contract](docs/api/contract.md)
* [FastAPI Service Details](docs/services/fastapi.md)
* [ML Models & Pipelines](docs/services/ml.md)
* [Local Development Guide](docs/engineering/local-development.md)
* [Making Changes & Definition of Done](docs/engineering/making-changes.md)
* [Testing Guide](docs/engineering/testing.md)

---

## Sibling Repositories

| Repository | Responsibility | Tech Stack |
|---|---|---|
| **[Chege-Photos-ML](https://github.com/niccher/Chege-Photos-ML)** | Face Detection, YOLOv8, CLIP & Qdrant | Python 3.12 / FastAPI |
| **[Chege-Photos-WebApp](https://github.com/niccher/Chege-Photos-WebApp)** | Core Web UI, Admin, Auth & Mobile Sync | PHP 8.3 / CodeIgniter 4 |
| **[Chege-Photos-Android](https://github.com/niccher/Chege-Photos-Android)** | Native Mobile Companion Client | Kotlin / Jetpack Compose |

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
