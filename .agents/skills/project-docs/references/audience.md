# Audience split

## User (README + docs/user)

**Goal:** the system is running on their machine (or they can open staging URLs if that is the intended user path).

**Success:** they can open the web UI, hit FastAPI `/docs` or `/health`, and optionally install a debug Android build.

Write like an operator manual:

- Numbered steps
- Exact working directory
- What “good” looks like (HTTP 200, screenshot optional)
- Next step if it fails (link troubleshooting)

Assume they may not know PHP, Python, or Gradle. Docker is the default story.

## Engineer (docs/)

**Goal:** change behaviour without breaking the other two stacks.

**Success:** they know which repo/folder to open, how services authenticate, how to migrate, how to test, and the definition of done.

Write like an internal handbook:

- Paths and symbols (`app/Controllers`, `app.api.routers`, `:app`)
- Sequences before “add a field”
- Cross-stack impact (schema change → API → Android)

## Voice

| User | Engineer |
|------|----------|
| "Copy `.env.example` to `.env`, then start Compose." | "CI4 `CURLRequest` uses `API_BASE_URL`; Android `dev` flavor uses `10.0.2.2`." |
| "The API is ready when `/health` returns 200." | "Health includes model load; `/ready` vs `/live` if both exist." |
| "If the app cannot login, see troubleshooting." | "401 on `/me` after login → check clock skew and `JWT_SECRET` match." |

## Do not mix

Putting `php spark make:controller` on the README fails both audiences: users are lost, engineers still lack architecture.
