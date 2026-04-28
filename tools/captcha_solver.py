"""
tools/captcha_solver.py — CAPTCHA solving integration for Conduit.

Supports CapSolver API (reCAPTCHA v2, hCaptcha, Cloudflare Turnstile).
Gracefully degrades when no API key is configured.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)

CAPSOLVER_BASE = "https://api.capsolver.com"


class CapSolverClient:
    """
    Client for the CapSolver CAPTCHA solving API.
    API key sourced from env CAPSOLVER_API_KEY or vault.get("capsolver_api_key").
    Gracefully returns {solved: False, error: "..."} when key is missing.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("CAPSOLVER_API_KEY", "")

    def _post_sync(self, path: str, payload: dict) -> dict:
        """Synchronous HTTP POST to CapSolver API (uses stdlib only). Runs in thread executor."""
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{CAPSOLVER_BASE}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            return {"errorCode": "REQUEST_FAILED", "errorDescription": str(exc)}

    async def _post(self, path: str, payload: dict) -> dict:
        """Async HTTP POST — runs _post_sync in a thread pool to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._post_sync, path, payload)

    async def _poll_task(self, task_id: str, max_wait_s: int = 120) -> dict:
        """Poll CapSolver until task is ready or timeout (non-blocking)."""
        import time
        deadline = time.monotonic() + max_wait_s
        while time.monotonic() < deadline:
            resp = await self._post("/getTaskResult", {"clientKey": self.api_key, "taskId": task_id})
            status = resp.get("status", "")
            if status == "ready":
                return resp.get("solution", {})
            if resp.get("errorCode"):
                return {}
            await asyncio.sleep(3)
        return {}

    async def solve_recaptcha_v2(self, site_key: str, page_url: str) -> str:
        """Solve reCAPTCHA v2. Returns gRecaptchaResponse token or empty string."""
        if not self.api_key:
            return ""
        resp = await self._post("/createTask", {
            "clientKey": self.api_key,
            "task": {
                "type": "ReCaptchaV2TaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
        })
        task_id = resp.get("taskId")
        if not task_id:
            logger.warning("CapSolver createTask failed: %s", resp)
            return ""
        solution = await self._poll_task(task_id)
        return solution.get("gRecaptchaResponse", "")

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        """Solve hCaptcha. Returns token or empty string."""
        if not self.api_key:
            return ""
        resp = await self._post("/createTask", {
            "clientKey": self.api_key,
            "task": {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
        })
        task_id = resp.get("taskId")
        if not task_id:
            return ""
        solution = await self._poll_task(task_id)
        token = solution.get("token") or solution.get("gRecaptchaResponse", "")
        return token

    async def solve_cloudflare_turnstile(self, site_key: str, page_url: str) -> str:
        """Solve Cloudflare Turnstile. Returns token or empty string."""
        if not self.api_key:
            return ""
        resp = await self._post("/createTask", {
            "clientKey": self.api_key,
            "task": {
                "type": "AntiTurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": site_key,
            }
        })
        task_id = resp.get("taskId")
        if not task_id:
            return ""
        solution = await self._poll_task(task_id)
        return solution.get("token", "")
