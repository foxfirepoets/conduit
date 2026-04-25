"""
demo_e2e_verification.py -- End-to-end buyer/seller/verifier demo.

WHAT THIS DOES:
  1. Buyer defines a specific job spec and pre-commits a rubric hash.
  2. Seller (this script) generates a deliverable that satisfies the spec.
  3. A local HTTP server serves the deliverable at a real URL.
  4. Conduit runs verify_deliverable()  -> exact SHA-256 hash check.
  5. Conduit runs verify_rubric()       -> predicate-based content check.
  6. Both results are printed in full so you can see the audit output.

USAGE:
  python demo_e2e_verification.py

No browser needed.  All verification uses the Python-primary path.
"""

from __future__ import annotations

import asyncio
import hashlib
import http.server
import json
import sys
import threading
import types
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Bootstrap the cato package shim so Conduit's relative imports work
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(__file__).resolve().parent

# Import rubric.py directly from its file so we don't fight with any
# other cato/tools package that might be on sys.path.
import importlib.util as _ilu

_rubric_spec = _ilu.spec_from_file_location(
    "conduit_rubric", CONDUIT_ROOT / "tools" / "rubric.py"
)
_rubric_mod = _ilu.module_from_spec(_rubric_spec)
_rubric_spec.loader.exec_module(_rubric_mod)
make_rubric_hash = _rubric_mod.make_rubric_hash
evaluate_rubric = _rubric_mod.evaluate_rubric


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def section(title: str) -> None:
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def pretty(label: str, data: Any) -> None:
    print(f"\n{label}:")
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Minimal local HTTP server (one file, served until we shut it down)
# ---------------------------------------------------------------------------

class _OneFileHandler(http.server.BaseHTTPRequestHandler):
    content: bytes = b""

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(self.__class__.content)))
        self.end_headers()
        self.wfile.write(self.__class__.content)

    def log_message(self, *_):
        pass  # silence access log


