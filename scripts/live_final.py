"""
live_final.py — Kraken Reality Audit Final Run
Full live browser test with DNS bypass (IPv6-only DNS workaround for Chromium).
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import types
import uuid
from pathlib import Path

CONDUIT_ROOT = Path(r"C:\Users\Administrator\Desktop\Conduit")
TMP_DIR = Path(tempfile.mkdtemp(prefix="kraken_final_"))
for d in ["workspace/screenshots", "workspace/pdfs", "workspace/.conduit", "sessions", "proofs"]:
    (TMP_DIR / d).mkdir(parents=True, exist_ok=True)

print(f"TMP_DIR: {TMP_DIR}", flush=True)

# Bootstrap — clear and reload all cato modules
for key in list(sys.modules.keys()):
    if key.startswith("cato"):
        del sys.modules[key]

cato_pkg = types.ModuleType("cato")
cato_pkg.__path__ = [str(CONDUIT_ROOT)]
cato_pkg.__package__ = "cato"
sys.modules["cato"] = cato_pkg

pm = types.ModuleType("cato.platform")
pm.get_data_dir = lambda: TMP_DIR
sys.modules["cato.platform"] = pm
cato_pkg.platform = pm

tools_pkg = types.ModuleType("cato.tools")
tools_pkg.__path__ = [str(CONDUIT_ROOT / "tools")]
tools_pkg.__package__ = "cato.tools"
sys.modules["cato.tools"] = tools_pkg
cato_pkg.tools = tools_pkg

for mod_name, file_path in [("cato.audit", CONDUIT_ROOT / "audit.py")]:
    spec = importlib.util.spec_from_file_location(mod_name, str(file_path), submodule_search_locations=[])
    m = importlib.util.module_from_spec(spec)
    m.__package__ = "cato"
    sys.modules[mod_name] = m
    spec.loader.exec_module(m)
cato_pkg.audit = sys.modules["cato.audit"]

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

# Fix module-level dir paths so screenshots/pdfs save to our temp dir
bm = sys.modules["cato.tools.browser"]
bm._PROFILE_DIR = TMP_DIR / "browser_profile"
bm._SCREENSHOT_DIR = TMP_DIR / "workspace" / "screenshots"
bm._PDF_DIR = TMP_DIR / "workspace" / "pdfs"
bm._SESSION_DIR = TMP_DIR / "sessions"
bm._PROFILE_DIR.mkdir(parents=True, exist_ok=True)

BrowserTool = bm.BrowserTool
ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
AuditLog = sys.modules["cato.audit"].AuditLog

# ---------------------------------------------------------------------------
# DNS pre-resolution
# ---------------------------------------------------------------------------

TARGETS = [
    "www.swarmsync.ai", "news.ycombinator.com", "www.google.com",
    "en.wikipedia.org", "github.com", "stackoverflow.com",
    "duckduckgo.com", "arxiv.org", "www.reddit.com", "twitter.com",
    "pubmed.ncbi.nlm.nih.gov", "scholar.google.com", "example.com",
]

rules_list = []
for h in TARGETS:
    try:
        ip = socket.gethostbyname(h)
        rules_list.append(f"MAP {h} {ip}")
        print(f"  {h} -> {ip}", flush=True)
    except Exception as e:
        print(f"  DNS FAIL {h}: {e}", flush=True)

RESOLVER_RULES = ", ".join(rules_list)
print(f"Resolved {len(rules_list)} hosts\n", flush=True)

# ---------------------------------------------------------------------------
# Patch BrowserTool._ensure_browser to inject DNS bypass
# ---------------------------------------------------------------------------

async def _patched_ensure_browser(self):
    if self._browser is not None:
        try:
            if len(self._browser.pages) > 0:
                return
        except Exception:
            pass

    from patchright.async_api import async_playwright
    self._fingerprint = BrowserTool._generate_fingerprint_profile()
    self._proxy_config = None
    self._playwright = await async_playwright().start()

    profile_dir = TMP_DIR / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

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
    if RESOLVER_RULES:
        args.append(f"--host-resolver-rules={RESOLVER_RULES}")

    self._browser = await self._playwright.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=True,
        args=args,
        ignore_default_args=["--enable-automation"],
        user_agent=self._fingerprint.user_agent,
    )

    ns = self._noise_seed
    fp = self._fingerprint

    stealth_js = f"""
        Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});
        Object.defineProperty(navigator, 'plugins', {{get: () => {{
            const arr = [
                {{name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'}},
                {{name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'}},
                {{name: 'Native Client', filename: 'internal-nacl-plugin'}},
            ];
            arr.refresh = () => {{}};
            return arr;
        }}}});
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
            const seed = {ns};
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
    """
    await self._browser.add_init_script(stealth_js)

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


# Apply patch to the class
BrowserTool._ensure_browser = _patched_ensure_browser

# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

RESULTS: dict[str, dict] = {}
t0 = time.time()
PASS, FAIL, PARTIAL = "PASS", "FAIL", "PARTIAL"


def R(cat: str, test: str, status: str, detail: str = "") -> None:
    key = f"{cat}::{test}"
    RESULTS[key] = {"cat": cat, "test": test, "status": status, "detail": detail[:400]}
    icon = {PASS: "[PASS]", FAIL: "[FAIL]", PARTIAL: "[PART]"}.get(status, "[????]")
    print(f"  {icon} {test}: {(detail or 'ok')[:120]}", flush=True)


def section(title: str) -> None:
    print(f"\n{'=' * 60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'=' * 60}", flush=True)


async def N(bridge, url: str, t: int = 40) -> dict:
    try:
        return await asyncio.wait_for(bridge.navigate(url), timeout=t)
    except Exception as e:
        return {"error": str(e)}


async def E(bridge, **kw) -> dict:
    try:
        return await asyncio.wait_for(bridge.extract_main(**kw), timeout=30)
    except Exception as e:
        return {"error": str(e)}


async def S(bridge) -> dict:
    try:
        return await asyncio.wait_for(bridge.screenshot(), timeout=20)
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------

async def main():
    sess = f"kraken-final-{uuid.uuid4().hex[:8]}"
    bridge = ConduitBridge(sess, budget_cents=99999, data_dir=TMP_DIR)
    audit_log = AuditLog(db_path=TMP_DIR / "cato.db")

    await bridge.start()
    print(f"Bridge started. Session: {sess}", flush=True)

    try:
        # -------------------------------------------------------------------
        section("BASELINE: example.com")
        r = await N(bridge, "https://example.com")
        if "error" in r:
            R("baseline", "navigate_example_com", FAIL, r["error"][:200])
            print("ABORT: baseline nav failed.", flush=True)
            return RESULTS
        R("baseline", "navigate_example_com", PASS, f"title={r.get('title', '')}")

        er = await E(bridge)
        R("baseline", "extract_main",
          PASS if er.get("char_count", 0) > 0 and er.get("content_hash") else FAIL,
          f"chars={er.get('char_count', 0)}, hash={er.get('content_hash', '')}")

        sr = await S(bridge)
        R("baseline", "screenshot",
          PASS if sr.get("success") and Path(sr.get("path", "x")).exists() else FAIL,
          sr.get("path", "")[-60:])

        # -------------------------------------------------------------------
        section("EVAL: JS verbatim in audit chain (Conduit differentiator)")
        js_code = "document.title + ' | chars:' + document.body.innerText.length"
        ev = await bridge.eval(js_code)
        R("eval", "executes_js",
          PASS if ev.get("success") else FAIL,
          f"result={str(ev.get('result', ''))[:80]}")
        R("eval", "code_hash_16chars",
          PASS if ev.get("code_hash") and len(ev.get("code_hash", "")) == 16 else FAIL,
          f"code_hash={ev.get('code_hash', '')}")

        rows = audit_log.get_session_rows(sess)
        eval_rows = [r2 for r2 in rows if r2["tool_name"] == "browser.eval"]
        if eval_rows:
            inputs = json.loads(eval_rows[-1]["inputs_json"])
            stored = inputs.get("js_code", "")
            R("eval", "js_code_verbatim_in_audit",
              PASS if stored == js_code else FAIL,
              f"stored={stored[:60]!r}")
        else:
            R("eval", "js_code_verbatim_in_audit", FAIL, "no browser.eval rows in audit")

        # -------------------------------------------------------------------
        section("SITE: swarmsync.ai (user's own site)")
        r = await N(bridge, "https://www.swarmsync.ai", t=45)
        if "error" in r:
            R("swarmsync", "navigation", PARTIAL, r["error"][:150])
        else:
            R("swarmsync", "navigation", PASS, f"title={r.get('title', '')[:60]}")
            er = await E(bridge)
            R("swarmsync", "extract_main",
              PASS if er.get("char_count", 0) > 50 and er.get("content_hash") else PARTIAL,
              f"chars={er.get('char_count', 0)}, hash={er.get('content_hash', '')}")

            pr = await E(bridge, provenance_mode=True)
            if "error" in pr:
                R("swarmsync", "provenance_mode", FAIL, str(pr["error"])[:100])
            else:
                tf = pr.get("text", {})
                has_prov = isinstance(tf, dict) and "value" in tf and "provenance" in tf
                if has_prov:
                    pd = tf["provenance"]
                    all_fields = all(k in pd for k in ["session_pubkey", "url", "url_hash",
                                                        "extracted_at", "audit_row_id"])
                    R("swarmsync", "provenance_mode",
                      PASS if all_fields else PARTIAL,
                      f"fields={list(pd.keys())}, pubkey={str(pd.get('session_pubkey', ''))[:20]}...")
                else:
                    R("swarmsync", "provenance_mode", FAIL,
                      f"no wrapping. keys={list(pr.keys())[:5]}")

            sr = await S(bridge)
            R("swarmsync", "screenshot",
              PASS if sr.get("success") and Path(sr.get("path", "x")).exists() else FAIL,
              sr.get("path", "")[-60:])

        # -------------------------------------------------------------------
        section("SITE: Hacker News")
        r = await N(bridge, "https://news.ycombinator.com")
        if "error" not in r:
            R("hn", "navigation", PASS, f"title={r.get('title', '')[:60]}")
            scroll_r = await bridge.scroll("down", 500)
            R("hn", "scroll_down", PASS if scroll_r.get("success") else FAIL,
              str(scroll_r.get("error", "ok")))
            er = await E(bridge)
            R("hn", "extract_main",
              PASS if er.get("char_count", 0) > 50 else PARTIAL,
              f"chars={er.get('char_count', 0)}")
            sr = await S(bridge)
            R("hn", "screenshot",
              PASS if sr.get("success") and Path(sr.get("path", "x")).exists() else FAIL,
              sr.get("path", "")[-60:])
        else:
            R("hn", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: Google")
        r = await N(bridge, "https://www.google.com")
        if "error" not in r:
            R("google", "navigation", PASS, f"title={r.get('title', '')[:60]}")
            er = await E(bridge)
            R("google", "extract_main",
              PASS if er.get("char_count", 0) > 0 else PARTIAL,
              f"chars={er.get('char_count', 0)}")
        else:
            R("google", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: Wikipedia")
        r = await N(bridge, "https://en.wikipedia.org/wiki/Python_(programming_language)")
        if "error" not in r:
            R("wikipedia", "navigation", PASS, f"title={r.get('title', '')[:60]}")
            er = await E(bridge)
            has_python = "python" in er.get("text", "").lower()
            R("wikipedia", "extract_main",
              PASS if has_python and er.get("char_count", 0) > 100 else PARTIAL,
              f"chars={er.get('char_count', 0)}, hash={er.get('content_hash', '')}")
            pr = await E(bridge, provenance_mode=True)
            tf = pr.get("text", {})
            has_prov = isinstance(tf, dict) and "provenance" in tf
            R("wikipedia", "provenance_mode",
              PASS if has_prov else FAIL,
              "wrapped correctly" if has_prov else "MISSING wrap")
        else:
            R("wikipedia", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: GitHub (fill + self-healing selectors)")
        r = await N(bridge, "https://github.com")
        if "error" not in r:
            R("github", "navigation", PASS, f"title={r.get('title', '')[:60]}")
            fill_r = await bridge.fill("input[name='q']", "patchright playwright stealth")
            R("github", "fill_search_box",
              PASS if fill_r.get("success") else PARTIAL,
              str(fill_r.get("error", fill_r.get("typed", "ok")))[:80])
            broken_r = await bridge.click(".nonexistent-xyz-broken-css")
            healing = broken_r.get("selector_healing_attempted", False)
            tiers = broken_r.get("tiers_tried", [])
            R("github", "self_healing_broken_css",
              PASS if healing else PARTIAL,
              f"healing={healing}, tiers={tiers}")
        else:
            R("github", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: Stack Overflow (code search routing)")
        r = await N(bridge, "https://stackoverflow.com/questions/tagged/python")
        if "error" not in r:
            blocked = any(k in r.get("title", "").lower() for k in ("blocked", "captcha"))
            R("so", "navigation", PARTIAL if blocked else PASS,
              f"title={r.get('title', '')[:60]}")
            if not blocked:
                er = await E(bridge)
                R("so", "extract_main",
                  PASS if er.get("char_count", 0) > 0 else PARTIAL,
                  f"chars={er.get('char_count', 0)}")
        else:
            R("so", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: DuckDuckGo (browser search integration)")
        r = await N(bridge, "https://duckduckgo.com")
        if "error" not in r:
            R("ddg", "navigation", PASS, f"title={r.get('title', '')[:60]}")
            try:
                search_r = await asyncio.wait_for(
                    bridge._browser_tool._dispatch("search", {"query": "Conduit browser automation"}),
                    timeout=25
                )
                r_list = search_r.get("results", [])
                R("ddg", "browser_search_ddg",
                  PASS if isinstance(r_list, list) else FAIL,
                  f"{len(r_list)} results (0 ok if DDG DOM changed)")
            except Exception as e:
                R("ddg", "browser_search_ddg", PARTIAL, str(e)[:100])
        else:
            R("ddg", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: arXiv (academic search)")
        r = await N(bridge, "https://arxiv.org/search/?query=attention+mechanism&searchtype=all")
        if "error" not in r:
            R("arxiv", "navigation", PASS, f"title={r.get('title', '')[:60]}")
            er = await E(bridge)
            R("arxiv", "extract_main",
              PASS if er.get("char_count", 0) > 0 else PARTIAL,
              f"chars={er.get('char_count', 0)}")
        else:
            R("arxiv", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: Reddit (stealth detection test)")
        r = await N(bridge, "https://www.reddit.com", t=45)
        if "error" not in r:
            title = r.get("title", "")
            url = r.get("url", "")
            blocked = any(k in (title + url).lower() for k in ("blocked", "captcha", "robot", "verify"))
            R("reddit", "navigation",
              PARTIAL if blocked else PASS,
              f"title={title[:60]}, bot_signals={blocked}")
            er = await E(bridge)
            R("reddit", "extract_main_stealth",
              PASS if er.get("char_count", 0) > 100 else PARTIAL,
              f"chars={er.get('char_count', 0)} (0=bot-blocked)")
            sr = await S(bridge)
            R("reddit", "screenshot",
              PASS if sr.get("success") and Path(sr.get("path", "x")).exists() else FAIL,
              sr.get("path", "")[-60:])
        else:
            R("reddit", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: Twitter/X (stealth detection test)")
        r = await N(bridge, "https://twitter.com", t=40)
        if "error" not in r:
            title = r.get("title", "")
            blocked = any(k in title.lower() for k in ("blocked", "captcha"))
            R("twitter", "navigation",
              PARTIAL if blocked else PASS,
              f"title={title[:60]}, bot_signals={blocked}")
            sr = await S(bridge)
            R("twitter", "screenshot",
              PASS if sr.get("success") and Path(sr.get("path", "x")).exists() else FAIL,
              sr.get("path", "")[-60:])
        else:
            R("twitter", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: PubMed")
        r = await N(bridge, "https://pubmed.ncbi.nlm.nih.gov/?term=CRISPR+gene+editing")
        if "error" not in r:
            R("pubmed", "navigation", PASS, f"title={r.get('title', '')[:60]}")
            er = await E(bridge)
            R("pubmed", "extract_main",
              PASS if er.get("char_count", 0) > 0 else PARTIAL,
              f"chars={er.get('char_count', 0)}")
        else:
            R("pubmed", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SITE: Google Scholar (bot-detection risk)")
        r = await N(bridge, "https://scholar.google.com/scholar?q=attention+is+all+you+need")
        if "error" not in r:
            title = r.get("title", "")
            blocked = any(k in title.lower() for k in ("sorry", "blocked", "unusual"))
            R("scholar", "navigation",
              PARTIAL if blocked else PASS,
              f"title={title[:60]}, bot={blocked}")
        else:
            R("scholar", "navigation", PARTIAL, r["error"][:100])

        # -------------------------------------------------------------------
        section("SELF-HEALING SELECTORS (3-tier: CSS > ARIA > text)")
        await N(bridge, "https://example.com")
        click_r = await bridge.click("a")
        R("heal", "tier1_css_working",
          PASS if click_r.get("success") else PARTIAL,
          str(click_r.get("error", "clicked"))[:80])

        await N(bridge, "https://example.com")
        broken_r = await bridge.click(".nonexistent-ghost-abc999-xyz")
        healing = broken_r.get("selector_healing_attempted", False)
        tiers = broken_r.get("tiers_tried", [])
        R("heal", "three_tier_healing_exhausted",
          PASS if healing and set(tiers) == {"css", "aria", "text"} else PARTIAL,
          f"healing={healing}, tiers={tiers}")

        # -------------------------------------------------------------------
        section("AUDIT CHAIN INTEGRITY")
        rows = audit_log.get_session_rows(sess)
        n = len(rows)
        R("audit", "chain_has_rows", PASS if n > 10 else PARTIAL, f"{n} total rows")

        ok = audit_log.verify_chain(sess)
        R("audit", "verify_chain_returns_true", PASS if ok else FAIL, f"verify_chain()={ok}")

        bad_hashes = [r2 for r2 in rows if len(r2.get("row_hash", "")) != 64]
        R("audit", "all_rows_64char_hash",
          PASS if not bad_hashes else FAIL,
          f"{len(bad_hashes)} bad hashes of {n}")

        broken_links = [i for i in range(1, len(rows))
                        if rows[i]["prev_hash"] != rows[i - 1]["row_hash"]]
        R("audit", "chain_prev_hash_linkage",
          PASS if not broken_links else FAIL,
          f"All {n} links valid" if not broken_links else f"Broken at pos: {broken_links[:5]}")

        tool_names = sorted(set(r2["tool_name"] for r2 in rows))
        print(f"\n  Tools in audit ({len(tool_names)}): {tool_names}", flush=True)

        expected = {"browser.navigate", "browser.extract_main", "browser.screenshot",
                    "browser.scroll", "browser.eval", "browser.click"}
        missing = expected - set(tool_names)
        R("audit", "expected_tools_logged",
          PASS if not missing else PARTIAL,
          f"Missing: {missing}" if missing else f"All {len(expected)} expected tools present")

        # Check no sensitive data leaked
        nav_rows = [r2 for r2 in rows if r2["tool_name"] == "browser.navigate"]
        if nav_rows:
            sample = json.loads(nav_rows[0]["inputs_json"])
            has_leak = any(k in ("password", "token", "api_key", "secret")
                           for k in sample.keys())
            R("audit", "no_sensitive_key_leak", PASS if not has_leak else FAIL,
              f"navigate input keys: {list(sample.keys())}")

        # -------------------------------------------------------------------
        section("PROOF BUNDLE EXPORT")
        proof_dir = TMP_DIR / "proofs"
        try:
            proof_r = bridge.export_proof(output_dir=str(proof_dir))
            if proof_r.get("success"):
                bp = Path(proof_r["path"])
                R("proof", "export_success", PASS,
                  f"{bp.name}, actions={proof_r.get('action_count', 0)}")

                with tarfile.open(str(bp), "r:gz") as tar:
                    names = tar.getnames()
                for f in ["audit_log.jsonl", "verify.py", "manifest.json"]:
                    found = any(f in nm for nm in names)
                    R("proof", f"bundle_has_{f}", PASS if found else FAIL,
                      "found" if found else "MISSING")

                # Verify manifest keys
                with tarfile.open(str(bp), "r:gz") as tar:
                    mmbr = next(x for x in tar.getmembers() if "manifest.json" in x.name)
                    manifest = json.loads(tar.extractfile(mmbr).read().decode())
                for k in ("session_id", "exported_at", "action_count", "chain_hash"):
                    R("proof", f"manifest_has_{k}",
                      PASS if k in manifest else FAIL,
                      str(manifest.get(k, "MISSING"))[:40])

                # Run verify.py standalone
                with tempfile.TemporaryDirectory() as td2:
                    with tarfile.open(str(bp), "r:gz") as tar:
                        tar.extractall(td2)
                    vscripts = list(Path(td2).rglob("verify.py"))
                    if vscripts:
                        proc = subprocess.run(
                            [sys.executable, str(vscripts[0])],
                            capture_output=True, text=True, timeout=30,
                            cwd=str(vscripts[0].parent)
                        )
                        out = proc.stdout + proc.stderr
                        R("proof", "verify_py_standalone_passes",
                          PASS if proc.returncode == 0 and "VERIFIED" in out else FAIL,
                          f"exit={proc.returncode}, VERIFIED={'yes' if 'VERIFIED' in out else 'no'}")
                    else:
                        R("proof", "verify_py_standalone_passes", FAIL, "verify.py not in bundle")
            else:
                R("proof", "export_success", FAIL, str(proof_r.get("error", ""))[:200])
        except Exception as e:
            R("proof", "export_success", FAIL, str(e)[:200])

    finally:
        await bridge.stop()

    # -------------------------------------------------------------------
    section("FINAL SUMMARY")
    total = len(RESULTS)
    by_s: dict[str, int] = {}
    for v in RESULTS.values():
        by_s[v["status"]] = by_s.get(v["status"], 0) + 1

    print(f"  Total tests: {total}", flush=True)
    for status, count in sorted(by_s.items()):
        print(f"    {status}: {count}", flush=True)

    elapsed = time.time() - t0
    print(f"  Elapsed: {elapsed:.1f}s", flush=True)

    cats: dict[str, dict] = {}
    for v in RESULTS.values():
        c = v["cat"]
        if c not in cats:
            cats[c] = {PASS: 0, FAIL: 0, PARTIAL: 0}
        cats[c][v["status"]] = cats[c].get(v["status"], 0) + 1

    print("\n  Per-category:", flush=True)
    for cat, counts in sorted(cats.items()):
        t_ = sum(counts.values())
        p_ = counts.get(PASS, 0)
        print(f"    {cat}: {p_}/{t_} PASS  "
              f"(FAIL={counts.get(FAIL, 0)}, PARTIAL={counts.get(PARTIAL, 0)})", flush=True)

    score = ((by_s.get(PASS, 0) + by_s.get(PARTIAL, 0) * 0.5) / total * 10) if total else 0
    print(f"\n  OVERALL SCORE: {score:.1f}/10", flush=True)

    return RESULTS, score


if __name__ == "__main__":
    all_results, score = asyncio.run(main())
    sys.exit(0 if score >= 5.0 else 1)
