# Troubleshooting Guide — ML Chege Photos

This guide covers common operational failures, root causes, and verified recovery procedures for the ML inference service.

---

## Common Issues & Solutions

### 1. Process Killed with Exit Code 137 (Out Of Memory / OOM)

* **Symptom**: Container suddenly exits during heavy scanning with `exit code 137` or `Killed`.
* **Root Cause**: InsightFace (`buffalo_l`), YOLOv8, and CLIP models loaded simultaneously exceed host memory limits. When batch processing high-resolution images, memory spikes beyond container quotas.
* **Resolution**:
  1. Increase container RAM limit in Railway / Docker to at least **2048 MB** (recommended: **4096 MB**).
  2. Reduce concurrency in `.env`:
     ```env
     ML_CONCURRENT_WORKERS=2
     ```
  3. Batch large scans into smaller batches of photos rather than triggering a full sweep of >500 images at once.

---

### 2. Photo Download Fails / `404 Not Found` / Missing Uploads

* **Symptom**: Logs display `Could not download photo: HTTP 404` or `ConnectionRefusedError` when fetching images from WebApp.
* **Root Cause**: The ML service cannot reach the PHP WebApp storage URL, or the WebApp URL is improperly configured.
* **Resolution**:
  1. Pass the `X-Webapp-Url` header in all requests from the WebApp:
     ```http
     X-Webapp-Url: http://chege-photos-webapp.railway.internal
     ```
  2. Explicitly set `WEBAPP_URL` in `.env`:
     ```env
     WEBAPP_URL=http://chege-photos-webapp:80
     ```
  3. If running locally with Docker Compose, verify both containers share the same network bridge (`chege_network`).

---

### 3. Qdrant Connection Refused or Timeout

* **Symptom**: Logs show `qdrant_client.http.exceptions.ResponseHandlingException: Connection refused` on port 6333.
* **Root Cause**: Qdrant container is not running, initialized slowly, or the hostname resolution failed.
* **Resolution**:
  1. Check Qdrant container status:
     ```bash
     docker compose ps qdrant
     ```
  2. Test network reachability:
     ```bash
     curl http://localhost:6333/collections
     ```
  3. In Railway or Docker, verify `QDRANT_HOST` matches the service DNS:
     ```env
     QDRANT_HOST=qdrant
     QDRANT_PORT=6333
     ```

---

### 4. `403 Forbidden: Invalid or missing X-API-KEY`

* **Symptom**: All requests to `/api/v1/*` return `403 Forbidden`.
* **Root Cause**: Missing or mismatched `X-API-KEY` header between CodeIgniter WebApp and ML service.
* **Resolution**:
  1. Check `ML_API_KEY` in ML `.env`:
     ```env
     ML_API_KEY=your_secure_shared_token
     ```
  2. Ensure WebApp `.env` has the identical value:
     ```env
     ml.apiKey = your_secure_shared_token
     ```
  3. Public endpoints like `/health` and `/metrics` do not require authentication.

---

### 5. ONNX Runtime Warnings / Slow Inference

* **Symptom**: Warning logs regarding `CUDAExecutionProvider not available, falling back to CPUExecutionProvider`.
* **Root Cause**: Standard Docker images use CPU-only ONNX Runtime binaries.
* **Resolution**:
  * CPU fallback is expected and supported for low-cost cloud hosting.
  * For production GPU instances, install `onnxruntime-gpu` and configure NVIDIA Container Toolkit.

---

## Diagnostic Commands

| Check | Command |
|---|---|
| Service Health | `curl http://localhost:8000/health` |
| Deep Diagnostic | `curl -H "X-API-KEY: $ML_API_KEY" http://localhost:8000/api/v1/health/deep` |
| Model Status | `curl -H "X-API-KEY: $ML_API_KEY" http://localhost:8000/api/v1/models` |
| Qdrant Collections | `curl http://localhost:6333/collections` |
| Container Logs | `docker compose logs -f ml_app` |

---

## Related Documentation

* [Setup & Run Guide](setup-and-run.md)
* [Configuration Reference](configuration.md)
* [Deployment Architecture](../architecture/deployment.md)
