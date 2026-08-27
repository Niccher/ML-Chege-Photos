# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-08-27

### Changed
- **Dockerization & Dependency Optimization**: Refactored `Dockerfile` to optimize image layer caching and minimize size.
  - Leveraged BuildKit cache mounts (`--mount=type=cache`) for `apt` package manager and `pip` installation caches.
  - Structured dependency installations into multi-layered stages: Core dependencies (`requirements-core.txt`), heavy Machine Learning libraries (`requirements-ml.txt`), and final model requirements (`requirements.txt` using local `wheels` cache directory).
  - Cleaned up wheels caches dynamically after installations.
- **Headless OpenCV Swap**: Replaced `opencv-python` with `opencv-python-headless` in `requirements.txt` to eliminate GUI/X11 runtime requirements, significantly reducing image footprint and runtime environment complexity in headless environments.
