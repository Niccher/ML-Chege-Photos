# Setup and Run Guide (ML Service)

Step-by-step instructions for operators to launch, verify, and monitor the ML Chege Photos service.

---

## 1. Quick Start via Docker Compose (Recommended)

Docker Compose starts both the FastAPI `ml-service` and a dedicated `ml-qdrant` vector database container.

### Step 1: Clone Repository
```bash
git clone https://github.com/niccher/Chege-Photos-ML.git
cd "ML Chege Photos"
```

### Step 2: Environment Configuration
Copy the template configuration file:
```bash
cp .env.example .env
```

Ensure MySQL connection details match your active database (e.g. `DB_HOST=mysql` or `DB_HOST=127.0.0.1`).

### Step 3: Launch Containers
```bash
docker compose up --build -d
```

### Step 4: Verify Container Startup
Monitor model loading and startup logs:
```bash
docker compose logs -f ml-service
```

Expected startup confirmation:
```text
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:9051 (Press CTRL+C to quit)
```

---

## 2. Health & Verification Probes

Test the following endpoints in your browser or via curl:

| Endpoint | Purpose | Expected Result |
|---|---|---|
| `GET http://localhost:9051/health` | Liveness check | Returns JSON `{"status": "ok", "database_connected": true, "qdrant_connected": true}`. |
| `GET http://localhost:9051/docs` | Interactive Swagger UI | Interactive OpenAPI documentation loads cleanly. |
| `GET http://localhost:9052/dashboard` | Qdrant Web UI | Qdrant console displays `face_embeddings` collection. |

---

## 3. Stopping the Service

```bash
docker compose stop
```

To remove containers while preserving vector data stored in volumes:
```bash
docker compose down
```
