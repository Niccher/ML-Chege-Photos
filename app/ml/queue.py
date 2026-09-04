from __future__ import annotations

import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

from app.config import settings

log = logging.getLogger("ml_chege_photos.queue")


class JobQueue:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker_tasks: list[asyncio.Task] = []
        self.is_running: bool = False
        self._current_tasks: dict[int, str] = {}
        self.total_processed: int = 0
        self.total_failed: int = 0
        self.last_error: str | None = None
        self.last_error_time: str | None = None
        self.num_workers: int = int(os.getenv("ML_CONCURRENT_WORKERS", str(settings.ml_concurrent_workers or 4)))

    @property
    def _current_task(self) -> str | None:
        """Compatibility property: returns any currently active task name."""
        if self._current_tasks:
            return next(iter(self._current_tasks.values()))
        return None

    async def start(self):
        self.is_running = True
        self.worker_tasks = [
            asyncio.create_task(self._worker(worker_id=i))
            for i in range(max(1, self.num_workers))
        ]
        log.info(
            "Background ML job queue started with %d concurrent workers.",
            len(self.worker_tasks)
        )

    async def stop(self):
        self.is_running = False
        for task in self.worker_tasks:
            task.cancel()
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()
        self._current_tasks.clear()
        log.info("Background ML job queue workers stopped.")

    async def add_job(self, func: Callable, *args, **kwargs):
        await self.queue.put((func, args, kwargs))
        log.info(
            "Job %s added to background queue. Pending queue size: %d",
            func.__name__,
            self.queue.qsize()
        )

    async def _worker(self, worker_id: int):
        while True:
            try:
                func, args, kwargs = await self.queue.get()
                self._current_tasks[worker_id] = func.__name__
                log.info(
                    "[Worker %d] Running ML job %s (queue depth remaining: %d)...",
                    worker_id,
                    func.__name__,
                    self.queue.qsize()
                )
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: func(*args, **kwargs))
                self.total_processed += 1
                log.info("[Worker %d] ML job %s finished successfully.", worker_id, func.__name__)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.total_failed += 1
                self.last_error = str(e)
                self.last_error_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                log.error("[Worker %d] Error running ML job %s: %s", worker_id, getattr(func, '__name__', 'unknown'), e, exc_info=True)
            finally:
                self._current_tasks.pop(worker_id, None)
                self.queue.task_done()


ml_job_queue = JobQueue()
