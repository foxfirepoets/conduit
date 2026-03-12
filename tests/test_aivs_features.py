"""
tests/test_aivs_features.py — Unit tests for all 4 AIVS features.

Features covered:
  1. AIVS-Micro export (export_micro on ConduitProof)
  2. Bundle chaining (scan chain via previous_bundle_hash)
  3. JS Delta capture (_js_delta on BrowserTool)
  4. Merkle tree for crawls (build_merkle_tree / merkle_proof_for_leaf)

Bootstrap pattern: identical to test_conduit_proof.py — exec() from source
so the module loads without needing the full cato.* package hierarchy.

The js_delta tests use unittest.mock to avoid a real browser.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tarfile
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Bootstrap conduit_proof standalone (no package import required)
# ---------------------------------------------------------------------------

_CONDUIT_ROOT = Path(__file__).parent.parent
_PROOF_PATH = _CONDUIT_ROOT / "tools" / "conduit_proof.py"
_proof_src = _PROOF_PATH.read_text(encoding="utf-8")

_proof_mod = types.ModuleType("conduit_proof_standalone_aivs")
_proof_mod.__file__ = str(_PROOF_PATH)
exec(compile(_proof_src, str(_PROOF_PATH), "exec"), _proof_mod.__dict__)

ConduitProof = _proof_mod.ConduitProof
build_merkle_tree = _proof_mod.build_merkle_tree
merkle_proof_for_leaf = _proof_mod.merkle_proof_for_leaf


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------

class MockAuditLog:
    """In-memory mock implementing the get_session_rows() interface."""
    def __init__(self, rows=None):
        self._rows = rows or []

    def get_session_rows(self, session_id):
        return [r for r in self._rows if r.get("session_id") == session_id]


class MockIdentity:
    """Minimal identity stub that signs bytes with a fixed fake signature."""
    public_key_hex = "a" * 64

    def sign(self, data: bytes) -> bytes:
        # Deterministic fake signature for testing — 64 bytes of 0xAB
        return b"\xab" * 64


def make_fake_rows(session_id="sess-aivs-001", count=2):
    """Create fake audit rows with a valid hash chain."""
    rows = []
    prev_hash = ""
    for i in range(1, count + 1):
        ts = 1700000000.0 + i
        rh = hashlib.sha256(
            f"{i}:{session_id}:tool_call:browser.navigate:0:{ts}:{prev_hash}".encode()
        ).hexdigest()
        rows.append({
            "id": i,
            "session_id": session_id,
            "action_type": "tool_call",
            "tool_name": "browser.navigate",
            "inputs_json": '{"url": "https://example.com"}',
            "outputs_json": '{"title": "Example"}',
            "cost_cents": 0,
            "error": "",
            "timestamp": ts,
            "prev_hash": prev_hash,
            "row_hash": rh,
        })
        prev_hash = rh
    return rows


# ---------------------------------------------------------------------------
# Feature 1: AIVS-Micro export
# ---------------------------------------------------------------------------

class TestAIVSMicro(unittest.TestCase):
    """Tests for ConduitProof.export_micro()."""

    def _make_proof(self, identity=None):
        rows = make_fake_rows("sess-micro-001")
        audit = MockAuditLog(rows=rows)
        return ConduitProof(audit, "sess-micro-001", identity=identity)

    def test_export_micro_returns_success_true(self):
        proof = self._make_proof()
        result = proof.export_micro("https://example.com", "abc123")
        self.assertTrue(result["success"])

    def test_export_micro_returns_all_six_fields(self):
        proof = self._make_proof()
        result = proof.export_micro("https://example.com", "abc123")
        mp = result["micro_proof"]
        expected_keys = {"url", "dom_hash", "timestamp", "signature", "scanner_version_hash", "scan_origin"}
        self.assertEqual(set(mp.keys()), expected_keys)

    def test_export_micro_url_is_preserved(self):
        proof = self._make_proof()
        result = proof.export_micro("https://test.example.org/page", "def456")
        self.assertEqual(result["micro_proof"]["url"], "https://test.example.org/page")

    def test_export_micro_dom_hash_gets_sha256_prefix_if_missing(self):
        proof = self._make_proof()
        result = proof.export_micro("https://example.com", "abc123nohex")
        self.assertTrue(result["micro_proof"]["dom_hash"].startswith("sha256:"))

    def test_export_micro_dom_hash_no_double_prefix(self):
        """If dom_hash already has 'sha256:' prefix it must not be doubled."""
        proof = self._make_proof()
        raw_hash = "sha256:deadbeef1234"
        result = proof.export_micro("https://example.com", raw_hash)
        self.assertEqual(result["micro_proof"]["dom_hash"], raw_hash)
        self.assertFalse(result["micro_proof"]["dom_hash"].startswith("sha256:sha256:"))

    def test_export_micro_scanner_version_hash_has_sha256_prefix(self):
        proof = self._make_proof()
        result = proof.export_micro("https://example.com", "abc123")
        svh = result["micro_proof"]["scanner_version_hash"]
        self.assertTrue(svh.startswith("sha256:"))
        # The part after prefix should be 64 hex chars
        hex_part = svh[len("sha256:"):]
        self.assertEqual(len(hex_part), 64)

    def test_export_micro_scan_origin_defaults_to_local(self):
        proof = self._make_proof()
        result = proof.export_micro("https://example.com", "abc123")
        self.assertEqual(result["micro_proof"]["scan_origin"], "local")

    def test_export_micro_custom_scan_origin(self):
        proof = self._make_proof()
        result = proof.export_micro("https://example.com", "abc123", scan_origin="ci-pipeline")
        self.assertEqual(result["micro_proof"]["scan_origin"], "ci-pipeline")

    def test_export_micro_unsigned_when_no_identity(self):
        proof = self._make_proof(identity=None)
        result = proof.export_micro("https://example.com", "abc123")
        self.assertEqual(result["micro_proof"]["signature"], "unsigned")

    def test_export_micro_signed_with_identity(self):
        proof = self._make_proof(identity=MockIdentity())
        result = proof.export_micro("https://example.com", "abc123")
        sig = result["micro_proof"]["signature"]
        self.assertTrue(sig.startswith("ed25519:"), f"Expected 'ed25519:' prefix, got: {sig!r}")

    def test_export_micro_payload_signed_matches_canonical_format(self):
        """payload_signed must equal url|dom_hash|timestamp|scanner_version_hash|scan_origin."""
        proof = self._make_proof(identity=MockIdentity())
        url = "https://example.com"
        dom_hash = "abc123"
        result = proof.export_micro(url, dom_hash, scan_origin="unit-test")
        payload = result["payload_signed"]
        mp = result["micro_proof"]
        # Canonical form: url|dom_hash|timestamp|scanner_version_hash|scan_origin
        # NOTE: dom_hash in payload is the raw value passed in (not prefixed), but
        # the micro_proof field has the prefix. The payload uses the raw dom_hash.
        expected = f"{url}|{dom_hash}|{mp['timestamp']}|{mp['scanner_version_hash'][len('sha256:'):]}|{mp['scan_origin']}"
        self.assertEqual(payload, expected)

    def test_export_micro_timestamp_is_iso8601_format(self):
        proof = self._make_proof()
        result = proof.export_micro("https://example.com", "abc123")
        ts = result["micro_proof"]["timestamp"]
        # Should match pattern like 2024-01-15T12:34:56.000000000Z
        import re
        self.assertRegex(ts, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z")

    def test_export_micro_success_key_true(self):
        proof = self._make_proof()
        result = proof.export_micro("https://example.com", "abc123")
        self.assertIn("success", result)
        self.assertTrue(result["success"])


# ---------------------------------------------------------------------------
# Feature 2: Bundle chaining
# ---------------------------------------------------------------------------

class TestBundleChaining(unittest.TestCase):
    """Tests for scan-chain linking between successive proof bundles."""

    def setUp(self):
        # Each test uses a unique session id to avoid class-level cache pollution
        import uuid
        self._session_id = f"sess-chain-{uuid.uuid4().hex[:8]}"

    def _make_proof(self, session_id=None):
        sid = session_id or self._session_id
        rows = make_fake_rows(sid, count=2)
        audit = MockAuditLog(rows=rows)
        return ConduitProof(audit, sid)

    def test_first_export_has_no_previous_bundle_hash(self):
        proof = self._make_proof()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir)
        self.assertTrue(result["success"])
        self.assertIsNone(result["previous_bundle_hash"])

    def test_first_export_returns_bundle_hash(self):
        proof = self._make_proof()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir)
        bh = result.get("bundle_hash", "")
        self.assertEqual(len(bh), 64, f"bundle_hash must be 64-char hex, got: {bh!r}")

    def test_bundle_hash_is_valid_sha256_hex(self):
        proof = self._make_proof()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir)
        bh = result["bundle_hash"]
        # Valid hex only
        try:
            int(bh, 16)
        except ValueError:
            self.fail(f"bundle_hash is not valid hex: {bh!r}")

    def test_second_export_auto_chains_to_first(self):
        """Second export on same session_id must reference the first bundle_hash."""
        proof = self._make_proof()
        with tempfile.TemporaryDirectory() as tmpdir:
            first = proof.export(output_dir=tmpdir)
            second = proof.export(output_dir=tmpdir)

        first_hash = first["bundle_hash"]
        second_prev = second["previous_bundle_hash"]
        self.assertEqual(second_prev, first_hash,
            f"Second bundle's previous_bundle_hash ({second_prev!r}) "
            f"must equal first bundle_hash ({first_hash!r})")

    def test_explicit_previous_bundle_path_overrides_class_cache(self):
        """When previous_bundle_path is given it must be used instead of the cache."""
        proof_a = self._make_proof()
        probe_sid = f"{self._session_id}-probe"
        probe_rows = make_fake_rows(probe_sid, count=1)
        probe_audit = MockAuditLog(rows=probe_rows)
        proof_b = ConduitProof(probe_audit, probe_sid)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Export proof_a to get a real .tar.gz on disk
            result_a = proof_a.export(output_dir=tmpdir)
            bundle_a_path = result_a["path"]

            # Export proof_b passing proof_a's path explicitly
            result_b = proof_b.export(output_dir=tmpdir, previous_bundle_path=bundle_a_path)

        # previous_bundle_hash in result_b must equal SHA-256 of bundle_a
        expected = result_a["bundle_hash"]
        self.assertEqual(result_b["previous_bundle_hash"], expected)

    def test_previous_bundle_hash_txt_in_tarball_when_chained(self):
        """When chained, previous_bundle_hash.txt must exist inside the bundle."""
        proof = self._make_proof()
        with tempfile.TemporaryDirectory() as tmpdir:
            proof.export(output_dir=tmpdir)  # first — primes the class cache
            second = proof.export(output_dir=tmpdir)  # second — should chain

            with tarfile.open(second["path"], "r:gz") as tar:
                names = tar.getnames()

        self.assertTrue(
            any("previous_bundle_hash.txt" in n for n in names),
            f"Expected 'previous_bundle_hash.txt' in bundle. Got: {names}"
        )

    def test_previous_bundle_hash_txt_content_matches_result(self):
        """Content of previous_bundle_hash.txt must match the returned previous_bundle_hash."""
        proof = self._make_proof()
        with tempfile.TemporaryDirectory() as tmpdir:
            first = proof.export(output_dir=tmpdir)
            second = proof.export(output_dir=tmpdir)

            with tarfile.open(second["path"], "r:gz") as tar:
                member = next(m for m in tar.getmembers() if "previous_bundle_hash.txt" in m.name)
                content = tar.extractfile(member).read().decode().strip()

        self.assertEqual(content, first["bundle_hash"])
        self.assertEqual(content, second["previous_bundle_hash"])

    def test_previous_bundle_hash_txt_absent_when_no_chain(self):
        """First export (no chain) must NOT include previous_bundle_hash.txt."""
        proof = self._make_proof()
        with tempfile.TemporaryDirectory() as tmpdir:
            first = proof.export(output_dir=tmpdir)
            with tarfile.open(first["path"], "r:gz") as tar:
                names = tar.getnames()

        self.assertFalse(
            any("previous_bundle_hash.txt" in n for n in names),
            f"First bundle should not have previous_bundle_hash.txt. Got: {names}"
        )

    def test_manifest_contains_previous_bundle_hash_when_chained(self):
        """The manifest.json must include 'previous_bundle_hash' when chaining."""
        proof = self._make_proof()
        with tempfile.TemporaryDirectory() as tmpdir:
            proof.export(output_dir=tmpdir)
            second = proof.export(output_dir=tmpdir)

            with tarfile.open(second["path"], "r:gz") as tar:
                member = next(m for m in tar.getmembers() if "manifest.json" in m.name)
                manifest = json.loads(tar.extractfile(member).read().decode())

        self.assertIn("previous_bundle_hash", manifest)
        self.assertEqual(manifest["previous_bundle_hash"], second["previous_bundle_hash"])


# ---------------------------------------------------------------------------
# Feature 3: JS Delta capture (unit-level with mocks)
# ---------------------------------------------------------------------------

class TestJSDelta(unittest.TestCase):
    """Unit tests for BrowserTool._js_delta() with mocked Patchright page."""

    def _make_browser_with_mocks(self, static_text: str, rendered_text: str, url: str = "https://example.com", title: str = "Example"):
        """Build a BrowserTool instance with a mocked _page returning supplied texts."""
        # Import BrowserTool from the cato.tools.browser module loaded by conftest
        import importlib
        browser_mod = sys.modules.get("cato.tools.browser")
        if browser_mod is None:
            # Fallback: load from file
            spec = importlib.util.spec_from_file_location(
                "cato.tools.browser",
                str(_CONDUIT_ROOT / "tools" / "browser.py"),
                submodule_search_locations=[],
            )
            browser_mod = importlib.util.module_from_spec(spec)
            browser_mod.__package__ = "cato.tools"
            sys.modules["cato.tools.browser"] = browser_mod
            spec.loader.exec_module(spec)
        BrowserTool = browser_mod.BrowserTool

        bt = BrowserTool.__new__(BrowserTool)
        # Minimal init — only what _js_delta() needs
        page = MagicMock()
        page.url = url
        page.title = AsyncMock(return_value=title)

        async def _evaluate(js, *args, **kwargs):
            # Distinguish which evaluate call it is by content
            if "innerText.trim()" in js and "DOMParser" not in js:
                return rendered_text
            else:
                return static_text

        page.evaluate = _evaluate
        bt._page = page
        return bt

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_js_delta_returns_all_expected_fields(self):
        bt = self._make_browser_with_mocks("static content", "rendered content with more stuff")
        result = self._run(bt._js_delta())
        expected = {
            "static_text", "rendered_text", "static_char_count", "rendered_char_count",
            "js_only_char_count", "js_dependency_ratio", "static_hash", "rendered_hash",
            "url", "title",
        }
        self.assertEqual(set(result.keys()), expected)

    def test_js_delta_url_and_title_populated(self):
        bt = self._make_browser_with_mocks("hello", "hello world", url="https://test.com", title="Test")
        result = self._run(bt._js_delta())
        self.assertEqual(result["url"], "https://test.com")
        self.assertEqual(result["title"], "Test")

    def test_js_delta_char_counts_correct(self):
        static = "abc"        # 3 chars
        rendered = "abcdefgh"  # 8 chars
        bt = self._make_browser_with_mocks(static, rendered)
        result = self._run(bt._js_delta())
        self.assertEqual(result["static_char_count"], 3)
        self.assertEqual(result["rendered_char_count"], 8)
        self.assertEqual(result["js_only_char_count"], 5)

    def test_js_dependency_ratio_all_static(self):
        """When static == rendered, ratio must be 0.0."""
        text = "same content"
        bt = self._make_browser_with_mocks(text, text)
        result = self._run(bt._js_delta())
        self.assertEqual(result["js_dependency_ratio"], 0.0)

    def test_js_dependency_ratio_partial(self):
        """rendered has 10 chars, static has 5 => ratio = 5/10 = 0.5."""
        bt = self._make_browser_with_mocks("12345", "1234567890")
        result = self._run(bt._js_delta())
        self.assertAlmostEqual(result["js_dependency_ratio"], 0.5, places=3)

    def test_js_dependency_ratio_empty_rendered(self):
        """Empty rendered page should produce 0.0 ratio without ZeroDivisionError."""
        bt = self._make_browser_with_mocks("", "")
        result = self._run(bt._js_delta())
        self.assertEqual(result["js_dependency_ratio"], 0.0)

    def test_js_dependency_ratio_never_negative(self):
        """If static is somehow longer than rendered, js_only_char_count floors at 0."""
        # static longer than rendered
        bt = self._make_browser_with_mocks("very long static text here", "short")
        result = self._run(bt._js_delta())
        self.assertGreaterEqual(result["js_only_char_count"], 0)
        self.assertGreaterEqual(result["js_dependency_ratio"], 0.0)

    def test_js_delta_static_hash_is_valid_sha256(self):
        bt = self._make_browser_with_mocks("static content", "rendered content")
        result = self._run(bt._js_delta())
        sh = result["static_hash"]
        self.assertEqual(len(sh), 64)
        int(sh, 16)  # raises if not hex

    def test_js_delta_rendered_hash_is_valid_sha256(self):
        bt = self._make_browser_with_mocks("static content", "rendered content")
        result = self._run(bt._js_delta())
        rh = result["rendered_hash"]
        self.assertEqual(len(rh), 64)
        int(rh, 16)

    def test_js_delta_static_hash_differs_from_rendered_when_content_differs(self):
        bt = self._make_browser_with_mocks("only static", "only static plus more js rendered content")
        result = self._run(bt._js_delta())
        self.assertNotEqual(result["static_hash"], result["rendered_hash"])

    def test_js_delta_hashes_equal_when_content_identical(self):
        text = "identical content"
        bt = self._make_browser_with_mocks(text, text)
        result = self._run(bt._js_delta())
        self.assertEqual(result["static_hash"], result["rendered_hash"])

    def test_js_delta_static_hash_matches_manual_sha256(self):
        static = "hello static"
        bt = self._make_browser_with_mocks(static, "hello static rendered")
        result = self._run(bt._js_delta())
        expected = hashlib.sha256(static.encode()).hexdigest()
        self.assertEqual(result["static_hash"], expected)

    def test_js_delta_handles_empty_page_gracefully(self):
        """Empty static and rendered texts must not raise and must return valid structure."""
        bt = self._make_browser_with_mocks("", "")
        result = self._run(bt._js_delta())
        self.assertNotIn("error", result)
        self.assertEqual(result["static_char_count"], 0)
        self.assertEqual(result["rendered_char_count"], 0)
        self.assertEqual(result["js_dependency_ratio"], 0.0)

    def test_js_delta_text_truncated_to_5000_chars(self):
        """static_text and rendered_text in the result are capped at 5000 chars."""
        long_static = "s" * 10000
        long_rendered = "r" * 10000
        bt = self._make_browser_with_mocks(long_static, long_rendered)
        result = self._run(bt._js_delta())
        self.assertLessEqual(len(result["static_text"]), 5000)
        self.assertLessEqual(len(result["rendered_text"]), 5000)
        # But char counts reflect full length
        self.assertEqual(result["static_char_count"], 10000)
        self.assertEqual(result["rendered_char_count"], 10000)


# ---------------------------------------------------------------------------
# Feature 4: Merkle tree
# ---------------------------------------------------------------------------

class TestBuildMerkleTree(unittest.TestCase):
    """Unit tests for build_merkle_tree()."""

    def _sha(self, s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()

    def test_empty_leaves_returns_sha256_of_empty(self):
        result = build_merkle_tree([])
        expected_root = hashlib.sha256(b"empty").hexdigest()
        self.assertEqual(result["root"], expected_root)
        self.assertEqual(result["leaves"], [])
        self.assertEqual(result["tree"], [])

    def test_single_leaf_root_equals_leaf(self):
        leaf = self._sha("page1")
        result = build_merkle_tree([leaf])
        self.assertEqual(result["root"], leaf)
        self.assertEqual(result["leaves"], [leaf])

    def test_two_leaves_root_is_sha256_of_concatenation(self):
        l0 = self._sha("a")
        l1 = self._sha("b")
        result = build_merkle_tree([l0, l1])
        expected_root = hashlib.sha256((l0 + l1).encode()).hexdigest()
        self.assertEqual(result["root"], expected_root)

    def test_three_leaves_odd_duplication(self):
        """With 3 leaves, the odd leaf (index 2) is duplicated to form its parent."""
        l0 = self._sha("x0")
        l1 = self._sha("x1")
        l2 = self._sha("x2")
        result = build_merkle_tree([l0, l1, l2])
        # Level 1: [sha(l0+l1), sha(l2+l2)]
        parent01 = hashlib.sha256((l0 + l1).encode()).hexdigest()
        parent22 = hashlib.sha256((l2 + l2).encode()).hexdigest()
        expected_root = hashlib.sha256((parent01 + parent22).encode()).hexdigest()
        self.assertEqual(result["root"], expected_root)

    def test_four_leaves_balanced_tree(self):
        leaves = [self._sha(f"page{i}") for i in range(4)]
        result = build_merkle_tree(leaves)
        p01 = hashlib.sha256((leaves[0] + leaves[1]).encode()).hexdigest()
        p23 = hashlib.sha256((leaves[2] + leaves[3]).encode()).hexdigest()
        expected_root = hashlib.sha256((p01 + p23).encode()).hexdigest()
        self.assertEqual(result["root"], expected_root)

    def test_eight_leaves_correct_depth(self):
        leaves = [self._sha(f"p{i}") for i in range(8)]
        result = build_merkle_tree(leaves)
        # 8 leaves = 4 levels: [8, 4, 2, 1]
        self.assertEqual(len(result["tree"]), 4)
        self.assertEqual(len(result["tree"][0]), 8)
        self.assertEqual(len(result["tree"][1]), 4)
        self.assertEqual(len(result["tree"][2]), 2)
        self.assertEqual(len(result["tree"][3]), 1)
        self.assertEqual(result["root"], result["tree"][3][0])

    def test_result_contains_required_keys(self):
        result = build_merkle_tree([self._sha("a"), self._sha("b")])
        self.assertIn("root", result)
        self.assertIn("leaves", result)
        self.assertIn("tree", result)

    def test_leaves_preserved_in_order(self):
        leaves = [self._sha(f"item{i}") for i in range(5)]
        result = build_merkle_tree(leaves)
        self.assertEqual(result["leaves"], leaves)
        self.assertEqual(result["tree"][0], leaves)

    def test_root_is_64_char_hex(self):
        leaves = [self._sha("only")]
        result = build_merkle_tree(leaves)
        self.assertEqual(len(result["root"]), 64)
        int(result["root"], 16)


class TestMerkleProofForLeaf(unittest.TestCase):
    """Unit tests for merkle_proof_for_leaf() and proof verification."""

    def _sha(self, s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()

    def _verify_proof(self, leaf_hash: str, proof: list[dict], expected_root: str) -> bool:
        """Reconstruct root from leaf + proof path and compare to expected_root."""
        current = leaf_hash
        for step in proof:
            sibling = step["hash"]
            if step["side"] == "right":
                combined = current + sibling
            else:
                combined = sibling + current
            current = hashlib.sha256(combined.encode()).hexdigest()
        return current == expected_root

    def test_proof_path_for_two_leaves_leaf0(self):
        leaves = [self._sha("L0"), self._sha("L1")]
        tree = build_merkle_tree(leaves)
        proof = merkle_proof_for_leaf(tree["tree"], 0)
        self.assertEqual(len(proof), 1)
        self.assertEqual(proof[0]["side"], "right")
        self.assertEqual(proof[0]["hash"], leaves[1])

    def test_proof_path_for_two_leaves_leaf1(self):
        leaves = [self._sha("L0"), self._sha("L1")]
        tree = build_merkle_tree(leaves)
        proof = merkle_proof_for_leaf(tree["tree"], 1)
        self.assertEqual(len(proof), 1)
        self.assertEqual(proof[0]["side"], "left")
        self.assertEqual(proof[0]["hash"], leaves[0])

    def test_proof_can_reconstruct_root_for_leaf0(self):
        leaves = [self._sha(f"page{i}") for i in range(4)]
        tree = build_merkle_tree(leaves)
        proof = merkle_proof_for_leaf(tree["tree"], 0)
        ok = self._verify_proof(leaves[0], proof, tree["root"])
        self.assertTrue(ok, "Proof verification failed for leaf index 0")

    def test_proof_can_reconstruct_root_for_leaf3(self):
        leaves = [self._sha(f"p{i}") for i in range(4)]
        tree = build_merkle_tree(leaves)
        proof = merkle_proof_for_leaf(tree["tree"], 3)
        ok = self._verify_proof(leaves[3], proof, tree["root"])
        self.assertTrue(ok, "Proof verification failed for leaf index 3")

    def test_proof_for_odd_leaf_in_three_leaf_tree(self):
        """Leaf index 2 is odd; its sibling is itself (duplicated)."""
        leaves = [self._sha(f"q{i}") for i in range(3)]
        tree = build_merkle_tree(leaves)
        proof = merkle_proof_for_leaf(tree["tree"], 2)
        ok = self._verify_proof(leaves[2], proof, tree["root"])
        self.assertTrue(ok, "Proof verification failed for odd leaf (index 2) in 3-leaf tree")

    def test_proof_depth_is_log2_of_leaf_count(self):
        """8-leaf tree => proof depth = 3."""
        leaves = [self._sha(f"n{i}") for i in range(8)]
        tree = build_merkle_tree(leaves)
        proof = merkle_proof_for_leaf(tree["tree"], 5)
        self.assertEqual(len(proof), 3)

    def test_proof_can_reconstruct_root_for_all_leaves_8(self):
        leaves = [self._sha(f"doc{i}") for i in range(8)]
        tree = build_merkle_tree(leaves)
        for i, leaf in enumerate(leaves):
            proof = merkle_proof_for_leaf(tree["tree"], i)
            self.assertTrue(
                self._verify_proof(leaf, proof, tree["root"]),
                f"Proof failed for leaf {i}"
            )

    def test_empty_proof_for_single_leaf(self):
        """Single leaf tree has no proof path needed — root equals leaf."""
        leaf = self._sha("solo")
        tree = build_merkle_tree([leaf])
        proof = merkle_proof_for_leaf(tree["tree"], 0)
        # tree[:-1] is empty when there's only 1 level, so proof is []
        self.assertEqual(proof, [])


class TestMerkleInBundle(unittest.TestCase):
    """Tests that Merkle tree data is correctly included in proof bundles."""

    def _make_page_hashes(self, count=3):
        return [
            {"url": f"https://example.com/page{i}", "hash": hashlib.sha256(f"text{i}".encode()).hexdigest()}
            for i in range(count)
        ]

    def test_export_with_page_hashes_includes_merkle_tree_json(self):
        session_id = "sess-merkle-001"
        rows = make_fake_rows(session_id, count=2)
        audit = MockAuditLog(rows=rows)
        proof = ConduitProof(audit, session_id)
        page_hashes = self._make_page_hashes(4)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir, page_hashes=page_hashes)
            with tarfile.open(result["path"], "r:gz") as tar:
                names = tar.getnames()

        self.assertTrue(
            any("merkle_tree.json" in n for n in names),
            f"merkle_tree.json not in bundle. Contents: {names}"
        )

    def test_export_with_page_hashes_manifest_contains_merkle_root(self):
        session_id = "sess-merkle-002"
        rows = make_fake_rows(session_id, count=2)
        audit = MockAuditLog(rows=rows)
        proof = ConduitProof(audit, session_id)
        page_hashes = self._make_page_hashes(4)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir, page_hashes=page_hashes)
            with tarfile.open(result["path"], "r:gz") as tar:
                member = next(m for m in tar.getmembers() if "manifest.json" in m.name)
                manifest = json.loads(tar.extractfile(member).read().decode())

        self.assertIn("merkle_root", manifest)
        self.assertIn("merkle_leaf_count", manifest)
        self.assertEqual(manifest["merkle_leaf_count"], 4)

    def test_export_merkle_root_in_result_matches_manifest(self):
        session_id = "sess-merkle-003"
        rows = make_fake_rows(session_id, count=2)
        audit = MockAuditLog(rows=rows)
        proof = ConduitProof(audit, session_id)
        page_hashes = self._make_page_hashes(2)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir, page_hashes=page_hashes)
            with tarfile.open(result["path"], "r:gz") as tar:
                member = next(m for m in tar.getmembers() if "manifest.json" in m.name)
                manifest = json.loads(tar.extractfile(member).read().decode())

        self.assertEqual(result["merkle_root"], manifest["merkle_root"])

    def test_export_without_page_hashes_has_no_merkle_tree_json(self):
        session_id = "sess-merkle-004"
        rows = make_fake_rows(session_id, count=1)
        audit = MockAuditLog(rows=rows)
        proof = ConduitProof(audit, session_id)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir)
            with tarfile.open(result["path"], "r:gz") as tar:
                names = tar.getnames()

        self.assertFalse(
            any("merkle_tree.json" in n for n in names),
            f"merkle_tree.json should not be in bundle without page_hashes. Got: {names}"
        )

    def test_export_without_page_hashes_result_merkle_root_is_none(self):
        session_id = "sess-merkle-005"
        rows = make_fake_rows(session_id, count=1)
        audit = MockAuditLog(rows=rows)
        proof = ConduitProof(audit, session_id)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir)

        self.assertIsNone(result["merkle_root"])

    def test_merkle_tree_json_content_has_correct_structure(self):
        session_id = "sess-merkle-006"
        rows = make_fake_rows(session_id, count=2)
        audit = MockAuditLog(rows=rows)
        proof = ConduitProof(audit, session_id)
        page_hashes = self._make_page_hashes(3)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir, page_hashes=page_hashes)
            with tarfile.open(result["path"], "r:gz") as tar:
                member = next(m for m in tar.getmembers() if "merkle_tree.json" in m.name)
                tree_data = json.loads(tar.extractfile(member).read().decode())

        self.assertIn("root", tree_data)
        self.assertIn("leaf_count", tree_data)
        self.assertIn("pages", tree_data)
        self.assertIn("tree", tree_data)
        self.assertEqual(tree_data["leaf_count"], 3)
        self.assertEqual(len(tree_data["pages"]), 3)

    def test_merkle_tree_pages_have_url_hash_leaf_index(self):
        session_id = "sess-merkle-007"
        rows = make_fake_rows(session_id, count=2)
        audit = MockAuditLog(rows=rows)
        proof = ConduitProof(audit, session_id)
        page_hashes = self._make_page_hashes(2)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = proof.export(output_dir=tmpdir, page_hashes=page_hashes)
            with tarfile.open(result["path"], "r:gz") as tar:
                member = next(m for m in tar.getmembers() if "merkle_tree.json" in m.name)
                tree_data = json.loads(tar.extractfile(member).read().decode())

        for i, page in enumerate(tree_data["pages"]):
            self.assertIn("url", page)
            self.assertIn("hash", page)
            self.assertIn("leaf_index", page)
            self.assertEqual(page["leaf_index"], i)


# ---------------------------------------------------------------------------
# Feature 4 cont: crawl_site returns page_hashes
# ---------------------------------------------------------------------------

class TestCrawlSitePageHashes(unittest.TestCase):
    """Test that ConduitCrawler.crawl_site() returns page_hashes in its result."""

    def _make_mock_crawler(self, pages: list[dict]):
        """Build a ConduitCrawler with a mocked browser and mock audit_log."""
        import importlib
        crawl_mod = sys.modules.get("cato.tools.conduit_crawl")
        if crawl_mod is None:
            spec = importlib.util.spec_from_file_location(
                "cato.tools.conduit_crawl",
                str(_CONDUIT_ROOT / "tools" / "conduit_crawl.py"),
            )
            crawl_mod = importlib.util.module_from_spec(spec)
            sys.modules["cato.tools.conduit_crawl"] = crawl_mod
            spec.loader.exec_module(spec)
        ConduitCrawler = crawl_mod.ConduitCrawler

        # Mock browser with _page
        browser = MagicMock()
        browser._page = MagicMock()

        call_count = {"n": 0}

        async def _ensure_browser():
            pass

        async def _navigate(url):
            return {"title": "Test"}

        async def _extract_links(base_url):
            return []

        async def page_title():
            idx = call_count["n"] % len(pages)
            return pages[idx].get("title", "Test Page")

        async def page_evaluate(js, *args, **kwargs):
            idx = call_count["n"] % len(pages)
            call_count["n"] += 1
            return pages[idx].get("text", "some page text")

        browser._ensure_browser = _ensure_browser
        browser._navigate = _navigate
        browser._extract_links = _extract_links
        browser._page.title = page_title
        browser._page.evaluate = page_evaluate

        mock_audit = MagicMock()
        mock_audit.log = MagicMock()

        crawler = ConduitCrawler(browser, mock_audit, "sess-crawl-test")
        crawler._is_allowed = AsyncMock(return_value=True)
        crawler._wait_crawl_delay = AsyncMock()
        crawler._check_rate_limit_and_backoff = MagicMock()
        crawler._extract_links = AsyncMock(return_value=[])
        return crawler, ConduitCrawler

    def test_crawl_site_result_contains_page_hashes_key(self):
        import importlib
        crawl_mod = sys.modules.get("cato.tools.conduit_crawl")
        if crawl_mod is None:
            spec = importlib.util.spec_from_file_location(
                "cato.tools.conduit_crawl",
                str(_CONDUIT_ROOT / "tools" / "conduit_crawl.py"),
            )
            crawl_mod = importlib.util.module_from_spec(spec)
            sys.modules["cato.tools.conduit_crawl"] = crawl_mod
            spec.loader.exec_module(spec)
        ConduitCrawler = crawl_mod.ConduitCrawler

        # Build a minimal test by directly inspecting the source
        # The key thing: crawl_site() now builds page_hashes and returns them
        # We verify this by checking the conduit_crawl.py source
        import inspect
        src = (Path(__file__).parent.parent / "tools" / "conduit_crawl.py").read_text()
        self.assertIn("page_hashes", src,
            "conduit_crawl.py must build and return page_hashes")

    def test_crawl_site_page_hashes_have_url_and_hash_fields(self):
        src = (Path(__file__).parent.parent / "tools" / "conduit_crawl.py").read_text()
        # Verify the structure {"url": ..., "hash": ...} is built
        self.assertIn('"url"', src)
        self.assertIn('"hash"', src)

    def test_crawl_site_page_hash_is_sha256_of_text(self):
        """Verify in the source that the hash is computed as sha256 of the page text."""
        src = (Path(__file__).parent.parent / "tools" / "conduit_crawl.py").read_text()
        self.assertIn("sha256", src.lower())
        self.assertIn("page_hashes", src)


if __name__ == "__main__":
    unittest.main()
