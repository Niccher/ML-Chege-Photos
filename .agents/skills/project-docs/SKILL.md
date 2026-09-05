---
name: project-docs
description: >
  Generate dual-audience documentation for CodeIgniter 4, Python FastAPI, and
  Kotlin/Java systems. Use when the user asks to write or update a README,
  document a project, create a docs/ folder, or explain how to set up, run, or
  change the system. README.md is for users/operators (setup and run only).
  docs/ is for software engineers (architecture, communication, editing, tests,
  deploy). Do not put setup or architecture inside the web app UI.
version: 3.1.0
---

# Project documentation skill

You are a technical writer for systems that typically combine:

- **CodeIgniter 4** (PHP) — web UI, admin, sometimes BFF
- **Python FastAPI** — HTTP API, workers, ML/inference, vector databases
- **Kotlin/Java** — Android app and/or JVM services

Your job is to produce **two products**:

1. **`README.md`** — for the **user** (operator, QA, new hire who must **run** the system)
2. **`docs/`** — for the **software engineer** (who must **understand and change** the system)

Never merge those into one giant README.

Read these if present next to this file:

- [references/audience.md](references/audience.md)
- [references/docs-tree.md](references/docs-tree.md)
- [references/diagrams.md](references/diagrams.md)
- [references/stacks.md](references/stacks.md)
- [references/docs-ux.md](references/docs-ux.md)
- [references/vector-ml.md](references/vector-ml.md)
- [references/storage-rehydration.md](references/storage-rehydration.md)
- [references/security-isolation.md](references/security-isolation.md)
- [references/polyrepo-ci.md](references/polyrepo-ci.md)
- [scripts/lint-docs.py](scripts/lint-docs.py)

---

## When to use

- “write readme”, “create readme”, “document this project”
- “generate docs”, “engineering docs”, “docs folder”
- setup/run guides, onboarding, “how do I change X”

Do not use for product copy (marketing site, in-app clerk help). That is a different surface (see Docs UX).

---

## Audiences

| Audience | Who | Goal | Surface |
|----------|-----|------|---------|
| **User** | Operator, QA, intern, anyone who must start the stack | Clone → configure → run → verify → stop | `README.md` + `docs/user/` |
| **Software engineer** | PHP / Python / Android / JVM developer | Understand architecture, change code safely, test, deploy | `docs/` (index + architecture + services + engineering) |

Optional extra readers (only add pages if the repo needs them):

| Audience | Surface |
|----------|---------|
| Integrator (external API consumer) | FastAPI Swagger + `docs/api/contract.md` |
| Business user already logged in | **In-app** CI4/Android help — **not** this skill’s `docs/` |
| On-call | `docs/runbooks/` + architecture |

**README rule:** if a sentence is about *editing code*, it does not belong in `README.md`. Link to `docs/`.

**Engineer rule:** do not hide “how to compose up” only in `docs/`. Users never open `making-changes.md`. Repeat the run path in README.

---

## Hard rules

1. **Never invent a stack.** Detect from the tree. Do not mention Rails, Inertia, Kamal, Vite-Ruby, Next.js, etc. unless those files exist.
2. **Never paste secrets.** Document `.env.example` / CI4 `env` only. No real passwords, JWT secrets, keystores, `google-services.json` production keys.
3. **Prefer Docker Compose for users** when compose files exist so they do not install PHP + Python + JDK.
4. **Commands must exist** in this repo (`spark`, `uvicorn` module path, `gradlew` tasks, Make targets). Do not copy sample commands blindly.
5. **Polyrepo:** if this workspace is one service, still describe how it talks to the others; ask once for sibling repo paths if unknown.
6. **Update, don’t duplicate.** Merge into existing README/`docs/`/mkdocs. Do not create a second competing tree.
7. **Diagrams required** in `docs/architecture/` (Mermaid): containers + at least one sequence + communication table.
8. **Facts from this codebase.** Ports, service names, routes, flavors. Unknown production URLs → `TODO`, never fiction.
9. **Do not put A–C docs in the CI4 UI.** Setup, architecture, and API handbooks stay in Git. In-app help is only for logged-in business users. Live API try-out is FastAPI `/docs`.
10. Skip files for stacks that are absent. No empty stubs.

---

## Before writing

### 1. Topology

Classify: single service | monorepo (folders) | polyrepo.

Detect:

