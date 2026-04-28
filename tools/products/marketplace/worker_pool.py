from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path

from ...browser import BrowserTool, ProxyConfig


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    stem = cleaned[:48] or "default"
    return f"{stem}_{digest}"


class MarketplaceBrowserWorkerPool:
    def __init__(self, data_dir: Path, max_workers: int = 10) -> None:
        self._data_dir = Path(data_dir)
        self._max_workers = max_workers
        self._workers: dict[str, BrowserTool] = {}
        self._worker_routes: dict[str, str] = {}

    @staticmethod
    def _route_signature(proxy_config: ProxyConfig | dict | None) -> str:
        if proxy_config is None:
            return ""
        if isinstance(proxy_config, ProxyConfig):
            payload = {
                "host": proxy_config.host,
                "port": proxy_config.port,
                "protocol": proxy_config.protocol,
                "username": proxy_config.username,
                "password": proxy_config.password,
            }
        else:
            payload = {
                "host": proxy_config.get("host", ""),
                "port": proxy_config.get("port", 0),
                "protocol": proxy_config.get("protocol", "http"),
                "username": proxy_config.get("username", ""),
                "password": proxy_config.get("password", ""),
            }
        return json.dumps(payload, sort_keys=True)

    def acquire(self, session_key: str, proxy_config: ProxyConfig | dict | None = None) -> BrowserTool:
        worker = self._workers.get(session_key)
        route_signature = self._route_signature(proxy_config)
        if worker is not None and self._worker_routes.get(session_key, "") == route_signature:
            return worker
        if worker is None and len(self._workers) >= self._max_workers:
            raise RuntimeError(
                f"Worker pool exhausted: {self._max_workers} workers already active. "
                "Release existing workers before acquiring new ones."
            )
        if worker is not None:
            self._workers.pop(session_key, None)
            self._worker_routes.pop(session_key, None)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None:
                loop.create_task(worker.close())

        route_suffix = hashlib.sha256(route_signature.encode("utf-8")).hexdigest()[:8] if route_signature else "direct"
        slug = _safe_segment(f"{session_key}_{route_suffix}")
        worker_root = self._data_dir / "marketplace_runtime" / slug
        worker = BrowserTool(
            data_dir=self._data_dir,
            profile_dir=worker_root / "profile",
            screenshot_dir=worker_root / "screenshots",
            pdf_dir=worker_root / "pdfs",
            session_dir=worker_root / "sessions",
            proxy_config=proxy_config,
        )
        self._workers[session_key] = worker
        self._worker_routes[session_key] = route_signature
        return worker

    async def release(self, session_key: str, keep_alive: bool = True) -> None:
        if keep_alive:
            return
        worker = self._workers.pop(session_key, None)
        self._worker_routes.pop(session_key, None)
        if worker is None:
            return
        try:
            await worker.close()
        except Exception:
            pass

    async def close_all(self) -> None:
        for worker in list(self._workers.values()):
            try:
                await worker.close()
            except Exception:
                pass
        self._workers.clear()
        self._worker_routes.clear()

    def stats(self) -> dict:
        return {
            "active_workers": len(self._workers),
            "max_workers": self._max_workers,
            "available_slots": self._max_workers - len(self._workers),
        }
