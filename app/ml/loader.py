from __future__ import annotations

# ── Model status (Phase 2 will replace this with actual loading) ──
_models_loaded: bool = False


def get_model_status() -> bool:
    return _models_loaded
