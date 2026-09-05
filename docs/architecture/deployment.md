# Deployment Architecture — ML Chege Photos

This guide describes production deployment options for ML Chege Photos, focusing on containerized hosting on Railway, Docker Compose, and resource sizing requirements to avoid Out-Of-Memory (OOM) failures.

---

## Hardware & Resource Requirements

InsightFace (`buffalo_l`), YOLOv8, and OpenAI CLIP are heavyweight neural networks loaded into memory simultaneously.

| Environment | Minimum RAM | Recommended RAM | CPU Cores |
|---|---|---|---|
| **Local Dev / Testing** | 2 GB | 4 GB | 2 cores |
| **Production (Railway / VPS)** | **2048 MB** | **4096 MB** | 2–4 cores |

> [!CAUTION]
> **OOM Warning (Exit Code 137)**: Deploying with less than 2048 MB of RAM will result in container terminations when multiple models execute concurrently. Always configure container memory reservations accordingly.

---

## 1. Cloud Deployment (Railway)

The ML service is packaged as a Docker container and deployed as a service within a Railway project alongside Qdrant and MySQL.

### Railway Configuration
1. **Source Repository**: Connect `Chege-Photos-ML` to Railway.
2. **Dockerfile**: Railway detects the root [Dockerfile](../../Dockerfile) automatically.
3. **Environment Variables**:
   ```env
   PORT=8000
   ML_API_KEY=your_production_secret_key
   QDRANT_HOST=qdrant.railway.internal
   QDRANT_PORT=6333
   MYSQL_URL=mysql://root:password@mysql.railway.internal:3306/railway
   WEBAPP_URL=https://chege-photos-webapp-production.up.railway.app
   ML_CONCURRENT_WORKERS=2
   ```
4. **Health Check Path**: `/health` (Port 8000).

---

## 2. Local Deployment (Docker Compose)

The multi-container stack can be launched locally using the provided [docker-compose.yml](../../docker-compose.yml).

```bash
docker compose up -d --build
```

### Stack Composition

```mermaid
graph TD
    subgraph Host["Host Machine"]
        ClientPort["Port 8000 (FastAPI)"]
        QdrantPort["Port 6333 (Qdrant REST)"]
    end

    subgraph DockerNetwork["Bridge: chege_network"]
        MLApp["Container: ml_app<br/>(FastAPI / Uvicorn)"]
        Qdrant["Container: qdrant<br/>(Vector Engine)"]
        MySQL["Container: mysql<br/>(Storage Engine)"]
    end

    ClientPort --> MLApp
    QdrantPort --> Qdrant
    MLApp -->|Internal DNS: qdrant:6333| Qdrant
    MLApp -->|Internal DNS: mysql:3306| MySQL
```

---

## Rollback & Zero-Downtime Updates

* **Model Caching**: ONNX model files are downloaded during the Docker build step or mounted via volume to prevent downloading weights on every container restart.
* **Rolling Deployments**: In Railway, enable zero-downtime rolling deploys so incoming requests transition smoothly after the `/health` endpoint responds with `HTTP 200 OK`.

---

## Related Documentation

* [Troubleshooting Guide](../user/troubleshooting.md)
* [Configuration Reference](../user/configuration.md)
* [Inter-Service Communication](communication.md)
