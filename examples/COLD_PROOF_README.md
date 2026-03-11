# Cold Proof Outbound

A cold outreach strategy built on Conduit's tamper-evident audit trail.
Instead of sending a pitch, you send proof.

---

## The Pharma Free-Sample Analogy

Pharmaceutical reps do not cold-call doctors and describe a drug.
They hand the doctor a physical sample.
The doctor experiences the product directly.
That experience is the pitch.

Cold Proof works the same way.

This agent audits a prospect's public website and packages the result into a
self-verifiable proof bundle.  The prospect receives the bundle, runs one
command with zero dependencies, and watches the Ed25519 signature verify
against the SHA-256 hash chain in real time.  They experience Conduit before
reading a single line of marketing copy.

The free sample IS the pitch.

---

## What the Agent Does

1. Navigates to the target URL in a headless Chromium browser.
2. Extracts main page content and scans for compliance signals (HTTPS, privacy
   policy, cookie consent, contact information).
3. Evaluates `performance.timing` via JavaScript to measure TTFB, DOM load
   time, and full page load time and assigns a letter grade.
4. Detects cookie consent DOM elements via JavaScript attribute scanning.
5. Confirms SSL/protocol via `window.location.protocol`.
6. Takes a screenshot as visual evidence.
7. Fingerprints the page with a SHA-256 content hash.
8. Exports every action into a self-verifiable `.tar.gz` proof bundle signed
   with an Ed25519 key.

All seven browser actions are written to a SHA-256 hash chain.  The chain and
signature live inside the bundle.  The recipient verifies both without
installing anything.

---

## How to Run It

```bash
# Basic usage
python examples/cold_proof_agent.py --url https://target.com

# Specify an output directory for the proof bundle
python examples/cold_proof_agent.py --url https://target.com --output-dir /tmp/proofs

# Also write a machine-readable JSON report
python examples/cold_proof_agent.py --url https://target.com --json

# Custom session ID (useful for tracking which prospect triggered which audit)
python examples/cold_proof_agent.py --url https://target.com --session-id acme-2026-03

# Full example with all options
python examples/cold_proof_agent.py \
    --url https://target.com \
    --output-dir /tmp/proofs \
    --session-id acme-outbound \
    --budget 200 \
    --json
```

The agent prints a structured summary to stdout and writes the proof bundle to
`~/.cato/proofs/` (or `--output-dir` if provided).

---

## What the Recipient Gets

The proof bundle is a `.tar.gz` archive.  Inside:

```
session_proof/
    audit_log.json      -- every browser action in order (JSON array)
    chain.json          -- SHA-256 hash chain linking each action
    signature.bin       -- Ed25519 signature over the chain root hash
    public_key.pem      -- the public key that verifies the signature
    verify.py           -- stdlib-only verifier (no pip install needed)
    screenshot.png      -- full-page screenshot taken during the audit
```

The recipient runs:

```bash
tar xzf session_proof.tar.gz
cd session_proof
python verify.py
```

`verify.py` uses only Python standard library modules.  It re-walks the hash
chain, recomputes the root hash, and verifies it against the Ed25519 signature.
Output is a clear pass/fail verdict with the chain hash and public key printed.

This is the moment the prospect understands what Conduit is.

---

## How to Use It for Marketing

### Step 1 — Run the agent against the prospect's website

```bash
python examples/cold_proof_agent.py --url https://prospect.com --session-id prospect-slug
```

### Step 2 — Locate the proof bundle

The bundle path is printed at the end of the summary:

```
  Proof bundle : /home/you/.cato/proofs/coldproof-a3f9b2c1d7e0.tar.gz
```

### Step 3 — Send the email

Attach the `.tar.gz` file and send this email:

---

**Subject:** Free security audit of [domain]

We used Conduit to audit your public website and signed the result with Ed25519.
The attached proof bundle is self-verifiable -- run `python verify.py` with zero dependencies.
If this is useful for your team, imagine what your agents could produce for your clients.

GitHub: https://github.com/bkauto3/Conduit

---

That is the entire outreach sequence.  Three sentences.  One attachment.

The prospect either runs `python verify.py` and gets curious, or they do not.
Either outcome is informative and requires no follow-up.

---

## Reading the Summary Output

```
================================================================
  CONDUIT COLD PROOF AUDIT
================================================================
  URL:        https://example.com
  Domain:     example.com
  Title:      Example Domain
  Timestamp:  2026-03-11T14:22:05Z
  Session:    coldproof-a3f9b2c1d7e0
================================================================

  PAGE PERFORMANCE:
    TTFB (time-to-first-byte) : 143 ms
    DOM Content Loaded        : 421 ms
    Full Load                 : 512 ms
    Redirect count            : 0
    Performance grade         : A

  COMPLIANCE SURFACE:
    [YES]  HTTPS enforced
    [YES]  Privacy policy reference found
    [NO ]  Cookie consent elements (0 found)
    [YES]  Contact information found

  PAGE FINGERPRINT (SHA-256):
    a1b2c3d4e5f6...

  PROOF BUNDLE:
    Actions recorded : 7
    Bundle path      : /home/you/.cato/proofs/coldproof-a3f9b2c1d7e0.tar.gz
    Verify with      : tar xzf <bundle> && cd session_proof && python verify.py

================================================================
  Powered by Conduit | Agents earn money at swarmsync.ai
================================================================
```

Performance grades follow Google's Core Web Vitals TTFB thresholds:
- A = under 200 ms
- B = 200-499 ms
- C = 500-999 ms
- D = 1000-1999 ms
- F = 2000 ms or above

---

## Why This Works

Cold outreach fails because it asks for attention before delivering value.
Cold Proof inverts the order.  Value is delivered first, in the form of a
cryptographically signed audit of the prospect's own infrastructure.

The proof bundle is concrete, specific to their domain, and verifiable without
trusting you.  It demonstrates technical credibility without a sales call.
And it shows — not tells — what Conduit's tamper-evident audit trail feels like
to a recipient.

---

## Requirements

- Python 3.10 or later
- Conduit dependencies installed (`pip install -r requirements.txt` from the
  repo root)
- A working internet connection for the target URL

The proof bundle recipient needs only Python 3 (any version with the standard
library).  No additional packages required.

---

## Related

- `examples/compliance_auditor.py` -- full five-check compliance audit agent
- `tools/conduit_bridge.py` -- ConduitBridge API reference
- `tools/conduit_proof.py` -- proof bundle implementation
- `skills/conduit.md` -- complete action reference for agents consuming Conduit
