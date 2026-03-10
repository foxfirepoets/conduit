# Conduit

**The only headless browser with a cryptographic audit layer.**

Every action Conduit takes — every click, every navigation, every JavaScript execution — is written to a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and verifiable by anyone with zero dependencies. No other headless browser does this.

---

## Why Conduit Instead of Playwright, Puppeteer, or Selenium?

| Feature | Conduit | Playwright | Puppeteer | Selenium |
|---|---|---|---|---|
| SHA-256 hash-chained audit log | ✅ | ❌ | ❌ | ❌ |
| JavaScript source stored in audit chain | ✅ | ❌ | ❌ | ❌ |
| Ed25519-signed session proofs | ✅ | ❌ | ❌ | ❌ |
| Self-verifiable proof bundles (zero deps) | ✅ | ❌ | ❌ | ❌ |
| Tamper detection on any past action | ✅ | ❌ | ❌ | ❌ |
| Built-in stealth (Patchright fork) | ✅ | ❌ | ❌ | ❌ |
| Robots.txt compliant BFS crawler | ✅ | ❌ | ❌ | ❌ |
| Page change fingerprinting (SHA-256) | ✅ | ❌ | ❌ | ❌ |
| Multi-engine web search built-in | ✅ | ❌ | ❌ | ❌ |
| Sensitive input auto-redaction | ✅ | ❌ | ❌ | ❌ |
| Billing ledger + cost enforcement | ✅ | ❌ | ❌ | ❌ |

The gap isn't features — it's **trust**. Playwright gives you automation. Conduit gives you automation you can **prove**.

---

## The Core Differentiator: Cryptographic Proof of What Ran

When you call `eval` on any other browser tool, you get a result back. You have no record of what code actually executed. Conduit is different:

```python
bridge.execute({"action": "eval", "js": "document.querySelectorAll('h1').length"})
```

The full JavaScript source is stored **verbatim in the audit hash chain**:

```json
{
  "id": 7,
  "session_id": "sess-abc123",
  "action_type": "tool_call",
  "tool_name": "browser.eval",
  "inputs_json": "{\"js_code\": \"document.querySelectorAll('h1').length\"}",
  "outputs_json": "{\"success\": true, \"result\": 3, \"code_hash\": \"a3f9...\"}",
  "timestamp": 1741564800.123,
  "prev_hash": "e8d2c4...",
  "row_hash": "7b1a3f..."
}
```

Row 8's hash depends on row 7's hash. Row 7's hash depends on row 6's. Change any row — any input, any output, any timestamp — and the entire chain breaks. `verify_chain()` will catch it.

This is cryptographic proof of **exactly which code executed**, not just that code ran.

---

## Session Proof Bundles

At any point, call `export_proof` to generate a self-verifiable `.tar.gz` bundle:

```python
bridge.execute({"action": "export_proof"})
# → ~/.cato/proofs/conduit_proof_sess-abc123_20260310.tar.gz
```

The bundle contains:

```
session_proof/
├── audit_log.jsonl      # Full hash-chained log (one JSON record per line)
├── manifest.json        # Session metadata + final chain hash
├── public_key.pem       # Ed25519 public key
├── session_sig.txt      # Ed25519 signature over final chain hash
└── verify.py            # Self-contained verifier — stdlib only, zero dependencies
```

Anyone can verify the proof with Python's standard library:

```bash
cd session_proof
python verify.py
# Chain OK (47 actions verified)
# Signature OK
```

No pip. No npm. No external libraries. Pure stdlib. The verification logic ships inside the bundle.

---

## Architecture

```
Agent / Your Code
        │
        ▼
  ConduitBridge          ← single entry point, Ed25519 signing, budget enforcement
        │
   ┌────┴────┐
   │         │
BrowserTool  Crawlers / Monitors / Proofs
(Patchright) (ConduitCrawler, ConduitMonitor, ConduitProof)
   │
   ▼
 _audit()               ← ONLY write point — writes to BOTH tables atomically
   │
   ├── conduit_billing  ← cost ledger (ConduitBillingLedger)
   └── audit_log        ← SHA-256 hash chain (AuditLog)
```

**The two-layer write path is a hard architectural constraint.** No action method ever calls `_ledger.record()` or `_audit_log.log()` directly. Everything flows through `_audit()`. This guarantees the billing ledger and audit chain are always in sync.

---

## Action Waves

### Wave 0 — Core Browser
`navigate` · `click` · `type` · `fill` · `extract` · `screenshot`

### Wave 1 — Interaction
`scroll` · `wait` · `wait_for` · `key_press` · `hover` · `select_option` · `handle_dialog` · `navigate_back` · `console_messages`

### Wave 2 — Extraction (Conduit-Exclusive)
- **`eval`** — Execute JavaScript. Full source stored in hash chain.
- **`extract_main`** — Readability-style extraction, strips nav/ads/footers. Optional Markdown output.
- **`extract_structured`** — Main content + JSON schema validation.
- **`output_to_file`** — Write to workspace. Path-safe (no directory traversal).
- **`accessibility_snapshot`** — Full Playwright accessibility tree.
- **`network_requests`** — Accumulated network log since last call.

