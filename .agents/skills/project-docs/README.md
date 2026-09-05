# project-docs skill (v3)

Dual-audience documentation generator for **CodeIgniter 4**, **Python FastAPI**, and **Kotlin/Java**.

| Reader | Gets |
|--------|------|
| **User** | Root `README.md` + `docs/user/` — setup and run only |
| **Software engineer** | `docs/` — architecture, communication, how to edit, tests, deploy |

## Install

Copy this folder into your agent skills directory **as a unit**:

```
project-docs/
  SKILL.md
  README.md          # this file
  scripts/
    lint-docs.py     # automated quality and secrets linter
  references/
    audience.md
    docs-tree.md
    diagrams.md
    stacks.md
    docs-ux.md
    vector-ml.md
    storage-rehydration.md
    security-isolation.md
    polyrepo-ci.md
```

Keep `references/` next to `SKILL.md`. Triggers: write/update README, document this project, generate `/docs`.

## What the agent should emit in a target repo

```
README.md
docs/
  README.md
  user/
  architecture/      # diagrams required
  api/               # if FastAPI
  services/          # ci4 / fastapi / android as present
  engineering/
```

See `SKILL.md` for templates, hard rules, contract definition of done, and why docs do **not** live in the CodeIgniter UI.
