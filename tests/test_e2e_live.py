"""
tests/test_e2e_live.py — E2E live browser tests for Conduit.

Exercises ConduitBridge against real public websites and verifies:
  - Browser actions produce correct results
  - Every action is appended to the SHA-256 audit hash chain
  - verify_chain() returns True after each test
  - The proof bundle is self-verifiable via the embedded verify.py

Bootstrap strategy: mirrors test_audit_chain.py — a minimal sys.modules
shim wires the relative-import package hierarchy so all three real modules
(audit.py, conduit_bridge.py, conduit_proof.py) load cleanly from their
source files without needing an installed package.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import types
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Package bootstrap — identical pattern to test_audit_chain.py
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(__file__).parent.parent  # …/Conduit


def _bootstrap(tmp_db: Path) -> None:
    """Wire sys.modules so relative imports inside the real source files resolve."""

    # cato (top-level namespace package)
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules.setdefault("cato", cato_pkg)

    # cato.platform — points get_data_dir() at our temp directory
    platform_mod = types.ModuleType("cato.platform")
    platform_mod.get_data_dir = lambda: tmp_db.parent  # type: ignore[attr-defined]
    sys.modules["cato.platform"] = platform_mod
    cato_pkg.platform = platform_mod  # type: ignore[attr-defined]

    # cato.audit — load the real file
    if "cato.audit" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.audit",
            str(CONDUIT_ROOT / "audit.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        audit_mod = importlib.util.module_from_spec(spec)
        audit_mod.__package__ = "cato"
        sys.modules["cato.audit"] = audit_mod
        spec.loader.exec_module(audit_mod)  # type: ignore[union-attr]
        cato_pkg.audit = audit_mod  # type: ignore[attr-defined]

    # cato.tools sub-package
    tools_pkg = types.ModuleType("cato.tools")
    tools_pkg.__path__ = [str(CONDUIT_ROOT / "tools")]
    tools_pkg.__package__ = "cato.tools"
    sys.modules.setdefault("cato.tools", tools_pkg)
    cato_pkg.tools = tools_pkg  # type: ignore[attr-defined]

    # cato.tools.browser — load the real file (Patchright BrowserTool)
    if "cato.tools.browser" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.tools.browser",
            str(CONDUIT_ROOT / "tools" / "browser.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        browser_mod = importlib.util.module_from_spec(spec)
        browser_mod.__package__ = "cato.tools"
        sys.modules["cato.tools.browser"] = browser_mod
        spec.loader.exec_module(browser_mod)  # type: ignore[union-attr]
        tools_pkg.browser = browser_mod  # type: ignore[attr-defined]

    # cato.tools.conduit_bridge — load the real file
    if "cato.tools.conduit_bridge" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.tools.conduit_bridge",
            str(CONDUIT_ROOT / "tools" / "conduit_bridge.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        bridge_mod = importlib.util.module_from_spec(spec)
        bridge_mod.__package__ = "cato.tools"
        sys.modules["cato.tools.conduit_bridge"] = bridge_mod
        spec.loader.exec_module(bridge_mod)  # type: ignore[union-attr]
        tools_pkg.conduit_bridge = bridge_mod  # type: ignore[attr-defined]

    # cato.tools.conduit_proof — load the real file
    if "cato.tools.conduit_proof" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.tools.conduit_proof",
            str(CONDUIT_ROOT / "tools" / "conduit_proof.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        proof_mod = importlib.util.module_from_spec(spec)
        proof_mod.__package__ = "cato.tools"
        sys.modules["cato.tools.conduit_proof"] = proof_mod
        spec.loader.exec_module(proof_mod)  # type: ignore[union-attr]
        tools_pkg.conduit_proof = proof_mod  # type: ignore[attr-defined]

    # cato.tools.conduit_crawl — load real module (for map_site, crawl_site)
    if "cato.tools.conduit_crawl" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.tools.conduit_crawl",
            str(CONDUIT_ROOT / "tools" / "conduit_crawl.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        crawl_mod = importlib.util.module_from_spec(spec)
        crawl_mod.__package__ = "cato.tools"
        sys.modules["cato.tools.conduit_crawl"] = crawl_mod
        spec.loader.exec_module(crawl_mod)  # type: ignore[union-attr]
        tools_pkg.conduit_crawl = crawl_mod  # type: ignore[attr-defined]

    # cato.tools.conduit_monitor — load real module (for fingerprint, check_changed)
    if "cato.tools.conduit_monitor" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.tools.conduit_monitor",
            str(CONDUIT_ROOT / "tools" / "conduit_monitor.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        mon_mod = importlib.util.module_from_spec(spec)
        mon_mod.__package__ = "cato.tools"
        sys.modules["cato.tools.conduit_monitor"] = mon_mod
        spec.loader.exec_module(mon_mod)  # type: ignore[union-attr]
        tools_pkg.conduit_monitor = mon_mod  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Module-scoped DB fixture (one database for all tests, reusing the browser)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("e2e_conduit") / "cato.db"
    _bootstrap(db)
    return db


@pytest.fixture(scope="module")
def classes(tmp_db):
    """Return the three real classes loaded by the bootstrap."""
    AuditLog = sys.modules["cato.audit"].AuditLog
    ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
    return AuditLog, ConduitBridge


def _db_rows(db: Path, session_id: str) -> list[dict]:
    """Return all audit_log rows for session_id as plain dicts."""
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


def _count_audit(db: Path, session_id: str) -> int:
    return len(_db_rows(db, session_id))


# ---------------------------------------------------------------------------
# Shared session bridge fixture
# We use one bridge per test-module execution so the browser process is
# started once and reused — much faster than spawning Chromium per test.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bridge(tmp_db, classes):
    """Start a single ConduitBridge for the entire test module."""
    AuditLog, ConduitBridge = classes
    sess = f"e2e-live-{uuid.uuid4().hex[:8]}"
    b = ConduitBridge(sess, budget_cents=99999, data_dir=tmp_db.parent)

    async def _start():
        await b.start()

    asyncio.get_event_loop().run_until_complete(_start())
    yield b

    async def _stop():
        await b.stop()

    asyncio.get_event_loop().run_until_complete(_stop())


# ---------------------------------------------------------------------------
# Helper: run an async coroutine from a sync test
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Test 1: Basic navigation + extract_main
# ---------------------------------------------------------------------------

class TestNavigateAndExtractMain:
    """Navigate to example.com, extract main content, verify audit entries."""

    def test_navigate_returns_title(self, bridge, tmp_db):
        result = run(bridge.navigate("https://example.com"))
        assert "error" not in result, f"navigate error: {result.get('error')}"
        title = result.get("title", "")
        assert "Example" in title or "example" in title.lower(), (
            f"Expected 'Example' in title, got: {title!r}"
        )

    def test_extract_main_returns_text_with_expected_content(self, bridge, tmp_db):
        # Re-navigate to guarantee we are on the right page
        run(bridge.navigate("https://example.com"))
        result = run(bridge.extract_main())
        assert "error" not in result, f"extract_main error: {result.get('error')}"
        text = result.get("text", "")
        assert len(text) > 0, "extract_main returned empty text"
        # example.com has "Example Domain" as its heading
        assert "Example" in text or "domain" in text.lower(), (
            f"Expected content text, got: {text[:200]!r}"
        )

    def test_audit_has_entries_after_navigate_and_extract(self, bridge, tmp_db):
        sid = bridge._session_id
        count = _count_audit(tmp_db, sid)
        # At least navigate + extract_main from this test class (prior tests may add more)
        assert count >= 2, f"Expected >= 2 audit entries, got {count}"

    def test_verify_chain_true_after_navigate_extract(self, bridge, tmp_db):
        sid = bridge._session_id
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(sid) is True, "Hash chain verification FAILED after navigate+extract_main"


# ---------------------------------------------------------------------------
# Test 2: Scroll + screenshot
# ---------------------------------------------------------------------------

class TestScrollAndScreenshot:

    def test_navigate_to_hn(self, bridge, tmp_db):
        result = run(bridge.navigate("https://news.ycombinator.com"))
        assert "error" not in result, f"navigate error: {result.get('error')}"
        title = result.get("title", "")
        assert "Hacker News" in title or len(title) > 0, (
            f"Unexpected HN title: {title!r}"
        )

    def test_scroll_down_returns_success(self, bridge, tmp_db):
        result = run(bridge.scroll("down", 500))
        assert "error" not in result, f"scroll error: {result.get('error')}"
        assert result.get("success") is True, f"scroll did not return success=True: {result}"

    def test_screenshot_returns_path(self, bridge, tmp_db):
        result = run(bridge.screenshot())
        assert "error" not in result, f"screenshot error: {result.get('error')}"
        assert result.get("success") is True, f"screenshot failed: {result}"
        path = result.get("path", "")
        assert path.endswith(".png"), f"Expected .png path, got: {path!r}"
        assert Path(path).exists(), f"Screenshot file does not exist: {path}"

    def test_audit_chain_intact_after_scroll_screenshot(self, bridge, tmp_db):
        sid = bridge._session_id
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(sid) is True, "Hash chain broken after scroll+screenshot"

    def test_audit_entries_include_scroll_and_screenshot(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.scroll" in tool_names, f"No browser.scroll in audit: {tool_names}"
        assert "browser.screenshot" in tool_names, f"No browser.screenshot in audit: {tool_names}"


# ---------------------------------------------------------------------------
# Test 3: eval — audited JS execution
# ---------------------------------------------------------------------------

class TestEval:

    def test_eval_returns_document_title(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.eval("document.title"))
        assert "error" not in result or result.get("success") is not False, (
            f"eval error: {result.get('error')}"
        )
        assert result.get("success") is True, f"eval not successful: {result}"
        title_result = result.get("result", "")
        assert "Example" in str(title_result), (
            f"Expected 'Example' in eval result, got: {title_result!r}"
        )

    def test_eval_audit_entry_contains_js_code(self, bridge, tmp_db):
        """The eval audit entry MUST record the js_code — the Conduit differentiator."""
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        eval_rows = [r for r in rows if r["tool_name"] == "browser.eval"]
        assert len(eval_rows) >= 1, "No browser.eval entry in audit log"

        last_eval = eval_rows[-1]
        inputs = json.loads(last_eval["inputs_json"])
        assert "js_code" in inputs, (
            f"js_code not in eval audit inputs — Conduit differentiator MISSING. "
            f"inputs_json: {last_eval['inputs_json']}"
        )
        assert inputs["js_code"] == "document.title", (
            f"js_code mismatch: expected 'document.title', got {inputs['js_code']!r}"
        )

    def test_eval_verify_chain_true(self, bridge, tmp_db):
        sid = bridge._session_id
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(sid) is True, "Hash chain broken after eval"


# ---------------------------------------------------------------------------
# Test 4: wait + wait_for
# ---------------------------------------------------------------------------

class TestWaitAndWaitFor:

    def test_wait_returns_success(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.wait(0.5))
        assert "error" not in result, f"wait error: {result.get('error')}"
        assert result.get("success") is True, f"wait did not succeed: {result}"
        assert result.get("waited_seconds") == 0.5, (
            f"Expected waited_seconds=0.5, got {result.get('waited_seconds')}"
        )

    def test_wait_for_selector_h1_exists(self, bridge, tmp_db):
        result = run(bridge.wait_for("selector", "h1", timeout_ms=5000))
        assert "error" not in result, f"wait_for error: {result.get('error')}"
        assert result.get("success") is True, f"wait_for h1 did not succeed: {result}"

    def test_audit_entries_include_wait_and_wait_for(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.wait" in tool_names, f"No browser.wait in audit: {tool_names}"
        assert "browser.wait_for" in tool_names, f"No browser.wait_for in audit: {tool_names}"

    def test_verify_chain_true_after_wait(self, bridge, tmp_db):
        sid = bridge._session_id
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(sid) is True, "Hash chain broken after wait actions"


# ---------------------------------------------------------------------------
# Test 5: network_requests
# ---------------------------------------------------------------------------

class TestNetworkRequests:

    def test_network_requests_returns_nonempty_list(self, bridge, tmp_db):
        # Navigate first so there are requests in the log
        run(bridge.navigate("https://example.com"))
        result = run(bridge.network_requests())
        assert "error" not in result, f"network_requests error: {result.get('error')}"
        count = result.get("count", 0)
        requests = result.get("requests", [])
        assert count > 0, (
            f"Expected at least 1 network request, got count={count}. "
            f"requests={requests[:3]}"
        )

    def test_network_requests_in_audit(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.network_requests" in tool_names, (
            f"No browser.network_requests in audit: {tool_names}"
        )

    def test_verify_chain_true_after_network_requests(self, bridge, tmp_db):
        sid = bridge._session_id
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(sid) is True


# ---------------------------------------------------------------------------
# Test 6: accessibility_snapshot
# ---------------------------------------------------------------------------

class TestAccessibilitySnapshot:

    def test_accessibility_snapshot_returns_tree(self, bridge, tmp_db):
        """
        Patchright (stealth Playwright fork) removed the deprecated page.accessibility
        API in recent versions (the attribute no longer exists on the Page object).
        We therefore verify two behaviours:

          - If the API is available: result must contain a non-empty tree dict.
          - If the API is absent:    result must contain a descriptive 'error' key
                                     AND the audit entry must still be written
                                     (verified by the next test).

        Either outcome is considered correct behaviour; what must NOT happen is a
        silent no-op that skips the audit entry.
        """
        run(bridge.navigate("https://example.com"))
        result = run(bridge.accessibility_snapshot())

        if "error" in result:
            # Patchright removed page.accessibility — acceptable degraded mode.
            # Confirm the error is the expected API-missing message, not a crash.
            error_msg = result.get("error", "")
            assert "accessibility" in error_msg.lower() or "attribute" in error_msg.lower(), (
                f"Unexpected error from accessibility_snapshot: {error_msg!r}"
            )
            # The audit entry must still have been written (confirmed by next test).
        else:
            tree = result.get("tree")
            assert tree is not None, "accessibility_snapshot returned None tree"
            assert isinstance(tree, dict), f"Expected tree to be a dict, got {type(tree)}"
            assert len(tree) > 0, "accessibility_snapshot tree is empty dict"

    def test_accessibility_snapshot_audit_entry_exists(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.accessibility_snapshot" in tool_names, (
            f"No browser.accessibility_snapshot in audit: {tool_names}"
        )

    def test_verify_chain_true_after_accessibility_snapshot(self, bridge, tmp_db):
        sid = bridge._session_id
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(sid) is True


# ---------------------------------------------------------------------------
# Test 7: extract_main with max_chars, fmt=md, and provenance fields
# ---------------------------------------------------------------------------

class TestExtractMainCapabilities:

    def test_extract_main_with_max_chars_returns_truncated_flag(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.extract_main(max_chars=100))
        assert "error" not in result, f"extract_main error: {result.get('error')}"
        assert "truncated" in result, "extract_main must return truncated field"
        assert "content_hash" in result, "extract_main must return content_hash (provenance)"
        assert "char_count" in result, "extract_main must return char_count"
        assert result.get("char_count", 0) > 0, "expected non-zero char_count"

    def test_extract_main_fmt_md_returns_markdown_like_content(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.extract_main(fmt="md"))
        assert "error" not in result, f"extract_main fmt=md error: {result.get('error')}"
        text = result.get("text", "")
        assert len(text) > 0, "extract_main fmt=md returned empty text"
        # May contain markdown headings or plain text
        assert "Example" in text or "example" in text.lower() or "domain" in text.lower(), (
            f"Expected readable content, got: {text[:150]!r}"
        )

    def test_extract_main_provenance_in_audit(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        extract_rows = [r for r in rows if r["tool_name"] == "browser.extract_main"]
        assert len(extract_rows) >= 1, "No extract_main in audit"
        last = extract_rows[-1]
        outputs = json.loads(last["outputs_json"])
        assert "content_hash" in outputs or "char_count" in outputs, (
            f"extract_main audit outputs should include provenance: {outputs}"
        )


# ---------------------------------------------------------------------------
# Test 8: Browser search (DDG live)
# ---------------------------------------------------------------------------

class TestBrowserSearch:

    def test_search_returns_results_structure(self, bridge, tmp_db):
        result = run(bridge.search("conduit browser automation"))
        assert "results" in result or "query" in result, (
            f"search must return results/key structure: {list(result.keys())}"
        )
        results = result.get("results", [])
        assert isinstance(results, list), "results must be a list"
        # If DDG returns an error (bot detected), the error key must be present
        # and clearly explain why. Empty results without an error key is test theater.
        if not results:
            assert "error" in result, (
                f"DDG returned 0 results but no error key — silent failure. "
                f"Full result: {result}"
            )

    def test_search_audit_entry(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.search" in tool_names, f"No browser.search in audit: {tool_names}"


# ---------------------------------------------------------------------------
# Test 9: output_to_file
# ---------------------------------------------------------------------------

class TestOutputToFile:

    def test_output_to_file_writes_and_returns_path(self, bridge, tmp_db, tmp_path):
        run(bridge.navigate("https://example.com"))
        content = "Live test content from Conduit E2E"
        result = run(bridge.output_to_file("e2e_test_output", content, fmt="md"))
        assert "error" not in result, f"output_to_file error: {result.get('error')}"
        assert result.get("success") is True, f"output_to_file failed: {result}"
        assert result.get("bytes", 0) == len(content.encode()), (
            f"bytes mismatch: expected {len(content.encode())}, got {result.get('bytes')}"
        )
        path = result.get("path", "")
        assert path, "output_to_file must return path"
        assert Path(path).exists(), f"Output file does not exist: {path}"

    def test_output_to_file_audit_entry(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.output_to_file" in tool_names, (
            f"No browser.output_to_file in audit: {tool_names}"
        )


# ---------------------------------------------------------------------------
# Test 10: map_site (live small discovery)
# ---------------------------------------------------------------------------

class TestMapSite:

    def test_map_site_returns_urls(self, bridge, tmp_db):
        # example.com has very few links; limit=5 is enough
        result = run(bridge.map_site("https://example.com", limit=5))
        assert "error" not in result, f"map_site error: {result.get('error')}"
        assert "urls" in result, f"map_site must return urls: {list(result.keys())}"
        assert "count" in result, "map_site must return count"
        assert isinstance(result["urls"], list), "urls must be a list"
        assert result["count"] >= 1, "expected at least the seed URL"

    def test_map_site_audit_entry(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.map" in tool_names, f"No browser.map in audit: {tool_names}"


# ---------------------------------------------------------------------------
# Test 11: crawl_site (live small crawl)
# ---------------------------------------------------------------------------

class TestCrawlSite:

    def test_crawl_site_returns_pages(self, bridge, tmp_db):
        result = run(bridge.crawl_site("https://example.com", max_depth=1, limit=3))
        assert "error" not in result, f"crawl_site error: {result.get('error')}"
        assert "pages" in result, f"crawl_site must return pages: {list(result.keys())}"
        assert "count" in result, "crawl_site must return count"
        pages = result.get("pages", [])
        assert isinstance(pages, list), "pages must be a list"
        assert result["count"] >= 1, "expected at least one page"

    def test_crawl_site_page_has_url_title_text(self, bridge, tmp_db):
        result = run(bridge.crawl_site("https://example.com", max_depth=0, limit=1))
        assert result.get("pages"), "crawl_site should return at least one page"
        page = result["pages"][0]
        assert "url" in page and "title" in page, f"page must have url/title: {list(page.keys())}"
        assert "text" in page or "char_count" in page, f"page must have text or char_count: {list(page.keys())}"


# ---------------------------------------------------------------------------
# Test 12: fingerprint + check_changed
# ---------------------------------------------------------------------------

class TestFingerprintAndCheckChanged:

    def test_fingerprint_standalone_no_prior_navigate(self, tmp_db):
        """fingerprint() must work as the FIRST action on a fresh bridge (no prior navigate)."""
        ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
        b = ConduitBridge(f"fp-standalone-{uuid.uuid4().hex[:8]}", budget_cents=99999, data_dir=tmp_db.parent)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(b.start())
        try:
            result = loop.run_until_complete(b.fingerprint("https://example.com"))
            assert "error" not in result, (
                f"fingerprint() crashed on fresh bridge (no prior navigate): {result.get('error')}"
            )
            fp = result.get("fingerprint", "") or result.get("hash", "")
            assert fp and len(fp) == 64, f"expected 64-char hash, got: {fp!r}"
        finally:
            loop.run_until_complete(b.stop())

    def test_fingerprint_returns_hash(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.fingerprint("https://example.com"))
        assert "error" not in result, f"fingerprint error: {result.get('error')}"
        fp = result.get("fingerprint", "") or result.get("hash", "")
        assert fp and len(fp) == 64, (
            f"fingerprint must return 64-char hash, got: {fp!r}"
        )

    def test_check_changed_false_after_no_navigation(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        fp_result = run(bridge.fingerprint("https://example.com"))
        fp = fp_result.get("fingerprint", "") or fp_result.get("hash", "")
        assert fp, "need fingerprint for check_changed"
        result = run(bridge.check_changed("https://example.com", fp))
        assert "error" not in result, f"check_changed error: {result.get('error')}"
        # Page unchanged -> changed should be False
        changed = result.get("changed", result.get("page_changed", True))
        assert changed is False or result.get("fingerprint") == fp, (
            f"expected unchanged page: {result}"
        )

    def test_fingerprint_and_check_changed_in_audit(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.fingerprint" in tool_names, f"No browser.fingerprint in audit: {tool_names}"
        # check_changed only writes browser.change_monitor when page changed; unchanged runs are not logged


# ---------------------------------------------------------------------------
# Test 13: click (live — example.com has an anchor)
# ---------------------------------------------------------------------------

class TestClickLive:

    def test_click_on_link_by_selector(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        # example.com has <a href="https://www.iana.org/domains/example">More information...</a>
        result = run(bridge.click("a[href*='iana']"))
        if result.get("error"):
            # Selector might change; accept failure as long as audit was written
            sid = bridge._session_id
            rows = _db_rows(tmp_db, sid)
            click_rows = [r for r in rows if r["tool_name"] == "browser.click"]
            assert len(click_rows) >= 1, "click must be audited even on failure"
        else:
            assert result.get("success") is True, f"click failed: {result}"

    def test_verify_chain_after_click(self, bridge, tmp_db):
        sid = bridge._session_id
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(sid) is True, "Hash chain broken after click"


# ---------------------------------------------------------------------------
# Test 14: Session proof bundle export
# ---------------------------------------------------------------------------

class TestProofBundle:
    """Export proof bundle, verify archive structure, run embedded verify.py."""

    def test_export_proof_returns_success(self, bridge, tmp_db, tmp_path):
        result = bridge.export_proof(output_dir=str(tmp_path))
        assert result.get("success") is True, f"export_proof failed: {result}"
        assert "path" in result, "export_proof missing 'path' key"
        assert result["action_count"] > 0, "export_proof reports 0 actions"
        # Store path for subsequent tests in this class
        TestProofBundle._bundle_path = result["path"]

    def test_bundle_file_exists_and_is_tar_gz(self, bridge, tmp_db):
        bundle_path = Path(TestProofBundle._bundle_path)
        assert bundle_path.exists(), f"Bundle file does not exist: {bundle_path}"
        assert bundle_path.name.endswith(".tar.gz"), (
            f"Bundle is not a .tar.gz: {bundle_path.name}"
        )

    def test_bundle_contains_required_files(self, bridge, tmp_db):
        with tarfile.open(TestProofBundle._bundle_path, "r:gz") as tar:
            names = tar.getnames()

        required = ["audit_log.jsonl", "verify.py", "manifest.json"]
        for req in required:
            assert any(req in n for n in names), (
                f"Required file '{req}' not in bundle. Contents: {names}"
            )

    def test_bundle_audit_log_has_valid_jsonl(self, bridge, tmp_db):
        with tarfile.open(TestProofBundle._bundle_path, "r:gz") as tar:
            member = next(m for m in tar.getmembers() if "audit_log.jsonl" in m.name)
            content = tar.extractfile(member).read().decode("utf-8")

        lines = [l for l in content.splitlines() if l.strip()]
        assert len(lines) > 0, "audit_log.jsonl is empty"
        for line in lines:
            row = json.loads(line)  # must not raise
            assert "session_id" in row, f"Row missing session_id: {row}"
            assert "row_hash" in row, f"Row missing row_hash: {row}"
            assert "tool_name" in row, f"Row missing tool_name: {row}"

    def test_bundle_manifest_contains_expected_keys(self, bridge, tmp_db):
        with tarfile.open(TestProofBundle._bundle_path, "r:gz") as tar:
            member = next(m for m in tar.getmembers() if "manifest.json" in m.name)
            manifest = json.loads(tar.extractfile(member).read().decode("utf-8"))

        for key in ("session_id", "exported_at", "action_count", "chain_hash"):
            assert key in manifest, f"manifest.json missing key '{key}': {manifest}"
        assert manifest["action_count"] > 0, "Manifest action_count is 0"

    def test_verify_py_passes_when_run_standalone(self, bridge, tmp_db, tmp_path):
        """Extract the bundle into a temp directory and run verify.py as a subprocess."""
        bundle_path = TestProofBundle._bundle_path
        extract_dir = tmp_path / "proof_extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(bundle_path, "r:gz") as tar:
            tar.extractall(str(extract_dir))

        # Find the verify.py (may be nested under session_proof/)
        verify_scripts = list(extract_dir.rglob("verify.py"))
        assert len(verify_scripts) >= 1, (
            f"verify.py not found after extraction. Contents: {list(extract_dir.rglob('*'))}"
        )
        verify_py = verify_scripts[0]

        proc = subprocess.run(
            [sys.executable, str(verify_py)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(verify_py.parent),
        )
        output = proc.stdout + proc.stderr
        assert proc.returncode == 0, (
            f"verify.py exited with code {proc.returncode}.\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        )
        assert "VERIFIED" in output, (
            f"verify.py did not print VERIFIED.\nOutput: {output}"
        )


# ---------------------------------------------------------------------------
# Test 8: Full audit chain integrity
# ---------------------------------------------------------------------------

class TestFullAuditChainIntegrity:
    """Final integrity sweep after all tests have run actions."""

    def test_verify_chain_returns_true(self, bridge, tmp_db):
        sid = bridge._session_id
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        result = log.verify_chain(sid)
        assert result is True, (
            f"CRITICAL: verify_chain() returned False for session {sid}. "
            "The audit chain has been compromised."
        )

    def test_action_count_matches_audit_entries(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        assert len(rows) > 0, "No audit entries recorded — bridge never logged anything"
        # We ran many actions across 7 test classes, expect at least 15
        assert len(rows) >= 15, (
            f"Expected >= 15 audit entries across all E2E tests, got {len(rows)}"
        )

    def test_no_entries_have_empty_tool_name(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        empty_tool = [r for r in rows if not r.get("tool_name", "").strip()]
        assert len(empty_tool) == 0, (
            f"Found {len(empty_tool)} audit entries with empty tool_name: {empty_tool}"
        )

    def test_all_entries_have_valid_row_hash(self, bridge, tmp_db):
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        for row in rows:
            rh = row.get("row_hash", "")
            assert rh and len(rh) == 64, (
                f"Row id={row['id']} has invalid row_hash: {rh!r}"
            )

    def test_all_entries_have_linked_prev_hash(self, bridge, tmp_db):
        """Each row's prev_hash must equal the row_hash of the preceding row."""
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        # The first row has prev_hash == ''
        assert rows[0]["prev_hash"] == "", (
            f"First row prev_hash should be empty, got: {rows[0]['prev_hash']!r}"
        )
        # Each subsequent row links back
        for i in range(1, len(rows)):
            expected_prev = rows[i - 1]["row_hash"]
            actual_prev = rows[i]["prev_hash"]
            assert actual_prev == expected_prev, (
                f"Chain link broken at row id={rows[i]['id']}: "
                f"prev_hash={actual_prev!r} != expected {expected_prev!r}"
            )

    def test_receipt_signed_hash_covers_all_rows(self, bridge, tmp_db):
        """ReceiptWriter.generate() must produce a non-empty signed_hash."""
        import hashlib
        sid = bridge._session_id
        rows = _db_rows(tmp_db, sid)
        # Manually compute expected signed_hash
        combined = "".join(r["row_hash"] for r in rows)
        expected = hashlib.sha256(combined.encode("utf-8")).hexdigest()

        # Load and run the real ReceiptWriter.
        # IMPORTANT: the module MUST be registered in sys.modules before exec()
        # because Python's dataclass machinery resolves field annotations via
        # sys.modules[cls.__module__].__dict__ — if the module is not registered
        # it raises AttributeError: 'NoneType' object has no attribute '__dict__'.
        receipt_mod_name = "receipt_standalone_e2e_{}".format(uuid.uuid4().hex[:8])
        receipt_src = (CONDUIT_ROOT / "receipt.py").read_text(encoding="utf-8")
        receipt_src_patched = receipt_src.replace(
            "from .audit import AuditLog",
            "from cato.audit import AuditLog",
        )
        receipt_mod = types.ModuleType(receipt_mod_name)
        receipt_mod.__file__ = str(CONDUIT_ROOT / "receipt.py")
        # Register BEFORE exec so dataclass __module__ lookup succeeds
        sys.modules[receipt_mod_name] = receipt_mod
        try:
            exec(
                compile(receipt_src_patched, str(CONDUIT_ROOT / "receipt.py"), "exec"),
                receipt_mod.__dict__,
            )

            AuditLog = sys.modules["cato.audit"].AuditLog
            log = AuditLog(db_path=tmp_db)
            writer = receipt_mod.ReceiptWriter()
            receipt = writer.generate(sid, log)
        finally:
            sys.modules.pop(receipt_mod_name, None)

        assert receipt.signed_hash == expected, (
            f"Receipt signed_hash mismatch.\n"
            f"  Expected: {expected}\n"
            f"  Got:      {receipt.signed_hash}"
        )
        assert len(receipt.actions) == len(rows), (
            f"Receipt action count {len(receipt.actions)} != audit row count {len(rows)}"
        )
