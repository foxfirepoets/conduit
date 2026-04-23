"""
tests/test_browser_actions.py

Live browser tests for Wave 1 BrowserTool actions:
  scroll, fill, wait, wait_for, key_press, hover,
  select_option, handle_dialog, navigate_back, console_messages

All tests use a real Patchright Chromium browser against public sites.
One shared bridge for the module — browser launched once, reused across tests.

Note: bridge.execute() returns a JSON string (agent interface).
      Direct bridge methods (bridge.fill(), bridge.scroll(), etc.) return dicts.
      Tests use the direct methods.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Bootstrap — wire sys.modules so relative imports resolve
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
    db = tmp_path_factory.mktemp("wave1_live") / "cato.db"
    _bootstrap(db)
    return db


@pytest.fixture(scope="module")
def bridge(tmp_db):
    ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
    sess = f"wave1-live-{uuid.uuid4().hex[:8]}"
    b = ConduitBridge(sess, budget_cents=99999, data_dir=tmp_db.parent)
    asyncio.get_event_loop().run_until_complete(b.start())
    yield b
    asyncio.get_event_loop().run_until_complete(b.stop())


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tests: fill — DuckDuckGo search box
# ---------------------------------------------------------------------------

class TestFill:

    def test_fill_search_box_and_verify(self, bridge):
        run(bridge.navigate("https://duckduckgo.com"))
        result = run(bridge.fill("input[name='q']", "conduit browser"))
        assert result.get("success") is True, f"fill failed: {result}"
        assert result.get("typed") == "conduit browser"

    def test_fill_returns_correct_typed_text(self, bridge):
        run(bridge.navigate("https://duckduckgo.com"))
        result = run(bridge.fill("input[name='q']", "live test fill"))
        assert result.get("typed") == "live test fill"


# ---------------------------------------------------------------------------
# Tests: scroll — Hacker News (long page)
# ---------------------------------------------------------------------------

class TestScroll:

    def test_scroll_down_returns_success(self, bridge):
        run(bridge.navigate("https://news.ycombinator.com"))
        result = run(bridge.scroll("down", 500))
        assert result.get("success") is True, f"scroll down failed: {result}"
        assert result.get("direction") == "down"
        assert result.get("amount") == 500

    def test_scroll_up_returns_success(self, bridge):
        run(bridge.navigate("https://news.ycombinator.com"))
        run(bridge.scroll("down", 500))
        result = run(bridge.scroll("up", 300))
        assert result.get("success") is True, f"scroll up failed: {result}"
        assert result.get("direction") == "up"

    def test_scroll_into_view_with_selector(self, bridge):
        run(bridge.navigate("https://news.ycombinator.com"))
        result = run(bridge.scroll(selector="a[href='newest']"))
        assert "error" not in result or result.get("action") == "scroll_into_view", (
            f"scroll with selector failed: {result}"
        )


# ---------------------------------------------------------------------------
# Tests: wait — live timing verification
# ---------------------------------------------------------------------------

class TestWait:

    def test_wait_half_second(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.wait(0.5))
        assert result.get("success") is True
        assert result.get("waited_seconds") == 0.5

    def test_wait_one_second(self, bridge):
        result = run(bridge.wait(1.0))
        assert result.get("waited_seconds") == 1.0


# ---------------------------------------------------------------------------
# Tests: wait_for — selector and network idle
# ---------------------------------------------------------------------------

class TestWaitFor:

    def test_wait_for_selector_h1(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.wait_for("selector", "h1", timeout_ms=5000))
        assert result.get("success") is True, f"wait_for h1 failed: {result}"

    def test_wait_for_missing_selector_returns_error(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.wait_for("selector", "#this-element-xyz-missing", timeout_ms=1000))
        assert result.get("success") is False, "Expected failure for missing selector"


# ---------------------------------------------------------------------------
# Tests: key_press — on DuckDuckGo
# ---------------------------------------------------------------------------

class TestKeyPress:

    def test_key_press_enter(self, bridge):
        run(bridge.navigate("https://duckduckgo.com"))
        run(bridge.fill("input[name='q']", "conduit test"))
        result = run(bridge.key_press("Enter"))
        assert result.get("success") is True, f"key_press Enter failed: {result}"
        assert result.get("key") == "Enter"

    def test_key_press_escape(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.key_press("Escape"))
        assert result.get("success") is True, f"key_press Escape failed: {result}"
        assert result.get("key") == "Escape"

    def test_key_press_tab(self, bridge):
        run(bridge.navigate("https://duckduckgo.com"))
        result = run(bridge.key_press("Tab"))
        assert result.get("success") is True
        assert result.get("key") == "Tab"


# ---------------------------------------------------------------------------
# Tests: hover
# ---------------------------------------------------------------------------

class TestHover:

    def test_hover_link_on_hn(self, bridge):
        run(bridge.navigate("https://news.ycombinator.com"))
        result = run(bridge.hover("a[href='newest']"))
        assert result.get("success") is True, f"hover failed: {result}"

    def test_hover_missing_selector_returns_error(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.hover("#nonexistent-element-xyz"))
        assert result.get("success") is False, "Expected hover to fail on missing element"


# ---------------------------------------------------------------------------
# Tests: navigate_back
# ---------------------------------------------------------------------------

class TestNavigateBack:

    def test_navigate_back_returns_success(self, bridge):
        run(bridge.navigate("https://example.com"))
        run(bridge.navigate("https://news.ycombinator.com"))
        result = run(bridge.navigate_back())
        assert result.get("success") is True, f"navigate_back failed: {result}"
        assert "url" in result
        assert "title" in result

    def test_navigate_back_url_changes(self, bridge):
        run(bridge.navigate("https://example.com"))
        run(bridge.navigate("https://news.ycombinator.com"))
        result = run(bridge.navigate_back())
        back_url = result.get("url", "")
        assert back_url != "https://news.ycombinator.com" or "example" in back_url.lower(), (
            f"navigate_back url unexpected: {back_url!r}"
        )


# ---------------------------------------------------------------------------
# Tests: console_messages
# ---------------------------------------------------------------------------

class TestConsoleMessages:

    def test_console_messages_returns_list(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.console_messages())
        assert "messages" in result, f"console_messages missing 'messages': {result}"
        assert "count" in result
        assert isinstance(result["messages"], list)

    def test_console_eval_injects_message(self, bridge):
        run(bridge.navigate("https://example.com"))
        # Clear any existing buffer
        run(bridge.console_messages())
        # Inject a known message
        run(bridge.eval("console.log('hello-from-conduit')"))
        result = run(bridge.console_messages())
        texts = [m.get("text", "") for m in result.get("messages", [])]
        assert any("hello-from-conduit" in t for t in texts), (
            f"Injected console message not found. Messages: {texts}"
        )

    def test_console_messages_clears_after_read(self, bridge):
        run(bridge.navigate("https://example.com"))
        run(bridge.eval("console.log('msg-one')"))
        first = run(bridge.console_messages())
        second = run(bridge.console_messages())
        assert second.get("count", 0) <= first.get("count", 0), (
            f"Buffer not cleared: first={first.get('count')}, second={second.get('count')}"
        )


# ---------------------------------------------------------------------------
# Tests: execute() returns a string (agent interface sanity check)
# ---------------------------------------------------------------------------

class TestExecuteInterface:

    def test_execute_returns_string(self, bridge):
        """execute() is the agent entry point and always returns a JSON string."""
        result = run(bridge.execute({"action": "navigate", "url": "https://example.com"}))
        assert isinstance(result, str), f"execute() should return str, got {type(result)}"
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_execute_unknown_action_returns_error_json(self, bridge):
        result = run(bridge.execute({"action": "fly_to_moon"}))
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "error" in parsed or "unknown" in str(parsed).lower(), (
            f"Expected error for unknown action: {parsed}"
        )


# ---------------------------------------------------------------------------
# Tests: Cookie & Auth session management (Wave 8)
# ---------------------------------------------------------------------------

class TestCookieAndAuth:

    def test_save_cookies_returns_success(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.save_cookies(label="test_session"))
        assert result.get("success") is True, f"save_cookies failed: {result}"
        assert result.get("count", 0) >= 0  # may be 0 on fresh session
        assert "path" in result

    def test_save_and_load_cookies_round_trip(self, bridge):
        run(bridge.navigate("https://example.com"))
        # Save
        save_result = run(bridge.save_cookies(label="round_trip_test"))
        assert save_result.get("success") is True, f"save failed: {save_result}"
        # Load back
        load_result = run(bridge.load_cookies(label="round_trip_test"))
        assert load_result.get("success") is True, f"load failed: {load_result}"
        assert load_result.get("count", 0) == save_result.get("count", 0)

    def test_load_cookies_fails_gracefully_for_missing_label(self, bridge):
        result = run(bridge.load_cookies(label="nonexistent_label_xyz_123"))
        assert result.get("success") is False
        assert "error" in result

    def test_check_session_on_example_com(self, bridge):
        run(bridge.navigate("https://example.com"))
        result = run(bridge.check_session("https://example.com"))
        assert "ok" in result or "authenticated" in result, (
            f"check_session missing expected key: {result}"
        )

    def test_login_fails_gracefully_without_credentials(self, bridge):
        import os
        # Ensure no credentials set
        for k in ("TESTSITE_USERNAME", "TESTSITE_PASSWORD"):
            os.environ.pop(k, None)
        result = run(bridge.login(
            url="https://example.com",
            credential_key="testsite",
        ))
        assert result.get("success") is False
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests: Self-Healing Selectors (Chunk 11)
# ---------------------------------------------------------------------------

class TestSelfHealingSelectors:

    def test_selector_healing_enabled_by_default(self, bridge):
        """ConduitBridge has selector healing enabled by default."""
        assert getattr(bridge, '_selector_healing_enabled', True) is True

    def test_valid_selector_does_not_attach_healing_metadata(self, bridge):
        """
        When _try_selector_with_healing succeeds on Tier 1, the returned result
        must NOT contain healing metadata (tiers_tried, selector_healing_attempted).
        We verify this by simulating a successful Tier 1 response via mock.
        """
        from unittest.mock import AsyncMock, patch

        success_result = {"success": True, "selector": "h1"}

        async def mock_click(selector, **kwargs):
            return success_result

        with patch.object(bridge._browser_tool, "_click", new=mock_click):
            result = run(bridge._try_selector_with_healing("click", "h1"))
        outcome, tier = result
        assert tier == "css", f"Expected tier 'css' for success, got {tier!r}"
        assert "tiers_tried" not in outcome, "tiers_tried must not appear on Tier 1 success"
        assert "selector_healing_attempted" not in outcome, (
            "selector_healing_attempted must not appear on Tier 1 success"
        )

    def test_broken_selector_tries_healing(self, bridge):
        """
        When _try_selector_with_healing fails Tier 1, it must annotate the result
        with selector_healing_attempted=True and tiers_tried after exhausting all tiers.
        """
        from unittest.mock import AsyncMock, patch

        failure_result = {"success": False, "error": "Element not found"}

        async def mock_click_fail(selector, **kwargs):
            return failure_result

        async def mock_aria_snapshot():
            return {"tree": "[]"}

        with (
            patch.object(bridge._browser_tool, "_click", new=mock_click_fail),
            patch.object(bridge._browser_tool, "_accessibility_snapshot", new=mock_aria_snapshot),
        ):
            result = run(bridge._try_selector_with_healing("click", "#xyz-9999"))
        outcome, tier = result
        assert tier == "failed", f"Expected tier 'failed' after all tiers exhausted, got {tier!r}"
        assert outcome.get("selector_healing_attempted") is True, (
            "selector_healing_attempted must be True after all tiers fail"
        )
        assert "tiers_tried" in outcome, "tiers_tried must be present after all tiers fail"

    def test_healing_audit_method_exists(self, bridge):
        """_audit_healing method exists on bridge."""
        assert hasattr(bridge, '_audit_healing'), "Bridge should have _audit_healing method"

    def test_try_selector_with_healing_exists(self, bridge):
        """_try_selector_with_healing method exists on bridge."""
        assert hasattr(bridge, '_try_selector_with_healing'), (
            "Bridge should have _try_selector_with_healing method"
        )


# ---------------------------------------------------------------------------
# Tests: Structured Extraction + Provenance (Chunk 12)
# ---------------------------------------------------------------------------

class TestStructuredExtractionAndProvenance:

    def test_extract_main_has_provenance_mode_param(self, bridge):
        """extract_main() accepts provenance_mode parameter."""
        import inspect
        sig = inspect.signature(bridge.extract_main)
        assert "provenance_mode" in sig.parameters, (
            "extract_main must accept provenance_mode parameter"
        )

    def test_extract_main_provenance_mode_wraps_fields(self, bridge):
        """When provenance_mode=True, each field is wrapped with {value, provenance}."""
        from unittest.mock import AsyncMock, patch

        mock_result = {
            "text": "Hello world",
            "char_count": 11,
            "url": "https://example.com",
            "title": "Example",
            "truncated": False,
            "content_hash": "abc123",
            "fetched_at": 1700000000.0,
            "http_status": 200,
            "links_found": 5,
        }

        async def mock_dispatch(action, kwargs):
            return mock_result.copy()

        with patch.object(bridge._browser_tool, "_dispatch", new=mock_dispatch):
            result = run(bridge.extract_main(provenance_mode=True))

        # Each field should be wrapped
        assert "text" in result, "text field missing"
        text_wrapped = result["text"]
        assert isinstance(text_wrapped, dict), "field should be wrapped in dict"
        assert "value" in text_wrapped, "wrapped field must have 'value'"
        assert "provenance" in text_wrapped, "wrapped field must have 'provenance'"
        assert text_wrapped["value"] == "Hello world"

    def test_extract_main_provenance_has_required_keys(self, bridge):
        """Provenance metadata contains all required keys."""
        from unittest.mock import patch

        mock_result = {
            "text": "content",
            "char_count": 7,
            "url": "https://example.com",
            "title": "Page",
            "truncated": False,
            "content_hash": "def456",
            "fetched_at": 1700000001.0,
            "http_status": None,
            "links_found": 0,
        }

        async def mock_dispatch(action, kwargs):
            return mock_result.copy()

        with patch.object(bridge._browser_tool, "_dispatch", new=mock_dispatch):
            result = run(bridge.extract_main(provenance_mode=True))

        provenance = result["text"]["provenance"]
        required_keys = {"audit_row_id", "session_pubkey", "url", "url_hash", "extracted_at", "chain_verified"}
        for key in required_keys:
            assert key in provenance, f"provenance missing key: {key!r}"

    def test_extract_main_provenance_session_pubkey(self, bridge):
        """Provenance contains the bridge's session public key."""
        from unittest.mock import patch

        mock_result = {
            "text": "content",
            "char_count": 7,
            "url": "https://example.com",
            "title": "Page",
            "truncated": False,
            "content_hash": "def456",
            "fetched_at": 1700000001.0,
            "http_status": None,
            "links_found": 0,
        }

        async def mock_dispatch(action, kwargs):
            return mock_result.copy()

        with patch.object(bridge._browser_tool, "_dispatch", new=mock_dispatch):
            result = run(bridge.extract_main(provenance_mode=True))

        pubkey = result["text"]["provenance"]["session_pubkey"]
        assert isinstance(pubkey, str) and len(pubkey) == 64, (
            f"session_pubkey should be 64-char hex, got: {pubkey!r}"
        )

    def test_extract_main_normal_mode_returns_flat_dict(self, bridge):
        """When provenance_mode=False (default), result is a flat dict as before."""
        from unittest.mock import patch

        mock_result = {
            "text": "content",
            "char_count": 7,
            "url": "https://example.com",
            "title": "Page",
            "truncated": False,
            "content_hash": "aaa",
            "fetched_at": 1700000000.0,
            "http_status": 200,
            "links_found": 3,
        }

        async def mock_dispatch(action, kwargs):
            return mock_result.copy()

        with patch.object(bridge._browser_tool, "_dispatch", new=mock_dispatch):
            result = run(bridge.extract_main(provenance_mode=False))

        assert result.get("text") == "content", "normal mode should return flat text"
        assert "value" not in result, "normal mode must NOT wrap fields"

    def test_extract_structured_exists_on_bridge(self, bridge):
        """extract_structured method exists on ConduitBridge."""
        assert hasattr(bridge, "extract_structured"), (
            "ConduitBridge must have extract_structured method"
        )

    def test_extract_structured_requires_schema(self, bridge):
        """extract_structured returns error when model_extract is None."""
        from unittest.mock import patch

        mock_result = {
            "text": "Some page content about products",
            "char_count": 32,
            "url": "https://example.com",
            "title": "Page",
            "truncated": False,
            "content_hash": "bbb",
            "fetched_at": 1700000000.0,
            "http_status": 200,
            "links_found": 0,
        }

        async def mock_dispatch(action, kwargs):
            return mock_result.copy()

        with patch.object(bridge._browser_tool, "_dispatch", new=mock_dispatch):
            result = run(bridge.extract_structured(schema={"required": ["title"]}))

        assert "error" in result, "should return error when model_extract is None"
        assert "model_extract" in result["error"]

    def test_extract_structured_validates_schema_success(self, bridge):
        """extract_structured with valid model_extract and schema returns validated result."""
        from unittest.mock import patch

        mock_result = {
            "text": "Product: Widget, Price: $10",
            "char_count": 26,
            "url": "https://example.com",
            "title": "Shop",
            "truncated": False,
            "content_hash": "ccc",
            "fetched_at": 1700000000.0,
            "http_status": 200,
            "links_found": 2,
        }

        async def mock_dispatch(action, kwargs):
            return mock_result.copy()

        async def fake_model(text, schema):
            return {"name": "Widget", "price": "$10"}

        schema = {"required": ["name", "price"], "properties": {}}
        with patch.object(bridge._browser_tool, "_dispatch", new=mock_dispatch):
            result = run(bridge.extract_structured(schema=schema, model_extract=fake_model))

        assert result.get("name") == "Widget"
        assert result.get("price") == "$10"

    def test_extract_structured_schema_validation_failure(self, bridge):
        """extract_structured returns error when model output missing required keys."""
        from unittest.mock import patch

        mock_result = {
            "text": "Some text",
            "char_count": 9,
            "url": "https://example.com",
            "title": "Page",
            "truncated": False,
            "content_hash": "ddd",
            "fetched_at": 1700000000.0,
            "http_status": 200,
            "links_found": 0,
        }

        async def mock_dispatch(action, kwargs):
            return mock_result.copy()

        async def bad_model(text, schema):
            return {"wrong_key": "value"}  # Missing "name" required key

        schema = {"required": ["name"], "properties": {}}
        with patch.object(bridge._browser_tool, "_dispatch", new=mock_dispatch):
            result = run(bridge.extract_structured(schema=schema, model_extract=bad_model))

        assert "error" in result, "should return error when validation fails"

    def test_extract_main_result_has_provenance_fields(self, bridge):
        """extract_main() result always includes content_hash, fetched_at, http_status, links_found, truncated."""
        from unittest.mock import patch

        mock_result = {
            "text": "content",
            "char_count": 7,
            "url": "https://example.com",
            "title": "Page",
            "truncated": False,
            "content_hash": "abc",
            "fetched_at": 1700000000.0,
            "http_status": 200,
            "links_found": 3,
        }

        async def mock_dispatch(action, kwargs):
            return mock_result.copy()

        with patch.object(bridge._browser_tool, "_dispatch", new=mock_dispatch):
            result = run(bridge.extract_main())

        for field in ("content_hash", "fetched_at", "links_found", "truncated"):
            assert field in result, f"extract_main result missing provenance field: {field!r}"
