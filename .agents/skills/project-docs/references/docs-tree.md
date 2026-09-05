# Canonical docs tree

Generate only nodes that apply. Keep user docs thin; engineer docs complete.

```
README.md                          # USER — setup and run
docs/
  README.md                        # Index
  user/
    setup-and-run.md
    configuration.md
    troubleshooting.md
  architecture/
    overview.md                    # C4 context + containers
    communication.md               # sequences, protocols, auth
    data-and-storage.md
    deployment.md
  api/
    contract.md                    # OpenAPI / versioning (if API exists)
  services/
    codeigniter.md
    fastapi.md
    android.md
    jvm.md
    ml.md                          # if FastAPI (or worker) serves models
  engineering/
    local-development.md
    making-changes.md
    database.md
    testing.md
    ci.md
    contributing.md
    troubleshooting.md
    security.md                    # optional
    release.md                     # optional
  adr/                             # optional
  runbooks/                        # optional
```

## Polyrepo

If each stack is its own git repo:

**Umbrella / org README** (or a `platform` repo):

- Product, repo table, Docker-from-root, links to each repo
- `docs/architecture/*` lives here (system truth)

**Each service repo:**

- Short user README: run **this** service + pointer to umbrella
- `docs/services/{this}.md` + engineering for **this** stack only
- Do not copy the full system architecture into every repo — link it

If there is no umbrella repo, put system architecture in the **API** repo (FastAPI) and link from CI4 and Android READMEs.

## User vs engineer checklist

**User docs may include**

- Clone, copy env, compose up, URLs, default **dev** logins
- "API is up when `/health` returns 200"
- Port conflicts, Docker not running, emulator networking
- Where to get a debug APK if you publish one

**User docs must not include**

- How to add a CI4 controller / FastAPI router / Compose screen
- ERD, Pydantic models, Gradle module graphs
- Production SSH, cloud account IDs, real secrets
- Long tech-stack essays

**Engineer docs must include**

- Directory maps with real paths
- Request path through services
- How to run tests for that stack
- How to migrate DB
- How to change a contract without breaking Android/CI4
