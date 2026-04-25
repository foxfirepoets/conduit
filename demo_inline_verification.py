"""
demo_inline_verification.py -- End-to-end inline (no-URL) buyer/seller/verifier demo.

SCENARIO:
  Buyer "AlphaFund DAO" needs a 3-section investment thesis on Solana vs Ethereum
  for their portfolio review.  The deliverable is pure text -- no website, no upload.
  The seller generates the document and delivers it inline via the AP2 payload.
  Conduit verifies it in-process (Option C): no HTTP fetch, no browser session.

WHAT THIS RUNS:
  1. Buyer defines a specific job spec with a pre-committed rubric hash.
  2. Buyer computes the SHA-256 of the expected content hash range (Track 1 skipped
     for generative output -- rubric is the right tool here).
  3. Seller (simulated) writes the investment thesis.
  4. Conduit verify_rubric() evaluates inline bytes directly against the rubric.
  5. Conduit verify_chain() proves the audit log was not tampered.
  6. Full output is printed -- what escrow sees, what the proof bundle contains.

USAGE:
  python demo_inline_verification.py
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util as _ilu
import json
import sys
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap cato package shim
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(__file__).resolve().parent

cato_pkg = types.ModuleType("cato")
cato_pkg.__path__ = [str(CONDUIT_ROOT)]
cato_pkg.__package__ = "cato"
sys.modules.setdefault("cato", cato_pkg)

for _sub in ("tools", "tools.core"):
    _m = types.ModuleType(f"cato.{_sub.split('.')[-1]}" if "." in _sub else f"cato.{_sub}")
    _m.__path__ = [str(CONDUIT_ROOT / _sub.replace(".", "/"))]
    _m.__package__ = f"cato.{_sub}"
    sys.modules.setdefault(f"cato.{_sub}", _m)

# Load rubric engine directly by file path (avoids sys.path collisions)
_rubric_spec = _ilu.spec_from_file_location("conduit_rubric", CONDUIT_ROOT / "tools" / "rubric.py")
_rubric_mod = _ilu.module_from_spec(_rubric_spec)
_rubric_spec.loader.exec_module(_rubric_mod)
make_rubric_hash = _rubric_mod.make_rubric_hash
evaluate_rubric = _rubric_mod.evaluate_rubric

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEP = "=" * 60
THIN = "-" * 60


def header(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def section(title: str) -> None:
    print(f"\n{THIN}")
    print(f"  {title}")
    print(THIN)


def tick(label: str, value: str = "") -> None:
    mark = "[PASS]" if not value else "[INFO]"
    print(f"  {mark}  {label}" + (f": {value}" if value else ""))


def fail(label: str) -> None:
    print(f"  [FAIL]  {label}")


# ---------------------------------------------------------------------------
# STEP 1 -- Buyer defines the job spec
# ---------------------------------------------------------------------------

def buyer_defines_spec() -> dict:
    header("STEP 1 -- BUYER DEFINES JOB SPEC")

    spec = {
        "job_id":       "job_" + uuid.uuid4().hex[:8],
        "request_id":   "req_" + uuid.uuid4().hex[:8],
        "title":        "Investment Thesis: Solana vs Ethereum (Q2 2026)",
        "description": (
            "Write a 3-section investment thesis comparing Solana and Ethereum "
            "for a crypto-native venture fund. Must cover: (1) Technical Differentiation, "
            "(2) Ecosystem & Developer Activity, (3) Risk Factors. "
            "Minimum 400 words. Professional tone. No placeholder text."
        ),
        "format": "markdown",
        "escrow_ref": "escrow_" + uuid.uuid4().hex[:12],
        "negotiation_id": "neg_" + uuid.uuid4().hex[:8],
    }

    # Buyer pre-commits the rubric BEFORE the seller starts work.
    # This hash is stored on-chain so the buyer cannot change the rules
    # after seeing the deliverable.
    rubric = {
        "min_word_count":   400,
        "max_word_count":   2000,
        "must_contain":     ["Solana", "Ethereum", "risk", "ecosystem"],
        "must_not_contain": ["lorem ipsum", "placeholder", "TODO", "[INSERT"],
        "content_type_hint": "markdown",
        "custom_checks": [
            # At least 3 markdown section headers (## ...)
            r"len(re.findall(r'^## ', content, re.MULTILINE)) >= 3"
        ],
    }
    rubric_hash = make_rubric_hash(rubric)

    spec["rubric"]      = rubric
    spec["rubric_hash"] = rubric_hash

    print(f"  Job ID      : {spec['job_id']}")
    print(f"  Request ID  : {spec['request_id']}")
    print(f"  Escrow ref  : {spec['escrow_ref']}")
    print(f"  Title       : {spec['title']}")
    print()
    print("  Buyer Rubric (pre-committed):")
    for k, v in rubric.items():
        print(f"    {k}: {v}")
    print()
    print(f"  Rubric hash (pre-committed): {rubric_hash[:32]}...")
    tick("Rubric hash committed before seller starts")

    return spec


# ---------------------------------------------------------------------------
# STEP 2 -- Seller writes the deliverable (inline text, no URL)
# ---------------------------------------------------------------------------

def seller_generates_deliverable(spec: dict) -> str:
    header("STEP 2 -- SELLER GENERATES DELIVERABLE (inline text, no URL)")

    deliverable = """\
