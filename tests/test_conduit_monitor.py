"""
tests/test_conduit_monitor.py

Live browser tests for ConduitMonitor: fingerprint + check_changed.

Uses a real Patchright browser against public sites.
Verifies SHA-256 fingerprinting, change detection, and PAGE_MUTATION audit events.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
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
    db = tmp_path_factory.mktemp("monitor_live") / "cato.db"
    _bootstrap(db)
    return db


@pytest.fixture(scope="module")
def bridge(tmp_db):
    ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
    sess = f"monitor-live-{uuid.uuid4().hex[:8]}"
    b = ConduitBridge(sess, budget_cents=99999, data_dir=tmp_db.parent)
    get_or_create_event_loop().run_until_complete(b.start())
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
# Tests: fingerprint — live against example.com
# ---------------------------------------------------------------------------

class TestFingerprint:

    def test_fingerprint_returns_64_char_hex(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.fingerprint("https://example.com"))
        assert "error" not in result, f"fingerprint error: {result}"
        fp = result.get("fingerprint", "")
        assert len(fp) == 64, f"fingerprint must be 64 chars, got {len(fp)}: {fp!r}"
        int(fp, 16)  # must be valid hex

    def test_fingerprint_includes_url_title_timestamp(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.fingerprint("https://example.com"))
        assert result.get("url") == "https://example.com"
        assert "title" in result
        assert "timestamp" in result
        assert "char_count" in result

    def test_fingerprint_is_deterministic_for_same_page(self, bridge):
        run(bridge.navigate("https://example.com"))
        fp1 = run(bridge.fingerprint("https://example.com"))
        fp2 = run(bridge.fingerprint("https://example.com"))
        assert fp1.get("fingerprint") == fp2.get("fingerprint"), (
            f"Fingerprint not deterministic: {fp1.get('fingerprint')!r} vs {fp2.get('fingerprint')!r}"
        )

    def test_fingerprint_differs_for_different_pages(self, bridge):
        run(bridge.navigate("https://example.com"))
        fp1 = run(bridge.fingerprint("https://example.com"))
        run(bridge.navigate("https://news.ycombinator.com"))
        fp2 = run(bridge.fingerprint("https://news.ycombinator.com"))
        assert fp1.get("fingerprint") != fp2.get("fingerprint"), (
            "Fingerprints of different pages must differ"
        )

    def test_fingerprint_audit_entry_written(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        run(bridge.fingerprint("https://example.com"))
        rows = _db_rows(tmp_db, bridge._session_id)
        tool_names = [r["tool_name"] for r in rows]
        assert "browser.fingerprint" in tool_names, (
            f"No browser.fingerprint in audit: {tool_names}"
        )

    def test_fingerprint_char_count_nonzero(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.fingerprint("https://example.com"))
        assert result.get("char_count", 0) > 0, "char_count should be non-zero for real page"


# ---------------------------------------------------------------------------
# Tests: check_changed — live
# ---------------------------------------------------------------------------

class TestCheckChanged:

    def test_check_changed_false_when_page_unchanged(self, bridge):
        run(bridge.navigate("https://example.com"))
        fp_result = run(bridge.fingerprint("https://example.com"))
        fp = fp_result.get("fingerprint", "")
        assert fp, "need fingerprint for check_changed"

        result = run(bridge.check_changed("https://example.com", fp))
        assert "error" not in result, f"check_changed error: {result}"
        changed = result.get("changed", result.get("page_changed", None))
        assert changed is False or result.get("fingerprint") == fp, (
            f"Page should be unchanged but got changed={changed}: {result}"
        )

    def test_check_changed_true_for_different_page(self, bridge):
        # Get fingerprint of example.com
        run(bridge.navigate("https://example.com"))
        fp_result = run(bridge.fingerprint("https://example.com"))
        example_fp = fp_result.get("fingerprint", "")

        # Check HN against example.com fingerprint — must detect change
        run(bridge.navigate("https://news.ycombinator.com"))
        result = run(bridge.check_changed("https://news.ycombinator.com", example_fp))
        assert "error" not in result, f"check_changed error: {result}"
        changed = result.get("changed", result.get("page_changed", False))
        assert changed is True, (
            f"Expected page changed=True when comparing different pages: {result}"
        )

    def test_check_changed_returns_both_fingerprints(self, bridge):
        run(bridge.navigate("https://example.com"))
        old_fp = "a" * 64  # deliberately wrong fingerprint
        result = run(bridge.check_changed("https://example.com", old_fp))
        assert "prev_fingerprint" in result, f"missing prev_fingerprint: {result}"
        assert "new_fingerprint" in result, f"missing new_fingerprint: {result}"
        assert result["prev_fingerprint"] == old_fp
        assert len(result["new_fingerprint"]) == 64

    def test_check_changed_unchanged_no_mutation_event(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        fp_result = run(bridge.fingerprint("https://example.com"))
        fp = fp_result.get("fingerprint", "")

        before_rows = _db_rows(tmp_db, bridge._session_id)
        run(bridge.check_changed("https://example.com", fp))
        after_rows = _db_rows(tmp_db, bridge._session_id)

        new_rows = after_rows[len(before_rows):]
        mutation_events = [r for r in new_rows if r.get("action_type") == "PAGE_MUTATION"]
        assert len(mutation_events) == 0, (
            f"PAGE_MUTATION should not fire for unchanged page, got: {mutation_events}"
        )

    def test_check_changed_changed_logs_mutation_event(self, bridge, tmp_db):
        run(bridge.navigate("https://example.com"))
        old_fp = "b" * 64  # wrong fingerprint — guarantees change detected

        before_rows = _db_rows(tmp_db, bridge._session_id)
        result = run(bridge.check_changed("https://example.com", old_fp))
        after_rows = _db_rows(tmp_db, bridge._session_id)

        changed = result.get("changed", result.get("page_changed", False))
        if changed:
            new_rows = after_rows[len(before_rows):]
            mutation_events = [r for r in new_rows if r.get("action_type") == "PAGE_MUTATION"]
            assert len(mutation_events) >= 1, (
                f"PAGE_MUTATION must be logged when change detected: new_rows={new_rows}"
            )

    def test_verify_chain_intact_after_monitor_operations(self, bridge, tmp_db):
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(bridge._session_id) is True, (
            "Hash chain broken after monitor operations"
        )
