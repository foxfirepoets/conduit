"""
live_audit_v2.py — Kraken Reality Audit (DNS-bypass, fresh profile per run)

Directly drives Patchright with a temp profile and host-resolver-rules,
then exercises ConduitBridge over that browser instance to test real functionality.

Run: python scripts/live_audit_v2.py 2>&1
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import socket
import sys
import tempfile
import time
import types
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(r"C:\Users\Administrator\Desktop\Conduit")


def make_tmp():
    td = tempfile.mkdtemp(prefix="kraken_audit_")
    p = Path(td)
    (p / "workspace" / "screenshots").mkdir(parents=True, exist_ok=True)
    (p / "workspace" / "pdfs").mkdir(parents=True, exist_ok=True)
    (p / "workspace" / ".conduit").mkdir(parents=True, exist_ok=True)
    (p / "sessions").mkdir(parents=True, exist_ok=True)
    return p


TMP_DIR = make_tmp()
TMP_DB = TMP_DIR / "cato.db"


def bootstrap(tmp_dir: Path):
    # Remove any stale entries from a previous run in this process
    for key in list(sys.modules.keys()):
        if key.startswith("cato"):
            del sys.modules[key]

    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules["cato"] = cato_pkg

    platform_mod = types.ModuleType("cato.platform")
    platform_mod.get_data_dir = lambda: tmp_dir
    sys.modules["cato.platform"] = platform_mod
    cato_pkg.platform = platform_mod

    for mod_name, file_path in [("cato.audit", CONDUIT_ROOT / "audit.py")]:
        spec = importlib.util.spec_from_file_location(mod_name, str(file_path), submodule_search_locations=[])
        m = importlib.util.module_from_spec(spec)
        m.__package__ = "cato"
        sys.modules[mod_name] = m
        spec.loader.exec_module(m)
    cato_pkg.audit = sys.modules["cato.audit"]

    tools_pkg = types.ModuleType("cato.tools")
    tools_pkg.__path__ = [str(CONDUIT_ROOT / "tools")]
    tools_pkg.__package__ = "cato.tools"
    sys.modules["cato.tools"] = tools_pkg
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
        spec = importlib.util.spec_from_file_location(
            mod_name, str(CONDUIT_ROOT / "tools" / file_name), submodule_search_locations=[]
        )
        m = importlib.util.module_from_spec(spec)
        m.__package__ = "cato.tools"
        sys.modules[mod_name] = m
        spec.loader.exec_module(m)
        setattr(tools_pkg, mod_name.split(".")[-1], m)


bootstrap(TMP_DIR)

# Update browser module paths to use our tmp dir
_browser_mod = sys.modules["cato.tools.browser"]
_browser_mod._CATO_DIR = TMP_DIR
_browser_mod._PROFILE_DIR = TMP_DIR / "browser_profile"
_browser_mod._SCREENSHOT_DIR = TMP_DIR / "workspace" / "screenshots"
_browser_mod._PDF_DIR = TMP_DIR / "workspace" / "pdfs"
_browser_mod._SESSION_DIR = TMP_DIR / "sessions"

ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
AuditLog = sys.modules["cato.audit"].AuditLog
BrowserTool = sys.modules["cato.tools.browser"].BrowserTool

# ---------------------------------------------------------------------------
# DNS resolution + browser launch patch
# ---------------------------------------------------------------------------

TARGETS = [
    "www.swarmsync.ai", "news.ycombinator.com", "www.google.com",
    "en.wikipedia.org", "github.com", "stackoverflow.com",
    "duckduckgo.com", "arxiv.org", "www.reddit.com", "twitter.com",
    "pubmed.ncbi.nlm.nih.gov", "scholar.google.com", "example.com",
]


def build_resolver_rules():
    rules = []
    for host in TARGETS:
        try:
            ip = socket.gethostbyname(host)
            rules.append(f"MAP {host} {ip}")
        except Exception as e:
            print(f"  DNS FAIL {host}: {e}", flush=True)
    return ", ".join(rules)


_RESOLVER_RULES = build_resolver_rules()
print(f"  Resolved {len(_RESOLVER_RULES.split(','))} hosts for Chromium bypass", flush=True)


# Patch BrowserTool._ensure_browser to use fresh profile + DNS rules
_orig_ensure = BrowserTool._ensure_browser.__func__ if hasattr(BrowserTool._ensure_browser, '__func__') else BrowserTool._ensure_browser


async def _patched_ensure_browser(self):
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

    profile_dir = TMP_DIR / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    proxy_dict = None
    if self._proxy_config:
        proxy_dict = {"server": self._proxy_config.server_url}
        if self._proxy_config.username:
            proxy_dict["username"] = self._proxy_config.username
        if self._proxy_config.password:
            proxy_dict["password"] = self._proxy_config.password

    args = [
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
    ]
    if _RESOLVER_RULES:
        args.append(f"--host-resolver-rules={_RESOLVER_RULES}")

    launch_kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": True,
        "args": args,
        "ignore_default_args": ["--enable-automation"],
        "user_agent": self._fingerprint.user_agent,
    }
    if proxy_dict:
        launch_kwargs["proxy"] = proxy_dict

    self._browser = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)

    noise_seed = self._noise_seed
    fp = self._fingerprint

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
        Object.defineProperty(screen, 'width', {{get: () => {fp.viewport_w}}});
        Object.defineProperty(screen, 'height', {{get: () => {fp.viewport_h}}});
        Object.defineProperty(screen, 'colorDepth', {{get: () => {fp.color_depth}}});
        Object.defineProperty(screen, 'pixelDepth', {{get: () => {fp.color_depth}}});
        (function() {{
            const seed = {noise_seed};
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
            const gpuRenderers = ['ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)', 'Intel Iris OpenGL Engine'];
            const vendor = gpuVendors[seed % gpuVendors.length];
            const renderer = gpuRenderers[seed % gpuRenderers.length];
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) return vendor;
                if (parameter === 37446) return renderer;
                return getParamOrig.apply(this, arguments);
            }};
            if (typeof WebGL2RenderingContext !== 'undefined') {{
                const orig2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) return vendor;
                    if (parameter === 37446) return renderer;
                    return orig2.apply(this, arguments);
                }};
            }}
        }})();
    """)

    self._page = await self._browser.new_page()
    await self._page.set_viewport_size({"width": fp.viewport_w, "height": fp.viewport_h})
    self._page.on("request", lambda req: self._network_log.append({
        "type": "request", "url": req.url, "method": req.method
    }))
    self._page.on("response", lambda res: self._network_log.append({
        "type": "response", "url": res.url, "status": res.status
    }))
    self._page.on("console", lambda msg: self._console_messages.append({
        "type": msg.type, "text": msg.text
    }))