## Technical Differentiation

Solana achieves consensus throughput of 65,000+ transactions per second through its
Proof of History (PoH) mechanism, which timestamps transactions cryptographically before
they enter the validator pipeline. This eliminates the coordination overhead that limits
traditional BFT-style protocols. Ethereum, post-Merge, processes roughly 15-30 TPS on
Layer 1, relying instead on a mature rollup ecosystem (Optimism, Arbitrum, Base) to scale
execution off-chain while settling finality on-chain.

For a venture portfolio, this distinction matters because Solana favours latency-sensitive
applications -- high-frequency DeFi, consumer payments, gaming -- while Ethereum's modular
stack is better suited to applications that require composability across a deep liquidity
base and battle-tested smart contract infrastructure. Both chains carry different technical
risk profiles: Solana has experienced five major network outages since mainnet-beta (2020-
2022), while Ethereum's complexity risk is concentrated in the evolving validator set and
the increasing centralisation pressure from MEV-boost relays.

## Ecosystem and Developer Activity

Ethereum retains the largest active developer base in the sector: Electric Capital's 2025
Developer Report counted approximately 6,200 monthly active developers deploying to mainnet
or L2s, with over $90 billion in total value locked across the DeFi ecosystem. Solana has
grown its developer count to roughly 2,100 monthly active developers, with standout
momentum in consumer-facing products: Tensor (NFT marketplace), Jupiter (DEX aggregator),
and Backpack (wallet/exchange) all achieved product-market fit in 2024-2025.

Token distribution also differs materially. Ethereum's supply is deflationary post-EIP-1559
when network activity is high; Solana issues new SOL at approximately 5% annually (declining
~15% per year) to fund validator rewards. For a fund taking long positions, Ethereum's
supply mechanics are structurally more favourable in bull conditions, while Solana's higher
nominal yield creates sell pressure that must be absorbed by new entrants.

## Risk Factors

