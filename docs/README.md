# ML Chege Photos — Engineering Handbook

Welcome to the engineering documentation for ML Chege Photos. This documentation is intended for machine learning engineers and backend developers building, training, and maintaining the computer vision inference pipeline.

If you only need to run or deploy the ML microservice, see the [Root README](../README.md).

---

## Documentation Navigation

| I want to… | Go here |
|---|---|
| **Run the ML service without coding** | [../README.md](../README.md) |
| **Understand system architecture & C4 containers** | [architecture/overview.md](architecture/overview.md) |
| **Inspect protocols, gRPC/REST & sequences** | [architecture/communication.md](architecture/communication.md) |
| **Review Qdrant vector collections & schemas** | [architecture/data-and-storage.md](architecture/data-and-storage.md) |
| **Review Railway deployment & memory limits** | [architecture/deployment.md](architecture/deployment.md) |
| **Review OpenAPI REST API endpoints** | [api/contract.md](api/contract.md) |
| **Work on FastAPI routing & lifespan logic** | [services/fastapi.md](services/fastapi.md) |
| **Inspect ML models (InsightFace, CLIP, YOLO)** | [services/ml.md](services/ml.md) |
| **Set up local Python virtual environment** | [engineering/local-development.md](engineering/local-development.md) |
| **Add an endpoint or model safely** | [engineering/making-changes.md](engineering/making-changes.md) |
| **Execute Pytest & syntax verification** | [engineering/testing.md](engineering/testing.md) |
| **Review operator configuration & environment** | [user/configuration.md](user/configuration.md) |
| **Troubleshoot OOM kills & vector issues** | [user/troubleshooting.md](user/troubleshooting.md) |

---

## Sibling Repositories

| Repository | Responsibility | Tech Stack |
|---|---|---|
| **[Chege-Photos-ML](https://github.com/niccher/Chege-Photos-ML)** | Face Detection, YOLOv8, CLIP & Qdrant | Python 3.12 / FastAPI |
| **[Chege-Photos-WebApp](https://github.com/niccher/Chege-Photos-WebApp)** | Core Web UI, Admin, Auth & Mobile Sync | PHP 8.3 / CodeIgniter 4 |
| **[Chege-Photos-Android](https://github.com/niccher/Chege-Photos-Android)** | Native Mobile Companion Client | Kotlin / Jetpack Compose |
