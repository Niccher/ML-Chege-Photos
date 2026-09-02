# syntax=docker/dockerfile:1
FROM python:3.12-slim

# ── OS deps ───────────────────────────────────────────────────────────────────
RUN --mount=type=cache,id=ml-apt-cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=ml-apt-lib,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
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
RUN --mount=type=cache,id=ml-pip-core,target=/root/.cache/pip \
    pip install -r requirements-core.txt

# ── Layer 2: Heavy ML / vision libraries ──────────────────────────────────────
# Re-runs only when requirements-ml.txt changes (occasional).
COPY requirements-ml.txt .
RUN --mount=type=cache,id=ml-pip-ml,target=/root/.cache/pip \
    pip install -r requirements-ml.txt

# ── Layer 3: PyTorch + Transformers via pre-built local wheels ─────────────────
# Uses the wheels/ directory to avoid re-downloading multi-GB packages from PyPI.
# NOTE: pin torch and transformers versions in requirements.txt for reproducibility.
COPY requirements.txt .
COPY wheels /wheels
RUN --mount=type=cache,id=ml-pip-wheels,target=/root/.cache/pip \
    pip install --find-links /wheels -r requirements.txt \
    && rm -rf /wheels

# ── Layer 4: Application code (changes most often — kept last) ────────────────
COPY . .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