# Apply patch
BrowserTool._ensure_browser = _patched_ensure_browser

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

results: dict[str, dict] = {}
start_time = time.time()
PASS, FAIL, PARTIAL = "PASS", "FAIL", "PARTIAL"


def record(cat, test, status, detail="", data=None):
    key = f"{cat}::{test}"
    results[key] = {"category": cat, "test": test, "status": status,
                    "detail": detail[:500], "data": data or {}}
    icon = {PASS: "[PASS]", FAIL: "[FAIL]", PARTIAL: "[PART]"}.get(status, "[ ?? ]")
    print(f"  {icon} {test}: {(detail or 'ok')[:120]}", flush=True)


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


def is_ok(r):
    return "error" not in r or not r["error"]


# ---------------------------------------------------------------------------
# TESTS
# ---------------------------------------------------------------------------

async def main():
    section("KRAKEN REALITY AUDIT — CONDUIT FULL LIVE TEST")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"  TMP_DIR: {TMP_DIR}", flush=True)

    sess = f"kraken-v2-{uuid.uuid4().hex[:8]}"
    bridge = ConduitBridge(sess, budget_cents=99999, data_dir=TMP_DIR)
    audit_log = AuditLog(db_path=TMP_DB)

    await bridge.start()
    print(f"  Bridge started. Session: {sess}", flush=True)

    try:
        # -------------------------------------------------------------------
        section("BASELINE: example.com")
        r = await nav(bridge, "https://example.com")
        if "error" in r:
            record("baseline", "navigate_example_com", FAIL, r["error"][:200])
            print("  ABORT: baseline failed — cannot test further browser actions", flush=True)
            return results
        else:
            record("baseline", "navigate_example_com", PASS, f"title={r.get('title','')}")

        ext_r = await ext(bridge)
        record("baseline", "extract_main",
               PASS if is_ok(ext_r) and ext_r.get("char_count", 0) > 0 else FAIL,
               f"chars={ext_r.get('char_count', 0)}, hash={ext_r.get('content_hash', '')}")

        ss_r = await ss(bridge)
        record("baseline", "screenshot",
               PASS if ss_r.get("success") and Path(ss_r.get("path", "x")).exists() else FAIL,
               ss_r.get("path", ss_r.get("error", ""))[:80])

        # -------------------------------------------------------------------
        section("SITE: swarmsync.ai")
        r = await nav(bridge, "https://www.swarmsync.ai", timeout=45)
        if "error" in r:
            record("swarmsync", "navigation", PARTIAL, r["error"][:200])
        else:
            title = r.get("title", "")
            record("swarmsync", "navigation", PASS, f"title={title[:60]}")

            ext_r = await ext(bridge)
            chars = ext_r.get("char_count", 0)
            ch = ext_r.get("content_hash", "")
            record("swarmsync", "extract_main",
                   PASS if is_ok(ext_r) and chars > 50 and ch else PARTIAL,
                   f"chars={chars}, hash={ch}")

            # Provenance mode
            prov_r = await ext(bridge, provenance_mode=True)
            if "error" in prov_r:
                record("swarmsync", "provenance_mode", FAIL, str(prov_r["error"]))
            else:
                tf = prov_r.get("text", {})
                has_prov = isinstance(tf, dict) and "value" in tf and "provenance" in tf
                if has_prov:
                    pd = tf["provenance"]
                    has_all_fields = all(k in pd for k in [
                        "session_pubkey", "url", "url_hash", "extracted_at", "audit_row_id"
                    ])
                    record("swarmsync", "provenance_mode",
                           PASS if has_all_fields else PARTIAL,
                           f"fields={list(pd.keys())}, pubkey={str(pd.get('session_pubkey',''))[:20]}...")
                else:
                    record("swarmsync", "provenance_mode", FAIL,
                           f"provenance wrapping absent. keys={list(prov_r.keys())[:6]}")

            ss_r = await ss(bridge)
            record("swarmsync", "screenshot",
                   PASS if ss_r.get("success") and Path(ss_r.get("path", "x")).exists() else FAIL,
                   ss_r.get("path", ss_r.get("error", ""))[:80])

        # -------------------------------------------------------------------
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
            record("hackernews", "extract_main",
                   PASS if is_ok(ext_r) and ext_r.get("char_count", 0) > 50 else PARTIAL,
                   f"chars={ext_r.get('char_count', 0)}")

            ss_r = await ss(bridge)
            record("hackernews", "screenshot",
                   PASS if ss_r.get("success") and Path(ss_r.get("path", "x")).exists() else FAIL,
                   ss_r.get("path", "")[-40:])

        # -------------------------------------------------------------------
        section("SITE: Google.com")
        r = await nav(bridge, "https://www.google.com")
        if "error" in r:
            record("google", "navigation", PARTIAL, r["error"][:100])
        else:
            record("google", "navigation", PASS, f"title={r.get('title','')[:60]}")
            ext_r = await ext(bridge)
            record("google", "extract_main",
                   PASS if is_ok(ext_r) and ext_r.get("char_count", 0) > 0 else PARTIAL,
                   f"chars={ext_r.get('char_count', 0)}")

        # -------------------------------------------------------------------
        section("SITE: Wikipedia")
        r = await nav(bridge, "https://en.wikipedia.org/wiki/Python_(programming_language)")
        if "error" in r:
            record("wikipedia", "navigation", PARTIAL, r["error"][:100])
        else:
            record("wikipedia", "navigation", PASS, f"title={r.get('title','')[:60]}")

            ext_r = await ext(bridge)
            text = ext_r.get("text", "")
            chars = ext_r.get("char_count", 0)
            has_python = "python" in text.lower()
            record("wikipedia", "extract_main",
                   PASS if has_python and chars > 100 else PARTIAL,
                   f"chars={chars}, hash={ext_r.get('content_hash','')}")

            # Provenance on Wikipedia
            prov_r = await ext(bridge, provenance_mode=True)
            tf = prov_r.get("text", {})
            has_prov = isinstance(tf, dict) and "provenance" in tf
            record("wikipedia", "provenance_mode",
                   PASS if has_prov else FAIL,
                   "wrapped correctly" if has_prov else "MISSING provenance wrap")

        # -------------------------------------------------------------------
        section("SITE: GitHub (fill + self-healing selectors)")
        r = await nav(bridge, "https://github.com")
        if "error" in r:
            record("github", "navigation", PARTIAL, r["error"][:100])
        else:
            record("github", "navigation", PASS, f"title={r.get('title','')[:60]}")

            # Fill search box
            fill_r = await bridge.fill("input[name='q']", "patchright playwright stealth")
            record("github", "fill_search_box",
                   PASS if fill_r.get("success") else PARTIAL,
                   str(fill_r.get("error", fill_r.get("typed", "ok")))[:80])

            # Self-healing: broken selector
            broken_r = await bridge.click(".nonexistent-class-zz99xyz")
            healing = broken_r.get("selector_healing_attempted", False)
            tiers = broken_r.get("tiers_tried", [])
            record("github", "self_healing_broken_css",
                   PASS if healing else PARTIAL,
                   f"healing={healing}, tiers={tiers}")

        # -------------------------------------------------------------------
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
                       PASS if is_ok(ext_r) and ext_r.get("char_count", 0) > 0 else PARTIAL,
                       f"chars={ext_r.get('char_count', 0)}")

        # -------------------------------------------------------------------
        section("SITE: DuckDuckGo")
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
                record("duckduckgo", "browser_search_ddg",
                       PASS if isinstance(r_list, list) else FAIL,
                       f"{len(r_list)} results (note: 0 is ok if DDG DOM changed)")
            except Exception as e:
                record("duckduckgo", "browser_search_ddg", PARTIAL, str(e)[:100])

        # -------------------------------------------------------------------
        section("SITE: arXiv")
        r = await nav(bridge, "https://arxiv.org/search/?query=attention+mechanism&searchtype=all")
        if "error" in r:
            record("arxiv", "navigation", PARTIAL, r["error"][:100])
        else:
            record("arxiv", "navigation", PASS, f"title={r.get('title','')[:60]}")
            ext_r = await ext(bridge)
            record("arxiv", "extract_main",
                   PASS if is_ok(ext_r) and ext_r.get("char_count", 0) > 0 else PARTIAL,
                   f"chars={ext_r.get('char_count', 0)}")

        # -------------------------------------------------------------------
        section("SITE: Reddit (stealth test)")
        r = await nav(bridge, "https://www.reddit.com", timeout=45)
        if "error" in r:
            record("reddit", "navigation", PARTIAL, r["error"][:100])
        else:
            title = r.get("title", "")
            url = r.get("url", "")
            blocked = any(kw in (title + url).lower() for kw in (
                "blocked", "captcha", "challenge", "robot", "verify"
            ))
            record("reddit", "navigation",
                   PARTIAL if blocked else PASS,
                   f"title={title[:60]}, bot_signals={blocked}")

            ext_r = await ext(bridge)
            chars = ext_r.get("char_count", 0)
            record("reddit", "extract_main_stealth_check",
                   PASS if chars > 100 else PARTIAL,
                   f"chars={chars} (low=bot-blocked)")

            ss_r = await ss(bridge)
            record("reddit", "screenshot",
                   PASS if ss_r.get("success") and Path(ss_r.get("path", "x")).exists() else FAIL,
                   ss_r.get("path", "")[-40:])

        # -------------------------------------------------------------------
        section("SITE: Twitter/X (stealth test)")
        r = await nav(bridge, "https://twitter.com", timeout=40)
        if "error" in r:
            record("twitter", "navigation", PARTIAL, r["error"][:100])
        else:
            title = r.get("title", "")
            blocked = any(kw in title.lower() for kw in ("blocked", "captcha", "challenge"))
            record("twitter", "navigation",
                   PARTIAL if blocked else PASS,
                   f"title={title[:60]}, bot_signals={blocked}")

            ss_r = await ss(bridge)
            record("twitter", "screenshot",
                   PASS if ss_r.get("success") and Path(ss_r.get("path", "x")).exists() else FAIL,
                   ss_r.get("path", "")[-40:])

        # -------------------------------------------------------------------
        section("SITE: PubMed")
        r = await nav(bridge, "https://pubmed.ncbi.nlm.nih.gov/?term=CRISPR+gene+editing")
        if "error" in r:
            record("pubmed", "navigation", PARTIAL, r["error"][:100])
        else:
            record("pubmed", "navigation", PASS, f"title={r.get('title','')[:60]}")
            ext_r = await ext(bridge)
            record("pubmed", "extract_main",
                   PASS if is_ok(ext_r) and ext_r.get("char_count", 0) > 0 else PARTIAL,
                   f"chars={ext_r.get('char_count', 0)}")

        # -------------------------------------------------------------------
        section("SITE: Google Scholar (bot-detection risk)")
        r = await nav(bridge, "https://scholar.google.com/scholar?q=attention+is+all+you+need")
        if "error" in r:
            record("scholar_google", "navigation", PARTIAL, r["error"][:100])
        else:
            title = r.get("title", "")
            blocked = any(kw in title.lower() for kw in ("sorry", "blocked", "captcha", "unusual"))
            record("scholar_google", "navigation",
                   PARTIAL if blocked else PASS,
                   f"title={title[:60]}, bot_detected={blocked}")

        # -------------------------------------------------------------------
        section("EVAL: JavaScript verbatim in audit chain")
        await nav(bridge, "https://example.com")
        js_code = "document.title + ' | chars:' + document.body.innerText.length"
        eval_r = await bridge.eval(js_code)
        if eval_r.get("success"):
            record("eval", "eval_executes_js", PASS,
                   f"result={str(eval_r.get('result', ''))[:80]}")
            code_hash = eval_r.get("code_hash", "")
            record("eval", "eval_code_hash_16chars",
                   PASS if code_hash and len(code_hash) == 16 else FAIL,
                   f"code_hash={code_hash!r}")
        else:
            record("eval", "eval_executes_js", FAIL,
                   str(eval_r.get("error", "unknown"))[:100])

        rows = audit_log.get_session_rows(sess)
        eval_rows = [r for r in rows if r["tool_name"] == "browser.eval"]
        if eval_rows:
            last = eval_rows[-1]
            inputs = json.loads(last["inputs_json"])
            stored = inputs.get("js_code", "")
            if stored == js_code:
                record("eval", "js_code_stored_verbatim_in_audit", PASS,
                       f"Stored: {stored[:60]!r}")
            else:
                record("eval", "js_code_stored_verbatim_in_audit", FAIL,
                       f"Expected: {js_code!r}\nGot: {stored!r}")
        else:
            record("eval", "js_code_stored_verbatim_in_audit", FAIL,
                   "No browser.eval rows in audit log")

        # -------------------------------------------------------------------
        section("SELF-HEALING SELECTORS (3-tier: CSS -> ARIA -> text)")
        await nav(bridge, "https://example.com")

        # Tier 1 success: working CSS selector
        click_r = await bridge.click("a")
        record("self_healing", "tier1_css_working_selector",
               PASS if click_r.get("success") else PARTIAL,
               str(click_r.get("error", "clicked"))[:80])

        await nav(bridge, "https://example.com")

        # Tier 1 failure -> healing should try tiers 2 and 3
        broken_r = await bridge.click(".nonexistent-ghost-selector-12345")
        healing = broken_r.get("selector_healing_attempted", False)
        tiers = broken_r.get("tiers_tried", [])
        if healing:
            record("self_healing", "three_tier_healing_exhausted",
                   PASS if set(tiers) == {"css", "aria", "text"} else PARTIAL,
                   f"Tiers tried: {tiers}")
        else:
            record("self_healing", "three_tier_healing_exhausted", PARTIAL,
                   f"healing_attempted not in response. Keys: {list(broken_r.keys())[:8]}")

        # -------------------------------------------------------------------
        section("AUDIT CHAIN INTEGRITY")
        rows = audit_log.get_session_rows(sess)
        n = len(rows)
        record("audit", "chain_has_rows", PASS if n > 5 else PARTIAL,
               f"{n} total audit rows")

        chain_ok = audit_log.verify_chain(sess)
        record("audit", "verify_chain", PASS if chain_ok else FAIL,
               f"verify_chain()={chain_ok}")

        bad_hash = [r for r in rows if len(r.get("row_hash", "")) != 64]
        record("audit", "all_rows_64char_hash",
               PASS if not bad_hash else FAIL,
               f"{len(bad_hash)} rows with bad hashes of {n} total")

        broken_links = []
        for i in range(1, len(rows)):
            if rows[i]["prev_hash"] != rows[i-1]["row_hash"]:
                broken_links.append(i)
        record("audit", "chain_prev_hash_linkage",
               PASS if not broken_links else FAIL,
               f"All {n} links valid" if not broken_links else f"Broken at pos: {broken_links[:5]}")

        tool_names = sorted(set(r["tool_name"] for r in rows))
        print(f"\n  Tools in audit ({len(tool_names)}): {tool_names}", flush=True)

        expected = {"browser.navigate", "browser.extract_main", "browser.screenshot",
                    "browser.scroll", "browser.eval", "browser.click"}
        missing = expected - set(tool_names)
        record("audit", "all_expected_tools_present",
               PASS if not missing else PARTIAL,
               f"Missing: {missing}" if missing else f"All {len(expected)} expected tools present")

        # Sensitive input redaction check
        nav_rows = [r for r in rows if r["tool_name"] == "browser.navigate"]
        if nav_rows:
            sample = json.loads(nav_rows[0]["inputs_json"])
            has_password = any("password" in str(v).lower() for v in sample.values())
            has_token = any("token" in str(v).lower() for v in sample.values())
            record("audit", "sensitive_inputs_not_leaked",
                   PASS if not has_password and not has_token else FAIL,
                   f"navigate inputs: {list(sample.keys())}")

        # -------------------------------------------------------------------
        section("PROOF BUNDLE EXPORT")
        proof_dir = TMP_DIR / "proofs"
        proof_dir.mkdir(parents=True, exist_ok=True)
        try:
            proof_r = bridge.export_proof(output_dir=str(proof_dir))
            if proof_r.get("success"):
                bundle_path = Path(proof_r["path"])
                action_count = proof_r.get("action_count", 0)
                record("proof", "export_proof_success", PASS,
                       f"bundle={bundle_path.name}, actions={action_count}")

                import tarfile
                with tarfile.open(str(bundle_path), "r:gz") as tar:
                    names = tar.getnames()

                for req_file in ["audit_log.jsonl", "verify.py", "manifest.json"]:
                    found = any(req_file in n for n in names)
                    record("proof", f"bundle_contains_{req_file}",
                           PASS if found else FAIL,
                           "found" if found else "MISSING")

                # Verify manifest
                with tarfile.open(str(bundle_path), "r:gz") as tar:
                    m = next(x for x in tar.getmembers() if "manifest.json" in x.name)
                    manifest = json.loads(tar.extractfile(m).read().decode())
                for k in ("session_id", "exported_at", "action_count", "chain_hash"):
                    record("proof", f"manifest_has_{k}",
                           PASS if k in manifest else FAIL,
                           f"value={str(manifest.get(k, 'MISSING'))[:40]}")

                # Run verify.py standalone
                import tarfile as _tf, subprocess, tempfile as _tmp
                with _tmp.TemporaryDirectory() as td2:
                    with _tf.open(str(bundle_path), "r:gz") as tar:
                        tar.extractall(td2)
                    vscripts = list(Path(td2).rglob("verify.py"))
                    if vscripts:
                        vp = vscripts[0]
                        proc = subprocess.run(
                            [sys.executable, str(vp)],
                            capture_output=True, text=True, timeout=30,
                            cwd=str(vp.parent)
                        )
                        out = proc.stdout + proc.stderr
                        record("proof", "verify_py_standalone_passes",
                               PASS if proc.returncode == 0 and "VERIFIED" in out else FAIL,
                               f"exit={proc.returncode}, VERIFIED={'yes' if 'VERIFIED' in out else 'no'}")
                    else:
                        record("proof", "verify_py_standalone_passes", FAIL, "verify.py not in bundle")
            else:
                record("proof", "export_proof_success", FAIL, str(proof_r.get("error", "")))
        except Exception as e:
            record("proof", "export_proof_success", FAIL, str(e)[:200])

    finally:
        await bridge.stop()
        print(f"\n  Bridge stopped. TMP: {TMP_DIR}", flush=True)

    # -----------------------------------------------------------------------
    section("FINAL SUMMARY")
    total = len(results)
    by_s: dict[str, int] = {}
    for r in results.values():
        s = r["status"]
        by_s[s] = by_s.get(s, 0) + 1

    print(f"  Total tests: {total}", flush=True)
    for status, count in sorted(by_s.items()):
        print(f"    {status}: {count}", flush=True)

    elapsed = time.time() - start_time
    print(f"  Elapsed: {elapsed:.1f}s", flush=True)

    cats: dict[str, dict] = {}
    for r in results.values():
        cat = r["category"]
        if cat not in cats:
            cats[cat] = {PASS: 0, FAIL: 0, PARTIAL: 0}
        cats[cat][r["status"]] = cats[cat].get(r["status"], 0) + 1

    print("\n  Per-category:", flush=True)
    for cat, counts in sorted(cats.items()):
        t = sum(counts.values())
        p = counts.get(PASS, 0)
        print(f"    {cat}: {p}/{t} PASS  "
              f"(FAIL={counts.get(FAIL,0)}, PARTIAL={counts.get(PARTIAL,0)})", flush=True)

    pass_n = by_s.get(PASS, 0)
    partial_n = by_s.get(PARTIAL, 0)
    score = ((pass_n + partial_n * 0.5) / total * 10) if total else 0
    print(f"\n  OVERALL SCORE: {score:.1f}/10", flush=True)

    return results, score


if __name__ == "__main__":
    all_results, score = asyncio.run(main())
    sys.exit(0 if score >= 5.0 else 1)
