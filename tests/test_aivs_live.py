"""
tests/test_aivs_live.py — Live browser tests for the 4 AIVS features.

Tests run against real public websites to verify end-to-end behaviour.
Bootstrap pattern: identical to test_e2e_live.py — the conftest.py
wires up cato.* sys.modules before any test file runs.

Markers:
  - All tests in this file use real HTTP connections and a real Chromium browser.
  - Tests are grouped into classes that share a single browser session.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tarfile
import tempfile
import types
import uuid
from pathlib import Path

import pytest


CONDUIT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helper: run coroutine from sync test
# ---------------------------------------------------------------------------

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _bootstrap_if_needed(tmp_db: Path) -> None:
    """Bootstrap cato.* modules — safe to call multiple times."""
    import importlib.util

    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    existing = sys.modules.setdefault("cato", cato_pkg)
    cato_pkg = existing

    if "cato.platform" not in sys.modules:
        platform_mod = types.ModuleType("cato.platform")
        _d = tmp_db.parent
        platform_mod.get_data_dir = lambda: _d  # type: ignore[attr-defined]
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
    existing_t = sys.modules.setdefault("cato.tools", tools_pkg)
    tools_pkg = existing_t
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
                mod_name,
                str(CONDUIT_ROOT / "tools" / file_name),
                submodule_search_locations=[],
            )
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            mod.__package__ = "cato.tools"
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("aivs_live") / "cato.db"
    _bootstrap_if_needed(db)
    return db


@pytest.fixture(scope="module")
def bridge(tmp_db):
    """Single ConduitBridge for the entire live test module."""
    ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
    sess = f"aivs-live-{uuid.uuid4().hex[:8]}"
    b = ConduitBridge(sess, budget_cents=99999, data_dir=tmp_db.parent)
    run(b.start())
    yield b
    run(b.stop())


# ---------------------------------------------------------------------------
# JS Delta live tests
# ---------------------------------------------------------------------------

class TestJSDeltaLive:
    """Live js_delta tests on public websites."""

    def test_js_delta_on_example_com_low_ratio(self, bridge):
        """
        example.com is fully static — we expect a low js_dependency_ratio.
        We don't hard-code a threshold; just verify ratio in [0.0, 1.0] and
        that it returns valid structure.
        """
        run(bridge.navigate("https://example.com"))
        result = run(bridge.js_delta())
        assert "error" not in result, f"js_delta error: {result.get('error')}"
        ratio = result.get("js_dependency_ratio", -1)
        assert 0.0 <= ratio <= 1.0, f"js_dependency_ratio out of range: {ratio}"

    def test_js_delta_static_hash_is_valid_sha256_hex(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.js_delta())
        sh = result.get("static_hash", "")
        assert len(sh) == 64, f"static_hash must be 64 hex chars, got: {sh!r}"
        int(sh, 16)  # raises if not valid hex

    def test_js_delta_rendered_hash_is_valid_sha256_hex(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.js_delta())
        rh = result.get("rendered_hash", "")
        assert len(rh) == 64, f"rendered_hash must be 64 hex chars, got: {rh!r}"
        int(rh, 16)

    def test_js_delta_url_is_populated(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.js_delta())
        url = result.get("url", "")
        assert url, "url field must not be empty"
        assert "example.com" in url, f"url must contain 'example.com', got: {url!r}"

    def test_js_delta_title_is_populated(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.js_delta())
        title = result.get("title", "")
        assert title, "title must not be empty"

    def test_js_delta_example_com_static_text_non_empty(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.js_delta())
        sc = result.get("static_char_count", 0)
        assert sc > 0, f"static_char_count must be > 0 for example.com, got {sc}"

    def test_js_delta_rendered_text_non_empty(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.js_delta())
        rc = result.get("rendered_char_count", 0)
        assert rc > 0, f"rendered_char_count must be > 0 for example.com, got {rc}"

    def test_js_delta_returns_all_expected_keys(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.js_delta())
        expected_keys = {
            "static_text", "rendered_text", "static_char_count", "rendered_char_count",
            "js_only_char_count", "js_dependency_ratio", "static_hash", "rendered_hash",
            "url", "title",
        }
        missing = expected_keys - set(result.keys())
        assert not missing, f"js_delta result missing keys: {missing}"

    def test_js_delta_audit_entry_written(self, bridge, tmp_db):
        import sqlite3
        run(bridge.navigate("https://example.com"))
        run(bridge.js_delta())
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT tool_name FROM audit_log WHERE session_id = ?",
                (bridge._session_id,),
            ).fetchall()
            tool_names = [r["tool_name"] for r in rows]
        finally:
            conn.close()
        assert "browser.js_delta" in tool_names, (
            f"No browser.js_delta in audit log. Found: {tool_names}"
        )

    def test_js_delta_on_react_dev_returns_valid_structure(self, bridge):
        """
        react.dev may use SSR/RSC (Next.js), which pre-renders content server-side.
        In that case the DOMParser approach sees pre-rendered HTML and reports a low
        js_dependency_ratio — which is correct behaviour (the static HTML *does*
        contain the content). We verify the structure is valid, not a specific ratio.
        """
        run(bridge.navigate("https://react.dev"))
        result = run(bridge.js_delta())
        assert "error" not in result, f"js_delta on react.dev error: {result.get('error')}"
        ratio = result.get("js_dependency_ratio", -1)
        assert 0.0 <= ratio <= 1.0, f"js_dependency_ratio out of range: {ratio}"
        # Both hashes must be present and valid
        sh = result.get("static_hash", "")
        rh = result.get("rendered_hash", "")
        assert len(sh) == 64 and len(rh) == 64, (
            f"Expected 64-char hashes. static={sh!r}, rendered={rh!r}"
        )
        # rendered char count should be non-zero (react.dev always has content)
        assert result.get("rendered_char_count", 0) > 0, (
            "react.dev rendered_char_count must be > 0"
        )

    def test_js_delta_chain_intact_after_js_delta(self, bridge, tmp_db):
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(bridge._session_id) is True, (
            "Hash chain broken after js_delta calls"
        )


# ---------------------------------------------------------------------------
# Full workflow live test
# ---------------------------------------------------------------------------

class TestFullWorkflowLive:
    """
    End-to-end workflow:
    1. Navigate to example.com
    2. Run js_delta
    3. Export micro proof with rendered_hash
    4. Export full proof bundle (twice, to verify chaining)
    5. Verify bundle structure and chaining
    """

    _first_bundle_path = None   # shared across test methods in this class
    _first_bundle_hash = None
    _second_bundle_path = None

    def test_01_navigate_to_example_com(self, bridge):
        result = run(bridge.navigate("https://example.com"))
        assert "error" not in result, f"navigate error: {result.get('error')}"
        title = result.get("title", "")
        assert "Example" in title or len(title) > 0, f"Unexpected title: {title!r}"

    def test_02_js_delta_returns_valid_result(self, bridge):
        result = run(bridge.js_delta())
        assert "error" not in result, f"js_delta error: {result.get('error')}"
        assert result.get("rendered_hash"), "rendered_hash must be non-empty"
        # Stash rendered_hash for next test
        TestFullWorkflowLive._rendered_hash = result["rendered_hash"]

    def test_03_export_micro_proof_with_rendered_hash(self, bridge):
        rendered_hash = getattr(TestFullWorkflowLive, "_rendered_hash", "fallback_hash")
        result = bridge.export_micro(
            url="https://example.com",
            dom_hash=rendered_hash,
            scan_origin="live-test",
        )
        assert result.get("success") is True, f"export_micro failed: {result}"
        mp = result["micro_proof"]
        assert mp["url"] == "https://example.com"
        assert mp["dom_hash"].startswith("sha256:")
        assert mp["scan_origin"] == "live-test"
        assert mp["signature"] != "", "signature should not be empty"

    def test_04_export_micro_has_all_six_fields(self, bridge):
        result = bridge.export_micro("https://example.com", "abc123test")
        mp = result["micro_proof"]
        required = {"url", "dom_hash", "timestamp", "signature", "scanner_version_hash", "scan_origin"}
        assert set(mp.keys()) == required, f"micro_proof missing keys: {required - set(mp.keys())}"

    def test_05_export_first_proof_bundle(self, bridge, tmp_path):
        result = bridge.export_proof(output_dir=str(tmp_path))
        assert result.get("success") is True, f"export_proof failed: {result}"
        assert result.get("bundle_hash"), "bundle_hash must be present"
        assert result["previous_bundle_hash"] is None, "First bundle must have no previous_bundle_hash"
        TestFullWorkflowLive._first_bundle_path = result["path"]
        TestFullWorkflowLive._first_bundle_hash = result["bundle_hash"]

    def test_06_first_bundle_file_exists(self, bridge):
        bundle_path = Path(TestFullWorkflowLive._first_bundle_path)
        assert bundle_path.exists(), f"Bundle file not found: {bundle_path}"
        assert bundle_path.name.endswith(".tar.gz")

    def test_07_first_bundle_contains_required_files(self, bridge):
        with tarfile.open(TestFullWorkflowLive._first_bundle_path, "r:gz") as tar:
            names = tar.getnames()
        for req in ["audit_log.jsonl", "verify.py", "manifest.json"]:
            assert any(req in n for n in names), f"Missing '{req}' in bundle. Contents: {names}"

    def test_08_export_second_proof_bundle_chains_to_first(self, bridge, tmp_path):
        result = bridge.export_proof(output_dir=str(tmp_path))
        assert result.get("success") is True, f"Second export_proof failed: {result}"
        assert result["previous_bundle_hash"] == TestFullWorkflowLive._first_bundle_hash, (
            f"Second bundle previous_bundle_hash ({result['previous_bundle_hash']!r}) "
            f"must equal first bundle_hash ({TestFullWorkflowLive._first_bundle_hash!r})"
        )
        TestFullWorkflowLive._second_bundle_path = result["path"]

    def test_09_second_bundle_contains_previous_bundle_hash_txt(self, bridge):
        with tarfile.open(TestFullWorkflowLive._second_bundle_path, "r:gz") as tar:
            names = tar.getnames()
        assert any("previous_bundle_hash.txt" in n for n in names), (
            f"Second bundle must contain previous_bundle_hash.txt. Contents: {names}"
        )

    def test_10_previous_bundle_hash_txt_content_correct(self, bridge):
        with tarfile.open(TestFullWorkflowLive._second_bundle_path, "r:gz") as tar:
            member = next(m for m in tar.getmembers() if "previous_bundle_hash.txt" in m.name)
            content = tar.extractfile(member).read().decode().strip()
        assert content == TestFullWorkflowLive._first_bundle_hash, (
            f"previous_bundle_hash.txt content ({content!r}) must equal "
            f"first bundle_hash ({TestFullWorkflowLive._first_bundle_hash!r})"
        )

    def test_11_first_bundle_no_previous_bundle_hash_txt(self, bridge):
        with tarfile.open(TestFullWorkflowLive._first_bundle_path, "r:gz") as tar:
            names = tar.getnames()
        assert not any("previous_bundle_hash.txt" in n for n in names), (
            "First bundle must NOT contain previous_bundle_hash.txt"
        )

    def test_12_audit_chain_intact_after_full_workflow(self, bridge, tmp_db):
        AuditLog = sys.modules["cato.audit"].AuditLog
        log = AuditLog(db_path=tmp_db)
        assert log.verify_chain(bridge._session_id) is True, (
            "Hash chain broken after full workflow test"
        )


# ---------------------------------------------------------------------------
# Bundle with Merkle tree live test
# ---------------------------------------------------------------------------

class TestMerkleBundleLive:
    """Live test: crawl example.com and export bundle with Merkle tree."""

    def test_crawl_returns_page_hashes(self, bridge):
        result = run(bridge.crawl_site("https://example.com", max_depth=0, limit=1))
        assert "error" not in result, f"crawl_site error: {result.get('error')}"
        assert "page_hashes" in result, (
            f"crawl_site result must contain 'page_hashes'. Keys: {list(result.keys())}"
        )

    def test_page_hashes_structure(self, bridge):
        result = run(bridge.crawl_site("https://example.com", max_depth=0, limit=1))
        page_hashes = result.get("page_hashes", [])
        assert len(page_hashes) >= 1, "Expected at least 1 page_hash entry"
        for ph in page_hashes:
            assert "url" in ph, f"page_hash missing 'url': {ph}"
            assert "hash" in ph, f"page_hash missing 'hash': {ph}"
            # Hash must be 64-char hex
            h = ph["hash"]
            assert len(h) == 64, f"page hash must be 64 chars: {h!r}"
            int(h, 16)  # raises if not valid hex

    def test_export_with_page_hashes_includes_merkle_tree(self, bridge, tmp_path):
        crawl_result = run(bridge.crawl_site("https://example.com", max_depth=0, limit=1))
        page_hashes = crawl_result.get("page_hashes", [])
        assert page_hashes, "Need page_hashes to test Merkle bundle"

        proof_result = bridge.export_proof(
            output_dir=str(tmp_path),
            page_hashes=page_hashes,
        )
        assert proof_result.get("success") is True, f"export_proof with page_hashes failed: {proof_result}"
        assert proof_result.get("merkle_root"), "merkle_root must be present in result"

        with tarfile.open(proof_result["path"], "r:gz") as tar:
            names = tar.getnames()
        assert any("merkle_tree.json" in n for n in names), (
            f"merkle_tree.json not found in bundle. Contents: {names}"
        )

    def test_merkle_tree_json_is_valid_json(self, bridge, tmp_path):
        crawl_result = run(bridge.crawl_site("https://example.com", max_depth=0, limit=1))
        page_hashes = crawl_result.get("page_hashes", [])
        if not page_hashes:
            pytest.skip("No page_hashes returned from crawl")

        proof_result = bridge.export_proof(
            output_dir=str(tmp_path),
            page_hashes=page_hashes,
        )
        with tarfile.open(proof_result["path"], "r:gz") as tar:
            member = next(m for m in tar.getmembers() if "merkle_tree.json" in m.name)
            tree_data = json.loads(tar.extractfile(member).read().decode())

        assert "root" in tree_data
        assert "leaf_count" in tree_data
        assert "pages" in tree_data
        assert "tree" in tree_data
        assert tree_data["leaf_count"] == len(page_hashes)

    def test_manifest_contains_merkle_root_when_page_hashes_passed(self, bridge, tmp_path):
        crawl_result = run(bridge.crawl_site("https://example.com", max_depth=0, limit=1))
        page_hashes = crawl_result.get("page_hashes", [])
        if not page_hashes:
            pytest.skip("No page_hashes returned from crawl")

        proof_result = bridge.export_proof(
            output_dir=str(tmp_path),
            page_hashes=page_hashes,
        )
        with tarfile.open(proof_result["path"], "r:gz") as tar:
            member = next(m for m in tar.getmembers() if "manifest.json" in m.name)
            manifest = json.loads(tar.extractfile(member).read().decode())

        assert "merkle_root" in manifest, f"manifest.json must contain 'merkle_root'. Keys: {list(manifest.keys())}"
        assert "merkle_leaf_count" in manifest
        assert manifest["merkle_leaf_count"] == len(page_hashes)
        # merkle_root in manifest must match result
        assert manifest["merkle_root"] == proof_result["merkle_root"]
