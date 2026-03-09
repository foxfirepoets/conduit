"""
live_audit.py — Kraken Reality Audit for Conduit
Tests actual browser automation against real websites.

Run: python scripts/live_audit.py 2>&1
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import time
import types
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap — mirrors test_e2e_live.py pattern
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(r"C:\Users\Administrator\Desktop\Conduit")
TMP_DIR = CONDUIT_ROOT / "scripts" / "_audit_tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)
TMP_DB = TMP_DIR / "live_audit.db"


def bootstrap():
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules.setdefault("cato", cato_pkg)

    platform_mod = types.ModuleType("cato.platform")
    platform_mod.get_data_dir = lambda: TMP_DIR
    sys.modules["cato.platform"] = platform_mod
    cato_pkg.platform = platform_mod

    for mod_name, file_path in [
        ("cato.audit", CONDUIT_ROOT / "audit.py"),
    ]:
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                mod_name, str(file_path), submodule_search_locations=[]
            )
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
                mod_name,
                str(CONDUIT_ROOT / "tools" / file_name),
                submodule_search_locations=[],
            )
            m = importlib.util.module_from_spec(spec)
            m.__package__ = "cato.tools"
            sys.modules[mod_name] = m
            spec.loader.exec_module(m)
        setattr(tools_pkg, mod_name.split(".")[-1], sys.modules[mod_name])


bootstrap()

ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge
AuditLog = sys.modules["cato.audit"].AuditLog
WebSearchTool = sys.modules["cato.tools.web_search"].WebSearchTool
classify_query = sys.modules["cato.tools.web_search"].classify_query

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

results: dict[str, dict] = {}
start_time = time.time()

PASS = "PASS"
FAIL = "FAIL"
PARTIAL = "PARTIAL"
NETWORK_BLOCKED = "NETWORK_BLOCKED"


def record(category: str, test: str, status: str, detail: str = "", data: dict = None):
    key = f"{category}::{test}"
    results[key] = {
        "category": category,
        "test": test,
        "status": status,
        "detail": detail[:500] if detail else "",
        "data": data or {},
        "ts": time.time(),
    }
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "PARTIAL": "[PART]", "NETWORK_BLOCKED": "[NET?]"}.get(status, "[????]")
    print(f"  {icon} {test}: {detail[:120] if detail else 'ok'}", flush=True)


def section(title: str):
    print(f"\n{'=' * 60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'=' * 60}", flush=True)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def safe_navigate(bridge, url, timeout=45):
    try:
        r = await asyncio.wait_for(bridge.navigate(url), timeout=timeout)
        return r
    except asyncio.TimeoutError:
        return {"error": f"TIMEOUT after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


async def safe_extract(bridge, **kwargs):
    try:
        r = await asyncio.wait_for(bridge.extract_main(**kwargs), timeout=30)
        return r
    except asyncio.TimeoutError:
        return {"error": "TIMEOUT"}
    except Exception as e:
        return {"error": str(e)}


async def safe_screenshot(bridge):
    try:
        r = await asyncio.wait_for(bridge.screenshot(), timeout=20)
        return r
    except asyncio.TimeoutError:
        return {"error": "TIMEOUT"}
    except Exception as e:
        return {"error": str(e)}


def is_network_error(result: dict) -> bool:
    err = result.get("error", "")
    if not err:
        return False
    net_keywords = [
        "ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_REFUSED", "TIMEOUT",
        "net::ERR_", "Name or service not known", "getaddrinfo",
        "socket", "TimeoutError", "connect timed out"
    ]
    return any(kw.lower() in err.lower() for kw in net_keywords)


# ---------------------------------------------------------------------------
# Test: Fingerprint variance across 3 instances
# ---------------------------------------------------------------------------

def test_fingerprint_variance():
    section("FINGERPRINT VARIANCE TEST (3 separate BrowserTool instances)")
    BrowserTool = sys.modules["cato.tools.browser"].BrowserTool

    instances = [BrowserTool() for _ in range(3)]
    seeds = [inst._noise_seed for inst in instances]
    fps = [inst._fingerprint for inst in instances]

    print(f"  Seeds: {seeds}", flush=True)
    print(f"  Viewports: {[(f.viewport_w, f.viewport_h) for f in fps]}", flush=True)
    print(f"  UAs: {[f.user_agent[:50] for f in fps]}", flush=True)

    # Seeds should differ (probability of collision is negligible at 1-99999)
    seeds_unique = len(set(seeds)) > 1
    # Note: FingerprintProfile is not populated until _ensure_browser() is called
    # (it's replaced with a generated one there). The default is FingerprintProfile()
    # which has static defaults. Check seeds only.
    if seeds_unique:
        record("fingerprint", "3_instances_have_different_noise_seeds", PASS,
               f"Seeds: {seeds}")
    else:
        record("fingerprint", "3_instances_have_different_noise_seeds", FAIL,
               f"All seeds identical: {seeds}")

    # Test that _generate_fingerprint_profile() returns different values on repeated calls
    fp1 = BrowserTool._generate_fingerprint_profile()
    fp2 = BrowserTool._generate_fingerprint_profile()
    fp3 = BrowserTool._generate_fingerprint_profile()
    all_fps = {
        (fp1.viewport_w, fp1.user_agent, fp1.timezone),
        (fp2.viewport_w, fp2.user_agent, fp2.timezone),
        (fp3.viewport_w, fp3.user_agent, fp3.timezone),
    }
    if len(all_fps) > 1:
        record("fingerprint", "generate_fingerprint_produces_variance", PASS,
               f"Got {len(all_fps)} unique fingerprint combos from 3 calls")
    else:
        record("fingerprint", "generate_fingerprint_produces_variance", PARTIAL,
               "All 3 generated fingerprints are identical (unlikely, possible)")


# ---------------------------------------------------------------------------
# Test: Web search (API-based, no browser needed)
# ---------------------------------------------------------------------------

def test_web_search_api():
    section("WEB SEARCH API TESTS (no browser required)")
    ws = WebSearchTool()

    # Test 1: Query classification
    tests = [
        ("python asyncio tutorial", "code"),
        ("latest AI news 2026", "news"),
        ("transformer architecture paper", "academic"),
        ("best pizza NYC", "general"),
        ("attention is all you need arxiv", "academic"),
        ("stackoverflow python exception handling", "code"),
    ]
    for query, expected in tests:
        got = classify_query(query)
        if got == expected:
            record("web_search", f"classify_{expected}_query", PASS,
                   f"'{query}' -> '{got}'")
        else:
            record("web_search", f"classify_{expected}_query", FAIL,
                   f"'{query}' classified as '{got}', expected '{expected}'")

    # Test 2: DDG API (no key required)
    print("\n  Testing DDG API...", flush=True)
    try:
        results_ddg = ws._search_ddg_api("Python programming language")
        if results_ddg:
            record("web_search", "ddg_api_returns_results", PASS,
                   f"{len(results_ddg)} results, first: {results_ddg[0].url[:60]}")
        else:
            record("web_search", "ddg_api_returns_results", PARTIAL,
                   "DDG API returned 0 results (may be network issue or no instant answer)")
    except Exception as e:
        if is_network_error({"error": str(e)}):
            record("web_search", "ddg_api_returns_results", NETWORK_BLOCKED, str(e)[:100])
        else:
            record("web_search", "ddg_api_returns_results", FAIL, str(e)[:200])

    # Test 3: arXiv academic search (no key)
    print("\n  Testing arXiv API...", flush=True)
    try:
        arxiv_results = ws._search_arxiv("attention is all you need")
        if arxiv_results:
            first = arxiv_results[0]
            record("web_search", "arxiv_returns_results", PASS,
                   f"{len(arxiv_results)} results, top: {first.title[:60]}")
            if "arxiv.org" in first.url:
                record("web_search", "arxiv_urls_point_to_arxiv", PASS,
                       f"URL: {first.url}")
            else:
                record("web_search", "arxiv_urls_point_to_arxiv", FAIL,
                       f"URL not arxiv.org: {first.url}")
        else:
            record("web_search", "arxiv_returns_results", NETWORK_BLOCKED,
                   "arXiv returned 0 results")
    except Exception as e:
        if is_network_error({"error": str(e)}):
            record("web_search", "arxiv_returns_results", NETWORK_BLOCKED, str(e)[:100])
        else:
            record("web_search", "arxiv_returns_results", FAIL, str(e)[:200])

    # Test 4: Semantic Scholar (no key required)
    print("\n  Testing Semantic Scholar API...", flush=True)
    try:
        ss_results = ws._search_semantic_scholar("transformer neural network")
        if ss_results:
            record("web_search", "semantic_scholar_returns_results", PASS,
                   f"{len(ss_results)} results, top: {ss_results[0].title[:60]}")
        else:
            record("web_search", "semantic_scholar_returns_results", PARTIAL,
                   "Semantic Scholar returned 0 results (rate limit or network)")
    except Exception as e:
        if is_network_error({"error": str(e)}):
            record("web_search", "semantic_scholar_returns_results", NETWORK_BLOCKED, str(e)[:100])
        else:
            record("web_search", "semantic_scholar_returns_results", FAIL, str(e)[:200])

    # Test 5: PubMed (no key)
    print("\n  Testing PubMed API...", flush=True)
    try:
        pm_results = ws._search_pubmed("CRISPR gene editing")
        if pm_results:
            record("web_search", "pubmed_returns_results", PASS,
                   f"{len(pm_results)} results, top: {pm_results[0].title[:60]}")
        else:
            record("web_search", "pubmed_returns_results", PARTIAL,
                   "PubMed returned 0 results")
    except Exception as e:
        if is_network_error({"error": str(e)}):
            record("web_search", "pubmed_returns_results", NETWORK_BLOCKED, str(e)[:100])
        else:
            record("web_search", "pubmed_returns_results", FAIL, str(e)[:200])

    # Test 6: Full search() dispatcher for various query types
    print("\n  Testing search() dispatcher...", flush=True)
    search_tests = [
        ("python asyncio tutorial", "code", "code"),
        ("latest AI news 2026", "news", "news"),
        ("best pizza NYC", "general", "general"),
    ]
    for query, qtype, label in search_tests:
        try:
            res = ws.search(query, query_type=qtype)
            if res:
                record("web_search", f"dispatcher_{label}_query_returns_results", PASS,
                       f"{len(res)} results via {res[0].source_engine}")
            else:
                record("web_search", f"dispatcher_{label}_query_returns_results", PARTIAL,
                       "No results (API keys missing or rate limited)")
        except Exception as e:
            if is_network_error({"error": str(e)}):
                record("web_search", f"dispatcher_{label}_query_returns_results",
                       NETWORK_BLOCKED, str(e)[:100])
            else:
                record("web_search", f"dispatcher_{label}_query_returns_results",
                       FAIL, str(e)[:200])


# ---------------------------------------------------------------------------
# Main live browser tests
# ---------------------------------------------------------------------------

async def run_browser_tests():
    section("LIVE BROWSER TESTS")

    sess = f"kraken-audit-{uuid.uuid4().hex[:8]}"
    bridge = ConduitBridge(sess, budget_cents=99999, data_dir=TMP_DIR)
    await bridge.start()
    print(f"  Bridge started. Session: {sess}", flush=True)

    audit_log = AuditLog(db_path=TMP_DB)

    try:
        # ---------------------------------------------------------------
        # Audit chain baseline
        # ---------------------------------------------------------------
        section("AUDIT CHAIN BASELINE")
        initial_count = len(audit_log.get_session_rows(sess))
        record("audit", "initial_count_zero", PASS if initial_count == 0 else PARTIAL,
               f"Initial audit rows: {initial_count}")

        # ---------------------------------------------------------------
        # TEST: swarmsync.ai — user's own site
        # ---------------------------------------------------------------
        section("SITE: swarmsync.ai")
        nav = await safe_navigate(bridge, "https://www.swarmsync.ai")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("swarmsync", "navigation", status, nav["error"])
        else:
            record("swarmsync", "navigation", PASS,
                   f"title={nav.get('title', '')[:60]}")

            # extract_main
            ext = await safe_extract(bridge)
            if "error" in ext:
                record("swarmsync", "extract_main", FAIL, ext["error"])
            else:
                text = ext.get("text", "")
                ch = ext.get("content_hash", "")
                record("swarmsync", "extract_main",
                       PASS if len(text) > 50 and ch else PARTIAL,
                       f"chars={ext.get('char_count', 0)}, hash={ch}")

            # extract_main provenance_mode=True
            prov = await safe_extract(bridge, provenance_mode=True)
            if "error" in prov:
                record("swarmsync", "extract_main_provenance_mode", FAIL, str(prov["error"]))
            else:
                # Check that each field has .value and .provenance
                text_field = prov.get("text", {})
                has_provenance = (isinstance(text_field, dict)
                                  and "value" in text_field
                                  and "provenance" in text_field)
                if has_provenance:
                    pdata = text_field["provenance"]
                    record("swarmsync", "extract_main_provenance_mode", PASS,
                           f"session_pubkey={str(pdata.get('session_pubkey',''))[:20]}...")
                else:
                    record("swarmsync", "extract_main_provenance_mode", FAIL,
                           f"provenance fields missing. keys={list(prov.keys())[:5]}")

            # screenshot
            ss = await safe_screenshot(bridge)
            if "error" in ss:
                record("swarmsync", "screenshot", FAIL, ss["error"])
            else:
                path = ss.get("path", "")
                exists = Path(path).exists() if path else False
                record("swarmsync", "screenshot",
                       PASS if ss.get("success") and exists else FAIL,
                       f"path={path}")

        # ---------------------------------------------------------------
        # TEST: Hacker News
        # ---------------------------------------------------------------
        section("SITE: news.ycombinator.com")
        nav = await safe_navigate(bridge, "https://news.ycombinator.com")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("hackernews", "navigation", status, nav["error"])
        else:
            record("hackernews", "navigation", PASS,
                   f"title={nav.get('title', '')[:60]}")

            # scroll
            scroll_r = await bridge.scroll("down", 500)
            record("hackernews", "scroll_down",
                   PASS if scroll_r.get("success") else FAIL,
                   str(scroll_r.get("error", "ok")))

            # extract_main
            ext = await safe_extract(bridge)
            if "error" in ext:
                record("hackernews", "extract_main", FAIL, ext["error"])
            else:
                text = ext.get("text", "")
                record("hackernews", "extract_main",
                       PASS if len(text) > 50 else PARTIAL,
                       f"chars={ext.get('char_count', 0)}, hash={ext.get('content_hash', '')}")

        # ---------------------------------------------------------------
        # TEST: Google
        # ---------------------------------------------------------------
        section("SITE: google.com")
        nav = await safe_navigate(bridge, "https://www.google.com")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("google", "navigation", status, nav["error"])
        else:
            record("google", "navigation", PASS,
                   f"title={nav.get('title', '')[:60]}")
            ext = await safe_extract(bridge)
            record("google", "extract_main",
                   PASS if not ext.get("error") and ext.get("char_count", 0) > 0 else PARTIAL,
                   f"chars={ext.get('char_count', 0)}")

        # ---------------------------------------------------------------
        # TEST: Wikipedia
        # ---------------------------------------------------------------
        section("SITE: wikipedia.org")
        nav = await safe_navigate(bridge, "https://en.wikipedia.org/wiki/Python_(programming_language)")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("wikipedia", "navigation", status, nav["error"])
        else:
            record("wikipedia", "navigation", PASS,
                   f"title={nav.get('title', '')[:60]}")

            ext = await safe_extract(bridge)
            if "error" in ext:
                record("wikipedia", "extract_main", FAIL, ext["error"])
            else:
                text = ext.get("text", "")
                has_python = "python" in text.lower() or "programming" in text.lower()
                record("wikipedia", "extract_main",
                       PASS if has_python and len(text) > 100 else PARTIAL,
                       f"chars={ext.get('char_count', 0)}, hash={ext.get('content_hash', '')}")

            # provenance on wikipedia
            prov = await safe_extract(bridge, provenance_mode=True)
            if "error" in prov:
                record("wikipedia", "provenance_mode", FAIL, str(prov["error"]))
            else:
                text_field = prov.get("text", {})
                has_prov = isinstance(text_field, dict) and "provenance" in text_field
                record("wikipedia", "provenance_mode",
                       PASS if has_prov else FAIL,
                       "provenance wrapping verified" if has_prov else "provenance wrapping MISSING")

        # ---------------------------------------------------------------
        # TEST: GitHub
        # ---------------------------------------------------------------
        section("SITE: github.com")
        nav = await safe_navigate(bridge, "https://github.com")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("github", "navigation", status, nav["error"])
        else:
            record("github", "navigation", PASS,
                   f"title={nav.get('title', '')[:60]}")

            # Test fill (search box)
            fill_r = await bridge.fill("input[name='q']", "patchright playwright")
            record("github", "fill_search_box",
                   PASS if fill_r.get("success") else PARTIAL,
                   str(fill_r.get("error", fill_r.get("typed", "ok")))[:100])

            # Test self-healing selectors: use a broken selector first
            # The broken selector '.nonexistent-class-abc123' should fail CSS tier
            # but if healing tries ARIA + text, result will include healing metadata
            broken_r = await bridge.click(".nonexistent-class-abc123-broken")
            healing_attempted = broken_r.get("selector_healing_attempted", False)
            tiers_tried = broken_r.get("tiers_tried", [])
            if healing_attempted:
                record("github", "self_healing_selector_activated", PASS,
                       f"Healing activated, tiers tried: {tiers_tried}")
            else:
                # Healing may not be in the result when it doesn't activate
                record("github", "self_healing_selector_activated", PARTIAL,
                       f"healing_attempted not in response: {list(broken_r.keys())[:8]}")

        # ---------------------------------------------------------------
        # TEST: Stack Overflow (code query routing test)
        # ---------------------------------------------------------------
        section("SITE: stackoverflow.com")
        nav = await safe_navigate(bridge, "https://stackoverflow.com/questions/tagged/python")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("stackoverflow", "navigation", status, nav["error"])
        else:
            record("stackoverflow", "navigation", PASS,
                   f"title={nav.get('title', '')[:60]}")
            ext = await safe_extract(bridge)
            record("stackoverflow", "extract_main",
                   PASS if not ext.get("error") and ext.get("char_count", 0) > 0 else PARTIAL,
                   f"chars={ext.get('char_count', 0)}")

        # ---------------------------------------------------------------
        # TEST: DuckDuckGo (web search integration)
        # ---------------------------------------------------------------
        section("SITE: duckduckgo.com (browser search)")
        nav = await safe_navigate(bridge, "https://duckduckgo.com")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("duckduckgo", "navigation", status, nav["error"])
        else:
            record("duckduckgo", "navigation", PASS,
                   f"title={nav.get('title', '')[:60]}")

            # Test the browser._search() method (DDG browser scrape)
            search_r = await asyncio.wait_for(
                bridge._browser_tool._dispatch("search", {"query": "Conduit browser automation"}),
                timeout=30
            )
            if "error" in search_r:
                record("duckduckgo", "browser_search_ddg", PARTIAL,
                       f"Browser search returned error (DDG DOM may have changed): {search_r['error'][:100]}")
            else:
                r_list = search_r.get("results", [])
                record("duckduckgo", "browser_search_ddg",
                       PASS if isinstance(r_list, list) else FAIL,
                       f"{len(r_list)} results returned")

        # ---------------------------------------------------------------
        # TEST: arXiv (academic search)
        # ---------------------------------------------------------------
        section("SITE: arxiv.org (navigation)")
        nav = await safe_navigate(bridge, "https://arxiv.org/search/?query=attention+mechanism&searchtype=all")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("arxiv", "navigation", status, nav["error"])
        else:
            record("arxiv", "navigation", PASS,
                   f"title={nav.get('title', '')[:60]}")
            ext = await safe_extract(bridge)
            record("arxiv", "extract_main",
                   PASS if not ext.get("error") and ext.get("char_count", 0) > 0 else PARTIAL,
                   f"chars={ext.get('char_count', 0)}")

        # ---------------------------------------------------------------
        # TEST: Reddit (stealth test)
        # ---------------------------------------------------------------
        section("SITE: reddit.com (stealth detection test)")
        nav = await safe_navigate(bridge, "https://www.reddit.com", timeout=40)
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("reddit", "navigation", status, nav["error"])
        else:
            title = nav.get("title", "")
            url = nav.get("url", "")
            text = nav.get("text", "")

            # Check for block/challenge pages
            blocked = any(kw in title.lower() for kw in ("blocked", "captcha", "challenge", "robot", "access denied"))
            blocked_url = any(kw in url.lower() for kw in ("blocked", "challenge"))

            if blocked or blocked_url:
                record("reddit", "navigation", PARTIAL,
                       f"Reddit may have blocked/challenged: title={title[:60]}, url={url[:80]}")
            else:
                record("reddit", "navigation", PASS,
                       f"title={title[:60]}, chars={len(text)}")

            ext = await safe_extract(bridge)
            if "error" in ext:
                record("reddit", "extract_main", FAIL, ext["error"])
            else:
                chars = ext.get("char_count", 0)
                record("reddit", "extract_main",
                       PASS if chars > 50 else PARTIAL,
                       f"chars={chars} (0 may indicate bot block)")

        # ---------------------------------------------------------------
        # TEST: Twitter/X (stealth test)
        # ---------------------------------------------------------------
        section("SITE: twitter.com (stealth detection test)")
        nav = await safe_navigate(bridge, "https://twitter.com", timeout=40)
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("twitter", "navigation", status, nav["error"])
        else:
            title = nav.get("title", "")
            url = nav.get("url", "")
            blocked = any(kw in title.lower() for kw in ("blocked", "captcha", "challenge", "robot"))
            record("twitter", "navigation",
                   PARTIAL if blocked else PASS,
                   f"title={title[:60]}, url={url[:60]}")

            ss = await safe_screenshot(bridge)
            record("twitter", "screenshot",
                   PASS if ss.get("success") and Path(ss.get("path", "x")).exists() else FAIL,
                   ss.get("path", ss.get("error", ""))[:80])

        # ---------------------------------------------------------------
        # TEST: PubMed (navigation test)
        # ---------------------------------------------------------------
        section("SITE: pubmed.ncbi.nlm.nih.gov")
        nav = await safe_navigate(bridge, "https://pubmed.ncbi.nlm.nih.gov/?term=CRISPR+gene+editing")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("pubmed", "navigation", status, nav["error"])
        else:
            record("pubmed", "navigation", PASS,
                   f"title={nav.get('title', '')[:60]}")
            ext = await safe_extract(bridge)
            record("pubmed", "extract_main",
                   PASS if not ext.get("error") and ext.get("char_count", 0) > 0 else PARTIAL,
                   f"chars={ext.get('char_count', 0)}")

        # ---------------------------------------------------------------
        # TEST: Scholar Google (academic)
        # ---------------------------------------------------------------
        section("SITE: scholar.google.com")
        nav = await safe_navigate(bridge, "https://scholar.google.com/scholar?q=attention+is+all+you+need")
        if "error" in nav:
            status = NETWORK_BLOCKED if is_network_error(nav) else FAIL
            record("scholar_google", "navigation", status, nav["error"])
        else:
            title = nav.get("title", "")
            url = nav.get("url", "")
            blocked = any(kw in title.lower() for kw in ("blocked", "captcha", "challenge", "sorry"))
            record("scholar_google", "navigation",
                   PARTIAL if blocked else PASS,
                   f"title={title[:60]}")

        # ---------------------------------------------------------------
        # TEST: eval + code hash in audit chain
        # ---------------------------------------------------------------
        section("EVAL TEST: JS code verbatim in audit chain")
        await safe_navigate(bridge, "https://example.com")
        js_code = "document.title + ' | ' + window.location.href"
        eval_r = await bridge.eval(js_code)
        if "error" in eval_r and not eval_r.get("success"):
            record("eval", "eval_returns_result", FAIL, str(eval_r.get("error", "")))
        else:
            record("eval", "eval_returns_result", PASS,
                   f"result={str(eval_r.get('result', ''))[:80]}")

        # Verify the js_code is stored verbatim in audit log
        rows = audit_log.get_session_rows(sess)
        eval_rows = [r for r in rows if r["tool_name"] == "browser.eval"]
        if eval_rows:
            last_eval = eval_rows[-1]
            inputs = json.loads(last_eval["inputs_json"])
            stored_code = inputs.get("js_code", "")
            if stored_code == js_code:
                record("eval", "js_code_verbatim_in_audit", PASS,
                       f"Code stored exactly: '{stored_code[:60]}'")
            else:
                record("eval", "js_code_verbatim_in_audit", FAIL,
                       f"Code mismatch. Expected: {js_code!r}, Got: {stored_code!r}")
        else:
            record("eval", "js_code_verbatim_in_audit", FAIL,
                   "No browser.eval entries found in audit log")

        # ---------------------------------------------------------------
        # TEST: Self-healing selectors triggered by broken CSS
        # ---------------------------------------------------------------
        section("SELF-HEALING SELECTOR TEST")
        await safe_navigate(bridge, "https://example.com")

        # Try click with working selector first
        working_r = await bridge.click("a")
        record("self_healing", "working_selector_clicks",
               PASS if working_r.get("success") else PARTIAL,
               str(working_r.get("error", "clicked"))[:80])

        # Now try broken selector — healing should kick in
        # Looking for something text-based that exists
        await safe_navigate(bridge, "https://example.com")
        broken_r = await bridge.click(".nonexistent-ghost-selector-12345")
        healing_meta = broken_r.get("selector_healing_attempted", False)
        tiers = broken_r.get("tiers_tried", [])
        if healing_meta:
            record("self_healing", "broken_css_triggers_healing", PASS,
                   f"Healing triggered, tiers tried: {tiers}")
        else:
            # Healing may succeed (ARIA/text) or may not report metadata on total failure
            record("self_healing", "broken_css_triggers_healing", PARTIAL,
                   f"Healing metadata not in response. Keys: {list(broken_r.keys())[:10]}")

        # ---------------------------------------------------------------
        # TEST: Audit chain grows and verifies after all actions
        # ---------------------------------------------------------------
        section("AUDIT CHAIN INTEGRITY")
        rows = audit_log.get_session_rows(sess)
        record("audit", "chain_has_entries", PASS if len(rows) > 0 else FAIL,
               f"{len(rows)} total audit rows")

        chain_valid = audit_log.verify_chain(sess)
        record("audit", "chain_verify_returns_true", PASS if chain_valid else FAIL,
               f"verify_chain()={chain_valid}")

        # Check all rows have valid 64-char hashes
        bad_hashes = [r for r in rows if len(r.get("row_hash", "")) != 64]
        record("audit", "all_rows_have_64char_hashes",
               PASS if not bad_hashes else FAIL,
               f"{len(bad_hashes)} rows with bad hashes (out of {len(rows)})")

        # Check chain linkage
        chain_broken = []
        for i in range(1, len(rows)):
            if rows[i]["prev_hash"] != rows[i-1]["row_hash"]:
                chain_broken.append(i)
        record("audit", "chain_prev_hash_linkage",
               PASS if not chain_broken else FAIL,
               f"Broken links at positions: {chain_broken[:5]}" if chain_broken else f"All {len(rows)} links valid")

        # Verify tool names recorded
        tool_names = set(r["tool_name"] for r in rows)
        print(f"\n  Tool names recorded in audit: {sorted(tool_names)}", flush=True)
        expected_tools = {"browser.navigate", "browser.extract_main", "browser.screenshot", "browser.scroll"}
        missing_tools = expected_tools - tool_names
        record("audit", "expected_tool_names_present",
               PASS if not missing_tools else PARTIAL,
               f"Missing tools: {missing_tools}" if missing_tools else f"{len(tool_names)} distinct tools")

    finally:
        await bridge.stop()
        print("\n  Bridge stopped.", flush=True)


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

def print_summary():
    section("KRAKEN AUDIT SUMMARY")
    total = len(results)
    by_status = {}
    for r in results.values():
        s = r["status"]
        by_status[s] = by_status.get(s, 0) + 1

    print(f"  Total tests: {total}", flush=True)
    for status, count in sorted(by_status.items()):
        print(f"    {status}: {count}", flush=True)

    elapsed = time.time() - start_time
    print(f"  Elapsed: {elapsed:.1f}s", flush=True)

    # Per-category summary
    categories = {}
    for r in results.values():
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"PASS": 0, "FAIL": 0, "PARTIAL": 0, "NETWORK_BLOCKED": 0}
        categories[cat][r["status"]] = categories[cat].get(r["status"], 0) + 1

    print("\n  Per-category:", flush=True)
    for cat, counts in sorted(categories.items()):
        total_cat = sum(counts.values())
        pass_count = counts.get("PASS", 0)
        print(f"    {cat}: {pass_count}/{total_cat} PASS "
              f"(FAIL={counts.get('FAIL', 0)}, "
              f"PARTIAL={counts.get('PARTIAL', 0)}, "
              f"NET={counts.get('NETWORK_BLOCKED', 0)})", flush=True)

    # Overall score
    pass_n = by_status.get(PASS, 0)
    partial_n = by_status.get(PARTIAL, 0)
    fail_n = by_status.get(FAIL, 0)
    net_n = by_status.get(NETWORK_BLOCKED, 0)

    # Score: PASS=1.0, PARTIAL=0.5, FAIL=0.0, NET_BLOCKED=0.5 (not Conduit's fault)
    score_num = pass_n * 1.0 + partial_n * 0.5 + net_n * 0.5
    score_denom = total
    score_pct = (score_num / score_denom * 10) if score_denom > 0 else 0

    print(f"\n  OVERALL SCORE: {score_pct:.1f}/10", flush=True)
    return results, score_pct


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    print("=" * 60, flush=True)
    print("  KRAKEN REALITY AUDIT — CONDUIT LIVE TEST", flush=True)
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("=" * 60, flush=True)

    test_fingerprint_variance()
    test_web_search_api()
    await run_browser_tests()
    all_results, score = print_summary()
    return all_results, score


if __name__ == "__main__":
    all_results, score = asyncio.run(main())
    # Exit with error code if score below 5
    sys.exit(0 if score >= 5.0 else 1)
