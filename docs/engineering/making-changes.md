# Making Changes & Definition of Done — ML Chege Photos

This document provides developer guidelines for modifying endpoints, database schemas, and ML pipelines, concluding with the mandatory Definition of Done (DoD).

---

## 1. Adding a New API Endpoint

1. **Define Request & Response Schemas**:
   Create Pydantic v2 models in [app/models/schemas.py](../../app/models/schemas.py) with explicit type hints and field descriptions.
2. **Implement Route Handler**:
   Add the endpoint function inside the appropriate sub-module under [app/api/](../../app/api/).
3. **Enforce Security**:
   Ensure `Depends(get_api_key)` protects the route if it modifies state or queries sensitive user embeddings.
4. **Register in Router**:
   If creating a new router module, mount it inside [app/main.py](../../app/main.py).
5. **Update API Documentation**:
   Reflect the new route in [docs/api/contract.md](../api/contract.md).

---

## 2. Database Schema Changes (Alembic)

All MySQL database modifications must be recorded as reproducible migrations:

1. **Update SQLAlchemy Model**:
   Edit or add models in [app/models/db.py](../../app/models/db.py).
2. **Generate Migration Script**:
   ```bash
   alembic revision --autogenerate -m "add_face_landmarks_table"
   ```
3. **Inspect Generated Migration**:
   Check the newly generated file in `app/migrations/versions/` to verify `upgrade()` and `downgrade()` methods are correct.
4. **Apply Migration Locally**:
   ```bash
   alembic upgrade head
   ```

---

## 3. Updating Neural Network Models or Hyperparameters

* **Thresholds**: Adjust confidence thresholds or cluster minimums in [app/config.py](../../app/config.py) via `Settings` attributes.
* **Vector Dimension Changes**:
  > [!WARNING]
  > Changing model architectures (e.g. switching to a 768-d embedding) requires recreating Qdrant collections and re-indexing all existing images. Coordinate with WebApp developers before altering vector dimensions.

---

## 4. Definition of Done (DoD) Checklist

Before submitting a Pull Request or deploying changes:

- [ ] **Type & Syntax Check**: Code passes formatting and static checks (`ruff check .`, `black --check .`).
- [ ] **Unit & Integration Tests**: Pytest passes cleanly without errors (`pytest tests/`).
- [ ] **Schema Migration**: Any new database tables include a reversible Alembic migration.
- [ ] **Contract Sync**: [docs/api/contract.md](../api/contract.md) is updated if request/response signatures changed.
- [ ] **Docs Linter Passed**: Run the documentation linter to verify zero broken links:
  ```bash
  python3 .agents/skills/project-docs/scripts/lint-docs.py .
  ```

---

## Related Documentation

* [Testing Guide](testing.md)
* [Local Development Guide](local-development.md)
* [API Contract](../api/contract.md)
