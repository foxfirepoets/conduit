from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable


class MarketplaceJobQueue:
    def __init__(self, executor: Callable[[str], Awaitable[dict[str, Any]]]) -> None:
        self._executor = executor
        self._tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}
        self._state: dict[str, dict[str, Any]] = {}

    def enqueue(self, job_id: str) -> dict[str, Any]:
        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            return self._state[job_id]
        loop = asyncio.get_running_loop()
        self._state[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "queued_at": time.time(),
            "started_at": None,
            "completed_at": None,
            "error": "",
        }
        task = loop.create_task(self._run(job_id))
        self._tasks[job_id] = task
        return self._state[job_id]

    async def _run(self, job_id: str) -> dict[str, Any]:
        state = self._state[job_id]
        state["status"] = "running"
        state["started_at"] = time.time()
        try:
            result = await self._executor(job_id)
        except Exception as exc:
            state["status"] = "failed"
            state["error"] = str(exc)
            state["completed_at"] = time.time()
            raise
        state["status"] = "completed"
        state["completed_at"] = time.time()
        state["result"] = result
        return result

    def get(self, job_id: str) -> dict[str, Any]:
        return self._state.get(job_id, {"job_id": job_id, "status": "missing"})

    def snapshot(self) -> dict[str, Any]:
        return {
            "jobs": [self._state[job_id] for job_id in sorted(self._state)],
        }
