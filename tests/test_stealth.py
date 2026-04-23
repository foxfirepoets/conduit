"""
tests/test_stealth.py

Live browser tests for stealth hardening: launch flags and init script patches.
Tests run against a real Patchright browser.
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
        spec = importlib.util.spec_from_file_location(
            "cato.audit", str(CONDUIT_ROOT / "audit.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
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
            spec = importlib.util.spec_from_file_location(
                mod_name, str(CONDUIT_ROOT / "tools" / file_name),
                submodule_search_locations=[],
            )
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            mod.__package__ = "cato.tools"
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)


@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("stealth") / "cato.db"
    _bootstrap(db)
    return db


@pytest.fixture(scope="module")
def bridge(tmp_db):
    ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
    sess = f"stealth-{uuid.uuid4().hex[:8]}"
    b = ConduitBridge(sess, budget_cents=99999, data_dir=tmp_db.parent)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(b.start())

    async def _init_browser():
        # Trigger lazy browser launch via _ensure_browser(), then navigate to a
        # data: URI — no network required.  Stealth JS is injected post-load via
        # the page "load" event handler registered in _ensure_browser.  We use
        # wait_until="load" so Playwright waits for the load event to fire (which
        # triggers the async stealth inject), then sleep briefly to let the
        # inject coroutine complete before tests begin.
        await b._browser_tool._ensure_browser()
        await b._browser_tool._page.goto(
            "data:text/html,<html><body><h1>stealth test</h1></body></html>",
            wait_until="load",
        )
        # Flush pending async tasks (stealth inject scheduled via ensure_future)
        import asyncio as _asyncio
        await _asyncio.sleep(0.1)

    loop.run_until_complete(_init_browser())
    yield b
    loop.run_until_complete(b.stop())


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestStealthFlags:

    def test_webdriver_flag_is_undefined(self, bridge):
        result = run(bridge.eval("typeof navigator.webdriver"))
        assert result.get("success") is True
        assert result.get("result") == "undefined", (
            f"navigator.webdriver should be undefined, got: {result.get('result')!r}"
        )

    def test_plugins_has_entries(self, bridge):
        result = run(bridge.eval("navigator.plugins.length"))
        assert result.get("success") is True
        count = result.get("result", 0)
        assert count >= 2, f"Expected >= 2 plugins, got {count}"

    def test_languages_non_empty(self, bridge):
        result = run(bridge.eval("navigator.languages.length"))
        assert result.get("success") is True
        assert result.get("result", 0) >= 1, "navigator.languages should be non-empty"

    def test_chrome_object_exists(self, bridge):
        result = run(bridge.eval("typeof window.chrome"))
        assert result.get("success") is True
        assert result.get("result") == "object", (
            f"window.chrome should be object, got: {result.get('result')!r}"
        )

    def test_user_agent_is_chrome(self, bridge):
        result = run(bridge.eval("navigator.userAgent"))
        assert result.get("success") is True
        ua = result.get("result", "")
        assert "Chrome" in ua, f"User agent should contain Chrome: {ua!r}"
        assert "HeadlessChrome" not in ua, f"User agent should not reveal headless: {ua!r}"


class TestFingerprintVariance:

    def test_fingerprint_profile_is_generated(self, bridge):
        """Bridge should have a fingerprint profile after start."""
        browser_tool = bridge._browser_tool  # access the underlying BrowserTool
        assert hasattr(browser_tool, '_fingerprint'), "BrowserTool should have _fingerprint attribute"

    def test_two_sessions_may_have_different_fingerprints(self, tmp_db):
        """Two independently created BrowserTools have different fingerprints."""
        BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
        profiles = set()
        for _ in range(10):
            fp = BrowserTool._generate_fingerprint_profile()
            profiles.add((fp.viewport_w, fp.viewport_h, fp.user_agent, fp.timezone))
        # With 10 samples from varied pools, we expect at least 2 unique profiles
        assert len(profiles) >= 2, f"Expected fingerprint variance, got only {len(profiles)} unique profiles"

    def test_fingerprint_profile_has_valid_viewport(self, bridge):
        BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
        fp = BrowserTool._generate_fingerprint_profile()
        assert fp.viewport_w >= 1280, f"viewport_w too small: {fp.viewport_w}"
        assert fp.viewport_h >= 768, f"viewport_h too small: {fp.viewport_h}"

    def test_fingerprint_user_agent_is_chrome(self, bridge):
        BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
        fp = BrowserTool._generate_fingerprint_profile()
        assert "Chrome" in fp.user_agent, f"UA should contain Chrome: {fp.user_agent!r}"

    def test_screen_color_depth_nonzero(self, bridge):
        result = run(bridge.eval("screen.colorDepth"))
        assert result.get("success") is True
        assert result.get("result", 0) >= 24, "screen.colorDepth should be >= 24"


class TestProxySupport:

    def test_proxy_config_none_when_not_configured(self):
        """_load_proxy_config() returns None when env vars not set."""
        import os
        BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
        # Ensure env not set
        for k in ("CONDUIT_PROXY_HOST", "CONDUIT_PROXY_PORT", "CONDUIT_PROXY_USER", "CONDUIT_PROXY_PASS"):
            os.environ.pop(k, None)
        cfg = BrowserTool._load_proxy_config()
        assert cfg is None, f"Expected None when no proxy env vars, got: {cfg}"

    def test_proxy_config_loads_from_env(self):
        """_load_proxy_config() returns ProxyConfig when env vars are set."""
        import os
        BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
        os.environ["CONDUIT_PROXY_HOST"] = "proxy.example.com"
        os.environ["CONDUIT_PROXY_PORT"] = "3128"
        os.environ["CONDUIT_PROXY_USER"] = "user1"
        os.environ["CONDUIT_PROXY_PROTOCOL"] = "socks5"
        try:
            cfg = BrowserTool._load_proxy_config()
            assert cfg is not None
            assert cfg.host == "proxy.example.com"
            assert cfg.port == 3128
            assert cfg.username == "user1"
            assert cfg.protocol == "socks5"
            assert "socks5://proxy.example.com:3128" == cfg.server_url
        finally:
            for k in ("CONDUIT_PROXY_HOST", "CONDUIT_PROXY_PORT", "CONDUIT_PROXY_USER", "CONDUIT_PROXY_PROTOCOL"):
                os.environ.pop(k, None)

    def test_rotate_proxy_fails_gracefully_without_list(self, bridge):
        import os
        import json
        os.environ.pop("CONDUIT_PROXY_LIST", None)
        result_str = run(bridge.execute({"action": "rotate_proxy"}))
        result = json.loads(result_str)
        assert result.get("success") is False, f"Should fail gracefully without proxy list: {result}"
        assert "error" in result

    def test_proxy_config_dataclass_server_url(self):
        """ProxyConfig.server_url returns correct format."""
        ProxyConfig = sys.modules["cato.tools.browser"].ProxyConfig
        cfg = ProxyConfig(host="10.0.0.1", port=9050, protocol="socks5")
        assert cfg.server_url == "socks5://10.0.0.1:9050"


class TestCanvasWebGLNoise:

    def test_noise_seed_set_on_browser_tool(self, bridge):
        """BrowserTool has _noise_seed attribute after initialization."""
        BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
        # Get the browser tool from bridge
        browser_tool = None
        for attr in ('_browser_tool', '_browser', 'browser_tool'):
            obj = getattr(bridge, attr, None)
            if obj is not None and isinstance(obj, BrowserTool):
                browser_tool = obj
                break
        if browser_tool is None:
            # Try to find it differently
            bt = getattr(bridge, '_browser_tool', getattr(bridge, '_bt', None))
            if bt is None:
                pytest.skip("Cannot access underlying BrowserTool instance")
        tool = browser_tool
        assert hasattr(tool, '_noise_seed'), "BrowserTool should have _noise_seed"
        assert isinstance(tool._noise_seed, int), "_noise_seed should be int"
        assert 1 <= tool._noise_seed <= 99999, f"_noise_seed out of range: {tool._noise_seed}"

    def test_noise_seed_is_randomized(self):
        """Two BrowserTool instances have different noise seeds."""
        BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
        seeds = set()
        for _ in range(5):
            bt = BrowserTool()
            seeds.add(bt._noise_seed)
        assert len(seeds) >= 2, f"Expected varied noise seeds, got: {seeds}"

    def test_webgl_vendor_not_default(self, bridge):
        """WebGL vendor is overridden to a realistic value."""
        result = run(bridge.eval("""
            (() => {
                try {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (!gl) return 'no_webgl';
                    const ext = gl.getExtension('WEBGL_debug_renderer_info');
                    if (!ext) return 'no_ext';
                    return gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
                } catch(e) { return 'error: ' + e.message; }
            })()
        """))
        assert result.get("success") is True
        vendor = result.get("result", "")
        # If WebGL is available, vendor should be from our override pool
        if vendor not in ("no_webgl", "no_ext", "") and not str(vendor).startswith("error"):
            known_vendors = ["Intel Inc.", "NVIDIA Corporation", "AMD", "Google Inc. (Intel)"]
            assert any(v in str(vendor) for v in known_vendors), (
                f"WebGL vendor should be from override pool: {vendor!r}"
            )

    def test_canvas_to_data_url_works(self, bridge):
        """Canvas toDataURL still works after noise injection (doesn't break)."""
        result = run(bridge.eval("""
            (() => {
                const canvas = document.createElement('canvas');
                canvas.width = 10; canvas.height = 10;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = 'red';
                ctx.fillRect(0, 0, 10, 10);
                const url = canvas.toDataURL();
                return url.startsWith('data:image/png');
            })()
        """))
        assert result.get("success") is True
        assert result.get("result") is True, "toDataURL should still return valid data URL"
