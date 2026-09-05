# Local Development Guide — ML Chege Photos

This guide walks through configuring a local Python development environment for building, debugging, and testing ML Chege Photos without needing a full cloud deployment.

---

## Prerequisites

* **Python**: 3.12+
* **Docker & Docker Compose**: For local Qdrant and MySQL dependencies
* **pip & virtualenv**
* **Git**

---

## 1. Environment Setup

### Clone Repository & Create Virtual Environment
```bash
cd path/to/ML_Chege_Photos
python3.12 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

---

## 2. Start Storage Infrastructure (Docker)

Start the local Qdrant vector engine and MySQL metadata database:

```bash
docker compose up -d qdrant mysql
```

Verify that Qdrant is accepting connections:
```bash
curl http://localhost:6333/collections
```

---

## 3. Configure Local Environment Variables

Copy the example configuration to `.env`:

```bash
cp .env.example .env
```

Ensure your `.env` contains local connection details:
```env
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=debug
ML_API_KEY=local_dev_key

# MySQL
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root_password
DB_NAME=ml_chege_photos

# Qdrant
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
```

---

## 4. Run Development Server

Launch Uvicorn with auto-reload:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

* **API Root**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
* **Interactive OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Related Documentation

* [Definition of Done & Making Changes](making-changes.md)
* [Testing Guide](testing.md)
* [Architecture Overview](../architecture/overview.md)