| Signal | Stack |
|--------|--------|
| `spark`, `app/Config/Paths.php`, `codeigniter4/framework` | CodeIgniter 4 |
| `FastAPI(`, `uvicorn`, `pyproject.toml` / `requirements.txt` | FastAPI |
| `AndroidManifest.xml`, `*.gradle.kts` | Android Kotlin/Java |
| `src/main/kotlin` or `src/main/java` without Android | JVM service |
| `compose.yaml` / `docker-compose.yml` | User full-stack run |
| `openapi.yaml` / FastAPI `/docs` | API contract |
| `.github/workflows/`, `Jenkinsfile`, `.gitlab-ci.yml` | CI |
| `mkdocs.yml`, `docusaurus.config.*` | Existing docs site — extend it |

Map each service: folder, language, start command, published port, who it calls.

### 2. Data and auth

- CI4: `app/Config/Database.php`, `.env` `database.*`, `app/Database/Migrations/`
- FastAPI: SQLAlchemy/SQLModel, Alembic, `DATABASE_URL`
- Android: Retrofit/Ktor, flavor base URL, DataStore/Room
- Auth: CI4 session/CSRF vs FastAPI JWT/OAuth2 vs Android interceptors
- Who **owns** the database? Do not assume CI4 and FastAPI share tables unless they do.

### 3. Ask once if blocked

- Product name
- Missing sibling repos
- Docker vs native as the **supported user** path

Do not block on credentials; use placeholders.

---

## Output tree (generate / update)

```
README.md
docs/
  README.md
  user/
    setup-and-run.md
    configuration.md
    troubleshooting.md
    assets/                         # screenshots if available
  architecture/
    overview.md                     # C4 context + containers
    communication.md                # protocols, sequences, auth
    data-and-storage.md
    deployment.md
  api/
    contract.md                     # if FastAPI or openapi exists
  services/
    codeigniter.md                  # if CI4
    fastapi.md                      # if FastAPI
    android.md                      # if Android
    jvm.md                          # if non-Android JVM
    ml.md                           # if models/inference
  engineering/
    local-development.md
    making-changes.md
    database.md
    testing.md
    ci.md
    contributing.md
    troubleshooting.md
    security.md                     # if auth/PII/payments
    release.md                      # if versions across app/API/model
  runbooks/                         # if compose/prod deploy exists
    restart.md
  adr/                              # only if you write a real decision
```

Polyrepo: system architecture lives in an umbrella repo **or** the FastAPI repo; service repos get a short README + `docs/services/{this}.md` and **link** to the system docs.

If MkDocs already exists, add pages to `mkdocs.yml` instead of a parallel nav.

---

## README.md — user only

**Limit ~150 lines.** No schema dumps, no Gradle graphs, no `spark make:controller`.

```markdown
# {Product name}

{2–3 sentences: what it does and who it is for.}

Stack (one line): CodeIgniter 4, FastAPI, Kotlin Android — only those that exist.

**If you only need to run the system, this page is enough.**  
Software engineers: [docs/README.md](docs/README.md).

## What “running” looks like

| Piece | URL / how to open | Dev login (if any) |
|-------|-------------------|--------------------|
| Web (CodeIgniter) | http://localhost:{port} | |
| API (FastAPI) | http://localhost:{port}/docs | |
| Health | GET /health → 200 | |
| Android | debug APK / Android Studio | |

## Prerequisites

### Option A — Docker (recommended for users)

- Git
- Docker Engine + Compose v2 (or Docker Desktop)

### Option B — Without Docker

Only if you must support it. List **exact** versions from the repo (PHP, Composer, Python, JDK, Android SDK). This is harder; say so.

## Setup and run

From a fresh machine, numbered, copy-pasteable:

1. Clone
2. Copy env files (`env` → `.env` for CI4, FastAPI `.env.example`, `local.properties` for Android)
3. `docker compose up --build` (or the real Make/script target)
4. Wait for healthchecks
5. Open the URLs above
6. `docker compose down`

Android vs local API: document **exact** base URL (`http://10.0.2.2:{port}` on emulator, not `localhost`).

## Configuration users may change

Short table: ports, `BASE_URL`, `DATABASE_URL`. Full list: [docs/user/configuration.md](docs/user/configuration.md).

## Something went wrong?

3–5 symptoms (port in use, DB not ready, emulator cannot reach host).  
Details: [docs/user/troubleshooting.md](docs/user/troubleshooting.md).

## Software engineers

- Architecture: [docs/architecture/overview.md](docs/architecture/overview.md)
- How services talk: [docs/architecture/communication.md](docs/architecture/communication.md)
- Change the code: [docs/engineering/making-changes.md](docs/engineering/making-changes.md)
```

---

## docs/README.md — engineer home

```markdown
# Engineering documentation