### Wave 3 — Advanced (Conduit-Exclusive)
- **`map`** — BFS site discovery, robots.txt compliant. Returns all reachable URLs.
- **`crawl`** — Bulk BFS extraction up to `max_depth`. Per-page: title, text, depth.
- **`fingerprint`** — SHA-256 page fingerprint (normalizes timestamps/nonces to avoid false positives).
- **`check_changed`** — Re-fingerprint URL. If changed, logs signed `PAGE_MUTATION` event.
- **`export_proof`** — Generate self-verifiable `.tar.gz` proof bundle.

### Wave 4 — CAPTCHA
`detect_captcha` · `solve_captcha` · `solve_captcha_vision`

### Wave 5 — Proxy
`rotate_proxy`

### Wave 6 — Web Search (Built-In)
- **`web_search`** — Multi-engine: DuckDuckGo, Brave, Exa, Tavily. Query-type routing (code → exa+brave, news → tavily+brave, general → brave+ddg).
- **`academic_search`** — Semantic Scholar + arXiv.

---

## Quick Start

```python
import asyncio
from tools.conduit_bridge import ConduitBridge

async def main():
    bridge = ConduitBridge()

    # Navigate and extract
    result = await bridge.execute({"action": "navigate", "url": "https://example.com"})
    print(result["title"])

    # Extract main content (strips nav/ads/footers)
    content = await bridge.execute({"action": "extract_main", "fmt": "md"})
    print(content["text"])

    # Execute JavaScript — source stored in audit chain
    js_result = await bridge.execute({
        "action": "eval",
        "js": "Array.from(document.links).map(l => l.href)"
    })

    # BFS crawl an entire site
    pages = await bridge.execute({
        "action": "crawl",
        "url": "https://docs.example.com",
        "max_depth": 2,
        "limit": 50
    })

    # Fingerprint a page and watch for changes
    fp = await bridge.execute({"action": "fingerprint", "url": "https://example.com"})
    changed = await bridge.execute({
        "action": "check_changed",
        "url": "https://example.com",
        "prev_fingerprint": fp["fingerprint"]
    })

    # Export cryptographic proof of the entire session
    proof = await bridge.execute({"action": "export_proof"})
    print(f"Proof bundle: {proof['path']}")
    print(f"Chain hash: {proof['chain_hash']}")

asyncio.run(main())
```

---

## Storage Layout

All runtime data lives under `~/.cato/`:

```
~/.cato/
├── cato.db                    # SQLite: audit_log + conduit_billing tables
├── conduit_identity.key       # Ed25519 private key (chmod 600)
├── workspace/
│   ├── screenshots/           # PNG screenshots
│   ├── pdfs/                  # PDF exports
│   └── .conduit/              # output_to_file outputs
├── proofs/                    # Exported proof bundles (.tar.gz)
├── browser_profile/           # Persistent Chromium profile
└── sessions/                  # Session data
```

---

## Security Design

**What Conduit logs:**
- Full inputs to every action (with sensitive keys auto-redacted)
- Full outputs from every action
- Timestamps, session IDs, costs
- The complete JavaScript source of every `eval` call
- The SHA-256 fingerprint of every page visited via `fingerprint`

**Auto-redacted keys** (value replaced with `[REDACTED]` before logging):
`password` · `token` · `api_key` · `secret` · `key` · `authorization` · `bearer` · `credential` · `passwd` · `passphrase`

**Navigation restrictions:**
- HTTP/HTTPS only — no `file://`, `data://`, `javascript://` schemes
- RFC-1918 and loopback IPs blocked — no SSRF via browser

**Crawlers:**
- Always check `robots.txt` before visiting any URL
- Honor `Crawl-delay` directives
- Exponential backoff on 429/503, logged as `RATE_LIMITED` events

---

## Running Tests

```bash
# All tests
pytest tests/

# Specific file
pytest tests/test_audit_chain.py -v

# Specific test
pytest tests/test_audit_chain.py::TestAuditLog::test_verify_chain_true_after_sequence -v
```

Tests use `pytest-asyncio`. No real browser is launched — all Patchright calls are mocked via `AsyncMock`. The package shim in `tests/conftest.py` makes the relative imports work without installing the package.

---

## Use Cases

**Compliance automation** — Need to prove a specific form was filled with specific values at a specific time? Export a proof bundle. The chain hash is your receipt.

**Security research** — Documenting what JS a page injected, what network requests it made, what the DOM looked like at each step — all signed and chained.

**AI agent browser control** — Designed as the browser engine for autonomous agents. Budget enforcement prevents runaway costs. The audit trail lets you replay and inspect exactly what the agent did.

**Web monitoring** — `fingerprint` + `check_changed` + `watch` gives you signed change detection with cryptographic proof of when a page mutated.

**Site mapping and bulk extraction** — BFS crawl with robots.txt compliance, adaptive rate limiting, and per-page audit events.

---

## License

See [LICENSE](LICENSE).

---

## Contributing

Issues and PRs welcome. See [ORGANIZATION.md](ORGANIZATION.md) for repo structure.
