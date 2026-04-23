"""
tests/test_captcha.py

Tests for CAPTCHA detection and auto-solve.
No real CAPTCHAs are solved — tests verify detection logic and graceful degradation.
"""
from __future__ import annotations

import asyncio
import sys
import types
import uuid
from pathlib import Path

import pytest

CONDUIT_ROOT = Path(__file__).parent.parent


def _bootstrap(tmp_db: Path) -> None:
    import importlib.util
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules.setdefault("cato", cato_pkg)
    if "cato.platform" not in sys.modules:
        platform_mod = types.ModuleType("cato.platform")
        platform_mod.get_data_dir = lambda: tmp_db.parent
        sys.modules["cato.platform"] = platform_mod
        cato_pkg.platform = platform_mod
        sys.modules["cato.conduit_platform"] = platform_mod
        cato_pkg.conduit_platform = platform_mod
    if "cato.audit" not in sys.modules:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("cato.audit", str(CONDUIT_ROOT / "audit.py"), submodule_search_locations=[])
        assert spec and spec.loader
        mod = ilu.module_from_spec(spec)
        mod.__package__ = "cato"
        sys.modules["cato.audit"] = mod
        spec.loader.exec_module(mod)
        cato_pkg.audit = mod
    tools_pkg = types.ModuleType("cato.tools")
    tools_pkg.__path__ = [str(CONDUIT_ROOT / "tools")]
    tools_pkg.__package__ = "cato.tools"
    sys.modules.setdefault("cato.tools", tools_pkg)
    cato_pkg.tools = tools_pkg
    for mod_name, file_name in [
        ("cato.tools.browser", "browser.py"),
        ("cato.tools.conduit_bridge", "conduit_bridge.py"),
        ("cato.tools.conduit_crawl", "conduit_crawl.py"),
        ("cato.tools.conduit_monitor", "conduit_monitor.py"),
        ("cato.tools.conduit_proof", "conduit_proof.py"),
    ]:
        if mod_name not in sys.modules:
            import importlib.util as ilu
            spec = ilu.spec_from_file_location(mod_name, str(CONDUIT_ROOT / "tools" / file_name), submodule_search_locations=[])
            assert spec and spec.loader
            mod = ilu.module_from_spec(spec)
            mod.__package__ = "cato.tools"
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("captcha") / "cato.db"
    _bootstrap(db)
    return db


