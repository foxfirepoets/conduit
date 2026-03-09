"""
Live test: IdeaBrowser scrape flow using Conduit instead of raw Patchright.
Run from the Conduit root: python test_ideabrowser_live.py
"""
import sys
import asyncio
import re
from pathlib import Path

# ── Bootstrap via conftest helper (handles all relative imports) ─────────────
CONDUIT_ROOT = Path(__file__).parent
sys.path.insert(0, str(CONDUIT_ROOT))
sys.path.insert(0, str(CONDUIT_ROOT / "tests"))

import conftest  # noqa: E402 — runs bootstrap_cato()

ConduitBridge = sys.modules["cato.tools.conduit_bridge"].ConduitBridge

# ── Config ──────────────────────────────────────────────────────────────────
EMAIL    = "Foxfirepoets@gmail.com"
PASSWORD = "Hudson1234%"
BASE_URL = "https://www.ideabrowser.com"

SUB_PAGES = [
    ("value-ladder",      "Value Ladder"),
    ("why-now",           "Why This Opportunity Matters Now"),
    ("proof-signals",     "Proof & Signals"),
    ("market-gap",        "Market Opportunity"),
    ("execution-plan",    "Detailed Execution Strategy"),
    ("community-signals", "Community Signals"),
    ("keywords",          "Full Keyword Analysis"),
]


def log(msg):
    print(msg.encode("ascii", errors="replace").decode("ascii"), flush=True)


async def main():
    b = ConduitBridge("ideabrowser-live", budget_cents=99999, data_dir=None)
    await b.start()

    try:
        # ── Step 1: Login ────────────────────────────────────────────────────
        log("=== Step 1: Navigate to login ===")
        r = await b.navigate(BASE_URL + "/login")
        log(f"  title: {r.get('title','')} | url: {r.get('url','')}")

        # Give the React app time to hydrate
        await asyncio.sleep(3)

        log("=== Step 2: Fill email (visible field) ===")
        r = await b.type_text('input[type="email"]:visible', EMAIL)
        log(f"  {r}")

        log("=== Step 3: Click 'Sign in with Password' (visible) ===")
        r = await b.click('button:has-text("Sign in with Password"):visible')
        log(f"  {r}")
        await asyncio.sleep(2)

        log("=== Step 4: Fill password (visible) ===")
        r = await b.type_text('input[type="password"]:visible', PASSWORD)
        log(f"  {r}")

        log("=== Step 5: Submit (visible) ===")
        r = await b.click('button[type="submit"]:visible')
        log(f"  {r}")
        await asyncio.sleep(5)

        log("=== Step 6: Navigate to Idea of the Day ===")
        r = await b.navigate(BASE_URL + "/idea-of-the-day")
        current_url = r.get("url", "")
        log(f"  url: {current_url}")
        log(f"  title: {r.get('title','')}")

        if "/login" in current_url:
            log("ERROR: Still on login page — login failed!")
            return

        log("LOGIN SUCCESS!")

        # ── Step 7: Extract idea slug ────────────────────────────────────────
        log("=== Step 7: Extract idea slug ===")
        r = await b.eval("""
            Array.from(document.querySelectorAll('a[href]'))
                 .map(a => a.href)
                 .filter(h => /\\/idea\\//.test(h))
                 .slice(0, 10)
        """)
        links = r.get("result", []) or []
        log(f"  idea links found: {links[:5]}")

        slug = None
        pattern = re.compile(r'/idea/([^/]+)/')
        for href in links:
            m = pattern.search(str(href))
            if m:
                slug = m.group(1)
                break

        if not slug:
            log("ERROR: Could not extract idea slug")
            return

        log(f"  slug: {slug}")
        idea_base = f"{BASE_URL}/idea/{slug}"

        # ── Step 8: Scrape main idea page ────────────────────────────────────
        log("=== Step 8: Scrape main idea page ===")
        r = await b.extract_main()
        main_text = r.get("text", "") or r.get("content", "")
        log(f"  main page text: {len(main_text)} chars")
        log(f"  preview: {main_text[:200]}")

        # ── Step 9: Scrape sub-pages ─────────────────────────────────────────
        log("=== Step 9: Scrape sub-pages ===")
        sections = []
        for path_suffix, section_name in SUB_PAGES:
            sub_url = f"{idea_base}/{path_suffix}"
            log(f"  -> {section_name}")
            r = await b.navigate(sub_url)
            landed = r.get("url", "")
            if "/login" in landed or "/pricing" in landed:
                log(f"     PAYWALL: redirected to {landed}")
                sections.append({"section": section_name, "url": sub_url, "content": "", "error": f"paywall: {landed}"})
            else:
                er = await b.extract_main()
                text = er.get("text", "") or er.get("content", "")
                log(f"     OK: {len(text)} chars")
                sections.append({"section": section_name, "url": sub_url, "content": text[:3000], "error": None})
            await asyncio.sleep(0.5)

        # ── Summary ──────────────────────────────────────────────────────────
        log("\n=== SUMMARY ===")
        log(f"slug: {slug}")
        log(f"main page: {len(main_text)} chars")
        for s in sections:
            status = "PAYWALL" if s["error"] else f"{len(s['content'])} chars"
            log(f"  {s['section']}: {status}")
        log("=== DONE ===")

    except Exception as e:
        import traceback
        log(f"FATAL ERROR: {e}")
        traceback.print_exc()
    finally:
        await b.stop()


if __name__ == "__main__":
    asyncio.run(main())
