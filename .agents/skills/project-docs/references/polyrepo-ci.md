# Polyrepo Cross-Linking & CI Verification

Guidelines and automated workflows for synchronizing and validating documentation across sibling repositories in a multi-repo ecosystem.

---

## 1. The Sibling Repository Linking Standard

In a polyrepo ecosystem (e.g. `Chege-Photos-WebApp`, `Chege-Photos-ML`, `Chege-Photos-Android`):
- Each repository must explicitly link to its sibling repositories in its root `README.md` and `docs/architecture/overview.md`.
- Use a standardized URL table format:

```markdown
### Sibling Ecosystem Repositories

| Component | Responsibility | Repository URL | Documentation |
|---|---|---|---|
| **Web App** | CodeIgniter 4 Web UI, Auth & Sync Gateway | [GitHub Repo](https://github.com/niccher/Chege-Photos-WebApp) | [docs/](https://github.com/niccher/Chege-Photos-WebApp/tree/main/docs) |
| **ML Microservice** | FastAPI, InsightFace, YOLO, CLIP & Qdrant | [GitHub Repo](https://github.com/niccher/Chege-Photos-ML) | [docs/](https://github.com/niccher/Chege-Photos-ML/tree/main/docs) |
| **Android App** | Jetpack Compose Native Mobile Client | [GitHub Repo](https://github.com/niccher/Chege-Photos-Android) | [docs/](https://github.com/niccher/Chege-Photos-Android/tree/main/docs) |
```

---

## 2. GitHub Actions CI Link Verifier

Add this automated workflow to `.github/workflows/docs-verify.yml` in each repository to ensure documentation quality and prevent broken links:

```yaml
name: Verify Documentation Quality

on:
  push:
    branches: [ main, master ]
    paths:
      - 'README.md'
      - 'docs/**'
  pull_request:
    paths:
      - 'README.md'
      - 'docs/**'

jobs:
  lint-docs:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Run project-docs Quality Linter
        run: |
          python .agents/skills/project-docs/scripts/lint-docs.py .

      - name: Check External Link Validity
        uses: gaurav-nelson/github-action-markdown-link-check@v1
        with:
          use-quiet-mode: 'yes'
          config-file: '.github/workflows/mlc_config.json'
```

---

## 3. Link Checker Configuration (`mlc_config.json`)

Configure ignore rules for internal staging URLs or emulator IP addresses:

```json
{
  "ignorePatterns": [
    { "pattern": "^http://10\\.0\\.2\\.2" },
    { "pattern": "^http://localhost" },
    { "pattern": "^https://your-domain\\.up\\.railway\\.app" }
  ],
  "timeout": "10s",
  "retryOn429": true
}
```
