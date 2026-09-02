# syntax=docker/dockerfile:1
FROM python:3.12-slim

# ── OS deps ───────────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libgomp1

WORKDIR /app

# ── Layer 1: Stable core API / database dependencies ─────────────────────────
# Re-runs only when requirements-core.txt changes (very infrequent).
COPY requirements-core.txt .
RUN pip install -r requirements-core.txt

# ── Layer 2: Heavy ML / vision libraries ──────────────────────────────────────
# Re-runs only when requirements-ml.txt changes (occasional).
COPY requirements-ml.txt .
RUN pip install -r requirements-ml.txt

# ── Layer 3: PyTorch + Transformers + App dependencies ─────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Layer 4: Application code (changes most often — kept last) ────────────────
COPY . .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
