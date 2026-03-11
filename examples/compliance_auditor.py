"""
Conduit Compliance Auditor -- Demo Agent
========================================
Audits websites for basic compliance requirements and generates
cryptographic proof of the audit via Conduit proof bundles.

SwarmSync Marketplace Listing:
  Price: $0.10 per audit
  Category: Compliance & Legal
  Tags: compliance, audit, privacy-policy, cookie-consent, proof-bundle

  Description: Automated website compliance checker that verifies privacy
  policies, cookie consent banners, terms of service, HTTPS, and contact
  info. Every check is recorded in a tamper-evident SHA-256 hash chain.
  Proof bundle included with every audit.

GitHub: https://github.com/bkauto3/Conduit/blob/main/examples/compliance_auditor.py
Built with: Conduit (https://github.com/bkauto3/Conduit)
Marketplace: SwarmSync.ai (https://swarmsync.ai)
"""

from __future__ import annotations

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
# resolve correctly.  This mirrors the pattern used in tests/conftest.py and
# scripts/live_audit.py.
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
logger = logging.getLogger("compliance_auditor")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

_CHECK_NAMES = (
    "https_enforcement",
    "privacy_policy",
    "terms_of_service",
    "cookie_consent",
    "contact_information",
)


@dataclass
class CheckResult:
    """Outcome of a single compliance check."""

    name: str
    passed: bool
    evidence: str
    weight: int = 20  # each check is worth 20 points (5 checks = 100 max)


