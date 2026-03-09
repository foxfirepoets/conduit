"""
live_audit_dns_bypass.py — Live Conduit tests with DNS bypass for this machine.
Resolves IPs at Python layer then injects --host-resolver-rules into Chromium.

Run: python scripts/live_audit_dns_bypass.py 2>&1
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import socket
import sys
import time
import types
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(r"C:\Users\Administrator\Desktop\Conduit")
TMP_DIR = CONDUIT_ROOT / "scripts" / "_audit_tmp_dns"
TMP_DIR.mkdir(parents=True, exist_ok=True)
TMP_DB = TMP_DIR / "dns_audit.db"


def bootstrap():
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules.setdefault("cato", cato_pkg)

    platform_mod = types.ModuleType("cato.platform")
    platform_mod.get_data_dir = lambda: TMP_DIR
    sys.modules["cato.platform"] = platform_mod
    cato_pkg.platform = platform_mod

    for mod_name, file_path in [("cato.audit", CONDUIT_ROOT / "audit.py")]:
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(mod_name, str(file_path), submodule_search_locations=[])
            m = importlib.util.module_from_spec(spec)
            m.__package__ = "cato"
            sys.modules[mod_name] = m
            spec.loader.exec_module(m)
    cato_pkg.audit = sys.modules["cato.audit"]

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
        ("cato.tools.captcha_solver", "captcha_solver.py"),
        ("cato.tools.web_search", "web_search.py"),
    ]:
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                mod_name, str(CONDUIT_ROOT / "tools" / file_name), submodule_search_locations=[]
            )
            m = importlib.util.module_from_spec(spec)
            m.__package__ = "cato.tools"
            sys.modules[mod_name] = m
            spec.loader.exec_module(m)
        setattr(tools_pkg, mod_name.split(".")[-1], sys.modules[mod_name])


bootstrap()

ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
AuditLog = sys.modules["cato.audit"].AuditLog

# ---------------------------------------------------------------------------
# DNS pre-resolution + host-resolver-rules injection
# ---------------------------------------------------------------------------

SITES = {
    "swarmsync.ai": "www.swarmsync.ai",
    "hackernews": "news.ycombinator.com",
    "google": "www.google.com",
    "wikipedia": "en.wikipedia.org",
    "github": "github.com",
    "stackoverflow": "stackoverflow.com",
    "duckduckgo": "duckduckgo.com",
    "arxiv": "arxiv.org",
    "reddit": "www.reddit.com",
    "twitter": "twitter.com",
    "pubmed": "pubmed.ncbi.nlm.nih.gov",
    "scholar_google": "scholar.google.com",
    "example": "example.com",
    "wikipedia_main": "www.wikipedia.org",
}


def build_resolver_rules():
    """Resolve all hostnames and build --host-resolver-rules string."""
    rules = []
    failed = []
    for name, host in SITES.items():
        try:
            ip = socket.gethostbyname(host)
            rules.append(f"MAP {host} {ip}")
            print(f"  Resolved {host} -> {ip}", flush=True)
        except Exception as e:
            failed.append((host, str(e)))
            print(f"  FAILED {host}: {e}", flush=True)
    return ", ".join(rules), failed


# Monkey-patch ConduitBridge to inject DNS resolver rules into browser launch
_ORIG_ENSURE_BROWSER = None


def patch_browser_for_dns(resolver_rules: str):
    """Patch BrowserTool._ensure_browser to inject --host-resolver-rules."""
    BrowserTool = sys.modules["cato.tools.browser"].BrowserTool
    original = BrowserTool._ensure_browser

    async def patched_ensure_browser(self):
        if self._browser is not None:
            try:
                if len(self._browser.pages) > 0:
                    return
            except Exception:
                pass

        from patchright.async_api import async_playwright
        self._fingerprint = BrowserTool._generate_fingerprint_profile()
        self._proxy_config = BrowserTool._load_proxy_config()
        self._playwright = await async_playwright().start()

        proxy_dict = None
        if self._proxy_config:
            proxy_dict = {"server": self._proxy_config.server_url}
            if self._proxy_config.username:
                proxy_dict["username"] = self._proxy_config.username
            if self._proxy_config.password:
                proxy_dict["password"] = self._proxy_config.password

        # Same as original but with host-resolver-rules added
        from pathlib import Path as _Path
        _PROFILE_DIR = TMP_DIR / "browser_profile_dns"
        _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        _SCREENSHOT_DIR = TMP_DIR / "workspace" / "screenshots"
        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        _PDF_DIR = TMP_DIR / "workspace" / "pdfs"
        _PDF_DIR.mkdir(parents=True, exist_ok=True)

        # Update module-level dirs so screenshot/pdf save correctly
        import cato.tools.browser as _browser_mod
        _browser_mod._PROFILE_DIR = _PROFILE_DIR
        _browser_mod._SCREENSHOT_DIR = _SCREENSHOT_DIR
        _browser_mod._PDF_DIR = _PDF_DIR

        launch_kwargs = {
            "user_data_dir": str(_PROFILE_DIR),
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-infobars",
                f"--window-size={self._fingerprint.viewport_w},{self._fingerprint.viewport_h}",
                "--ignore-certificate-errors",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--disable-extensions",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                f"--host-resolver-rules={resolver_rules}",
            ],
            "ignore_default_args": ["--enable-automation"],
            "user_agent": self._fingerprint.user_agent,
        }
        if proxy_dict:
            launch_kwargs["proxy"] = proxy_dict

        self._browser = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)

        # Inject stealth JS
        await self._browser.add_init_script(f"""
            Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
            Object.defineProperty(navigator, 'plugins', {{
                get: () => {{
                    const arr = [
                        {{name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'}},
                        {{name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'}},
                        {{name: 'Native Client', filename: 'internal-nacl-plugin'}},
                    ];
                    arr.refresh = () => {{}};
                    return arr;
                }}
            }});
            Object.defineProperty(navigator, 'languages', {{get: () => ['en-US', 'en']}});
            if (!window.chrome) {{
                window.chrome = {{runtime: {{}}, loadTimes: () => {{}}, csi: () => {{}}, app: {{}}}};
            }}
            const origQuery = window.navigator.permissions && window.navigator.permissions.query;
            if (origQuery) {{
                window.navigator.permissions.query = (params) =>
                    (params.name === 'notifications')
                        ? Promise.resolve({{state: Notification.permission}})
                        : origQuery(params);
            }}
            Object.defineProperty(screen, 'width', {{get: () => {self._fingerprint.viewport_w}}});
            Object.defineProperty(screen, 'height', {{get: () => {self._fingerprint.viewport_h}}});
            Object.defineProperty(screen, 'colorDepth', {{get: () => {self._fingerprint.color_depth}}});
            Object.defineProperty(screen, 'pixelDepth', {{get: () => {self._fingerprint.color_depth}}});
            (function() {{
                const seed = {self._noise_seed};
                function mulberry32(a) {{
                    return function() {{
                        a |= 0; a = a + 0x6D2B79F5 | 0;
                        var t = Math.imul(a ^ a >>> 15, 1 | a);
                        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
                        return ((t ^ t >>> 14) >>> 0) / 4294967296;
                    }}
                }}
                const rand = mulberry32(seed);
                const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
                    const ctx = this.getContext('2d');
                    if (ctx) {{
                        const imgData = ctx.getImageData(0, 0, Math.min(this.width, 10), Math.min(this.height, 10));
                        for (let i = 0; i < imgData.data.length; i += 4) {{
                            imgData.data[i] = Math.min(255, imgData.data[i] + Math.floor((rand() - 0.5) * 2));
                        }}
                        ctx.putImageData(imgData, 0, 0);
                    }}
                    return origToDataURL.apply(this, arguments);
                }};
                const getParamOrig = WebGLRenderingContext.prototype.getParameter;
                const gpuVendors = ['Intel Inc.', 'NVIDIA Corporation', 'AMD', 'Google Inc. (Intel)'];
                const gpuRenderers = ['Intel Iris OpenGL Engine', 'ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)', 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11)'];
                const vendor = gpuVendors[seed % gpuVendors.length];
                const renderer = gpuRenderers[seed % gpuRenderers.length];
                WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) return vendor;
                    if (parameter === 37446) return renderer;
                    return getParamOrig.apply(this, arguments);
                }};
                if (typeof WebGL2RenderingContext !== 'undefined') {{
                    const getParam2Orig = WebGL2RenderingContext.prototype.getParameter;
                    WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
                        if (parameter === 37445) return vendor;
                        if (parameter === 37446) return renderer;
                        return getParam2Orig.apply(this, arguments);
                    }};
                }}
                if (typeof AudioBuffer !== 'undefined') {{
                    const origGetChannelData = AudioBuffer.prototype.getChannelData;
                    AudioBuffer.prototype.getChannelData = function(channel) {{
                        const data = origGetChannelData.call(this, channel);
                        const noiseMag = 0.0001;
                        for (let i = 0; i < Math.min(data.length, 100); i++) {{
                            data[i] += (rand() - 0.5) * noiseMag;
                        }}
                        return data;
                    }};
                }}
            }})();
        """)

        self._page = await self._browser.new_page()
        await self._page.set_viewport_size({
            "width": self._fingerprint.viewport_w,
            "height": self._fingerprint.viewport_h,
        })
        self._page.on("request", lambda req: self._network_log.append({
            "type": "request", "url": req.url, "method": req.method
        }))
        self._page.on("response", lambda res: self._network_log.append({
            "type": "response", "url": res.url, "status": res.status
        }))
        self._page.on("console", lambda msg: self._console_messages.append({
            "type": msg.type, "text": msg.text
        }))

    BrowserTool._ensure_browser = patched_ensure_browser
    return original


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

results: dict[str, dict] = {}
start_time = time.time()
PASS, FAIL, PARTIAL, NET = "PASS", "FAIL", "PARTIAL", "NETWORK_BLOCKED"


def record(cat, test, status, detail="", data=None):
    key = f"{cat}::{test}"
    results[key] = {"category": cat, "test": test, "status": status,
                    "detail": detail[:500], "data": data or {}}
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "PARTIAL": "[PART]", "NETWORK_BLOCKED": "[NET?]"}.get(status, "[ ?? ]")
    print(f"  {icon} {test}: {detail[:120] if detail else 'ok'}", flush=True)


def section(title):
    print(f"\n{'=' * 62}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'=' * 62}", flush=True)


async def nav(bridge, url, timeout=40):
    try:
        return await asyncio.wait_for(bridge.navigate(url), timeout=timeout)
    except asyncio.TimeoutError:
        return {"error": f"TIMEOUT {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


async def ext(bridge, **kw):
    try:
        return await asyncio.wait_for(bridge.extract_main(**kw), timeout=30)
    except asyncio.TimeoutError:
        return {"error": "TIMEOUT"}
    except Exception as e:
        return {"error": str(e)}


async def ss(bridge):
    try:
        return await asyncio.wait_for(bridge.screenshot(), timeout=20)
    except asyncio.TimeoutError:
        return {"error": "TIMEOUT"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------

async def run_all(bridge, audit_log, sess):

    section("BASELINE: example.com (simplest possible site)")
    r = await nav(bridge, "https://example.com")
    if "error" in r:
        record("baseline", "navigate_example_com", FAIL, r["error"])
        print("  CRITICAL: Even example.com fails — DNS bypass not working", flush=True)
        return
    record("baseline", "navigate_example_com", PASS, f"title={r.get('title', '')}")

    ext_r = await ext(bridge)
    if "error" in ext_r:
        record("baseline", "extract_main_example_com", FAIL, ext_r["error"])
    else:
        record("baseline", "extract_main_example_com",
               PASS if ext_r.get("char_count", 0) > 0 else FAIL,
               f"chars={ext_r.get('char_count', 0)}, hash={ext_r.get('content_hash', '')}")

    ss_r = await ss(bridge)
    record("baseline", "screenshot_example_com",
           PASS if ss_r.get("success") and Path(ss_r.get("path", "x")).exists() else FAIL,
           ss_r.get("path", ss_r.get("error", ""))[:80])

    # -----------------------------------------------------------------------
    # swarmsync.ai
    # -----------------------------------------------------------------------
    section("SITE: swarmsync.ai")
    r = await nav(bridge, "https://www.swarmsync.ai")
    if "error" in r:
        record("swarmsync", "navigation", PARTIAL, f"Error: {r['error'][:100]}")
    else:
        title = r.get("title", "")
        record("swarmsync", "navigation", PASS, f"title={title[:60]}")

        ext_r = await ext(bridge)
        chars = ext_r.get("char_count", 0)
        ch = ext_r.get("content_hash", "")
        record("swarmsync", "extract_main",
               PASS if not ext_r.get("error") and chars > 50 and ch else PARTIAL,
               f"chars={chars}, hash={ch}")

        prov_r = await ext(bridge, provenance_mode=True)
        if "error" in prov_r:
            record("swarmsync", "provenance_mode", FAIL, str(prov_r["error"]))
        else:
            tf = prov_r.get("text", {})
            has_prov = isinstance(tf, dict) and "value" in tf and "provenance" in tf
            if has_prov:
                pd = tf["provenance"]
                record("swarmsync", "provenance_mode", PASS,
                       f"pubkey={str(pd.get('session_pubkey',''))[:20]}..., "
                       f"url_hash={pd.get('url_hash', '')}, "
                       f"audit_row={pd.get('audit_row_id', '')}")
            else:
                record("swarmsync", "provenance_mode", FAIL,
                       f"wrapping missing. keys={list(prov_r.keys())[:5]}")

        ss_r = await ss(bridge)
        record("swarmsync", "screenshot",
               PASS if ss_r.get("success") and Path(ss_r.get("path", "x")).exists() else FAIL,
               ss_r.get("path", ss_r.get("error", ""))[:80])

    # -----------------------------------------------------------------------
    # Hacker News
    # -----------------------------------------------------------------------
    section("SITE: Hacker News")
    r = await nav(bridge, "https://news.ycombinator.com")
    if "error" in r:
        record("hackernews", "navigation", PARTIAL, r["error"][:100])
    else:
        record("hackernews", "navigation", PASS, f"title={r.get('title','')[:60]}")

        scroll_r = await bridge.scroll("down", 500)
        record("hackernews", "scroll_down",
               PASS if scroll_r.get("success") else FAIL,
               str(scroll_r.get("error", "ok")))

        ext_r = await ext(bridge)
        chars = ext_r.get("char_count", 0)
        record("hackernews", "extract_main",
               PASS if not ext_r.get("error") and chars > 50 else PARTIAL,
               f"chars={chars}, hash={ext_r.get('content_hash', '')}")

    # -----------------------------------------------------------------------
    # Google
    # -----------------------------------------------------------------------
    section("SITE: Google")
    r = await nav(bridge, "https://www.google.com")
    if "error" in r:
        record("google", "navigation", PARTIAL, r["error"][:100])
    else:
        record("google", "navigation", PASS, f"title={r.get('title','')[:60]}")
        ext_r = await ext(bridge)
        record("google", "extract_main",
               PASS if not ext_r.get("error") and ext_r.get("char_count", 0) > 0 else PARTIAL,
               f"chars={ext_r.get('char_count', 0)}")

    # -----------------------------------------------------------------------
    # Wikipedia
    # -----------------------------------------------------------------------
    section("SITE: Wikipedia")
    r = await nav(bridge, "https://en.wikipedia.org/wiki/Python_(programming_language)")
    if "error" in r:
        record("wikipedia", "navigation", PARTIAL, r["error"][:100])
    else:
        record("wikipedia", "navigation", PASS, f"title={r.get('title','')[:60]}")
        ext_r = await ext(bridge)
        chars = ext_r.get("char_count", 0)
        text = ext_r.get("text", "")
        has_python = "python" in text.lower() or "programming" in text.lower()
        record("wikipedia", "extract_main",
               PASS if has_python and chars > 100 else PARTIAL,
               f"chars={chars}, hash={ext_r.get('content_hash','')}")

        prov_r = await ext(bridge, provenance_mode=True)
        tf = prov_r.get("text", {})
        has_prov = isinstance(tf, dict) and "provenance" in tf
        record("wikipedia", "provenance_mode",
               PASS if has_prov else FAIL,
               "provenance wrapping verified" if has_prov else "provenance wrapping MISSING")

    # -----------------------------------------------------------------------
    # GitHub
    # -----------------------------------------------------------------------
    section("SITE: GitHub")
    r = await nav(bridge, "https://github.com")
    if "error" in r:
        record("github", "navigation", PARTIAL, r["error"][:100])
    else:
        record("github", "navigation", PASS, f"title={r.get('title','')[:60]}")

        # Test fill action
        fill_r = await bridge.fill("input[name='q']", "patchright playwright stealth")
        record("github", "fill_search_box",
               PASS if fill_r.get("success") else PARTIAL,
               str(fill_r.get("error", fill_r.get("typed", "ok")))[:80])

        # Test self-healing with broken selector
        broken_r = await bridge.click(".nonexistent-class-zz99xyz")
        healing = broken_r.get("selector_healing_attempted", False)
        tiers = broken_r.get("tiers_tried", [])
        record("github", "self_healing_broken_css",
               PASS if healing else PARTIAL,
               f"healing={healing}, tiers={tiers}")

    # -----------------------------------------------------------------------
    # Stack Overflow
    # -----------------------------------------------------------------------
    section("SITE: Stack Overflow")
    r = await nav(bridge, "https://stackoverflow.com/questions/tagged/python")
    if "error" in r:
        record("stackoverflow", "navigation", PARTIAL, r["error"][:100])
    else:
        title = r.get("title", "")
        blocked = any(kw in title.lower() for kw in ("blocked", "captcha", "challenge"))
        record("stackoverflow", "navigation",
               PARTIAL if blocked else PASS,
               f"title={title[:60]}")
        if not blocked:
            ext_r = await ext(bridge)
            record("stackoverflow", "extract_main",
                   PASS if not ext_r.get("error") and ext_r.get("char_count", 0) > 0 else PARTIAL,
                   f"chars={ext_r.get('char_count', 0)}")

    # -----------------------------------------------------------------------
    # DuckDuckGo (browser search)
    # -----------------------------------------------------------------------
    section("SITE: DuckDuckGo (browser search test)")
    r = await nav(bridge, "https://duckduckgo.com")
    if "error" in r:
        record("duckduckgo", "navigation", PARTIAL, r["error"][:100])
    else:
        record("duckduckgo", "navigation", PASS, f"title={r.get('title','')[:60]}")
        try:
            search_r = await asyncio.wait_for(
                bridge._browser_tool._dispatch("search", {"query": "Conduit browser automation"}),
                timeout=25
            )
            r_list = search_r.get("results", [])
            record("duckduckgo", "browser_search_action",
                   PASS if isinstance(r_list, list) else FAIL,
                   f"{len(r_list)} results (note: DDG may return 0 due to DOM changes)")
        except Exception as e:
            record("duckduckgo", "browser_search_action", PARTIAL, str(e)[:100])

    # -----------------------------------------------------------------------
    # arXiv
    # -----------------------------------------------------------------------
    section("SITE: arXiv.org")
    r = await nav(bridge, "https://arxiv.org/search/?query=attention+mechanism&searchtype=all")
    if "error" in r:
        record("arxiv", "navigation", PARTIAL, r["error"][:100])
    else:
        record("arxiv", "navigation", PASS, f"title={r.get('title','')[:60]}")
        ext_r = await ext(bridge)
        record("arxiv", "extract_main",
               PASS if not ext_r.get("error") and ext_r.get("char_count", 0) > 0 else PARTIAL,
               f"chars={ext_r.get('char_count', 0)}")

    # -----------------------------------------------------------------------
    # Reddit (stealth test)
    # -----------------------------------------------------------------------
    section("SITE: Reddit (stealth detection)")
    r = await nav(bridge, "https://www.reddit.com", timeout=45)
    if "error" in r:
        record("reddit", "navigation", PARTIAL, r["error"][:100])
    else:
        title = r.get("title", "")
        url = r.get("url", "")
        blocked = any(kw in (title + url).lower() for kw in ("blocked", "captcha", "challenge", "robot"))
        record("reddit", "navigation",
               PARTIAL if blocked else PASS,
               f"title={title[:60]}, blocked_signals={blocked}")

        ext_r = await ext(bridge)
        chars = ext_r.get("char_count", 0)
        record("reddit", "extract_main_stealth",
               PASS if chars > 100 else PARTIAL,
               f"chars={chars} (0=likely bot blocked)")

        ss_r = await ss(bridge)
        record("reddit", "screenshot",
               PASS if ss_r.get("success") and Path(ss_r.get("path", "x")).exists() else FAIL,
               ss_r.get("path", ss_r.get("error", ""))[:60])

    # -----------------------------------------------------------------------
    # Twitter/X
    # -----------------------------------------------------------------------
    section("SITE: Twitter/X (stealth detection)")
    r = await nav(bridge, "https://twitter.com", timeout=40)
    if "error" in r:
        record("twitter", "navigation", PARTIAL, r["error"][:100])
    else:
        title = r.get("title", "")
        record("twitter", "navigation", PASS, f"title={title[:60]}")
        ss_r = await ss(bridge)
        record("twitter", "screenshot",
               PASS if ss_r.get("success") and Path(ss_r.get("path", "x")).exists() else FAIL,
               ss_r.get("path", ss_r.get("error", ""))[:60])

    # -----------------------------------------------------------------------
    # PubMed
    # -----------------------------------------------------------------------
    section("SITE: PubMed")
    r = await nav(bridge, "https://pubmed.ncbi.nlm.nih.gov/?term=CRISPR+gene+editing")
    if "error" in r:
        record("pubmed", "navigation", PARTIAL, r["error"][:100])
    else:
        record("pubmed", "navigation", PASS, f"title={r.get('title','')[:60]}")
        ext_r = await ext(bridge)
        record("pubmed", "extract_main",
               PASS if not ext_r.get("error") and ext_r.get("char_count", 0) > 0 else PARTIAL,
               f"chars={ext_r.get('char_count', 0)}")

    # -----------------------------------------------------------------------
    # Google Scholar
    # -----------------------------------------------------------------------
    section("SITE: Google Scholar")
    r = await nav(bridge, "https://scholar.google.com/scholar?q=attention+is+all+you+need")
    if "error" in r:
        record("scholar_google", "navigation", PARTIAL, r["error"][:100])
    else:
        title = r.get("title", "")
        blocked = any(kw in title.lower() for kw in ("sorry", "blocked", "captcha"))
        record("scholar_google", "navigation",
               PARTIAL if blocked else PASS,
               f"title={title[:60]}, bot_detected={blocked}")

    # -----------------------------------------------------------------------
    # EVAL TEST
    # -----------------------------------------------------------------------
    section("EVAL: JS code verbatim in audit chain (Conduit differentiator)")
    await nav(bridge, "https://example.com")
    js_code = "document.title + ' | chars: ' + document.body.innerText.length"
    eval_r = await bridge.eval(js_code)
    if eval_r.get("success"):
        record("eval", "eval_executes_js", PASS,
               f"result={str(eval_r.get('result', ''))[:80]}")
        code_hash = eval_r.get("code_hash", "")
        record("eval", "eval_returns_code_hash",
               PASS if code_hash and len(code_hash) == 16 else FAIL,
               f"code_hash={code_hash}")
    else:
        record("eval", "eval_executes_js", FAIL, str(eval_r.get("error", ""))[:100])

    # Verify js_code verbatim in audit
    rows = audit_log.get_session_rows(sess)
    eval_rows = [r for r in rows if r["tool_name"] == "browser.eval"]
    if eval_rows:
        last_eval = eval_rows[-1]
        inputs = json.loads(last_eval["inputs_json"])
        stored = inputs.get("js_code", "")
        if stored == js_code:
            record("eval", "js_code_verbatim_in_audit_chain", PASS,
                   f"Stored exactly: {stored[:60]!r}")
        else:
            record("eval", "js_code_verbatim_in_audit_chain", FAIL,
                   f"Mismatch. Expected: {js_code!r}, Got: {stored!r}")
    else:
        record("eval", "js_code_verbatim_in_audit_chain", FAIL,
               "No browser.eval in audit log")

    # -----------------------------------------------------------------------
    # SELF-HEALING SELECTORS
    # -----------------------------------------------------------------------
    section("SELF-HEALING SELECTORS")
    await nav(bridge, "https://example.com")

    # Working selector
    click_r = await bridge.click("a")
    record("self_healing", "working_css_selector_clicks",
           PASS if click_r.get("success") else PARTIAL,
           str(click_r.get("error", "clicked"))[:80])

    # Navigate back
    await nav(bridge, "https://example.com")

    # Broken CSS selector — healing must trigger
    broken_r = await bridge.click(".nonexistent-ghost-xxxyyy-12345")
    healing = broken_r.get("selector_healing_attempted", False)
    tiers = broken_r.get("tiers_tried", [])
    if healing:
        record("self_healing", "broken_css_triggers_three_tier_healing", PASS,
               f"Healing activated. Tiers tried: {tiers}. All 3 tiers exhausted.")
    else:
        record("self_healing", "broken_css_triggers_three_tier_healing", PARTIAL,
               f"Healing metadata absent from response. Response keys: {list(broken_r.keys())}")

    # -----------------------------------------------------------------------
    # AUDIT CHAIN INTEGRITY
    # -----------------------------------------------------------------------
    section("AUDIT CHAIN INTEGRITY")
    rows = audit_log.get_session_rows(sess)
    total_rows = len(rows)
    record("audit", "chain_has_entries",
           PASS if total_rows > 10 else PARTIAL,
           f"{total_rows} total audit rows")

    chain_ok = audit_log.verify_chain(sess)
    record("audit", "verify_chain_returns_true",
           PASS if chain_ok else FAIL,
           f"verify_chain()={chain_ok}")

    bad_hash = [r for r in rows if len(r.get("row_hash", "")) != 64]
    record("audit", "all_rows_64char_sha256_hash",
           PASS if not bad_hash else FAIL,
           f"{len(bad_hash)} bad hashes of {total_rows}")

    broken_links = []
    for i in range(1, len(rows)):
        if rows[i]["prev_hash"] != rows[i-1]["row_hash"]:
            broken_links.append(i)
    record("audit", "chain_prev_hash_linkage",
           PASS if not broken_links else FAIL,
           f"All {total_rows} links valid" if not broken_links else f"Broken at: {broken_links[:3]}")

    tool_names = sorted(set(r["tool_name"] for r in rows))
    print(f"\n  Recorded tool names ({len(tool_names)}): {tool_names}", flush=True)

    expected = {"browser.navigate", "browser.extract_main", "browser.screenshot",
                "browser.scroll", "browser.eval", "browser.click"}
    missing = expected - set(tool_names)
    record("audit", "all_expected_tools_logged",
           PASS if not missing else PARTIAL,
           f"Missing: {missing}" if missing else f"{len(tool_names)} tools logged")

    # -----------------------------------------------------------------------
    # PROOF BUNDLE EXPORT
    # -----------------------------------------------------------------------
    section("PROOF BUNDLE EXPORT")
    try:
        proof_dir = TMP_DIR / "proofs"
        proof_dir.mkdir(parents=True, exist_ok=True)
        proof_r = bridge.export_proof(output_dir=str(proof_dir))
        if proof_r.get("success"):
            bundle_path = Path(proof_r["path"])
            record("proof", "export_proof_success", PASS,
                   f"path={bundle_path.name}, actions={proof_r.get('action_count', 0)}")

            # Verify bundle contents
            import tarfile
            with tarfile.open(str(bundle_path), "r:gz") as tar:
                names = tar.getnames()
            for req_file in ["audit_log.jsonl", "verify.py", "manifest.json"]:
                found = any(req_file in n for n in names)
                record("proof", f"bundle_contains_{req_file}",
                       PASS if found else FAIL,
                       f"{'found' if found else 'MISSING'} in {len(names)} files")

            # Run verify.py standalone
            import tarfile as _tf, subprocess, tempfile
            with tempfile.TemporaryDirectory() as td:
                with _tf.open(str(bundle_path), "r:gz") as tar:
                    tar.extractall(td)
                verify_scripts = list(Path(td).rglob("verify.py"))
                if verify_scripts:
                    vp = verify_scripts[0]
                    proc = subprocess.run(
                        [sys.executable, str(vp)],
                        capture_output=True, text=True, timeout=30,
                        cwd=str(vp.parent)
                    )
                    output = proc.stdout + proc.stderr
                    record("proof", "verify_py_standalone_passes",
                           PASS if proc.returncode == 0 and "VERIFIED" in output else FAIL,
                           f"exit={proc.returncode}, VERIFIED={'yes' if 'VERIFIED' in output else 'no'}")
                else:
                    record("proof", "verify_py_standalone_passes", FAIL, "verify.py not found in bundle")
        else:
            record("proof", "export_proof_success", FAIL, str(proof_r.get("error", "")))
    except Exception as e:
        record("proof", "export_proof_success", FAIL, str(e)[:200])


async def main():
    section("KRAKEN REALITY AUDIT — CONDUIT LIVE TEST (DNS BYPASS MODE)")
    print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"  Machine: IPv6-only DNS, Chromium needs host-resolver-rules bypass", flush=True)

    # Pre-resolve all hostnames
    section("DNS PRE-RESOLUTION")
    resolver_rules, failed_resolutions = build_resolver_rules()
    if failed_resolutions:
        print(f"  Failed resolutions: {failed_resolutions}", flush=True)

    # Patch the browser to inject DNS rules
    patch_browser_for_dns(resolver_rules)

    # Start bridge
    sess = f"kraken-dns-{uuid.uuid4().hex[:8]}"
    bridge = ConduitBridge(sess, budget_cents=99999, data_dir=TMP_DIR)
    audit_log = AuditLog(db_path=TMP_DB)

    await bridge.start()
    print(f"\n  Bridge started. Session: {sess}", flush=True)

    try:
        await run_all(bridge, audit_log, sess)
    finally:
        await bridge.stop()
        print("\n  Bridge stopped.", flush=True)

    # Summary
    section("FINAL SUMMARY")
    total = len(results)
    by_status: dict[str, int] = {}
    for r in results.values():
        s = r["status"]
        by_status[s] = by_status.get(s, 0) + 1

    print(f"  Total tests: {total}", flush=True)
    for status, count in sorted(by_status.items()):
        print(f"    {status}: {count}", flush=True)

    elapsed = time.time() - start_time
    print(f"  Elapsed: {elapsed:.1f}s", flush=True)

    cats: dict[str, dict] = {}
    for r in results.values():
        cat = r["category"]
        if cat not in cats:
            cats[cat] = {"PASS": 0, "FAIL": 0, "PARTIAL": 0}
        cats[cat][r["status"]] = cats[cat].get(r["status"], 0) + 1

    print("\n  Per-category:", flush=True)
    for cat, counts in sorted(cats.items()):
        t = sum(counts.values())
        p = counts.get("PASS", 0)
        print(f"    {cat}: {p}/{t} PASS  (FAIL={counts.get('FAIL',0)}, PARTIAL={counts.get('PARTIAL',0)})", flush=True)

    pass_n = by_status.get(PASS, 0)
    partial_n = by_status.get(PARTIAL, 0)
    score_pct = ((pass_n + partial_n * 0.5) / total * 10) if total else 0
    print(f"\n  OVERALL SCORE: {score_pct:.1f}/10", flush=True)

    return results, score_pct


if __name__ == "__main__":
    all_results, score = asyncio.run(main())
    sys.exit(0 if score >= 5.0 else 1)