def start_local_server(content_bytes: bytes) -> tuple[http.server.HTTPServer, str]:
    _OneFileHandler.content = content_bytes
    server = http.server.HTTPServer(("127.0.0.1", 0), _OneFileHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/deliverable.txt"
    return server, url


# ---------------------------------------------------------------------------
# verify_deliverable() -- standalone (no browser required)
# ---------------------------------------------------------------------------
# We call the underlying logic directly since spinning up ConduitBridge
# requires Patchright.  The Python-primary path is pure stdlib.

import ipaddress
import socket
import urllib.request as _urllib_req
from urllib.request import HTTPRedirectHandler


def _block_private_ip(url: str) -> str:
    """Raises ValueError if url resolves to a private/loopback IP."""
    parsed = _urllib_req.urlparse(url) if hasattr(_urllib_req, "urlparse") else None
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError(f"DNS resolution failed for host: {host!r}")
    for info in infos:
        addr_str = info[4][0]
        try:
            ip = ipaddress.ip_address(addr_str)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(
                f"Blocked: {url!r} resolved to private/loopback IP {addr_str}"
            )
    return url


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _block_private_ip(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def python_verify_deliverable(
    url: str,
    expected_hash: str = "",
    request_id: str = "",
) -> dict:
    """Pure-Python verify_deliverable (no browser)."""
    # SSRF guard (demo exemption: 127.0.0.1 is allowed for local test server)
    # In production, _block_private_ip would reject this. We skip it here
    # because the demo server IS on localhost intentionally.
    try:
        opener = _urllib_req.build_opener(_SafeRedirectHandler)
        req = _urllib_req.Request(url, headers={"User-Agent": "ConduitVerify/1.0"})
        with opener.open(req, timeout=15) as resp:
            sha = hashlib.sha256()
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                sha.update(chunk)
            actual_hash = sha.hexdigest()
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "url": url,
            "actual_hash": "",
            "expected_hash": expected_hash,
            "hash_match": None,
            "deliverable_verified": False,
            "source": "python_fetch",
            "request_id": request_id,
        }

    hash_match: bool | None = None
    if expected_hash:
        hash_match = actual_hash.lower() == expected_hash.lower()

    return {
        "success": True,
        "url": url,
        "actual_hash": actual_hash,
        "expected_hash": expected_hash,
        "hash_match": hash_match,
        "deliverable_verified": hash_match is True,
        "source": "python_fetch",
        "request_id": request_id,
        "error": "",
    }


def python_verify_rubric(
    url: str,
    rubric: dict,
    rubric_hash: str,
    request_id: str,
) -> dict:
    """Pure-Python verify_rubric (no browser)."""
    # 1. Verify rubric was not tampered with
    recomputed = make_rubric_hash(rubric)
    if recomputed != rubric_hash:
        return {
            "success": False,
            "error": (
                f"rubric_hash mismatch -- provided {rubric_hash[:16]}..."
                f" but rubric hashes to {recomputed[:16]}..."
            ),
            "rubric_pass": False,
            "predicate_results": [],
            "rubric_hash": rubric_hash,
            "request_id": request_id,
        }

    # 2. Fetch content
    try:
        opener = _urllib_req.build_opener(_SafeRedirectHandler)
        req = _urllib_req.Request(url, headers={"User-Agent": "ConduitVerify/1.0"})
        with opener.open(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "rubric_pass": False,
            "predicate_results": [],
            "rubric_hash": rubric_hash,
            "request_id": request_id,
        }

    # 3. Evaluate predicates
    result = evaluate_rubric(content, rubric)
    return {
        "success": True,
        "url": url,
        "rubric_pass": result["rubric_pass"],
        "predicate_results": result["predicate_results"],
        "content_length": result["content_length"],
        "word_count": result["word_count"],
        "rubric_hash": rubric_hash,
        "request_id": request_id,
        "error": "",
    }


# ---------------------------------------------------------------------------
# The demo
# ---------------------------------------------------------------------------

def run_demo() -> None:

    # ================================================================
    # STEP 1: Buyer defines the job spec
    # ================================================================
    section("STEP 1 -- BUYER: Define job spec and pre-commit rubric")

    REQUEST_ID = "req_demo_20260416_001"

    BUYER_SPEC = {
        "job_title": "Product Comparison: Stripe vs. Paddle for SaaS",
        "format": "Markdown",
        "required_sections": [
            "## Overview",
            "## Pricing",
            "## Developer Experience",
            "## Recommendation",
        ],
        "required_mentions": ["Stripe", "Paddle", "revenue recognition", "checkout"],
        "forbidden_content": ["lorem ipsum", "placeholder", "TODO"],
        "word_count_range": [300, 1000],
        "content_type": "markdown",
    }

    RUBRIC: dict = {
        "min_word_count": 300,
        "max_word_count": 1000,
        "must_contain": ["Stripe", "Paddle", "revenue recognition", "checkout"],
        "must_not_contain": ["lorem ipsum", "placeholder", "TODO"],
        "content_type_hint": "markdown",
        "custom_checks": [
            # Deliverable must contain at least 2 markdown H2 headings
            "len(re.findall(r'^## ', content, re.MULTILINE)) >= 2",
        ],
    }

    # Buyer computes and stores this hash BEFORE the job is assigned
    RUBRIC_HASH = make_rubric_hash(RUBRIC)

    print(f"\nJob Title : {BUYER_SPEC['job_title']}")
    print(f"Request ID: {REQUEST_ID}")
    print(f"\nRubric (pre-committed by buyer):")
    print(json.dumps(RUBRIC, indent=2))
    print(f"\nRubric hash (stored on order): {RUBRIC_HASH}")
    print("\n[Buyer commits rubric hash to SwarmSync order. Work begins.]")

    # ================================================================
    # STEP 2: Seller generates the deliverable
    # ================================================================
    section("STEP 2 -- SELLER: Generate deliverable")

    DELIVERABLE = """\
## Overview

Stripe and Paddle are the two dominant payment platforms for SaaS businesses.
Both handle checkout flows, subscriptions, and global tax compliance, but they
differ significantly in pricing model, developer experience, and how they handle
revenue recognition. This comparison covers the factors that matter most when
choosing a payment stack for a new or growing SaaS product.

## Pricing

**Stripe** charges 2.9% + $0.30 per successful transaction in the US.
International cards add 1.5%, and currency conversion adds another 1%.
Stripe does not charge a monthly platform fee for the core product, but
advanced features such as Radar fraud detection, Revenue Recognition
(ASC 606 / IFRS 15 compliant), and Tax are billed separately and can
add meaningful cost at scale.

**Paddle** operates as a Merchant of Record (MoR), taking 5% + $0.50 per
transaction but covering VAT/GST collection, remittance, and revenue
recognition automatically. For companies selling in 50+ countries, the
compliance cost that Paddle absorbs often makes the effective rate
comparable to or lower than Stripe once you factor in the cost of a
dedicated finance team or third-party tax tools.

## Developer Experience

Stripe is widely regarded as the gold standard for developer experience.
Its API is consistent, versioned carefully, well-documented, and supported
by official SDKs in every major language. The checkout sessions API, webhook
infrastructure, and test mode environment are all first-class and
straightforward to integrate. The Stripe dashboard provides excellent
visibility into disputes, refunds, and subscription lifecycle events.

Paddle provides a hosted checkout that is simpler to integrate but less
customisable. The Paddle Billing API is modern and actively improving.
It lags Stripe in ecosystem breadth (third-party integrations, community
tooling, StackOverflow coverage), but the gap has narrowed significantly
since the 2023 product revamp.

## Recommendation

Choose **Stripe** if you are US/EU-focused, need deep customisation of the
checkout experience, and have engineering resources to manage tax compliance
separately. It is the better choice for enterprise deals where custom invoicing
and net-terms are required.

Choose **Paddle** if you sell globally at scale, want revenue recognition and
tax handled completely out of the box, and can accept a slightly higher
per-transaction rate in exchange for zero compliance overhead. It is the
faster path to compliant international revenue for lean teams.
"""

    content_bytes = DELIVERABLE.encode("utf-8")
    EXPECTED_HASH = sha256_of(DELIVERABLE)

    print(f"\nDeliverable length : {len(content_bytes)} bytes")
    print(f"Word count         : {len(DELIVERABLE.split())}")
    print(f"SHA-256 hash       : {EXPECTED_HASH}")
    print(f"\n--- BEGIN DELIVERABLE ---\n{DELIVERABLE}\n--- END DELIVERABLE ---")

    # ================================================================
    # STEP 3: Serve the deliverable over HTTP
    # ================================================================
    section("STEP 3 -- INFRASTRUCTURE: Serve deliverable at a real URL")

    server, DELIVERY_URL = start_local_server(content_bytes)
    print(f"\nDeliverable served at: {DELIVERY_URL}")

    # ================================================================
    # STEP 4: Conduit -- verify_deliverable (exact hash)
    # ================================================================
    section("STEP 4 -- CONDUIT: verify_deliverable (exact SHA-256 match)")

    vd_result = python_verify_deliverable(
        url=DELIVERY_URL,
        expected_hash=EXPECTED_HASH,
        request_id=REQUEST_ID,
    )
    pretty("verify_deliverable result", vd_result)

    print(f"\n>>> deliverable_verified = {vd_result['deliverable_verified']}")
    print(f"    hash_match           = {vd_result['hash_match']}")
    print(f"    source               = {vd_result['source']}")

    # ================================================================
    # STEP 5: Conduit -- verify_rubric (predicate check)
    # ================================================================
    section("STEP 5 -- CONDUIT: verify_rubric (rubric predicate evaluation)")

    vr_result = python_verify_rubric(
        url=DELIVERY_URL,
        rubric=RUBRIC,
        rubric_hash=RUBRIC_HASH,
        request_id=REQUEST_ID,
    )

    # Print summary first
    print(f"\n>>> rubric_pass    = {vr_result['rubric_pass']}")
    print(f"    word_count     = {vr_result.get('word_count')}")
    print(f"    content_length = {vr_result.get('content_length')}")
    print(f"    request_id     = {vr_result['request_id']}")
    print(f"    rubric_hash    = {vr_result['rubric_hash'][:32]}...")

    print("\nPredicate-by-predicate results:")
    for p in vr_result.get("predicate_results", []):
        icon = "PASS" if p["passed"] else "FAIL"
        print(f"  [{icon}] [{p['predicate']}] {p['reason']}")

    pretty("\nFull verify_rubric result", vr_result)

    # ================================================================
    # STEP 6: Demonstrate a FAILING deliverable
    # ================================================================
    section("STEP 6 -- DEMONSTRATION: Reject a bad deliverable")

    BAD_DELIVERABLE = """\
## Overview

This is a placeholder document. TODO: add real content.
"""
    bad_bytes = BAD_DELIVERABLE.encode("utf-8")
    bad_hash = sha256_of(BAD_DELIVERABLE)

    server2, bad_url = start_local_server(bad_bytes)
    print(f"\nBad deliverable served at: {bad_url}")
    print(f"Content preview: {BAD_DELIVERABLE[:80].strip()}")

    # verify_deliverable: hash won't match
    vd_bad = python_verify_deliverable(
        url=bad_url,
        expected_hash=EXPECTED_HASH,  # buyer's original hash
        request_id=REQUEST_ID,
    )
    print(f"\nverify_deliverable -> hash_match = {vd_bad['hash_match']}  "
          f"(actual={vd_bad['actual_hash'][:16]}..., expected={EXPECTED_HASH[:16]}...)")

    # verify_rubric: will fail multiple predicates
    vr_bad = python_verify_rubric(
        url=bad_url,
        rubric=RUBRIC,
        rubric_hash=RUBRIC_HASH,
        request_id=REQUEST_ID,
    )
    print(f"\nverify_rubric -> rubric_pass = {vr_bad['rubric_pass']}")
    print("Predicate results for bad deliverable:")
    for p in vr_bad.get("predicate_results", []):
        icon = "PASS" if p["passed"] else "FAIL"
        print(f"  [{icon}] [{p['predicate']}] {p['reason']}")

    # ================================================================
    # DONE
    # ================================================================
    section("SUMMARY")
    print(f"""
  Request ID   : {REQUEST_ID}
  Job           : {BUYER_SPEC['job_title']}

  GOOD deliverable:
    verify_deliverable -> deliverable_verified = {vd_result['deliverable_verified']}
    verify_rubric      -> rubric_pass          = {vr_result['rubric_pass']}
    -> ESCROW RELEASE APPROVED

  BAD deliverable:
    verify_deliverable -> deliverable_verified = {vd_bad['deliverable_verified']}
    verify_rubric      -> rubric_pass          = {vr_bad['rubric_pass']}
    -> ESCROW HELD -- dispute window opens
""")

    server.shutdown()
    server2.shutdown()


if __name__ == "__main__":
    run_demo()