| I want to… | Go here |
|------------|---------|
| Run the system without coding | [../README.md](../README.md) |
| Understand the system | [architecture/overview.md](architecture/overview.md) |
| See how web / API / Android talk | [architecture/communication.md](architecture/communication.md) |
| Work on CodeIgniter 4 | [services/codeigniter.md](services/codeigniter.md) |
| Work on FastAPI | [services/fastapi.md](services/fastapi.md) |
| Work on Android | [services/android.md](services/android.md) |
| Native dev machine | [engineering/local-development.md](engineering/local-development.md) |
| Change behaviour safely | [engineering/making-changes.md](engineering/making-changes.md) |
| Database / migrations | [engineering/database.md](engineering/database.md) |
| Tests | [engineering/testing.md](engineering/testing.md) |
| API contract | [api/contract.md](api/contract.md) |
```

Adjust rows to stacks that exist.

---

## User docs (`docs/user/`)

**setup-and-run.md** — same path as README with extra checks (what a healthy `docker compose ps` looks like, how to confirm Swagger loads). Screenshots in `docs/user/assets/` if you can capture them: CI4 login, FastAPI `/docs`, Android run config. No PII; compress images.

**configuration.md** — env vars a **user** may edit. Columns: `Variable | Service | Required | Example | Purpose`. No internals (JWT algorithm, pool size) unless they must set them.

**troubleshooting.md** — run/start only:

- Docker daemon not running
- Port already allocated
- Postgres not healthy before API
- CI4 `writable/` permissions
- Android `localhost` vs `10.0.2.2` vs `adb reverse`
- Cleartext HTTP blocked on Android

Engineer build failures go to `docs/engineering/troubleshooting.md`.

---

## Architecture (required)

### overview.md

1. Context: people + external systems (Play, SMTP, S3, payments)
2. Containers: CI4, FastAPI, Android, DB, cache, object storage
3. Table: container → repo/folder → runtime
4. Trust boundary: cookies on CI4 vs Bearer on FastAPI vs CI4-as-BFF (document the **real** pattern)

Mermaid `flowchart` example (replace with real ports and owners):

```mermaid
flowchart LR
  subgraph clients
    U[User]
    A[Android]
    B[Browser]
  end
  subgraph backend
    W[CodeIgniter 4]
    F[FastAPI]
  end
  subgraph data
    PG[(PostgreSQL)]
    RD[(Redis)]
  end
  U --> A
  U --> B
  B --> W
  A -->|JSON + Bearer| F
  W -->|JSON| F
  F --> PG
  F --> RD
```

If CI4 does not touch Postgres, do not draw that edge.

### communication.md

- Table: From | To | Transport | Auth | Dev base URL | Notes
- Sequence: login
- Sequence: one core business action
- Token refresh if any
- Error body convention
- API versioning (`/api/v1`) and breaking-change rule
- CORS origins (CI4 origin + Android debug)
- Emulator networking diagram

```mermaid
sequenceDiagram
  autonumber
  participant App as Android
  participant API as FastAPI
  participant DB as DB
  App->>API: POST /auth/login
  API->>DB: verify
  API-->>App: access + refresh
  App->>API: GET /me Bearer
  API-->>App: profile
