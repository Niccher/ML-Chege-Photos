# Stack detection and command cheatsheet

Use **only** commands and paths that exist in the repo. This file is a search guide.

## CodeIgniter 4

**Detect:** `spark`, `app/Config/Paths.php`, `app/Config/App.php`, `composer.json` requiring `codeigniter4/framework`, `public/index.php`.

**Typical layout**

```
app/Config/Routes.php
app/Controllers/
app/Models/
app/Views/
app/Filters/
app/Database/Migrations/
public/          # document root
writable/        # logs, cache, session — must be writable
env              # copied to .env
spark
composer.json
phpunit.xml.dist
tests/
```

**User run (native, only if no Compose)**

```bash
composer install
cp env .env
php spark migrate
php spark serve --host 0.0.0.0 --port 8080
```

**Engineer commands (if present)**

```bash
php spark list
php spark migrate
php spark migrate:rollback
php spark db:seed
php spark make:controller Name
php spark make:model Name
php spark make:migration Name
vendor/bin/phpunit
```

**Config:** `CI_ENVIRONMENT`, `app.baseURL`, `database.default.*`, `security.*` in `.env`.

**Gotchas to document when seen:** `public/` as web root; `writable/` permissions; `baseURL` mismatch; CSRF filters on API routes; calling FastAPI with `CURLRequest` / Guzzle.

## FastAPI

**Detect:** `FastAPI(`, `uvicorn`, `pyproject.toml` / `requirements.txt` / `Pipfile`, `alembic.ini`.

**Typical layout**

```
app/main.py
app/api/          # routers
app/models/
app/schemas/
app/core/config.py
alembic/
tests/
```

**Run**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # or uv sync / poetry install
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health: `GET /health` or `GET /docs`.

**Gotchas:** CORS origins for CI4 host and Android; Pydantic v1 vs v2; blocking ML inference on the event loop (use threadpool); model file path in image vs volume; `DATABASE_URL` async driver (`postgresql+asyncpg`).

**ML extras:** weights path, startup `lifespan` load, `GET /health` includes `model_loaded`, GPU `nvidia-smi` / CPU fallback, training **not** required to *run* the API (say so on the user README).

## Kotlin / Java Android

**Detect:** `AndroidManifest.xml`, `settings.gradle.kts`, `app/build.gradle.kts`.

**Typical**

```
app/src/main/java|kotlin
app/src/main/AndroidManifest.xml
gradle/wrapper/gradle-wrapper.properties
local.properties          # sdk.dir, not committed
```

**Run**

```bash
./gradlew :app:assembleDevDebug    # use real flavor/task
./gradlew :app:installDevDebug
./gradlew test
```

**Base URL:** `build.gradle.kts` `buildConfigField`, `res/values/`, or flavors. Document each flavor.

**Gotchas & Production Patterns:**
- **Zero-Copy Streaming Uploads**: Never use `inputStream.readBytes()` for large photo or video uploads, which exhausts the JVM heap. Document `ContentUriRequestBody` using Okio (`sink.writeAll(source)`) to pipe streams directly from `ContentResolver` into the network socket.
- **Fast 64 KB SHA-256 Hashing**: Use 64 KB chunk buffers (`ByteArray(65536)`) for client-side hashing to verify against `POST /api/v1/photos/check-hashes` before uploading.
- **Edge-to-Edge Window Insets**: With `enableEdgeToEdge()` enabled, document `.statusBarsPadding().navigationBarsPadding()` on fullscreen carousels so hardware notches, camera cutouts, and system navigation bars do not crop media.
- **WorkManager Constraints**: Document background sync workers (`SyncWorker`, `OfflineSyncWorker`, `ManualUploadWorker`) with `NetworkType.CONNECTED` and `StorageNotLow` constraints.
- **Networking**: Emulator uses `10.0.2.2`; cleartext HTTP (`android:usesCleartextTraffic="true"` or network security config) for local http; minSdk; JDK 17/21 for Gradle.

## Vector Databases (Qdrant, Milvus, pgvector)

**Detect:** `QdrantClient`, `qdrant`, `milvus`, `pgvector`, port `6333` / `6334`.

See [references/vector-ml.md](vector-ml.md) for full collection schemas, HNSW parameter tuning, and ArcFace/CLIP vector dimensions.

## Java/Kotlin JVM (non-Android)

**Detect:** `src/main/kotlin`, Spring `pom.xml` / `build.gradle.kts` with `org.springframework.boot`, Ktor `embeddedServer`.

Document port, `application.yml`, how it is reached from CI4/FastAPI/Android.

## Docker Compose (user default)

**Detect:** `docker-compose.yml`, `compose.yaml`, `compose/*.yml`.

Document:

- `docker compose up --build`
- service names and **published ports**
- healthchecks / wait order (db then api then web)
- volumes for models/uploads
- `docker compose down -v` warning (wipes local DB)

Example service names to look for: `web`, `ci4`, `php`, `api`, `fastapi`, `db`, `postgres`, `redis`, `worker`.

## Contracts

Prefer documenting **one** source of truth:

1. FastAPI generated OpenAPI (`/openapi.json`)
2. Checked-in `openapi.yaml`
3. Ad-hoc JSON — mark as fragile

Android DTOs and CI4 payloads should point at that contract. If they drifted, say so in `docs/api/contract.md`.
