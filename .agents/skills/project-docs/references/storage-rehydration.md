# Cloud Ephemeral Storage & Media Rehydration

Architectural patterns for running stateful media applications on ephemeral cloud container platforms (Railway, Render, Fly.io).

---

## 1. The Ephemeral Container Problem

Modern Platform-as-a-Service (PaaS) providers deploy applications inside stateless containers:
- **Redeployment Reset**: Every git push, redeploy, or container restart re-provisions the container from a fresh image, wiping all files written to local disk (e.g. `public/uploads/`).
- **Persistent Volume Cost/Limits**: Persistent disk attachments are expensive, often single-zone locked, and cannot scale horizontally.
- **Latency Dilemma**: Direct client-side streaming from object storage (S3/GCS) adds latency, egress costs, and complex presigned URL management.

---

## 2. The Hybrid On-Demand Rehydration Pattern

The recommended architecture combines **ephemeral local disk caching** with **durable cloud object storage (GCS/S3)** and **on-demand rehydration**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HYBRID REHYDRATION PATTERN                        │
│                                                                             │
│   Browser / Client                                                          │
│         │                                                                   │
│         │ 1. GET /uploads/users/1/2026/09/photo.jpg                         │
│         ▼                                                                   │
│   Web Server (Apache / Nginx)                                               │
│         │                                                                   │
│         ├── File exists on disk? ────▶ YES: Stream directly (0 ms overhead) │
│         │                                                                   │
│         └── NO (Disk wiped by redeploy)                                     │
│               │                                                             │
│               ▼ Rewrite to MediaFallback Controller                         │
│         ┌──────────────────────────────────────────────────────────────┐    │
│         │  MediaFallback Controller                                    │    │
│         │  1. Parse nested subpath: users/1/2026/09/                   │    │
│         │  2. Query Cloud Storage (GCS / S3)                           │    │
│         │  3. Recreate parent directories on local disk                │    │
│         │  4. Stream media bytes to Client                             │    │
│         │  5. Save cached copy to local disk asynchronously            │    │
│         └──────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Path Preservation & Directory Structure

> [!CAUTION]
> **Subpath Flattening Bug**: A common vulnerability during rehydration is using `basename($path)`, which flattens nested structures (`users/1/2026/09/photo.jpg` becomes `photo.jpg`). Always preserve the full relative hierarchy:

```php
// In MediaFallback Controller:
$segments = explode('/', $requestPath);
$sanitizedSegments = array_map(function($seg) {
    return basename($seg); // Sanitize each segment against directory traversal
}, $segments);
$relativePath = implode('/', $sanitizedSegments);

$targetLocalPath = FCPATH . 'uploads/' . $relativePath;
$parentDir = dirname($targetLocalPath);
if (!is_dir($parentDir)) {
    mkdir($parentDir, 0777, true);
}
```

---

## 4. Lifecycle & CLI Maintenance

Document the maintenance Spark or Artisan commands that govern cloud synchronization:

| Command | Schedule | Purpose |
|---|---|---|
| `cloud:sync --direction=up` | Every 5 minutes | Scans database for `gcp_synced = 0` and uploads media to cloud bucket. |
| `storage:prune-cache --max-age=30` | Daily | Prunes local cached files older than 30 days if verified safely synced to cloud. |
| `media:process-pending` | Asynchronous worker | Computes SHA-256 hash and mirrors large video files in the background. |

---

## 5. What to Document in `docs/`

In `docs/architecture/data-and-storage.md` and `docs/architecture/deployment.md`:
1. **Primary vs Secondary Storage**: Clearly state that local disk is an ephemeral cache, while GCS/S3 is the persistent source of truth.
2. **Directory Permissions**: Note that web server user (`www-data`) must have recursive write permissions (`0777`) on the writable and upload directories.
3. **Environment Credentials**: Document bucket name, service account JSON or HMAC credentials, and fallback behaviors when cloud storage is unreachable.
