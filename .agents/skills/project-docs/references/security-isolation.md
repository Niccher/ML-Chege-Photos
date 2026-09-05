# Multi-Tenant Isolation, Security & Observability

Guidelines for documenting row-level multi-tenancy, authorization hardening, binary deduplication, and telemetry in polyglot ecosystems.

---

## 1. Multi-Tenant Data Isolation & Query Scoping

In shared database architectures where multiple users store private photos and face embeddings, cross-tenant data isolation is the highest security priority.

### The Parenthesis / Operator Precedence Leak
In CodeIgniter 4, Laravel, and other ORMs, mixing `where()` and `orWhere()` without explicit grouping causes tenant boundary bypass:

```php
// VULNERABLE: Any photo from ANY user matching the OR condition leaks into the result
$memories = $photoModel->where('user_id', $userId)
                       ->where("DATE_FORMAT(taken_at, '%m-%d') =", $today)
                       ->orWhere('DATE(taken_at) =', $sixMonthsAgo) // LEAK!
                       ->findAll();

// SECURE: Enclosed in groupStart() / groupEnd()
$memories = $photoModel->where('user_id', $userId)
                       ->groupStart()
                           ->where("DATE_FORMAT(taken_at, '%m-%d') =", $today)
                           ->orWhere('DATE(taken_at) =', $sixMonthsAgo)
                       ->groupEnd()
                       ->findAll();
```

### IDOR (Insecure Direct Object Reference) Prevention
Document that every controller action modifying resources (albums, tags, face bounding boxes, person identities) must verify ownership against `auth()->id()`:
- **Bulk album additions**: Filter `$photoIds` against `where('user_id', auth()->id())` prior to inserting into pivot tables.
- **Face assignments & naming**: Verify that the face's parent photo belongs to the authenticated user.
- **Person merges**: Ensure both source and target person records belong to the active tenant.

---

## 2. Binary Deduplication & SHA-256 Checksums

High-volume photo and video applications must eliminate redundant storage and network transfer:
- **Pre-Flight Hash Checking**: Clients (web or Android) compute a SHA-256 binary hash before transmitting file data.
- **Batch Hash Check API**: `POST /api/v1/photos/check-hashes` accepts a list of hashes (e.g. 500 hashes per request). The server returns which hashes already exist in `tbl_photos`, allowing the client to skip uploading existing media.
- **Buffered Hash Computation**: When hashing large multi-gigabyte media, read files in **64 KB chunks** (`ByteArray(65536)`) rather than loading the entire file into memory, which prevents Out-Of-Memory errors.

---

## 3. Near-Realtime Container Telemetry & Health

In `docs/architecture/overview.md` and `docs/user/troubleshooting.md`, document how system administrators monitor container health:

| Metric | Source / Method | Alert Threshold | Remediation |
|---|---|---|---|
| **PHP Peak Memory** | `memory_get_peak_usage(true)` | > 80% of `memory_limit` | Increase `upload-limits.ini` memory or stream large uploads |
| **PHP-FPM / WebApp RAM** | `/sys/fs/cgroup/memory.current` | > 85% container limit | Scale Railway / Docker RAM |
| **System Load (1m / 5m)** | `sys_getloadavg()` | > 2.0 × CPU cores | Throttle background ML rescan batch size |
| **ML Process RSS RAM** | `psutil.Process().memory_info().rss` | > 2000 MB | Configure minimum 2048 MB memory limit |
| **Qdrant Vector Points** | `GET /collections/{name}` | Vectors count = 0 after scans | Check collection name mapping and rescan logs |
| **MySQL Buffer Pool Used** | `SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_%'` | > 95% buffer pool | Increase `innodb_buffer_pool_size` |

---

## 4. Secret Scanning & Sanitization Rules

Before generating or committing documentation, apply these regex filters to prevent secret leakage:

| Secret Category | Detection Regex Pattern | Safe Replacement |
|---|---|---|
| **Google Service Account** | `"type":\s*"service_account"`, `"private_key":\s*"-----BEGIN PRIVATE KEY` | `{ "type": "service_account", "private_key": "YOUR_PRIVATE_KEY" }` |
| **Master Encryption Keys** | `[a-f0-9]{64}`, `bin2hex(...)` | `<generate-via-php-spark-key:generate>` |
| **API Secret Keys** | `(ML_API_KEY\|API_KEY)=\S+` | `ML_API_KEY=your_secure_random_key` |
| **Database Passwords** | `(MYSQLPASSWORD\|DB_PASSWORD)=[^\s]+` | `MYSQLPASSWORD=root_password` (dev) or `your_secure_password` |
| **Railway Domains** | `[a-z0-9-]+\.up\.railway\.app` | `https://your-domain.up.railway.app` |