@dataclass
class ComplianceReport:
    """Structured compliance audit report returned to the caller."""

    url: str
    timestamp: str
    page_title: str
    checks: list[CheckResult] = field(default_factory=list)
    overall_score: int = 0
    proof_bundle_path: str = ""
    session_id: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize the report to a JSON-compatible dictionary."""
        d = asdict(self)
        d["checks"] = [asdict(c) for c in self.checks]
        return d


# ---------------------------------------------------------------------------
# Compliance checks -- pure functions operating on extracted page content
# ---------------------------------------------------------------------------

_PRIVACY_PATTERNS = re.compile(
    r"privacy\s*policy|privacy\s*notice|data\s*protection|gdpr",
    re.IGNORECASE,
)

_TOS_PATTERNS = re.compile(
    r"terms\s*(of\s*service|of\s*use|&\s*conditions|\s*and\s*conditions)"
    r"|terms\s*of\s*service|acceptable\s*use\s*policy",
    re.IGNORECASE,
)

_COOKIE_PATTERNS = re.compile(
    r"cookie\s*(consent|notice|banner|policy|preferences)"
    r"|we\s*use\s*cookies"
    r"|accept\s*(all\s*)?cookies"
    r"|cookie\s*settings",
    re.IGNORECASE,
)

_CONTACT_PATTERNS = re.compile(
    r"contact\s*us|get\s*in\s*touch|support@|info@|help@"
    r"|customer\s*service|customer\s*support"
    r"|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)


def check_https(url: str) -> CheckResult:
    """Verify the target URL uses HTTPS."""
    parsed = urlparse(url)
    passed = parsed.scheme == "https"
    evidence = (
        f"URL scheme is '{parsed.scheme}' -- HTTPS enforced"
        if passed
        else f"URL scheme is '{parsed.scheme}' -- HTTPS NOT enforced"
    )
    return CheckResult(name="https_enforcement", passed=passed, evidence=evidence)


def check_privacy_policy(page_text: str) -> CheckResult:
    """Search page text for a privacy policy link or mention."""
    match = _PRIVACY_PATTERNS.search(page_text)
    passed = match is not None
    evidence = (
        f"Found privacy policy reference: '{match.group()}'"
        if passed
        else "No privacy policy link or mention found in page content"
    )
    return CheckResult(name="privacy_policy", passed=passed, evidence=evidence)


def check_terms_of_service(page_text: str) -> CheckResult:
    """Search page text for terms of service / terms of use."""
    match = _TOS_PATTERNS.search(page_text)
    passed = match is not None
    evidence = (
        f"Found terms of service reference: '{match.group()}'"
        if passed
        else "No terms of service link or mention found in page content"
    )
    return CheckResult(name="terms_of_service", passed=passed, evidence=evidence)


def check_cookie_consent(page_text: str) -> CheckResult:
    """Search page text for a cookie consent banner or notice."""
    match = _COOKIE_PATTERNS.search(page_text)
    passed = match is not None
    evidence = (
        f"Found cookie consent reference: '{match.group()}'"
        if passed
        else "No cookie consent banner or notice found in page content"
    )
    return CheckResult(name="cookie_consent", passed=passed, evidence=evidence)


def check_contact_info(page_text: str) -> CheckResult:
    """Search page text for contact information."""
    match = _CONTACT_PATTERNS.search(page_text)
    passed = match is not None
    evidence = (
        f"Found contact information: '{match.group()}'"
        if passed
        else "No contact information (email, 'Contact Us' link) found in page content"
    )
    return CheckResult(name="contact_information", passed=passed, evidence=evidence)


# ---------------------------------------------------------------------------
# Core auditor
# ---------------------------------------------------------------------------

async def run_compliance_audit(
    target_url: str,
    *,
    session_id: str = "",
    budget_cents: int = 100,
    proof_output_dir: Optional[str] = None,
) -> ComplianceReport:
    """
    Execute a full compliance audit against *target_url*.

    Steps:
      1. Navigate to the URL via ConduitBridge.
      2. Extract the page title and main content.
      3. Run five compliance checks against the extracted content.
      4. Take a screenshot as visual evidence.
      5. Export a cryptographic proof bundle of the audit session.
      6. Return a structured ComplianceReport.

    Parameters
    ----------
    target_url : str
        The URL to audit.  Must be http:// or https://.
    session_id : str, optional
        Unique session identifier. Auto-generated if empty.
    budget_cents : int, optional
        Per-session cost budget in cents (default 100).
    proof_output_dir : str, optional
        Directory for the proof bundle.  Defaults to ~/.cato/proofs/.

    Returns
    -------
    ComplianceReport
        Structured audit results with score and proof bundle path.
    """
    import uuid

    if not session_id:
        session_id = f"compliance-{uuid.uuid4().hex[:12]}"

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    report = ComplianceReport(
        url=target_url,
        timestamp=timestamp,
        page_title="",
        session_id=session_id,
    )

    bridge = ConduitBridge(session_id, budget_cents=budget_cents)

    try:
        # -- Initialise the browser engine --
        logger.info("Starting compliance audit for %s (session=%s)", target_url, session_id)
        await bridge.start()

        # -- Step 1: Navigate --
        logger.info("Navigating to %s", target_url)
        nav_result = await bridge.navigate(target_url)

        if nav_result.get("error"):
            report.error = f"Navigation failed: {nav_result['error']}"
            logger.error(report.error)
            return report

        report.page_title = nav_result.get("title", "")
        logger.info("Page loaded: '%s'", report.page_title)

        # -- Step 2: Extract main content --
        logger.info("Extracting page content")
        extract_result = await bridge.extract_main(max_chars=20000)

        page_text = extract_result.get("text", "")
        if not page_text:
            # Fall back to raw extract if extract_main returns empty
            fallback = await bridge.extract()
            page_text = fallback.get("text", "")

        logger.info(
            "Extracted %d characters of content",
            len(page_text),
        )

        # -- Step 3: Run compliance checks --
        logger.info("Running compliance checks")

        checks: list[CheckResult] = [
            check_https(target_url),
            check_privacy_policy(page_text),
            check_terms_of_service(page_text),
            check_cookie_consent(page_text),
            check_contact_info(page_text),
        ]

        report.checks = checks
        report.overall_score = sum(c.weight for c in checks if c.passed)

        for c in checks:
            status = "PASS" if c.passed else "FAIL"
            logger.info("  [%s] %s -- %s", status, c.name, c.evidence)

        logger.info("Overall compliance score: %d/100", report.overall_score)

        # -- Step 4: Screenshot as visual evidence --
        logger.info("Taking screenshot as evidence")
        screenshot_result = await bridge.screenshot(
            path=f"compliance_audit_{session_id}.png",
        )
        if screenshot_result.get("error"):
            logger.warning("Screenshot failed: %s", screenshot_result["error"])

        # -- Step 5: Export cryptographic proof bundle --
        logger.info("Exporting proof bundle")
        proof_result = bridge.export_proof(output_dir=proof_output_dir)

        if proof_result.get("success"):
            report.proof_bundle_path = proof_result["path"]
            logger.info(
                "Proof bundle exported: %s (%d actions, chain_hash=%s)",
                proof_result["path"],
                proof_result.get("action_count", 0),
                proof_result.get("chain_hash", "")[:16] + "...",
            )
        else:
            logger.warning("Proof export failed: %s", proof_result.get("error"))

    except Exception as exc:
        report.error = f"Audit failed with exception: {exc}"
        logger.exception("Compliance audit failed")
    finally:
        await bridge.stop()
        logger.info("Browser closed, audit complete")

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _print_report(report: ComplianceReport) -> None:
    """Pretty-print the compliance report to stdout."""
    sep = "=" * 64
    print(f"\n{sep}")
    print("  CONDUIT COMPLIANCE AUDIT REPORT")
    print(sep)
    print(f"  URL:        {report.url}")
    print(f"  Title:      {report.page_title}")
    print(f"  Timestamp:  {report.timestamp}")
    print(f"  Session:    {report.session_id}")
    print(sep)

    if report.error:
        print(f"\n  ERROR: {report.error}\n")

    print("\n  COMPLIANCE CHECKS:")
    print(f"  {'-' * 58}")

    for check in report.checks:
        icon = "[PASS]" if check.passed else "[FAIL]"
        print(f"    {icon} {check.name}")
        print(f"           {check.evidence}")

    print(f"\n  {'-' * 58}")
    print(f"  OVERALL SCORE: {report.overall_score}/100")
    print()

    if report.proof_bundle_path:
        print(f"  Proof bundle: {report.proof_bundle_path}")
        print("  Verify with:  tar xzf <bundle> && cd session_proof && python verify.py")
    else:
        print("  Proof bundle: (not generated)")

    print(f"\n{sep}")
    print("  Powered by Conduit | Agents earn money at swarmsync.ai")
    print(f"{sep}\n")


async def main(url: str = "https://example.com") -> ComplianceReport:
    """Run a compliance audit against *url* and print the report."""
    report = await run_compliance_audit(url)
    _print_report(report)

    # Also write machine-readable JSON alongside the human-readable output
    json_path = Path.home() / ".cato" / "proofs" / f"report_{report.session_id}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    logger.info("JSON report written to %s", json_path)

    return report


if __name__ == "__main__":
    import sys as _sys

    target = _sys.argv[1] if len(_sys.argv) > 1 else "https://example.com"
    asyncio.run(main(target))
