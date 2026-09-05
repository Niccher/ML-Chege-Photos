# Docs UX — what lives where

Documentation is **several products**, not one page. Putting everything in the CodeIgniter web UI, or everything in GitHub Markdown, both fail.

## Four kinds of “docs” (do not mix)

| Kind | Audience | Needed when the app is **down**? | Best home |
|------|----------|----------------------------------|-----------|
| **A. Run the system** | Operator, QA | **Yes** (they are trying to start it) | Root `README.md` + `docs/user/` |
| **B. Change the system** | Engineers | **Yes** (onboarding, PR review, incident) | `docs/` in Git (optional MkDocs later) |
| **C. Call the API** | Engineers + integrators | API should be **up** for try-it | FastAPI **Swagger** `/docs` (live) + `openapi.yaml` in Git |
| **D. Use the product** | Business users, admins, customers | No — they are already inside | **In-app** CI4 (and Android) help |

A–C are **project documentation** (this skill).  
D is **product help**. Different owners, different UX, different versioning.

---

## Why not use the webapp UI for A–C?

The CodeIgniter app is a bad host for “how to clone, compose, and migrate”:

1. **Chicken and egg.** README exists so someone can start CI4. Help pages inside CI4 are unreachable until that works.
2. **Wrong consumer.** Android/FastAPI engineers should not boot PHP + MySQL to read how JWT works.
3. **Incidents.** When production is down, you need architecture and runbooks in Git/Slack, not behind the broken site.
4. **Auth and roles.** Engineer docs would need a “developer” login or be public on the same origin as customer data.
5. **Version skew.** In-app help ships with **deployed** code. PRs, tags, and `main` vs `release/1.4` need docs next to the commit. Git Markdown does that for free.
6. **Review.** Docs in Git are reviewed in the same PR as the API change. CMS pages in CI4 usually are not.
7. **Search & nav.** MkDocs/Docusaurus/VitePress are built for trees of Markdown. CI4 `Views/help/*.php` becomes a second, worse docs site.
8. **Mobile.** Play/internal engineers live in Android Studio + GitHub, not in the admin panel.

**Do not** build a `/documentation` module in CI4 for architecture, env vars, or Gradle flavors.

---

## When the webapp UI **is** the right docs surface (kind D)

Use CI4 (and the Android app) for **people who already run the product**:

- What this screen means (domain language, not HTTP)
- How to complete a business task (issue invoice, approve claim)
- Tooltips, empty states, “first run” checklist
- What’s new after a release (in-app changelog)
- Tenant-specific policy text
- Links out: “API status” or “download Android” — **links**, not the handbook

Treat that as **product copy**, possibly from a `help/` table or Markdown rendered **inside** the app, with the same auth as the rest of CI4.

Pattern that works:

```
Git docs/          → engineers + operators
FastAPI /docs      → live API try-out
CI4 /help          → business users
Android in-app     → short task help + link to support
```

Do **not** duplicate Swagger endpoint lists as CI4 HTML. Link to `/docs` (protect it in prod if needed).

---

## GitHub-native Markdown first, MkDocs later

**Phase 1 (default for this skill):** Markdown in `README.md` + `docs/` so GitHub/GitLab render it. No extra build. PRs show diffs.

**Phase 2 — add MkDocs (or Docusaurus/VitePress) when** at least two of these are true:

- `docs/` has ≳15 pages or people get lost
- You want full-text search, version switcher (`1.3` / `1.4`)
- Non-Git users (ops, PMs) need a URL like `https://docs.example.com`
- You want a consistent nav/theme

Then:

- Keep files **in** `docs/` (do not move to a CMS)
- Add `mkdocs.yml` (Material for MkDocs is the usual choice for engineering)
- CI publishes GitHub Pages / GitLab Pages / S3
- README still stays the **run** page; it links to the published site **and** to `docs/` for offline

Docusaurus fits **product** docs (marketing + user manuals) more than internal architecture. For CI4+FastAPI+Android **engineering**, MkDocs or VitePress is usually less overhead than Docusaurus (Node, React, versioning config).

**Do not** start with Docusaurus on day one. A dead docs generator is worse than GitHub Markdown.

---

## Screenshots (user docs)

Put images in Git, not only in the live app:

```
docs/user/assets/
  compose-up.png          # terminals or Docker Desktop healthy
  web-login.png           # CI4
  fastapi-swagger.png     # /docs
  android-dev-flavor.png  # where base URL is picked
```

Rules:

- **User** screenshots: “you are in the right place” (login, Swagger list, green health). Crop; no PII; fake names.
- **Engineer** screenshots: rare. Prefer Mermaid + exact paths. Screenshot a Gradle flavor panel only if words fail.
- Refresh screenshots when UI/nav changes or they rot and people distrust all docs.
- Prefer **one** annotated image per step over a gallery.
- For Swagger: screenshot the **list of tags** and a single “Try it out” success, then tell users the live UI is at `http://localhost:PORT/docs`.

Alt text in Markdown. Do not store 4K PNGs; compress.

---

## Definition of done (contract change)

A “contract” is anything another process depends on: FastAPI path/schema, CI4 route used by Android, env var, error shape, auth header.

**Do not merge** if any box is missing:

1. **Code** in the owning service (usually FastAPI schema + router).
2. **Test** that locks the contract (`pytest` for API; PHPUnit for CI4 BFF; unit test for Android DTO parse if the client ships in the same PR).
3. **`.env.example` / `env`** updated if a new variable exists (never real secrets).
4. **Docs line:**
   - User-visible URL/port/login → `README.md` or `docs/user/`
   - Behaviour / sequence → `docs/architecture/communication.md`
   - New endpoint → OpenAPI (automatic from FastAPI) + one line in `docs/api/contract.md` if versioning/breaking
   - New screen → `docs/services/android.md` or CI4 service page only if engineers must configure something
5. **Consumers:** Android DTO / CI4 client updated **or** explicitly versioned (`/v2`) with old route kept.
6. **Changelog** one bullet (`docs/engineering/release.md` or `CHANGELOG.md`).

Tiny template for PRs (optional `PULL_REQUEST_TEMPLATE.md`):

```markdown
## Contract
- [ ] API schema / CI4 route
- [ ] Test
- [ ] env example
- [ ] docs (user and/or engineer)
- [ ] Android / CI4 consumer or versioned as non-breaking
```

---

## In-app vs static: decision rule

```
Is the reader trying to START or REPAIR the system?
  → Git README / docs / runbooks. Never CI4.

Is the reader calling HTTP?
  → Live FastAPI /docs (+ exported openapi.yaml in Git).

Is the reader logged in as a business user doing a job?
  → In-app help (CI4 / Android).

Is it architecture, env, Gradle, migrations?
  → Git docs/. Optional MkDocs site generated FROM that Git tree.
```

**Hybrid (good):** CI4 footer: “Engineer docs” → `https://docs.example.com` or GitHub `docs/`. FastAPI `/docs` link in the admin **only** for technical admins, not clerks.

**Hybrid (bad):** Copy of `docs/architecture/overview.md` pasted into a CI4 WYSIWYG. It will drift immediately.

---

## Practical layout with a future docs site

```
README.md                 # always works on GitHub
docs/                     # source of truth
mkdocs.yml                # added later; nav points at the same files
site/                     # build artifact, gitignored
```

`mkdocs.yml` nav should mirror `docs/README.md` (user vs architecture vs services vs engineering). One nav, two skins (GitHub vs published).
