"""
tests/test_verify_rubric.py

Tests for rubric.py (evaluate_rubric, make_rubric_hash) and
ConduitBridge.verify_rubric().

Classes:
  TestRubricPredicates   — unit tests for evaluate_rubric(), no network
  TestRubricCustomChecks — sandbox security tests for custom_checks
  TestMakeRubricHash     — determinism / key-order / change-sensitivity
  TestVerifyRubricBridge — bridge-level tests with monkeypatched urllib
"""

from __future__ import annotations

import asyncio
import sys
import types
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap (same pattern as test_audit_chain.py)
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(__file__).parent.parent


def _bootstrap(tmp_db: Path) -> None:
    """Install minimal sys.modules shims so relative imports resolve."""
    import importlib.util

    # --- cato (top-level) ---
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules.setdefault("cato", cato_pkg)

    # --- cato.platform ---
    platform_mod = types.ModuleType("cato.platform")
    platform_mod.get_data_dir = lambda: tmp_db.parent
    sys.modules["cato.platform"] = platform_mod
    cato_pkg.platform = platform_mod  # type: ignore[attr-defined]

    # --- cato.audit ---
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

    # --- cato.tools (sub-package) ---
    tools_pkg = types.ModuleType("cato.tools")
    tools_pkg.__path__ = [str(CONDUIT_ROOT / "tools")]
    tools_pkg.__package__ = "cato.tools"
    sys.modules.setdefault("cato.tools", tools_pkg)
    cato_pkg.tools = tools_pkg  # type: ignore[attr-defined]

    # --- cato.tools.browser (stub) ---
    if "cato.tools.browser" not in sys.modules:
        browser_mod = types.ModuleType("cato.tools.browser")
        browser_mod.__package__ = "cato.tools"

        class _StubBrowserTool:
            pass

        browser_mod.BrowserTool = _StubBrowserTool  # type: ignore[attr-defined]
        sys.modules["cato.tools.browser"] = browser_mod

    # --- cato.tools.rubric (the real file) ---
    if "cato.tools.rubric" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.tools.rubric",
            str(CONDUIT_ROOT / "tools" / "rubric.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        rubric_mod = importlib.util.module_from_spec(spec)
        rubric_mod.__package__ = "cato.tools"
        sys.modules["cato.tools.rubric"] = rubric_mod
        spec.loader.exec_module(rubric_mod)  # type: ignore[union-attr]
        tools_pkg.rubric = rubric_mod  # type: ignore[attr-defined]

    # --- cato.tools.conduit_bridge (the real file) ---
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


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("rubric_test") / "cato.db"
    _bootstrap(db)
    return db


@pytest.fixture(scope="module")
def rubric_mod(tmp_db):
    # rubric.py can be imported directly — no relative imports needed
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_rubric_direct",
        str(CONDUIT_ROOT / "tools" / "rubric.py"),
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def evaluate_rubric(rubric_mod):
    return rubric_mod.evaluate_rubric


@pytest.fixture(scope="module")
def make_rubric_hash(rubric_mod):
    return rubric_mod.make_rubric_hash


@pytest.fixture(scope="module")
def ConduitBridge(tmp_db):
    return sys.modules["cato.tools.conduit_bridge"].ConduitBridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIFTY_WORDS = " ".join(["word"] * 50)
_FIVE_WORDS = "one two three four five"


def _make_bridge(ConduitBridge, tmp_db: Path, session_id: str | None = None):
    import uuid
    sid = session_id or f"rubric-test-{uuid.uuid4().hex[:8]}"
    bridge = ConduitBridge(sid, budget_cents=9999, data_dir=tmp_db.parent)
    bridge._ledger.connect()
    bridge._audit_log.connect()
    return bridge


# ---------------------------------------------------------------------------
# Class 1: TestRubricPredicates
# ---------------------------------------------------------------------------


class TestRubricPredicates:
    """Unit tests for evaluate_rubric() — no bridge, no network."""

    def test_min_word_count_pass(self, evaluate_rubric):
        result = evaluate_rubric(_FIFTY_WORDS, {"min_word_count": 10})
        assert result["rubric_pass"] is True
        assert result["predicate_results"][0]["passed"] is True

    def test_min_word_count_fail(self, evaluate_rubric):
        result = evaluate_rubric(_FIVE_WORDS, {"min_word_count": 10})
        assert result["rubric_pass"] is False
        assert result["predicate_results"][0]["passed"] is False

    def test_max_word_count_pass(self, evaluate_rubric):
        result = evaluate_rubric(_FIVE_WORDS, {"max_word_count": 10})
        assert result["rubric_pass"] is True
        assert result["predicate_results"][0]["passed"] is True

    def test_max_word_count_fail(self, evaluate_rubric):
        result = evaluate_rubric(_FIFTY_WORDS, {"max_word_count": 10})
        assert result["rubric_pass"] is False
        assert result["predicate_results"][0]["passed"] is False

    def test_must_contain_pass(self, evaluate_rubric):
        result = evaluate_rubric("hello world this is content", {"must_contain": ["hello"]})
        assert result["rubric_pass"] is True
        assert result["predicate_results"][0]["passed"] is True

    def test_must_contain_fail(self, evaluate_rubric):
        result = evaluate_rubric("goodbye world", {"must_contain": ["hello"]})
        assert result["rubric_pass"] is False
        pr = result["predicate_results"][0]
        assert pr["passed"] is False
        assert "hello" in pr["reason"]

    def test_must_not_contain_pass(self, evaluate_rubric):
        result = evaluate_rubric("this is clean content", {"must_not_contain": ["badword"]})
        assert result["rubric_pass"] is True
        assert result["predicate_results"][0]["passed"] is True

    def test_must_not_contain_fail(self, evaluate_rubric):
        result = evaluate_rubric("this has badword in it", {"must_not_contain": ["badword"]})
        assert result["rubric_pass"] is False
        assert result["predicate_results"][0]["passed"] is False

    def test_min_length_chars_pass(self, evaluate_rubric):
        content = "a" * 100
        result = evaluate_rubric(content, {"min_length_chars": 50})
        assert result["rubric_pass"] is True
        assert result["predicate_results"][0]["passed"] is True

    def test_min_length_chars_fail(self, evaluate_rubric):
        content = "a" * 10
        result = evaluate_rubric(content, {"min_length_chars": 50})
        assert result["rubric_pass"] is False
        assert result["predicate_results"][0]["passed"] is False

    def test_content_type_hint_json_pass(self, evaluate_rubric):
        result = evaluate_rubric('{"key": "value"}', {"content_type_hint": "json"})
        assert result["rubric_pass"] is True
        assert result["predicate_results"][0]["passed"] is True

    def test_content_type_hint_json_fail(self, evaluate_rubric):
        result = evaluate_rubric("this is not json {{{", {"content_type_hint": "json"})
        assert result["rubric_pass"] is False
        assert result["predicate_results"][0]["passed"] is False

    def test_content_type_hint_html_pass(self, evaluate_rubric):
        result = evaluate_rubric("<html><body>hello</body></html>", {"content_type_hint": "html"})
        assert result["rubric_pass"] is True
        assert result["predicate_results"][0]["passed"] is True

    def test_content_type_hint_markdown_pass(self, evaluate_rubric):
        result = evaluate_rubric("# Heading\n\nSome content here.", {"content_type_hint": "markdown"})
        assert result["rubric_pass"] is True
        assert result["predicate_results"][0]["passed"] is True

    def test_content_type_hint_text_always_passes(self, evaluate_rubric):
        # Any content should pass for hint="text"
        result = evaluate_rubric("", {"content_type_hint": "text"})
        assert result["rubric_pass"] is True
        assert result["predicate_results"][0]["passed"] is True

    def test_all_predicates_pass(self, evaluate_rubric):
        content = "hello world " + " ".join(["word"] * 20)
        rubric = {
            "min_word_count": 5,
            "must_contain": ["hello"],
            "min_length_chars": 10,
        }
        result = evaluate_rubric(content, rubric)
        assert result["rubric_pass"] is True
        assert all(p["passed"] for p in result["predicate_results"])

    def test_one_predicate_fails(self, evaluate_rubric):
        content = "hello world " + " ".join(["word"] * 20)
        rubric = {
            "min_word_count": 5,        # passes
            "must_contain": ["missing_phrase"],  # fails
            "min_length_chars": 10,     # passes
        }
        result = evaluate_rubric(content, rubric)
        assert result["rubric_pass"] is False
        failed = [p for p in result["predicate_results"] if not p["passed"]]
        assert len(failed) == 1
        assert "missing_phrase" in failed[0]["reason"]

    def test_empty_rubric_returns_pass(self, evaluate_rubric):
        result = evaluate_rubric("any content", {})
        assert result["rubric_pass"] is True
        assert result["predicate_results"] == []


# ---------------------------------------------------------------------------
# Class 2: TestRubricCustomChecks
# ---------------------------------------------------------------------------


class TestRubricCustomChecks:
    """Sandbox security tests for custom_checks predicate."""

    def _run(self, evaluate_rubric, expr: str, content: str = "hello world") -> dict:
        result = evaluate_rubric(content, {"custom_checks": [expr]})
        return result["predicate_results"][0]

    def test_custom_check_pass(self, evaluate_rubric):
        pr = self._run(evaluate_rubric, "len(content) > 0", content="hello")
        assert pr["passed"] is True

    def test_custom_check_fail(self, evaluate_rubric):
        pr = self._run(evaluate_rubric, "len(content) > 999999", content="short")
        assert pr["passed"] is False

    def test_custom_check_blocks_import(self, evaluate_rubric):
        pr = self._run(evaluate_rubric, "__import__('os').system('echo pwned')")
        assert pr["passed"] is False
        assert "unsafe" in pr["reason"].lower()

    def test_custom_check_blocks_dunder_attr(self, evaluate_rubric):
        pr = self._run(evaluate_rubric, "content.__class__.__bases__")
        assert pr["passed"] is False
        # reason should mention "unsafe" or "blocked" or "dunder"
        reason_lower = pr["reason"].lower()
        assert any(kw in reason_lower for kw in ("unsafe", "blocked", "dunder"))

    def test_custom_check_blocks_exec_builtin(self, evaluate_rubric):
        pr = self._run(evaluate_rubric, "exec('import os')")
        assert pr["passed"] is False
        reason_lower = pr["reason"].lower()
        assert any(kw in reason_lower for kw in ("unsafe", "blocked"))

    def test_custom_check_runtime_error_is_caught(self, evaluate_rubric):
        pr = self._run(evaluate_rubric, "1/0")
        assert pr["passed"] is False
        assert "error" in pr["reason"].lower()

    def test_custom_check_non_bool_coerced(self, evaluate_rubric):
        # Expression returns int 1, which should be coerced to True
        pr = self._run(evaluate_rubric, "1")
        assert pr["passed"] is True

    def test_custom_check_blocks_walrus_operator(self, evaluate_rubric):
        # Walrus (:=) allows mid-expression name rebinding; it must be blocked.
        pr = self._run(evaluate_rubric, "(x := len)(content)")
        assert pr["passed"] is False
        reason_lower = pr["reason"].lower()
        assert any(kw in reason_lower for kw in ("unsafe", "walrus", "blocked"))


# ---------------------------------------------------------------------------
# Class 3: TestMakeRubricHash
# ---------------------------------------------------------------------------


class TestMakeRubricHash:
    def test_hash_deterministic(self, make_rubric_hash):
        rubric = {"min_word_count": 10, "must_contain": ["hello"]}
        assert make_rubric_hash(rubric) == make_rubric_hash(rubric)

    def test_hash_sort_keys(self, make_rubric_hash):
        r1 = {"b": 2, "a": 1}
        r2 = {"a": 1, "b": 2}
        assert make_rubric_hash(r1) == make_rubric_hash(r2)

    def test_hash_differs_on_change(self, make_rubric_hash):
        r1 = {"min_word_count": 10}
        r2 = {"min_word_count": 99}
        assert make_rubric_hash(r1) != make_rubric_hash(r2)


# ---------------------------------------------------------------------------
# Class 4: TestVerifyRubricBridge
# ---------------------------------------------------------------------------


class TestVerifyRubricBridge:
    """Bridge-level tests using monkeypatched urllib — no real network calls."""

    def _rubric_and_hash(self, rubric_mod, rubric: dict) -> tuple[dict, str]:
        h = rubric_mod.make_rubric_hash(rubric)
        return rubric, h

    def _mock_opener_with_content(self, content: str):
        """Return a mock opener whose .open() context manager yields the content."""
        resp = MagicMock()
        resp.status = 200
        # Simulate chunked read: first call returns content bytes, second returns b""
        raw = content.encode("utf-8")
        resp.read.side_effect = [raw, b""]
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)

        opener = MagicMock()
        opener.open.return_value = resp
        return opener

    def test_rubric_hash_mismatch_returns_error(self, ConduitBridge, tmp_db, rubric_mod):
        bridge = _make_bridge(ConduitBridge, tmp_db)
        rubric = {"min_word_count": 5}
        wrong_hash = "0" * 64

        result = asyncio.get_event_loop().run_until_complete(
            bridge.verify_rubric(
                url="https://example.com",
                rubric=rubric,
                rubric_hash=wrong_hash,
                request_id="req-001",
            )
        )

        assert result["success"] is False
        assert "tampered" in result["error"].lower()

    def test_rubric_pass_true_on_matching_content(self, ConduitBridge, tmp_db, rubric_mod):
        bridge = _make_bridge(ConduitBridge, tmp_db)
        content = "hello world " + " ".join(["word"] * 20)
        rubric = {"min_word_count": 5, "must_contain": ["hello"]}
        _, rubric_hash = self._rubric_and_hash(rubric_mod, rubric)

        opener = self._mock_opener_with_content(content)
        bridge_mod = sys.modules["cato.tools.conduit_bridge"]

        # Patch _audit to absorb the call so bridge internals don't fail
        with patch.object(bridge, "_audit"), \
             patch.object(bridge_mod._urllib_req, "build_opener", return_value=opener):
            result = asyncio.get_event_loop().run_until_complete(
                bridge.verify_rubric(
                    url="https://example.com",
                    rubric=rubric,
                    rubric_hash=rubric_hash,
                    request_id="req-002",
                )
            )

        assert result["success"] is True
        assert result["rubric_pass"] is True

    def test_rubric_pass_false_on_failing_content(self, ConduitBridge, tmp_db, rubric_mod):
        bridge = _make_bridge(ConduitBridge, tmp_db)
        content = "goodbye world"  # missing "required_phrase"
        rubric = {"must_contain": ["required_phrase"]}
        _, rubric_hash = self._rubric_and_hash(rubric_mod, rubric)

        opener = self._mock_opener_with_content(content)
        bridge_mod = sys.modules["cato.tools.conduit_bridge"]

        with patch.object(bridge, "_audit"), \
             patch.object(bridge_mod._urllib_req, "build_opener", return_value=opener):
            result = asyncio.get_event_loop().run_until_complete(
                bridge.verify_rubric(
                    url="https://example.com",
                    rubric=rubric,
                    rubric_hash=rubric_hash,
                    request_id="req-003",
                )
            )

        # Fetch succeeded but rubric evaluation failed
        assert result["success"] is True
        assert result["rubric_pass"] is False

    def test_fetch_failure_returns_error(self, ConduitBridge, tmp_db, rubric_mod):
        bridge = _make_bridge(ConduitBridge, tmp_db)
        rubric = {"min_word_count": 5}
        _, rubric_hash = self._rubric_and_hash(rubric_mod, rubric)

        opener = MagicMock()
        opener.open.side_effect = urllib.error.URLError("connection refused")
        bridge_mod = sys.modules["cato.tools.conduit_bridge"]

        # _audit IS called on fetch failure (audit chain logs all attempts)
        with patch.object(bridge, "_audit"), \
             patch.object(bridge_mod._urllib_req, "build_opener", return_value=opener):
            result = asyncio.get_event_loop().run_until_complete(
                bridge.verify_rubric(
                    url="https://example.com",
                    rubric=rubric,
                    rubric_hash=rubric_hash,
                    request_id="req-004",
                )
            )

        assert result["success"] is False
        assert "error" in result

    def test_audit_called_on_fetch_failure(self, ConduitBridge, tmp_db, rubric_mod):
        """_audit must be called exactly once even when the fetch fails."""
        bridge = _make_bridge(ConduitBridge, tmp_db)
        rubric = {"min_word_count": 5}
        _, rubric_hash = self._rubric_and_hash(rubric_mod, rubric)

        opener = MagicMock()
        opener.open.side_effect = urllib.error.URLError("connection refused")
        bridge_mod = sys.modules["cato.tools.conduit_bridge"]

        audit_calls = []
        bridge._audit = lambda *a, **kw: audit_calls.append((a, kw))

        with patch.object(bridge_mod._urllib_req, "build_opener", return_value=opener):
            asyncio.get_event_loop().run_until_complete(
                bridge.verify_rubric(
                    url="https://example.com",
                    rubric=rubric,
                    rubric_hash=rubric_hash,
                    request_id="req-004b",
                )
            )

        assert len(audit_calls) == 1

    def test_audit_called_once(self, ConduitBridge, tmp_db, rubric_mod):
        bridge = _make_bridge(ConduitBridge, tmp_db)
        content = "hello world and more words here for a good count"
        rubric = {"min_word_count": 3}
        _, rubric_hash = self._rubric_and_hash(rubric_mod, rubric)

        opener = self._mock_opener_with_content(content)
        bridge_mod = sys.modules["cato.tools.conduit_bridge"]

        audit_calls = []

        def _spy(*args, **kwargs):
            audit_calls.append((args, kwargs))

        # Replace _audit with spy — absorbs any kwarg signature the source uses
        bridge._audit = _spy

        with patch.object(bridge_mod._urllib_req, "build_opener", return_value=opener):
            asyncio.get_event_loop().run_until_complete(
                bridge.verify_rubric(
                    url="https://example.com",
                    rubric=rubric,
                    rubric_hash=rubric_hash,
                    request_id="req-005",
                )
            )

        assert len(audit_calls) == 1

    def test_audit_called_on_private_ip_block(self, ConduitBridge, tmp_db, rubric_mod):
        """SSRF attempts (private-IP targets) must be logged to the audit chain."""
        bridge = _make_bridge(ConduitBridge, tmp_db)
        rubric = {"min_word_count": 1}
        _, rubric_hash = self._rubric_and_hash(rubric_mod, rubric)

        audit_calls = []
        bridge._audit = lambda *a, **kw: audit_calls.append((a, kw))

        result = asyncio.get_event_loop().run_until_complete(
            bridge.verify_rubric(
                url="http://127.0.0.1/secret",
                rubric=rubric,
                rubric_hash=rubric_hash,
                request_id="req-006",
            )
        )

        assert result["success"] is False
        assert len(audit_calls) == 1, "private-IP block must be logged to audit chain"
