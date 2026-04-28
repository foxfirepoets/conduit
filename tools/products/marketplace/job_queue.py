from __future__ import annotations

import asyncio
import time
import traceback
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
            self._state[job_id] = {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "completed_at": time.time(),
            }
            return {}
        state["status"] = "completed"
        state["completed_at"] = time.time()
        state["result"] = result
        return result

    def get(self, job_id: str) -> dict[str, Any]:
        task = self._tasks.get(job_id)
        if (
            task is not None
            and task.done()
            and not task.cancelled()
            and task.exception() is not None
            and self._state.get(job_id, {}).get("status") != "failed"
        ):
            exc = task.exception()
            self._state[job_id] = {
                "status": "failed",
                "error": str(exc),
                "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                "completed_at": time.time(),
            }
        return self._state.get(job_id, {"job_id": job_id, "status": "missing"})

    def cancel(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            task.cancel()
            return True
        return False

    def cleanup_completed(self, max_age_seconds: int = 3600) -> int:
        now = time.time()
        to_remove = [
            job_id
            for job_id, state in self._state.items()
            if state.get("status") in ("completed", "failed")
            and state.get("completed_at") is not None
            and (now - state["completed_at"]) > max_age_seconds
        ]
        for job_id in to_remove:
            self._state.pop(job_id, None)
            self._tasks.pop(job_id, None)
        return len(to_remove)

    def snapshot(self) -> dict[str, Any]:
        return {
            "jobs": [self._state[job_id] for job_id in sorted(self._state)],
        }
