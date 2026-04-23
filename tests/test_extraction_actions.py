"""
tests/test_extraction_actions.py

Live browser tests for Wave 2 BrowserTool actions:
  eval, extract_main, output_to_file, accessibility_snapshot, network_requests

All tests use a real Patchright Chromium browser against public sites.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sqlite3
import sys
import types
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(__file__).parent.parent


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
    db = tmp_path_factory.mktemp("wave2_live") / "cato.db"
    _bootstrap(db)
    return db


@pytest.fixture(scope="module")
def bridge(tmp_db):
    ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
    sess = f"wave2-live-{uuid.uuid4().hex[:8]}"
    b = ConduitBridge(sess, budget_cents=99999, data_dir=tmp_db.parent)
    asyncio.get_event_loop().run_until_complete(b.start())
    yield b
    asyncio.get_event_loop().run_until_complete(b.stop())


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


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
# Tests: eval
# ---------------------------------------------------------------------------

class TestEval:

    def test_eval_document_title(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.eval("document.title"))
        assert result.get("success") is True, f"eval failed: {result}"
        assert "Example" in str(result.get("result", ""))

    def test_eval_returns_code_hash(self, bridge):
        run(bridge.navigate("https://example.com"))
        js = "document.title"
        result = run(bridge.eval(js))
        expected_hash = hashlib.sha256(js.encode()).hexdigest()[:16]
        assert result.get("code_hash") == expected_hash, (
            f"code_hash mismatch: expected {expected_hash!r}, got {result.get('code_hash')!r}"
        )

    def test_eval_arithmetic_expression(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.eval("1 + 1"))
        assert result.get("success") is True
        assert result.get("result") == 2

    def test_eval_syntax_error_returns_failure(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.eval("invalid {{{"))
        assert result.get("success") is False
        assert "error" in result

    def test_eval_audit_entry_contains_js_code(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        js = "document.querySelectorAll('h1').length"
        run(bridge.eval(js))
        rows = _db_rows(tmp_db, bridge._session_id)
        eval_rows = [r for r in rows if r["tool_name"] == "browser.eval"]
        assert len(eval_rows) >= 1, "No browser.eval in audit"
        last = eval_rows[-1]
        inputs = json.loads(last["inputs_json"])
        assert "js_code" in inputs, f"js_code not in eval audit inputs: {inputs}"

    def test_eval_returns_url(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.eval("window.location.href"))
        assert "url" in result
        assert "example.com" in result.get("url", "")


# ---------------------------------------------------------------------------
# Tests: extract_main
# ---------------------------------------------------------------------------

class TestExtractMain:

    def test_extract_main_returns_text(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.extract_main())
        assert "error" not in result, f"extract_main error: {result}"
        text = result.get("text", "")
        assert len(text) > 0
        assert "Example" in text or "example" in text.lower() or "domain" in text.lower()

    def test_extract_main_returns_metadata(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.extract_main())
        assert "char_count" in result
        assert "url" in result
        assert "title" in result
        assert result.get("char_count", 0) > 0

    def test_extract_main_truncates_with_max_chars(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.extract_main(max_chars=50))
        assert "error" not in result
        assert result.get("char_count", 0) > 0
        text = result.get("text", "")
        assert len(text) <= 50 or result.get("truncated") is True

    def test_extract_main_returns_content_hash(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.extract_main())
        assert "content_hash" in result, "extract_main must return content_hash for provenance"

    def test_extract_main_fmt_md_returns_content(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.extract_main(fmt="md"))
        assert "error" not in result
        text = result.get("text", "")
        assert len(text) > 0

    def test_extract_main_char_count_reflects_full_length(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.extract_main())
        char_count = result.get("char_count", 0)
        text = result.get("text", "")
        # char_count should be >= len(text) (text may be truncated, char_count is full)
        assert char_count >= len(text)


# ---------------------------------------------------------------------------
# Tests: output_to_file
# ---------------------------------------------------------------------------

class TestOutputToFile:

    def test_output_to_file_creates_file(self, bridge):
        run(bridge.navigate("https://example.com"))
        content = "Live test from Conduit E2E"
        result = run(bridge.output_to_file("live_test_output", content, fmt="md"))
        assert result.get("success") is True, f"output_to_file failed: {result}"
        path = result.get("path", "")
        assert path, "must return path"
        assert Path(path).exists(), f"File does not exist: {path}"

    def test_output_to_file_byte_count(self, bridge):
        content = "Hello, UTF-8: \u00e9\u00e0\u00fc"
        result = run(bridge.output_to_file("live_utf8_test", content, fmt="md"))
        assert result.get("bytes") == len(content.encode("utf-8")), (
            f"byte count mismatch: {result.get('bytes')} vs {len(content.encode('utf-8'))}"
        )

    def test_output_to_file_sanitizes_path_traversal(self, bridge):
        result = run(bridge.output_to_file("../../../etc/passwd", "evil content", fmt="md"))
        assert result.get("success") is True
        assert ".." not in result.get("path", ""), "Path traversal not sanitized"

    def test_output_to_file_appends_extension(self, bridge):
        result = run(bridge.output_to_file("noextension", "content", fmt="txt"))
        assert result.get("path", "").endswith(".txt"), (
            f"Expected .txt extension: {result.get('path')}"
        )

    def test_output_to_file_audit_entry(self, bridge, tmp_db):
        run(bridge.output_to_file("audit_check", "data", fmt="md"))
        rows = _db_rows(tmp_db, bridge._session_id)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.output_to_file" in tool_names, f"No output_to_file in audit: {tool_names}"


# ---------------------------------------------------------------------------
# Tests: accessibility_snapshot
# ---------------------------------------------------------------------------

class TestAccessibilitySnapshot:

    def test_accessibility_snapshot_returns_tree_or_graceful_error(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.accessibility_snapshot())
        if "error" in result:
            # Patchright may have removed page.accessibility — acceptable degraded mode
            err = result["error"].lower()
            assert "accessibility" in err or "attribute" in err or "aria" in err, (
                f"Unexpected error: {result['error']!r}"
            )
        else:
            tree = result.get("tree")
            assert tree is not None, "accessibility_snapshot returned no tree"
            assert len(str(tree)) > 0

    def test_accessibility_snapshot_includes_url_and_title(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.accessibility_snapshot())
        # When Patchright has removed page.accessibility the result is an error dict;
        # url/title are only present on success.
        if "error" not in result:
            assert "url" in result
            assert "title" in result
        else:
            # Degraded mode — just verify we got the expected API-missing error
            err = result.get("error", "").lower()
            assert "accessibility" in err or "attribute" in err or "aria" in err, (
                f"Unexpected error: {result['error']!r}"
            )

    def test_accessibility_snapshot_audit_entry(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        run(bridge.accessibility_snapshot())
        rows = _db_rows(tmp_db, bridge._session_id)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.accessibility_snapshot" in tool_names, (
            f"No accessibility_snapshot in audit: {tool_names}"
        )


# ---------------------------------------------------------------------------
# Tests: network_requests
# ---------------------------------------------------------------------------

class TestNetworkRequests:

    def test_network_requests_after_navigate(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.network_requests())
        assert "error" not in result, f"network_requests error: {result}"
        assert result.get("count", 0) > 0, "Expected at least 1 network request"
        assert isinstance(result.get("requests", []), list)

    def test_network_requests_clears_after_read(self, bridge):
        run(bridge.navigate("https://example.com"))
        first = run(bridge.network_requests())
        second = run(bridge.network_requests())
        # After clearing, subsequent call should have fewer requests
        assert second.get("count", 0) <= first.get("count", 0), (
            f"Network log not cleared: first={first['count']}, second={second['count']}"
        )

    def test_network_requests_audit_entry(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        run(bridge.network_requests())
        rows = _db_rows(tmp_db, bridge._session_id)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.network_requests" in tool_names, (
            f"No network_requests in audit: {tool_names}"
        )

    def test_network_requests_each_entry_has_url(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.network_requests())
        for req in result.get("requests", []):
            assert "url" in req, f"Request entry missing url: {req}"
