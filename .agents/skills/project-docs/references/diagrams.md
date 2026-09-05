# Diagrams (required)

Use **Mermaid** in Markdown (GitHub/GitLab render it). No "paste this into mermaid.live" notes.

Every system gets at least:

1. Context or container diagram (`docs/architecture/overview.md`)
2. One login/auth sequence (`docs/architecture/communication.md`)
3. One core-feature sequence
4. ERD **only** if schema was read from migrations/models (not invented)

Fill names, ports, and auth from the repo.

## Container diagram (adapt)

```mermaid
flowchart LR
  subgraph Clients
    U[User]
    A[Android Kotlin]
    B[Browser]
  end
  subgraph Edge
    W[CodeIgniter 4 web]
    F[FastAPI]
  end
  subgraph Data
    PG[(PostgreSQL)]
    RD[(Redis)]
    S3[Object storage]
  end
  U --> A
  U --> B
  B --> W
  A -->|HTTPS JSON + Bearer| F
  W -->|HTTP JSON server-side| F
  W --> PG
  F --> PG
  F --> RD
  F --> S3
```

If CI4 is only a UI and FastAPI owns data, **do not** draw CI4 → Postgres. Draw the real ownership.

## Sequence: login (example pattern — replace with actual)

```mermaid
sequenceDiagram
  autonumber
  participant App as Android
  participant API as FastAPI
  participant DB as Postgres
  App->>API: POST /auth/login {email, password}
  API->>DB: verify user
  API-->>App: {access_token, refresh_token}
  App->>App: store tokens (encrypted prefs)
  App->>API: GET /me  Authorization Bearer
  API-->>App: user profile
```

If login is CI4 session and Android uses a **BFF**:

```mermaid
sequenceDiagram
  autonumber
  participant App as Android
  participant CI as CodeIgniter 4
  participant API as FastAPI
  App->>CI: POST /api/login
  CI->>API: POST /internal/auth
  API-->>CI: JWT
  CI-->>App: JWT or session cookie
```

## Sequence: emulator networking (document this if Android exists)

```mermaid
flowchart TB
  E[Android emulator]
  H[Host machine]
  F[FastAPI :8000]
  E -->|"http://10.0.2.2:8000"| H --> F
```

Physical device: same LAN IP, or `adb reverse tcp:8000 tcp:8000`.

## Communication table (always pair with diagrams)

| From | To | Transport | Auth | Base URL (dev) | Notes |
|------|----|-----------|------|----------------|-------|
| Android | FastAPI | HTTPS JSON | Bearer JWT | `http://10.0.2.2:8000` | flavors for staging/prod |
| Browser | CI4 | HTTPS + cookie | CI4 session | `http://localhost:8080` | CSRF filters |
| CI4 | FastAPI | HTTP JSON | service token / JWT | `http://fastapi:8000` | compose DNS name |

## ERD snippet (from real models only)

```mermaid
erDiagram
  USER ||--o{ ORDER : places
  USER {
    int id PK
    string email
  }
  ORDER {
    int id PK
    int user_id FK
    string status
  }
```

## C4-style context (simple)

```mermaid
C4Context
  title System context
  Person(user, "End user")
  Person(admin, "Admin")
  System(sys, "Product", "CI4 + FastAPI + Android")
  System_Ext(play, "Google Play")
  System_Ext(mail, "SMTP")
  Rel(user, sys, "Uses Android / web")
  Rel(admin, sys, "CI4 admin")
  Rel(sys, play, "Distributes app")
  Rel(sys, mail, "Sends email")
```

If C4 Mermaid is unsupported in their host, use `flowchart` instead.

## Rules

- Label protocols (`HTTPS`, `JWT`, `cookie`)
- Label **dev ports** that compose actually publishes
- Do not show both "shared DB" and "API owns data" — pick the truth
- Keep diagrams readable: 5–12 nodes
