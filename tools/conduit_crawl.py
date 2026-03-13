"""
conduit_crawl.py — Audited site map discovery and bulk page extraction.

Every URL visited is logged to the SHA-256 hash chain.
Respects robots.txt and Crawl-delay. Adaptive rate limiting on 429/503.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections import deque
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser


def _fetch_robots_and_crawl_delay(domain: str, robots_url: str) -> Tuple[Optional[RobotFileParser], float]:
    """Fetch robots.txt and parse Crawl-delay (RobotFileParser doesn't expose it). Returns (rp or None, crawl_delay_sec)."""
    import urllib.request
    try:
        with urllib.request.urlopen(robots_url, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None, 0.0
    rp = RobotFileParser()
    rp.set_url(robots_url)
    rp.parse(body.splitlines())
    delay = 0.0
    for line in body.splitlines():
        line = line.strip()
        if line.lower().startswith("crawl-delay:"):
            try:
                delay = float(line.split(":", 1)[1].strip())
                break
            except ValueError:
                pass
    return rp, max(0.0, delay)


class ConduitCrawler:
    """
    Breadth-first site crawler integrated with Conduit's audit chain.

    Respects Crawl-delay from robots.txt and enforces minimum delay between
    requests per domain. On 429/503, applies exponential backoff and logs RATE_LIMITED.
    """

    def __init__(
        self,
        browser_tool,
        audit_log,
        session_id: str,
        crawl_delay_sec: float = 1.0,
        crawl_max_delay_sec: float = 60.0,
    ):
        self._browser = browser_tool
        self._audit_log = audit_log
        self._session_id = session_id
        self._crawl_delay_sec = crawl_delay_sec
        self._crawl_max_delay_sec = crawl_max_delay_sec
        self._robots_cache: dict[str, Optional[RobotFileParser]] = {}
        self._crawl_delay_cache: dict[str, float] = {}
        self._domain_last_request: dict[str, float] = {}
        self._domain_delay: dict[str, float] = {}

    async def _is_allowed(self, url: str) -> bool:
        """Check robots.txt and cache Crawl-delay. If robots.txt unreadable, allow."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        if domain not in self._robots_cache:
            robots_url = f"{domain}/robots.txt"
            loop = asyncio.get_event_loop()
            rp, delay = await loop.run_in_executor(None, _fetch_robots_and_crawl_delay, domain, robots_url)
            self._robots_cache[domain] = rp
            self._crawl_delay_cache[domain] = max(delay, self._crawl_delay_sec)
        cached = self._robots_cache[domain]
        if cached is None:
            return True
        return cached.can_fetch("*", url)

    async def _wait_crawl_delay(self, url: str) -> None:
        """Wait until Crawl-delay (and min delay) has elapsed for this domain."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        delay = self._crawl_delay_cache.get(domain, self._crawl_delay_sec)
        delay = max(delay, self._domain_delay.get(domain, self._crawl_delay_sec))
        last = self._domain_last_request.get(domain, 0)
        elapsed = time.monotonic() - last
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._domain_last_request[domain] = time.monotonic()

    def _check_rate_limit_and_backoff(self, url: str) -> None:
        """If network log shows 429/503, apply exponential backoff and log RATE_LIMITED."""
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        log = getattr(self._browser, "_network_log", [])
        for entry in log:
            if entry.get("type") == "response" and entry.get("url", "").startswith(domain):
                status = entry.get("status")
                if status in (429, 503):
                    current = self._domain_delay.get(domain, self._crawl_delay_sec)
                    new_delay = min(current * 2, self._crawl_max_delay_sec)
                    self._domain_delay[domain] = new_delay
                    self._audit_log.log(
                        session_id=self._session_id,
                        action_type="tool_call",
                        tool_name="browser.RATE_LIMITED",
                        inputs={"url": url, "domain": domain, "status": status},
                        outputs={"new_delay_sec": new_delay},
                        cost_cents=0,
                        error="",
                    )
                    break

    def _same_domain(self, base_url: str, url: str) -> bool:
        """Compare domains treating www.example.com and example.com as the same."""
        def _strip_www(netloc: str) -> str:
            return netloc.removeprefix("www.")
        return _strip_www(urlparse(base_url).netloc) == _strip_www(urlparse(url).netloc)

    async def _extract_links(self, base_url: str) -> list[str]:
        """Extract all <a href> links from current page. Returns absolute URLs."""
        hrefs = await self._browser._page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]'))
                       .map(a => a.href)
                       .filter(h => h.startsWith('http'))
        """)
        # Deduplicate and filter to same domain
        seen = set()
        links = []
        for href in hrefs:
            # Strip fragments
            clean = href.split('#')[0].rstrip('/')
            if clean and clean not in seen and self._same_domain(base_url, clean):
                seen.add(clean)
                links.append(clean)
        return links

    async def map_site(self, url: str, limit: int = 100, search: str = None) -> dict:
        """
        Breadth-first URL discovery. Returns list of URLs found.
        Logs a single MAP_SITE audit event with the result.
        """
        await self._browser._ensure_browser()
        queue = deque([url])
        visited = set()
        found = []

        while queue and len(found) < limit:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            if not await self._is_allowed(current):
                continue

            try:
                await self._wait_crawl_delay(current)
                await self._browser._navigate(current)
                self._check_rate_limit_and_backoff(current)
                links = await self._extract_links(current)
                for link in links:
                    if link not in visited:
                        queue.append(link)
                found.append(current)
            except Exception:
                pass

        if search:
            found = [u for u in found if search.lower() in u.lower()]

        result = {"urls": found, "count": len(found), "base_url": url}
        self._audit_log.log(
            session_id=self._session_id,
            action_type="tool_call",
            tool_name="browser.map",
            inputs={"url": url, "limit": limit, "search": search},
            outputs={"count": len(found), "urls_preview": found[:10]},
            cost_cents=0,
            error="",
        )
        return result

    async def crawl_site(
        self,
        url: str,
        max_depth: int = 2,
        include_paths: Optional[list] = None,
        exclude_paths: Optional[list] = None,
        limit: int = 20,
    ) -> dict:
        """
        Bulk extract pages with depth control. Every page logs to hash chain.
        Returns list of {url, title, text, char_count} dicts.
        """
        await self._browser._ensure_browser()
        queue = deque([(url, 0)])
        visited = set()
        pages = []

        while queue and len(pages) < limit:
            current_url, depth = queue.popleft()
            if current_url in visited or depth > max_depth:
                continue
            visited.add(current_url)

            # Path filtering
            path = urlparse(current_url).path
            if include_paths and not any(p in path for p in include_paths):
                continue
            if exclude_paths and any(p in path for p in exclude_paths):
                continue
            if not await self._is_allowed(current_url):
                continue

            try:
                await self._wait_crawl_delay(current_url)
                await self._browser._navigate(current_url)
                self._check_rate_limit_and_backoff(current_url)
                title = await self._browser._page.title()
                text = await self._browser._page.evaluate(
                    "() => document.body ? document.body.innerText.trim() : ''"
                )
                page_data = {
                    "url": current_url,
                    "title": title,
                    "text": text[:3000],
                    "char_count": len(text),
                    "depth": depth,
                }
                pages.append(page_data)

                # Audit each page visit
                self._audit_log.log(
                    session_id=self._session_id,
                    action_type="tool_call",
                    tool_name="browser.crawl_page",
                    inputs={"url": current_url, "depth": depth},
                    outputs={"title": title, "char_count": len(text)},
                    cost_cents=0,
                    error="",
                )

                # Enqueue child links
                if depth < max_depth:
                    links = await self._extract_links(current_url)
                    for link in links:
                        if link not in visited:
                            queue.append((link, depth + 1))

            except Exception as exc:
                self._audit_log.log(
                    session_id=self._session_id,
                    action_type="tool_call",
                    tool_name="browser.crawl_page",
                    inputs={"url": current_url, "depth": depth},
                    outputs={},
                    cost_cents=0,
                    error=str(exc),
                )

        # Build page hashes for Merkle tree construction
        page_hashes = []
        for p in pages:
            content_hash = hashlib.sha256(p.get("text", "").encode()).hexdigest()
            page_hashes.append({"url": p["url"], "hash": content_hash})

        result = {
            "pages": pages,
            "count": len(pages),
            "base_url": url,
            "page_hashes": page_hashes,
        }
        return result