```

Replace with the actual flow (CI4 session BFF if that is what the code does).

### data-and-storage.md

Source of truth, extra DBs, Redis, files/S3, on-device Room/tokens. ERD in Mermaid **only** from real migrations/models.

### deployment.md

Only mechanisms in the repo: Compose, nginx+php-fpm, systemd, k8s, Play bundle. No generic Heroku/Rails.

---

## Per-stack engineer pages

Fill from the tree. Typical commands below are **defaults** — swap for what `composer.json` / Gradle / compose actually use.

### services/codeigniter.md

- Path, PHP version, document root `public/`
- Layout: `app/Controllers`, `Models`, `Views`, `Filters`, `Config/Routes.php`
- `.env` from `env`; `app.baseURL`; `database.default.*`
- `php spark migrate`, seeds, `php spark serve`
- How CI4 calls FastAPI (`CURLRequest`, Guzzle, env base URL)
- Filters/CSRF vs JSON API routes
- PHPUnit
- Recipes: add route + controller + view; add filter; add migration

### services/fastapi.md

- App module (`app.main:app` or real path)
- Routers, `Depends`, Pydantic schemas
- `uvicorn ... --reload --host 0.0.0.0 --port {port}`
- venv / uv / poetry — whichever exists
- OpenAPI `/docs`; CORS
- Alembic
- Workers (Celery/ARQ) if present
- pytest
- Recipes: new router + schema + test

### services/android.md

- Gradle modules, `minSdk` / `compileSdk`, Kotlin version
- Flavors and **API base URL per flavor**
- Retrofit/Ktor, token store
- `./gradlew` tasks that exist
- Emulator `10.0.2.2`, cleartext config, `local.properties` not committed
- Recipes: new screen + viewmodel + DTO matching OpenAPI

### services/jvm.md / ml.md

Only if present. ML: weights path, lifespan load, `/health` includes `model_loaded`, GPU vs CPU, **users do not train to run the API**.

---

## Engineering pages

**local-development.md** — native per-service setup for people who will edit code (PHP, Composer, Python, JDK, Android Studio). Compose still OK for dependencies (Postgres).

**making-changes.md** — task table:

| If you want to… | Touch |
|-----------------|--------|
| Add a public API endpoint | FastAPI router + schema + test; OpenAPI; Android DTO |
| Add an admin page | CI4 route, controller, view, auth filter |
| Add an Android screen | UI + viewmodel + repository |
| Change a column | Migration in the **owning** service, then consumers |
| Change auth | All clients — update `communication.md` first |

**Definition of done** (contract change — do not merge without):

- [ ] Code in the owning service
- [ ] Test locking the contract
- [ ] `.env.example` / `env` if a new variable
- [ ] Docs line (user README if they must do something new; else engineer page / OpenAPI)
- [ ] Consumers updated **or** versioned (`/v2`)
- [ ] Changelog bullet

**database.md** — spark migrate vs alembic vs Room; never two sources of truth undocumented.

**testing.md** — phpunit, pytest, `./gradlew test` / connectedAndroidTest; how to run in CI.

**ci.md** — from real workflow files only.

**contributing.md** — branch names, PR template, link DoD.

**troubleshooting.md** — composer ext, Python wheels, Gradle JDK, device not seeing API.

**security.md** (if needed) — CSRF, JWT storage, secrets, PII in logs, keystore.

---

## Docs UX (do not confuse surfaces)

| Kind | Audience | App can be down? | Home |
|------|----------|------------------|------|
| Run the system | User | Must work if app is down | `README.md` |
| Change the system | Software engineer | Yes | `docs/` |
| Call HTTP | Engineer / integrator | API should be up | FastAPI **Swagger** `/docs` + `openapi.yaml` |
| Use the product | Business user | No | **In-app** CI4 / Android help |

Do **not** build `/documentation` in CodeIgniter for architecture or Compose. Chicken-and-egg, wrong audience, useless in outages, version skew vs Git.

**Later:** MkDocs/Material (or VitePress) **from the same `docs/` files** when the tree is large or you need `https://docs.example.com`. Do not start Docusaurus on day one. Do not paste Markdown into a CI4 CMS.

In-app footer may **link** to GitHub `docs/` or the MkDocs URL. FastAPI `/docs` may be linked for technical admins only.

---

## Environment tables

Users: short in README + `docs/user/configuration.md`.  
Engineers: full table on each service page.

`Variable | Service | Required | Example | Purpose`

Group: CI4 `.env`, FastAPI, Android `BuildConfig`/flavors, Compose.

---

## Writing principles

1. Audience first — users never see Pydantic or Filters.
2. Facts from the repo.
3. Copy-pasteable commands with `cd` into the service directory.
4. Why belongs in engineer docs; users need what/when.
5. Tables for env, ports, scripts, communication.
6. Mermaid for architecture and sequences.
7. `TODO` over invented URLs.
8. Keep README short; depth in `docs/`.
9. Git Markdown is source of truth; MkDocs is a skin.
10. Screenshots only to confirm “you are in the right UI”.

---

## Quality bar

- [ ] A user can run the system from README alone (Compose or documented native)
- [ ] README has **no** edit-the-code instructions and is $\le 150$ lines
- [ ] `docs/README.md` indexes every generated page
- [ ] Architecture + communication diagrams match real ports/auth/DB ownership
- [ ] Vector collections documented with dimensions, distance metric & HNSW params if vector DB exists
- [ ] Ephemeral storage rehydration documented if cloud deployment exists
- [ ] Zero-copy streaming RequestBody documented if Android upload exists
- [ ] Multi-tenant isolation and IDOR prevention documented in architecture
- [ ] Secrets not copied; examples only
- [ ] Android localhost caveat if Android exists
- [ ] making-changes table matches real folders
- [ ] Existing MkDocs/Sphinx nav updated if present
- [ ] Contract DoD described for engineers
- [ ] Validated via `python scripts/lint-docs.py .` with zero errors

## Limitations

- Not a substitute for running tests or expert review.
- Do not invent OpenAPI, Gradle flavors, or shared databases.
- Stop if there is no tree to inspect and the user gave no repo.

## Suggested extras (only with evidence)

OpenAPI contract page · model card · threat model · runbooks · ADRs · ERD · observability · release train (Android `versionName` vs API vs model) · Play privacy questionnaire.
