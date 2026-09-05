# Testing Guide — ML Chege Photos

This guide describes how to run automated tests, mock heavy neural network dependencies, and verify API endpoints in ML Chege Photos.

---

## Test Framework

The project uses [pytest](https://docs.pytest.org/) for test discovery and execution, together with FastAPI's `TestClient` (built on `httpx`).

### Required Packages
```bash
pip install pytest pytest-asyncio pytest-mock httpx
```

---

## 1. Running Tests

Execute all tests from the repository root:

```bash
pytest
```

Run tests with verbose output and print logging:
```bash
pytest -v -s
```

Run a specific test module or test case:
```bash
pytest tests/test_faces.py -k test_detect_faces
```

---

## 2. Mocking Machine Learning Dependencies

Loading InsightFace or CLIP models during unit tests is slow and requires GPU/CPU model weight files. Use `pytest-mock` or `unittest.mock` to stub model inferences:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_face_detection_mocked(mocker):
    # Mock InsightFace return structure
    mock_face = mocker.MagicMock()
    mock_face.bbox = [10.0, 20.0, 100.0, 120.0]
    mock_face.det_score = 0.98
    mock_face.kps = None
    mock_face.embedding = [0.1] * 512

    mocker.patch("app.api.faces.get_face_analysis", return_value=mocker.MagicMock(get=lambda img: [mock_face]))
    mocker.patch("app.api.faces.get_model_status", return_value=True)

    with open("test_sample.jpg", "wb") as f:
        f.write(b"fake_image_bytes")

    with open("test_sample.jpg", "rb") as f:
        response = client.post(
            "/api/v1/faces/detect",
            files={"file": ("test.jpg", f, "image/jpeg")},
            headers={"X-API-KEY": "local_dev_key"}
        )
    assert response.status_code == 200
```

---

## 3. Pre-Commit Quality Checks

Run linting and syntax verification before pushing code:

```bash
# Style check with ruff
ruff check .

# Validate documentation links
python3 .agents/skills/project-docs/scripts/lint-docs.py .
```

---

## Related Documentation

* [Making Changes & Definition of Done](making-changes.md)
* [Local Development Guide](local-development.md)
* [FastAPI Service Architecture](../services/fastapi.md)
