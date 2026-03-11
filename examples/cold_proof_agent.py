"""
Conduit Cold Proof Agent
========================
Audits a prospect's public website and exports a self-verifiable proof bundle
as a "free sample" for outbound marketing.

Cold Proof Concept
------------------
Traditional cold outreach sends a pitch.  Cold Proof sends evidence.

The proof bundle produced by this agent IS the marketing material.  The
recipient downloads a single .tar.gz file and runs one command::

    tar xzf session_proof.tar.gz && cd session_proof && python verify.py

No pip install.  No API keys.  No cloud call.  Pure stdlib.

The script re-walks the SHA-256 hash chain logged during the audit, verifies
the Ed25519 signature, and prints a pass/fail verdict.  The recipient
experiences Conduit's tamper-evident audit trail first-hand before reading a
single line of marketing copy.

This mirrors the pharmaceutical free-sample model: the sample IS the pitch.
Seeing is believing; a self-verifying bundle is more convincing than any slide
deck.

SwarmSync Marketplace Listing:
  Category: Outbound Marketing / Lead Generation
  Tags: cold-outreach, proof-bundle, website-audit, ed25519, tamper-evident

GitHub: https://github.com/bkauto3/Conduit/blob/main/examples/cold_proof_agent.py
Built with: Conduit (https://github.com/bkauto3/Conduit)
Marketplace: SwarmSync.ai (https://swarmsync.ai)
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import re
import sys
import time
import types
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Bootstrap -- wire the cato.* package shim so ConduitBridge relative imports
# resolve correctly.  Mirrors compliance_auditor.py / tests/conftest.py.
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = Path.home() / ".cato"


def _bootstrap_cato() -> None:
    """Install sys.modules shim for the cato.* namespace package."""
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    existing = sys.modules.setdefault("cato", cato_pkg)
    cato_pkg = existing

    if "cato.platform" not in sys.modules:
        platform_mod = types.ModuleType("cato.platform")
        platform_mod.get_data_dir = lambda: _DATA_DIR  # type: ignore[attr-defined]
        sys.modules["cato.platform"] = platform_mod
        cato_pkg.platform = platform_mod  # type: ignore[attr-defined]

    if "cato.audit" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.audit",
            str(CONDUIT_ROOT / "audit.py"),
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
    existing_tools = sys.modules.setdefault("cato.tools", tools_pkg)
    cato_pkg.tools = existing_tools  # type: ignore[attr-defined]

    for mod_name, file_name in [
        ("cato.tools.browser", "browser.py"),
        ("cato.tools.conduit_bridge", "conduit_bridge.py"),
        ("cato.tools.conduit_proof", "conduit_proof.py"),
    ]:
        if mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                mod_name,
                str(CONDUIT_ROOT / "tools" / file_name),
                submodule_search_locations=[],
            )
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            mod.__package__ = "cato.tools"
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]


_bootstrap_cato()

from cato.tools.conduit_bridge import ConduitBridge  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cold_proof_agent")

# ---------------------------------------------------------------------------
# Performance JS snippets
# ---------------------------------------------------------------------------

_PERF_TIMING_JS = """
(function() {
    var t = window.performance && window.performance.timing;
    if (!t) return {error: 'performance.timing unavailable'};
    var nav = window.performance.getEntriesByType('navigation')[0];
    var ttfb = nav ? Math.round(nav.responseStart) : (t.responseStart - t.navigationStart);
    var domLoad = t.domContentLoadedEventEnd - t.navigationStart;
    var fullLoad = t.loadEventEnd > 0 ? (t.loadEventEnd - t.navigationStart) : null;
    return {
        ttfb_ms: ttfb,
        dom_content_loaded_ms: domLoad,
        full_load_ms: fullLoad,
        redirect_count: window.performance.navigation ? window.performance.navigation.redirectCount : 0
    };
})();
"""

_SSL_INFO_JS = """
(function() {
    return {
        protocol: window.location.protocol,
        host: window.location.host,
        origin: window.location.origin
    };
})();
"""

_COOKIE_BANNER_JS = """
(function() {
    var keywords = ['cookie', 'consent', 'gdpr', 'accept', 'tracking'];
    var found = [];
    var nodes = document.querySelectorAll('[id], [class]');
    for (var i = 0; i < Math.min(nodes.length, 200); i++) {
        var id = (nodes[i].id || '').toLowerCase();
        var cls = (nodes[i].className && typeof nodes[i].className === 'string')
                  ? nodes[i].className.toLowerCase() : '';
        for (var k = 0; k < keywords.length; k++) {
            if (id.indexOf(keywords[k]) !== -1 || cls.indexOf(keywords[k]) !== -1) {
                found.push({tag: nodes[i].tagName, id: nodes[i].id, class: nodes[i].className});
                break;
            }
        }
        if (found.length >= 3) break;
    }
    return {cookie_elements_found: found.length, samples: found.slice(0, 2)};
})();
"""

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PerformanceMetrics:
    """Page load timing data gathered via JS performance.timing."""

    ttfb_ms: Optional[int] = None
    dom_content_loaded_ms: Optional[int] = None
    full_load_ms: Optional[int] = None
    redirect_count: int = 0
    error: Optional[str] = None

    @property
    def grade(self) -> str:
        """Return A/B/C/D/F rating based on TTFB."""
        if self.ttfb_ms is None:
            return "?"
        if self.ttfb_ms < 200:
            return "A"
        if self.ttfb_ms < 500:
            return "B"
        if self.ttfb_ms < 1000:
            return "C"
        if self.ttfb_ms < 2000:
            return "D"
        return "F"


@dataclass
class ComplianceSignals:
    """Quick compliance surface signals extracted from page content and DOM."""

    https_enforced: bool = False
    privacy_policy_found: bool = False
    cookie_banner_elements: int = 0
    contact_info_found: bool = False

    @property
    def summary(self) -> str:
        signals = []
        signals.append("HTTPS" if self.https_enforced else "NO-HTTPS")
        signals.append("PRIVACY-OK" if self.privacy_policy_found else "NO-PRIVACY")
        signals.append(f"COOKIE-ELEMENTS:{self.cookie_banner_elements}")
        signals.append("CONTACT-OK" if self.contact_info_found else "NO-CONTACT")
        return " | ".join(signals)


@dataclass
class ColdProofBundle:
    """Full result of a cold proof audit session."""

    url: str
    domain: str
    timestamp: str
    session_id: str
    page_title: str = ""
    page_text_chars: int = 0
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    compliance: ComplianceSignals = field(default_factory=ComplianceSignals)
    fingerprint_hash: str = ""
    action_count: int = 0
    proof_bundle_path: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Regex helpers for compliance surface scan
# ---------------------------------------------------------------------------

_PRIVACY_RE = re.compile(
    r"privacy\s*policy|privacy\s*notice|data\s*protection|gdpr",
    re.IGNORECASE,
)

_CONTACT_RE = re.compile(
    r"contact\s*us|get\s*in\s*touch|support@|info@|help@"
    r"|customer\s*service"
    r"|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Core audit runner
# ---------------------------------------------------------------------------

async def run_cold_proof_audit(
    target_url: str,
    *,
    session_id: str = "",
    budget_cents: int = 200,
    proof_output_dir: Optional[str] = None,
) -> ColdProofBundle:
    """
    Execute a cold proof audit against *target_url*.

    Steps
    -----
    1. Navigate to the target URL.
    2. Extract main page content for compliance surface scan.
    3. Evaluate JS to gather performance.timing metrics.
    4. Evaluate JS to detect cookie consent DOM elements.
    5. Evaluate JS to confirm SSL/protocol information.
    6. Take a screenshot as visual evidence.
    7. Fingerprint the page (SHA-256 noise-stripped content hash).
    8. Export a cryptographic proof bundle.
    9. Return a ColdProofBundle with all findings.

    Parameters
    ----------
    target_url : str
        URL to audit.  Must be http:// or https://.
    session_id : str, optional
        Unique session identifier.  Auto-generated if empty.
    budget_cents : int, optional
        Per-session cost budget in cents (default 200).
    proof_output_dir : str, optional
        Directory for the proof bundle.  Defaults to ~/.cato/proofs/.

    Returns
    -------
    ColdProofBundle
        Structured audit result with performance, compliance, and proof path.
    """
    import uuid

    if not session_id:
        session_id = f"coldproof-{uuid.uuid4().hex[:12]}"

    parsed = urlparse(target_url)
    domain = parsed.netloc or target_url
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    bundle = ColdProofBundle(
        url=target_url,
        domain=domain,
        timestamp=timestamp,
        session_id=session_id,
    )

    bridge = ConduitBridge(session_id, budget_cents=budget_cents)

    try:
        logger.info(
            "Cold Proof audit starting — url=%s session=%s", target_url, session_id
        )
        await bridge.start()

        # ------------------------------------------------------------------
        # Step 1: Navigate
        # ------------------------------------------------------------------
        logger.info("Navigating to %s", target_url)
        nav_result = await bridge.navigate(target_url)

        if nav_result.get("error"):
            bundle.error = f"Navigation failed: {nav_result['error']}"
            logger.error(bundle.error)
            return bundle

        bundle.page_title = nav_result.get("title", "")
        logger.info("Page loaded: '%s'", bundle.page_title)

        # ------------------------------------------------------------------
        # Step 2: Extract main content for compliance scan
        # ------------------------------------------------------------------
        logger.info("Extracting main content")
        extract_result = await bridge.extract_main(max_chars=25000)
        page_text = extract_result.get("text", "")

        if not page_text:
            fallback = await bridge.extract()
            page_text = fallback.get("text", "")

        bundle.page_text_chars = len(page_text)
        logger.info("Extracted %d characters", bundle.page_text_chars)

        # Compliance surface scan (text-based)
        bundle.compliance.https_enforced = parsed.scheme == "https"
        bundle.compliance.privacy_policy_found = bool(_PRIVACY_RE.search(page_text))
        bundle.compliance.contact_info_found = bool(_CONTACT_RE.search(page_text))

        # ------------------------------------------------------------------
        # Step 3: JS performance.timing
        # ------------------------------------------------------------------
        logger.info("Evaluating performance.timing")
        perf_result = await bridge.eval(_PERF_TIMING_JS)
        perf_value = perf_result.get("value", {})

        if isinstance(perf_value, dict) and not perf_value.get("error"):
            bundle.performance = PerformanceMetrics(
                ttfb_ms=perf_value.get("ttfb_ms"),
                dom_content_loaded_ms=perf_value.get("dom_content_loaded_ms"),
                full_load_ms=perf_value.get("full_load_ms"),
                redirect_count=perf_value.get("redirect_count", 0),
            )
            logger.info(
                "Performance: TTFB=%sms  DOMLoad=%sms  FullLoad=%sms  Grade=%s",
                bundle.performance.ttfb_ms,
                bundle.performance.dom_content_loaded_ms,
                bundle.performance.full_load_ms,
                bundle.performance.grade,
            )
        else:
            bundle.performance.error = str(perf_value.get("error", "eval returned no value"))
            logger.warning("Performance timing unavailable: %s", bundle.performance.error)

        # ------------------------------------------------------------------
        # Step 4: Cookie banner DOM detection
        # ------------------------------------------------------------------
        logger.info("Scanning for cookie consent DOM elements")
        cookie_result = await bridge.eval(_COOKIE_BANNER_JS)
        cookie_value = cookie_result.get("value", {})

        if isinstance(cookie_value, dict):
            bundle.compliance.cookie_banner_elements = cookie_value.get(
                "cookie_elements_found", 0
            )
            logger.info(
                "Cookie banner elements detected: %d",
                bundle.compliance.cookie_banner_elements,
            )

        # ------------------------------------------------------------------
        # Step 5: SSL/protocol confirmation via JS
        # ------------------------------------------------------------------
        logger.info("Confirming SSL/protocol via JS")
        ssl_result = await bridge.eval(_SSL_INFO_JS)
        ssl_value = ssl_result.get("value", {})

        if isinstance(ssl_value, dict):
            js_protocol = ssl_value.get("protocol", "")
            if js_protocol and not bundle.compliance.https_enforced:
                # JS-confirmed protocol overrides URL-based check if they differ
                bundle.compliance.https_enforced = js_protocol == "https:"
            logger.info("JS-confirmed protocol: %s", js_protocol)

        # ------------------------------------------------------------------
        # Step 6: Screenshot as visual evidence
        # ------------------------------------------------------------------
        logger.info("Taking screenshot")
        screenshot_result = await bridge.screenshot(
            path=f"cold_proof_{session_id}.png"
        )
        if screenshot_result.get("error"):
            logger.warning("Screenshot failed: %s", screenshot_result["error"])
        else:
            logger.info("Screenshot captured")

        # ------------------------------------------------------------------
        # Step 7: Fingerprint the page
        # ------------------------------------------------------------------
        logger.info("Fingerprinting page content")
        fp_result = await bridge.fingerprint(target_url)

        if fp_result.get("error"):
            logger.warning("Fingerprint failed: %s", fp_result["error"])
        else:
            bundle.fingerprint_hash = fp_result.get("fingerprint", "")
            logger.info(
                "Fingerprint: %s",
                bundle.fingerprint_hash[:32] + "..." if bundle.fingerprint_hash else "n/a",
            )

        # ------------------------------------------------------------------
        # Step 8: Export proof bundle
        # ------------------------------------------------------------------
        logger.info("Exporting proof bundle")
        proof_result = bridge.export_proof(output_dir=proof_output_dir)

        if proof_result.get("success"):
            bundle.proof_bundle_path = proof_result["path"]
            bundle.action_count = proof_result.get("action_count", 0)
            logger.info(
                "Proof bundle exported: %s  (%d actions  chain_hash=%s)",
                proof_result["path"],
                bundle.action_count,
                (proof_result.get("chain_hash", "") or "")[:16] + "...",
            )
        else:
            logger.warning("Proof export failed: %s", proof_result.get("error"))

    except Exception as exc:
        bundle.error = f"Audit failed with exception: {exc}"
        logger.exception("Cold Proof audit failed")
    finally:
        await bridge.stop()
        logger.info("Browser closed")

    return bundle


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

def _print_summary(bundle: ColdProofBundle) -> None:
    """Print a human-readable summary of the cold proof audit."""
    sep = "=" * 64
    print(f"\n{sep}")
    print("  CONDUIT COLD PROOF AUDIT")
    print(sep)
    print(f"  URL:        {bundle.url}")
    print(f"  Domain:     {bundle.domain}")
    print(f"  Title:      {bundle.page_title}")
    print(f"  Timestamp:  {bundle.timestamp}")
    print(f"  Session:    {bundle.session_id}")
    print(sep)

    if bundle.error:
        print(f"\n  ERROR: {bundle.error}\n")

    # -- Performance --
    print("\n  PAGE PERFORMANCE:")
    p = bundle.performance
    if p.error:
        print(f"    Timing data unavailable: {p.error}")
    else:
        print(f"    TTFB (time-to-first-byte) : {p.ttfb_ms} ms")
        print(f"    DOM Content Loaded        : {p.dom_content_loaded_ms} ms")
        print(f"    Full Load                 : {p.full_load_ms} ms")
        print(f"    Redirect count            : {p.redirect_count}")
        print(f"    Performance grade         : {p.grade}")

    # -- Compliance signals --
    print("\n  COMPLIANCE SURFACE:")
    c = bundle.compliance
    _flag = lambda ok: "[YES]" if ok else "[NO] "
    print(f"    {_flag(c.https_enforced)}  HTTPS enforced")
    print(f"    {_flag(c.privacy_policy_found)}  Privacy policy reference found")
    print(f"    {'[YES]' if c.cookie_banner_elements > 0 else '[NO] '}  Cookie consent elements ({c.cookie_banner_elements} found)")
    print(f"    {_flag(c.contact_info_found)}  Contact information found")

    # -- Fingerprint --
    if bundle.fingerprint_hash:
        print(f"\n  PAGE FINGERPRINT (SHA-256):")
        print(f"    {bundle.fingerprint_hash}")

    # -- Proof bundle --
    print(f"\n  PROOF BUNDLE:")
    print(f"    Actions recorded : {bundle.action_count}")

    if bundle.proof_bundle_path:
        print(f"    Bundle path      : {bundle.proof_bundle_path}")
        print(
            "    Verify with      : "
            "tar xzf <bundle> && cd session_proof && python verify.py"
        )
    else:
        print("    Bundle path      : (not generated)")

    print(f"\n{sep}")
    print("  Powered by Conduit | Agents earn money at swarmsync.ai")
    print(f"{sep}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="cold_proof_agent",
        description="Audit a public website and export a self-verifiable proof bundle.",
    )
    parser.add_argument(
        "--url",
        required=True,
        metavar="URL",
        help="Target URL to audit (e.g. https://example.com)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="PATH",
        help="Directory for the exported proof bundle (default: ~/.cato/proofs/)",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=200,
        metavar="CENTS",
        help="Per-session action budget in cents (default: 200)",
    )
    parser.add_argument(
        "--session-id",
        default="",
        metavar="ID",
        help="Custom session identifier (auto-generated if omitted)",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Write machine-readable JSON report to ~/.cato/proofs/",
    )
    return parser.parse_args(argv)


async def main(argv: Optional[list[str]] = None) -> ColdProofBundle:
    """Parse CLI arguments, run the audit, and print the summary."""
    args = _parse_args(argv)

    # Basic URL sanity check
    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https"):
        print(
            f"ERROR: URL scheme must be http or https, got: {parsed.scheme!r}",
            file=sys.stderr,
        )
        sys.exit(1)

    bundle = await run_cold_proof_audit(
        args.url,
        session_id=args.session_id,
        budget_cents=args.budget,
        proof_output_dir=args.output_dir,
    )

    _print_summary(bundle)

    if args.output_json:
        json_path = (
            Path.home()
            / ".cato"
            / "proofs"
            / f"coldproof_{bundle.session_id}.json"
        )
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(bundle.to_dict(), indent=2), encoding="utf-8"
        )
        logger.info("JSON report written to %s", json_path)
        print(f"  JSON report: {json_path}\n")

    return bundle


if __name__ == "__main__":
    asyncio.run(main())
