from __future__ import annotations

import asyncio
import logging
from typing import Callable

log = logging.getLogger("ml_chege_photos.queue")

class JobQueue:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker_task = None
        self.is_running: bool = False
        self._current_task: str | None = None  # name of currently executing job

    async def start(self):
        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker())
        log.info("Background ML job queue worker started.")

    async def stop(self):
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            log.info("Background ML job queue worker stopped.")

    async def add_job(self, func: Callable, *args, **kwargs):
        await self.queue.put((func, args, kwargs))
        log.info(f"Job {func.__name__} added to background queue. Queue size: {self.queue.qsize()}")

    async def _worker(self):
        while True:
            try:
                func, args, kwargs = await self.queue.get()
                self._current_task = func.__name__
                log.info(f"Running ML job {func.__name__} from queue...")
                # Run CPU-bound sync functions in the default executor to not block the event loop
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: func(*args, **kwargs))
                log.info(f"ML job {func.__name__} completed successfully.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error running ML job {func.__name__}: {e}", exc_info=True)
            finally:
                self._current_task = None
                self.queue.task_done()

ml_job_queue = JobQueue()