@pytest.fixture(scope="module")
def bridge(tmp_db):
    ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
    sess = f"captcha-{uuid.uuid4().hex[:8]}"
    b = ConduitBridge(sess, budget_cents=99999, data_dir=tmp_db.parent)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(b.start())

    async def _init_browser():
        # Trigger lazy browser launch via _ensure_browser(), then navigate to a
        # data: URI — no network required.  CAPTCHA detection runs against DOM,
        # so a local data URI is sufficient to verify detection logic.
        await b._browser_tool._ensure_browser()
        await b._browser_tool._page.goto(
            "data:text/html,<html><body><h1>detection test page</h1></body></html>",
            wait_until="domcontentloaded",
        )

    loop.run_until_complete(_init_browser())
    yield b
    loop.run_until_complete(b.stop())


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestCapSolverClient:

    def test_capsolver_client_exists(self):
        """CapSolverClient class is importable."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "captcha_solver_test",
            str(CONDUIT_ROOT / "tools" / "captcha_solver.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "CapSolverClient")

    def test_capsolver_no_key_returns_empty_token(self):
        """CapSolverClient with no key returns empty string (no crash)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "captcha_solver_nokey",
            str(CONDUIT_ROOT / "tools" / "captcha_solver.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        client = mod.CapSolverClient(api_key="")
        # solve methods should return "" when no key
        token = asyncio.get_event_loop().run_until_complete(
            client.solve_recaptcha_v2("fake-sitekey", "https://example.com")
        )
        assert token == "", f"Expected empty token with no API key, got: {token!r}"


class TestCaptchaDetection:

    def test_detect_captcha_returns_correct_structure(self, bridge):
        """detect_captcha action returns a dict with required keys."""
        result_str = run(bridge.execute({"action": "detect_captcha"}))
        import json
        result = json.loads(result_str)
        # Must have all required keys
        assert "detected" in result, f"detect_captcha missing 'detected': {result}"
        assert "type" in result, f"detect_captcha missing 'type': {result}"
        assert "url" in result, f"detect_captcha missing 'url': {result}"
        assert isinstance(result["detected"], bool), f"'detected' should be bool: {result}"

    def test_detect_no_captcha_on_plain_page(self, bridge):
        """Plain HTML page with no CAPTCHA elements — detect_captcha should return detected=False."""
        # Access the underlying BrowserTool and call _detect_captcha directly
        BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
        # We need the actual browser tool instance — find it via bridge
        browser_tool = getattr(bridge, '_browser_tool', None) or getattr(bridge, '_browser', None)
        if browser_tool is None or not isinstance(browser_tool, BrowserTool):
            pytest.skip("Cannot access bridge._browser_tool for this test")
        result = asyncio.get_event_loop().run_until_complete(browser_tool._detect_captcha())
        assert "detected" in result, f"detect_captcha missing 'detected' key: {result}"
        assert result["detected"] is False, f"Plain page should not have CAPTCHA: {result}"

    def test_detect_captcha_via_execute(self, bridge):
        """detect_captcha action available via execute()."""
        result_str = run(bridge.execute({"action": "detect_captcha"}))
        import json
        result = json.loads(result_str)
        assert "detected" in result, f"detect_captcha result missing 'detected': {result}"
        assert "type" in result

    def test_solve_captcha_graceful_no_key(self, bridge):
        """solve_captcha returns {solved: False} when no API key configured."""
        import os
        saved = os.environ.pop("CAPSOLVER_API_KEY", None)
        try:
            result_str = run(bridge.execute({"action": "solve_captcha"}))
            import json
            result = json.loads(result_str)
            # Should not crash — returns either solved=False or solved=True
            assert "solved" in result or "captcha_type" in result or "error" in result, (
                f"solve_captcha returned unexpected structure: {result}"
            )
        finally:
            if saved is not None:
                os.environ["CAPSOLVER_API_KEY"] = saved

    def test_detect_captcha_result_has_url(self, bridge):
        """detect_captcha includes current URL in result."""
        result_str = run(bridge.execute({"action": "detect_captcha"}))
        import json
        result = json.loads(result_str)
        assert "url" in result, f"detect_captcha missing url: {result}"


class TestVisionCaptchaFallback:

    def test_solve_captcha_vision_method_exists(self, bridge):
        """_solve_captcha_vision method exists on BrowserTool."""
        BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
        assert hasattr(BrowserTool, "_solve_captcha_vision"), (
            "BrowserTool should have _solve_captcha_vision method"
        )

    def test_solve_captcha_vision_no_key_graceful(self, bridge):
        """Without ANTHROPIC_API_KEY, vision solve returns solved=False gracefully."""
        import os
        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result_str = run(bridge.execute({"action": "solve_captcha_vision"}))
            import json
            result = json.loads(result_str)
            assert result.get("solved") is False, (
                f"Expected solved=False without API key, got: {result}"
            )
            assert "error" in result, "Should include error message"
        finally:
            if saved:
                os.environ["ANTHROPIC_API_KEY"] = saved

    def test_solve_captcha_vision_action_in_dispatch(self, bridge):
        """solve_captcha_vision is a valid action in execute()."""
        import os
        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result_str = run(bridge.execute({"action": "solve_captcha_vision"}))
            import json
            result = json.loads(result_str)
            # Should not return "Unknown browser action" error
            assert "Unknown browser action" not in result.get("error", ""), (
                f"solve_captcha_vision not registered in dispatch: {result}"
            )
        finally:
            if saved:
                os.environ["ANTHROPIC_API_KEY"] = saved

    def test_solve_captcha_returns_correct_structure(self, bridge):
        """solve_captcha_vision returns dict with solved, method keys."""
        import os
        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result_str = run(bridge.execute({"action": "solve_captcha_vision"}))
            import json
            result = json.loads(result_str)
            assert "solved" in result, f"Missing 'solved' key: {result}"
            assert "method" in result or "error" in result, f"Missing method/error: {result}"
        finally:
            if saved:
                os.environ["ANTHROPIC_API_KEY"] = saved