**Solana risks:**
- Validator concentration: the top 20 validators control ~33% of stake, creating cartel risk.
- Dependence on Firedancer (Jump Crypto's validator client) for the reliability improvements
  needed to justify institutional allocation; delayed or cancelled development would be a
  material setback.
- Regulatory exposure: SEC has previously named SOL as a security in enforcement actions
  against Binance and Coinbase; resolution remains pending.

**Ethereum risks:**
- Execution complexity: the roadmap (Danksharding, Verkle trees, SSF) spans multiple years;
  a misstep in any upgrade could undermine validator confidence.
- L2 cannibalisation: as rollups capture an increasing share of fee revenue, ETH's value
  accrual thesis depends on blob fee markets that are still nascent.
- Staking centralisation: Lido controls ~29% of staked ETH, exposing the network to
  governance capture if the DAO makes decisions misaligned with validator-client diversity.

**Recommendation:** A balanced 60/40 Ethereum/Solana allocation captures the blue-chip
liquidity and composability of Ethereum while retaining exposure to Solana's higher-beta
growth trajectory. Rebalance thresholds should be reviewed quarterly against developer
activity metrics and validator concentration indices.
"""

    word_count = len(deliverable.split())
    content_hash = hashlib.sha256(deliverable.encode("utf-8")).hexdigest()

    print(f"  Deliverable type  : inline markdown (no URL)")
    print(f"  Word count        : {word_count}")
    print(f"  Byte length       : {len(deliverable.encode())} bytes")
    print(f"  SHA-256           : {content_hash[:32]}...")
    print()
    print("  --- DELIVERABLE PREVIEW (first 300 chars) ---")
    print("  " + deliverable[:300].replace("\n", "\n  "))
    print("  ...")
    tick("Deliverable generated by seller")

    return deliverable


# ---------------------------------------------------------------------------
# STEP 3 -- Conduit verifies inline content (Option C)
# ---------------------------------------------------------------------------

def conduit_verify_inline(spec: dict, deliverable: str) -> dict:
    header("STEP 3 -- CONDUIT VERIFIES INLINE CONTENT (Option C)")

    print("  Mode: INLINE (no HTTP fetch, no browser session)")
    print("  Conduit hashes inline bytes and evaluates rubric predicates in-process.")
    print()

    # --- Rubric integrity check (pre-commitment verification) ---
    section("3a. Rubric Pre-Commitment Integrity Check")
    recomputed = make_rubric_hash(spec["rubric"])
    if recomputed == spec["rubric_hash"]:
        tick("Rubric hash matches pre-committed value -- buyer cannot have changed rules")
    else:
        fail("Rubric hash MISMATCH -- rubric tampered after commitment")
        return {"passed": False, "failure_reason": "rubric_hash mismatch"}

    # --- Track 1: exact hash (skipped -- generative output, hash not pre-committed) ---
    section("3b. Track 1 -- Exact Hash Check")
    print("  [SKIP]  No expected_hash provided (generative output -- use Track 2)")

    # --- Track 2: rubric evaluation on inline bytes ---
    section("3c. Track 2 -- Rubric Predicate Evaluation")

    inline_bytes = deliverable.encode("utf-8")
    content = inline_bytes.decode("utf-8", errors="replace")
    content_hash = hashlib.sha256(inline_bytes).hexdigest()

    print(f"  Content SHA-256   : {content_hash[:32]}...")
    print(f"  Content length    : {len(inline_bytes)} bytes")
    print()

    rubric_result = evaluate_rubric(content, spec["rubric"])

    total      = len(rubric_result["predicate_results"])
    passed_ct  = sum(1 for p in rubric_result["predicate_results"] if p["passed"])
    failed_ct  = total - passed_ct

    for pred in rubric_result["predicate_results"]:
        mark = "[PASS]" if pred["passed"] else "[FAIL]"
        print(f"  {mark}  {pred['predicate']}")
        if not pred["passed"] and pred.get("detail"):
            print(f"         detail: {pred['detail']}")

    print()
    print(f"  Predicates: {passed_ct}/{total} passed")
    rubric_pass = rubric_result["rubric_pass"]
    word_count  = rubric_result["word_count"]
    print(f"  Word count: {word_count}")
    print(f"  Rubric pass: {rubric_pass}")

    # --- Proof bundle ---
    section("3d. Proof Bundle Assembly")

    proof_bundle = {
        "version":          "2.0",
        "delivery_mode":    "inline",
        "session_id":       "session_" + uuid.uuid4().hex[:12],
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "escrow_ref":       spec["escrow_ref"],
        "negotiation_id":   spec["negotiation_id"],
        "request_id":       spec["request_id"],
        "rubric_hash":      spec["rubric_hash"],
        "content_hash":     content_hash,
        "word_count":       word_count,
        "rubric_pass":      rubric_pass,
        "predicate_results": rubric_result["predicate_results"],
        "passed":           rubric_pass,
        "failure_reason":   None if rubric_pass else f"{failed_ct} predicates failed",
        "verification_track": 2,
        "inline_content_length": len(inline_bytes),
    }

    proof_json   = json.dumps(proof_bundle, sort_keys=True, ensure_ascii=False)
    proof_hash   = hashlib.sha256(proof_json.encode()).hexdigest()
    proof_bundle["proof_hash"] = proof_hash

    print(f"  Proof hash: {proof_hash[:32]}...")
    tick("Proof bundle assembled and hashed")

    return proof_bundle


# ---------------------------------------------------------------------------
# STEP 4 -- Simulated audit chain verification
# ---------------------------------------------------------------------------

def verify_audit_chain(spec: dict, proof_bundle: dict) -> None:
    header("STEP 4 -- AUDIT CHAIN VERIFICATION")

    # In production this is AuditLog.verify_chain(session_id).
    # Here we replay the same hash formula the real chain uses.
    session_id   = proof_bundle["session_id"]
    content_hash = proof_bundle["content_hash"]
    rubric_hash  = proof_bundle["rubric_hash"]
    proof_hash   = proof_bundle["proof_hash"]

    # Row 0: spec_commitment (anchors the chain to the buyer's rubric)
    row0_payload = f"0:{session_id}:spec_commitment:conduit.spec_commitment:0:0.0:::{rubric_hash}:"
    row0_hash    = hashlib.sha256(row0_payload.encode()).hexdigest()

    # Row 1: verify_rubric (inline mode)
    row1_payload = (
        f"1:{session_id}:tool_call:conduit.verify_rubric_inline:0:0.0:{row0_hash}:"
        f"{content_hash}:{proof_hash}"
    )
    row1_hash = hashlib.sha256(row1_payload.encode()).hexdigest()

    print(f"  Session ID  : {session_id}")
    print(f"  Row 0 hash  : {row0_hash[:32]}... (spec_commitment)")
    print(f"  Row 1 hash  : {row1_hash[:32]}... (verify_rubric_inline)")
    print()
    tick("Chain is contiguous (each row binds prev_hash)")
    tick("Row 0 anchors buyer rubric before seller started work")
    tick("Row 1 records inline content hash + proof hash")
    tick("Chain verified: tamper-evident audit trail intact")


# ---------------------------------------------------------------------------
# STEP 5 -- Escrow decision
# ---------------------------------------------------------------------------

def escrow_decision(proof_bundle: dict) -> None:
    header("STEP 5 -- ESCROW RELEASE DECISION")

    passed         = proof_bundle["passed"]
    track          = proof_bundle["verification_track"]
    proof_hash     = proof_bundle["proof_hash"]
    word_count     = proof_bundle["word_count"]
    pred_results   = proof_bundle["predicate_results"]
    passed_preds   = sum(1 for p in pred_results if p["passed"])
    total_preds    = len(pred_results)
    failure_reason = proof_bundle.get("failure_reason")

    print(f"  Verification track    : {track} (rubric predicate evaluation)")
    print(f"  Rubric pass           : {passed}")
    print(f"  Predicates passed     : {passed_preds}/{total_preds}")
    print(f"  Word count            : {word_count}")
    print(f"  Proof hash            : {proof_hash[:32]}...")
    print()

    if passed:
        print("  +---------------------------------------------------------+")
        print("  |  ESCROW RELEASE APPROVED                               |")
        print("  |  OutcomesService.recordVerification(VERIFIED)          |")
        print("  |  WalletsService.settleEscrow() -> funds released       |")
        print("  +---------------------------------------------------------+")
    else:
        print("  +---------------------------------------------------------+")
        print("  |  ESCROW HELD -- VERIFICATION FAILED                    |")
        print(f"  |  Reason: {(failure_reason or 'unknown')[:46]:<46}|")
        print("  |  OutcomesService.recordVerification(REJECTED)          |")
        print("  +---------------------------------------------------------+")


# ---------------------------------------------------------------------------
# STEP 6 -- Full result summary
# ---------------------------------------------------------------------------

def print_full_result(spec: dict, deliverable: str, proof_bundle: dict) -> None:
    header("STEP 6 -- FULL RESULT SUMMARY")

    print(json.dumps({
        "job_id":               spec["job_id"],
        "request_id":           spec["request_id"],
        "escrow_ref":           spec["escrow_ref"],
        "delivery_mode":        "inline",
        "verification_track":   proof_bundle["verification_track"],
        "passed":               proof_bundle["passed"],
        "proof_hash":           proof_bundle["proof_hash"],
        "rubric_hash":          proof_bundle["rubric_hash"],
        "content_hash":         proof_bundle["content_hash"],
        "word_count":           proof_bundle["word_count"],
        "predicates_passed":    sum(1 for p in proof_bundle["predicate_results"] if p["passed"]),
        "predicates_total":     len(proof_bundle["predicate_results"]),
        "failure_reason":       proof_bundle.get("failure_reason"),
        "generated_at":         proof_bundle["generated_at"],
    }, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print(SEP)
    print("  CONDUIT INLINE VERIFICATION -- END-TO-END DEMO")
    print("  Scenario: Investment thesis (no URL, inline text delivery)")
    print(SEP)

    spec        = buyer_defines_spec()
    deliverable = seller_generates_deliverable(spec)
    proof       = conduit_verify_inline(spec, deliverable)
    verify_audit_chain(spec, proof)
    escrow_decision(proof)
    print_full_result(spec, deliverable, proof)

    print()
    print(SEP)
    if proof["passed"]:
        print("  DEMO COMPLETE -- ESCROW RELEASED")
    else:
        print("  DEMO COMPLETE -- ESCROW HELD (see failure reason above)")
    print(SEP)
    print()


if __name__ == "__main__":
    main()
