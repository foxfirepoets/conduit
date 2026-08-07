"""
tests/test_conduit_crawl.py

Live browser tests for ConduitCrawler: map_site + crawl_site.

Uses a real Patchright browser against public sites.
Target: books.toscrape.com — a purpose-built scraping sandbox with many internal
links and a permissive robots.txt.

IMPORTANT: bridge.navigate() must be called before map_site/crawl_site in each
test because BrowserTool._page is None until the first navigation. The crawler
calls _browser._navigate() directly, which requires _page to already be open.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import sys
import types
import uuid
from pathlib import Path

import pytest

from tests.conftest import get_or_create_event_loop

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(__file__).parent.parent
SEED = "https://books.toscrape.com"  # scraping sandbox, permissive robots.txt


def _bootstrap(tmp_db: Path) -> None:
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules.setdefault("cato", cato_pkg)

    if "cato.platform" not in sys.modules:
        platform_mod = types.ModuleType("cato.platform")
        platform_mod.get_data_dir = lambda: tmp_db.parent  # type: ignore[attr-defined]
        sys.modules["cato.platform"] = platform_mod
        cato_pkg.platform = platform_mod  # type: ignore[attr-defined]
        sys.modules["cato.conduit_platform"] = platform_mod
        cato_pkg.conduit_platform = platform_mod  # type: ignore[attr-defined]

    if "cato.audit" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.audit", str(CONDUIT_ROOT / "audit.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "cato"
        sys.modules["cato.audit"] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        cato_pkg.audit = mod  # type: ignore[attr-defined]

    tools_pkg = types.ModuleType("cato.tools")
    tools_pkg.__path__ = [str(CONDUIT_ROOT / "tools")]
    tools_pkg.__package__ = "cato.tools"
    sys.modules.setdefault("cato.tools", tools_pkg)
    cato_pkg.tools = tools_pkg  # type: ignore[attr-defined]

    for mod_name, file_name in [
        ("cato.tools.browser", "browser.py"),
        ("cato.tools.conduit_bridge", "conduit_bridge.py"),
        ("cato.tools.conduit_crawl", "conduit_crawl.py"),
        ("cato.tools.conduit_monitor", "conduit_monitor.py"),
        ("cato.tools.conduit_proof", "conduit_proof.py"),
    ]:
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                mod_name, str(CONDUIT_ROOT / "tools" / file_name),
                submodule_search_locations=[],
            )
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            mod.__package__ = "cato.tools"
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("crawl_live") / "cato.db"
    _bootstrap(db)
    return db


@pytest.fixture(scope="module")
def bridge(tmp_db):
    ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
    sess = f"crawl-live-{uuid.uuid4().hex[:8]}"
    b = ConduitBridge(sess, budget_cents=99999, data_dir=tmp_db.parent)
    get_or_create_event_loop().run_until_complete(b.start())
    # Seed the browser so _page is initialized before crawler tests run
    get_or_create_event_loop().run_until_complete(b.navigate(SEED))
    yield b
    get_or_create_event_loop().run_until_complete(b.stop())


def run(coro):
    return get_or_create_event_loop().run_until_complete(coro)


def _db_rows(db: Path, session_id: str) -> list[dict]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests: map_site
# ---------------------------------------------------------------------------

class TestMapSite:

    def test_map_site_returns_required_fields(self, bridge):
        result = run(bridge.map_site(SEED, limit=5))
        assert "error" not in result, f"map_site error: {result}"
        assert "urls" in result
        assert "count" in result
        assert "base_url" in result
        assert result["base_url"] == SEED

    def test_map_site_includes_seed_url(self, bridge):
        result = run(bridge.map_site(SEED, limit=5))
        assert result["count"] >= 1, f"expected >= 1 URL, got {result['count']}"
        assert isinstance(result["urls"], list)

    def test_map_site_respects_limit(self, bridge):
        result = run(bridge.map_site(SEED, limit=4))
        assert result["count"] <= 4, (
            f"map_site exceeded limit of 4, got {result['count']}"
        )

    def test_map_site_urls_are_same_domain(self, bridge):
        result = run(bridge.map_site(SEED, limit=10))
        for url in result.get("urls", []):
            assert "books.toscrape.com" in url, (
                f"map_site returned off-domain URL: {url!r}"
            )

    def test_map_site_no_duplicate_urls(self, bridge):
        result = run(bridge.map_site(SEED, limit=10))
        urls = result.get("urls", [])
        assert len(urls) == len(set(urls)), (
            f"Duplicate URLs: {[u for u in urls if urls.count(u) > 1]}"
        )

    def test_map_site_audit_entry_written(self, bridge, tmp_db):
        run(bridge.map_site(SEED, limit=3))
        rows = _db_rows(tmp_db, bridge._session_id)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.map" in tool_names, f"No browser.map in audit: {tool_names}"

    def test_map_site_audit_entry_has_correct_url(self, bridge, tmp_db):
        run(bridge.map_site(SEED, limit=2))
        rows = _db_rows(tmp_db, bridge._session_id)
        map_rows = [r for r in rows if r["tool_name"] == "browser.map"]
        assert len(map_rows) >= 1
        inputs = json.loads(map_rows[-1]["inputs_json"])
        assert inputs.get("url") == SEED


# ---------------------------------------------------------------------------
# Tests: crawl_site
# ---------------------------------------------------------------------------

class TestCrawlSite:

    def test_crawl_site_returns_required_fields(self, bridge):
        result = run(bridge.crawl_site(SEED, max_depth=0, limit=1))
        assert "error" not in result, f"crawl_site error: {result}"
        assert "pages" in result
        assert "count" in result
        assert "base_url" in result

    def test_crawl_site_returns_at_least_one_page(self, bridge):
        result = run(bridge.crawl_site(SEED, max_depth=0, limit=1))
        assert result["count"] >= 1, f"expected >= 1 page, got {result['count']}"

    def test_crawl_site_page_has_required_fields(self, bridge):
        result = run(bridge.crawl_site(SEED, max_depth=0, limit=1))
        assert result.get("pages"), "no pages returned"
        page = result["pages"][0]
        assert "url" in page, f"page missing url: {list(page.keys())}"
        assert "title" in page, f"page missing title: {list(page.keys())}"
        assert "text" in page or "char_count" in page, (
            f"page missing text/char_count: {list(page.keys())}"
        )

    def test_crawl_site_respects_limit(self, bridge):
        result = run(bridge.crawl_site(SEED, max_depth=1, limit=3))
        assert result["count"] <= 3, (
            f"crawl_site exceeded limit of 3, got {result['count']}"
        )

    def test_crawl_site_page_text_is_nonempty(self, bridge):
        result = run(bridge.crawl_site(SEED, max_depth=0, limit=1))
        assert result.get("pages")
        page = result["pages"][0]
        text = page.get("text", "")
        char_count = page.get("char_count", 0)
        assert len(text) > 0 or char_count > 0, "Page text must not be empty"

    def test_crawl_site_page_url_is_valid(self, bridge):
        result = run(bridge.crawl_site(SEED, max_depth=0, limit=1))
        for page in result.get("pages", []):
            assert page["url"].startswith("http"), (
                f"Invalid page URL: {page['url']!r}"
            )

    def test_crawl_site_audit_entry_written(self, bridge, tmp_db):
        run(bridge.crawl_site(SEED, max_depth=0, limit=1))
        rows = _db_rows(tmp_db, bridge._session_id)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.crawl_page" in tool_names, (
            f"No browser.crawl_page in audit: {tool_names}"
        )

    def test_crawl_site_multi_depth_discovers_child_pages(self, bridge):
        result = run(bridge.crawl_site(SEED, max_depth=1, limit=5))
        assert result["count"] >= 1, "expected at least 1 page"
        urls = [p["url"] for p in result.get("pages", [])]
        assert any("books.toscrape.com" in u for u in urls), (
            f"Expected pages from books.toscrape.com: {urls}"
        )


# ---------------------------------------------------------------------------
# Tests: audit chain integrity after crawl
# ---------------------------------------------------------------------------

class TestCrawlAuditChain:

    def test_verify_chain_intact_after_crawl(self, bridge, tmp_db):
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(bridge._session_id) is True, (
            "Hash chain broken after crawl operations"
        )
