from __future__ import annotations

import os
import time
import logging
from typing import Dict, Any
from fastapi import APIRouter

log = logging.getLogger("ml_chege_photos.metrics")
router = APIRouter(prefix="/api/v1/system", tags=["system"])

START_TIME = time.time()


def get_process_memory_mb() -> float:
    """Read resident memory (RSS) in MB using psutil or /proc/self/status fallback."""
    try:
        import psutil
        process = psutil.Process()
        return round(process.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        pass

    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return round(float(parts[1]) / 1024, 2)
    except Exception:
        pass

    return 0.0


def get_system_memory() -> Dict[str, Any]:
    """Read system / container memory metrics."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {
            "total_mb": round(vm.total / (1024 * 1024), 2),
            "available_mb": round(vm.available / (1024 * 1024), 2),
            "used_mb": round(vm.used / (1024 * 1024), 2),
            "percent": vm.percent,
        }
    except Exception:
        pass

    # Linux cgroups v2 fallback for container limits
    cgroup_mem_current = None
    cgroup_mem_max = None
    try:
        if os.path.exists("/sys/fs/cgroup/memory.current"):
            with open("/sys/fs/cgroup/memory.current") as f:
                cgroup_mem_current = int(f.read().strip())
        if os.path.exists("/sys/fs/cgroup/memory.max"):
            with open("/sys/fs/cgroup/memory.max") as f:
                val = f.read().strip()
                if val != "max":
                    cgroup_mem_max = int(val)
    except Exception:
        pass

    used_mb = round(cgroup_mem_current / (1024 * 1024), 2) if cgroup_mem_current else 0.0
    total_mb = round(cgroup_mem_max / (1024 * 1024), 2) if cgroup_mem_max else 512.0
    pct = round((used_mb / total_mb) * 100, 1) if total_mb > 0 else 0.0

    return {
        "total_mb": total_mb,
        "available_mb": round(max(0.0, total_mb - used_mb), 2),
        "used_mb": used_mb,
        "percent": pct,
    }


def get_cpu_percent() -> float:
    """Get current process CPU percentage."""
    try:
        import psutil
        return round(psutil.Process().cpu_percent(interval=0.05), 1)
    except Exception:
        return 0.0


@router.get("/metrics")
def system_metrics() -> Dict[str, Any]:
    """Provide real-time telemetry: RAM, CPU, PyTorch allocations, and model load states."""
    from app.ml.loader import get_model_status
    
    # ── PyTorch GPU/CPU memory ──
    torch_info: Dict[str, Any] = {"cuda_available": False}
    try:
        import torch
        torch_info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            torch_info["allocated_mb"] = round(torch.cuda.memory_allocated() / (1024 * 1024), 2)
            torch_info["reserved_mb"] = round(torch.cuda.memory_reserved() / (1024 * 1024), 2)
            torch_info["device_name"] = torch.cuda.get_device_name(0)
    except Exception:
        pass

    # ── Model states ──
    clip_ok = False
    try:
        from app.ml import semantic_search
        clip_ok = (semantic_search._clip_model is not None)
    except Exception:
        pass

    yolo_ok = False
    try:
        from app.ml import object_detection
        yolo_ok = (object_detection._net is not None)
    except Exception:
        pass

    rss_mb = get_process_memory_mb()
    sys_mem = get_system_memory()
    uptime_sec = round(time.time() - START_TIME, 1)

    return {
        "status": "ok",
        "service": "ml_chege_photos",
        "uptime_seconds": uptime_sec,
        "cpu_percent": get_cpu_percent(),
        "memory": {
            "rss_mb": rss_mb,
            "system_used_mb": sys_mem.get("used_mb", 0.0),
            "system_total_mb": sys_mem.get("total_mb", 0.0),
            "system_percent": sys_mem.get("percent", 0.0),
        },
        "torch": torch_info,
        "models": {
            "face_insightface": bool(get_model_status()),
            "clip_semantic": clip_ok,
            "yolov8_objects": yolo_ok,
        },
    }
