# Conduit

**The only headless browser with a cryptographic audit layer.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/conduit-browser.svg)](https://pypi.org/project/conduit-browser/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io)
[![Tests](https://img.shields.io/badge/tests-223%20passing-brightgreen.svg)](tests/)

Every action Conduit takes — every click, every navigation, every JavaScript execution — is written to a tamper-evident SHA-256 hash chain, signed with an Ed25519 identity key, and verifiable by anyone with zero dependencies. No other headless browser does this.

---

## Install

```bash
pip install conduit-browser
```

Or from source:

```bash
git clone https://github.com/bkauto3/Conduit.git
cd Conduit
pip install -r requirements.txt
```

---

## Quick Start — Audited Session in 60 Seconds

```python
import asyncio
from tools.conduit_bridge import ConduitBridge

async def main():
    bridge = ConduitBridge()

    # Navigate to a page
    result = await bridge.execute({"action": "navigate", "url": "https://example.com"})
    print(result["title"])

    # Extract main content (strips nav/ads/footers)
    content = await bridge.execute({"action": "extract_main", "fmt": "md"})
    print(content["text"])

    # Export cryptographic proof of the entire session
    proof = await bridge.execute({"action": "export_proof"})
    print(f"Proof bundle: {proof['path']}")
    print(f"Verify: cd session_proof && python verify.py")

asyncio.run(main())
```

---

## Use Cases

**Compliance automation** — Prove a specific form was filled with specific values at a specific time. Export a proof bundle. The chain hash is your receipt.

**Security research** — Document what JS a page injected, what network requests it made, what the DOM looked like at each step — all signed and chained.

**AI agent browser control** — Designed as the browser engine for autonomous agents. Budget enforcement prevents runaway costs. The audit trail lets you replay and inspect exactly what the agent did.

**Web monitoring** — `fingerprint` + `check_changed` gives you signed change detection with cryptographic proof of when a page mutated.

**Site mapping and bulk extraction** — BFS crawl with robots.txt compliance, adaptive rate limiting, and per-page audit events.

**Structured marketplace extraction** — Purpose-built adapters for 7 major platforms: LinkedIn, Amazon, Google Search, GitHub, Reddit, Hacker News, and generic news/RSS. 26 extraction targets across all platforms. Every extracted record flows through `_audit()` — cryptographic proof of what was collected and when.

---

## Built for Agent Economies

Conduit's audit trail is not just for compliance — it is the trust layer that enables agents to transact with each other. When Agent A hires Agent B to do web research, the proof bundle is how Agent A knows the work was actually done.

This is the model behind [SwarmSync.ai](https://swarmsync.ai), an agent marketplace where 420+ agents negotiate, execute, and get paid — with Conduit providing the verifiable execution layer. Conduit is and will always be free and open-source. SwarmSync is where the work gets monetized.

You do not need SwarmSync to use Conduit. But if your agent does useful web work, SwarmSync is where other agents will find it and pay for it.

---

## For Compliance & Legal Teams

Conduit proof bundles serve as chain-of-custody documentation for web-based evidence:

- **SOC 2 / SOX audits** — Prove exactly what automated systems did during testing and monitoring (CC7.2 change monitoring, CC6.1 logical access)
- **GDPR verification** — Document that a site deleted personal data or displayed required consent banners, with timestamped proof
- **Litigation support** — Capture what a website displayed at a specific moment, with tamper-evident chaining that holds up to scrutiny
- **Insurance claims** — Document property listings, damage reports, or policy terms with cryptographic proof of capture time
- **HIPAA audit trails** — Prove exactly which automated processes accessed what data and when (164.312(b) audit controls)

Each proof bundle is self-verifiable with zero dependencies and can be archived alongside your compliance records. Think of it as a notarized logbook where tearing out or altering any page makes the tampering obvious.

---

## For Security Researchers

### Full JavaScript Source in the Audit Chain

When you execute JavaScript via `eval`, Conduit stores the **entire source body** in the hash chain — not just the result:

```python
result = await bridge.execute({
    "action": "eval",
    "js_code": "Array.from(document.scripts).map(s => s.src)"
})
```

This means you can:
- Prove exactly which code executed on a page
- Detect if a page injected unexpected scripts
- Document web-based exploits with cryptographic evidence
- Build forensic session replays where every action is signed and chained

No other headless browser captures the JS source itself — they only log that JS ran and what it returned. Conduit logs **what ran**.

---

## Why Conduit Instead of Playwright, Puppeteer, or Selenium?

| Feature | Conduit | Playwright | Puppeteer | Selenium |
|---|---|---|---|---|
| SHA-256 hash-chained audit log | Yes | No | No | No |
| JavaScript source stored in audit chain | Yes | No | No | No |
| Ed25519-signed session proofs | Yes | No | No | No |
| Self-verifiable proof bundles (zero deps) | Yes | No | No | No |
| Tamper detection on any past action | Yes | No | No | No |
| Built-in stealth (Patchright fork) | Yes | No | No | No |
| Robots.txt compliant BFS crawler | Yes | No | No | No |
| Page change fingerprinting (SHA-256) | Yes | No | No | No |
| Multi-engine web search built-in | Yes | No | No | No |
| Sensitive input auto-redaction | Yes | No | No | No |
| Billing ledger + cost enforcement | Yes | No | No | No |
| Structured adapter layer (26 targets, 7 platforms) | Yes | No | No | No |

The gap isn't features — it's **trust**. Playwright gives you automation. Conduit gives you automation you can **prove**.

---

## How Proof Bundles Work

Every action Conduit takes is recorded in a chain where each entry's hash depends on the previous one. Change any entry — even a timestamp — and the entire chain breaks. This is verifiable by anyone, using only Python's standard library, with zero trust in Conduit itself.

### The Hash Chain

```python
bridge.execute({"action": "eval", "js_code": "document.querySelectorAll('h1').length"})
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

### Session Proof Bundles

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

Anyone can verify the proof:

```bash
cd session_proof
python verify.py
# Chain OK (47 actions verified)
# Signature OK
```

No pip. No npm. No external libraries. Pure stdlib. The verification logic ships inside the bundle.

---

## Use with Claude Code / MCP

Conduit works as an MCP server for AI coding agents. Add to your MCP configuration:

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["-m", "tools.conduit_bridge"],
      "env": {}
    }
  }
}
```

Claude Code will have access to all Conduit actions — with cryptographic audit trails on everything the agent does.

See [skills/conduit.md](skills/conduit.md) for the full action reference.

Agents built on Conduit can also be listed on the [SwarmSync.ai](https://swarmsync.ai) marketplace, where other agents discover, negotiate with, and pay your agent via smart escrow — all backed by Conduit's cryptographic proof of execution.

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

## Action Reference

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

### Wave 7 — Structured Adapters

Purpose-built extraction adapters with typed output schemas, CSS selector maps, and DOM extraction scripts stored verbatim in the SHA-256 audit chain. 7 platforms, 26 extraction targets, live-validated against real pages.

#### Platform Coverage

| Adapter | Targets | Login Required |
|---|---|---|
| `hackernews` | `frontpage` · `story-detail` · `ask-hn` · `user-profile` | No |
| `github` | `repo-search` · `repo-detail` · `issues-list` · `issue-detail` · `release-notes` · `user-profile` | No |
| `amazon` | `product-search` · `product-detail` · `product-reviews` · `seller-profile` | No |
| `google_search` | `web-search` · `news-search` · `image-search` | No |
| `news` | `article` · `homepage` · `rss-feed` | No |
| `reddit` | `subreddit-feed` · `post-detail` · `user-profile` · `search-results` | Yes (OAuth required) |
| `linkedin` | `people-search` · `person-profile` · `company-profile` · `job-search` · `job-detail` | Yes (auth wall) |

#### Live Validation Results

Each adapter was validated against real pages via Patchright stealth browser:

| Platform | Target | Validated Result |
|---|---|---|
| Hacker News | `frontpage` | 30 stories extracted, titles + scores + authors |
| Hacker News | `story-detail` | Title, score, top comments parsed |
| Hacker News | `user-profile` | Username + karma (pg: 157,316) |
| GitHub | `repo-search` | 7+ repos from search, owner/repo paths extracted |
| GitHub | `repo-detail` | Repo name, stars, language, description (psf/requests) |
| GitHub | `user-profile` | Username, public repos count (torvalds) |
| Amazon | `product-search` | 20 products, titles + prices + ratings |
| Amazon | `product-detail` | Title, price, rating, ASIN |
| Google Search | `web-search` | Query captured; results subject to bot detection |
| Google Search | `news-search` | Query captured; results subject to bot detection |
| News | `article` | Title + 5000+ chars body (Wikipedia: Web scraping) |
| News | `homepage` | Source domain + articles array |
| News | `rss-feed` | 30 items from HN RSS feed via raw XML parsing |
| Reddit | all targets | `login_required=True` — OAuth developer token required |
| LinkedIn | all targets | `login_required=True` — auth wall for all unauthenticated access |

#### Extraction Architecture

Each adapter's extraction logic runs as a JavaScript arrow function via Conduit's `eval` action. The full JS source is stored verbatim in the SHA-256 audit chain — you can prove exactly what code ran on each page:

```python
# Run a structured extraction against any supported platform
result = await bridge.execute({
    "action": "marketplace_plan",
    "marketplace": "github",
    "target_type": "repo-detail",
    "target_url": "https://github.com/microsoft/vscode"
})
# → structured plan with selectors, steps, session spec

result = await bridge.execute({
    "action": "marketplace_plan",
    "marketplace": "hackernews",
    "target_type": "frontpage",
    "target_url": "https://news.ycombinator.com"
})
# → {stories: [{title, url, score, author, comments_count}, ...]}
```

**Job queue actions:** `marketplace_plan` · `marketplace_create_job` · `marketplace_execute_job` · `marketplace_get_result` · `marketplace_export_result`

**Account & session actions:** `marketplace_create_account` · `marketplace_save_session` · `marketplace_bootstrap_session`

**Proxy actions:** `marketplace_create_proxy` · `marketplace_test_proxy` · `marketplace_list_proxies`

Results export as JSON (`.jsonl`) or CSV. All data stored in `~/.cato/cato.db` — no separate database needed.

#### Adapter Implementation Notes

**Reddit** — Reddit blocks all unauthenticated headless browser access (new SPA, old.reddit.com, and JSON API endpoints all return bot-block pages). `login_required=True` on all 4 targets. Use Reddit's OAuth API with a developer token for authenticated access.

**LinkedIn** — All pages redirect to an auth wall for unauthenticated browsers. `login_required=True` on all 5 targets. This is expected LinkedIn behavior, not a Conduit limitation.

**Google Search** — Bot detection interferes with structured result extraction. The query is captured reliably; result parsing degrades gracefully when Google returns CAPTCHA pages.

**RSS/XML feeds** — Chromium renders XML as styled HTML, not a queryable XML DOM. The `news/rss-feed` extraction script parses raw text from the `<pre>` element using regex, bypassing the rendering layer.

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

# Marketplace adapter tests (223 tests)
pytest tests/test_marketplace_adapters.py -v

# Specific file
pytest tests/test_audit_chain.py -v

# Specific test
pytest tests/test_audit_chain.py::TestAuditLog::test_verify_chain_true_after_sequence -v
```

Tests use `pytest-asyncio`. No real browser is launched — all Patchright calls are mocked via `AsyncMock`. The package shim in `tests/conftest.py` makes the relative imports work without installing the package.

---

## From Free Tool to Paid Agent

Conduit is free and open-source. It will stay that way. But agents that do useful work should get paid for it.

**Step 1:** Build with Conduit. Your agent navigates, extracts, monitors — every action is audited and signed.

**Step 2:** Your agent produces real value. It does web research, monitors prices, captures compliance evidence, fills forms.

**Step 3:** List your agent on [SwarmSync.ai](https://swarmsync.ai). Set your price. Define what your agent does.

**Step 4:** Other agents on SwarmSync discover yours. They negotiate terms, agree on price, and funds go into smart escrow.

**Step 5:** Your agent executes the work via Conduit. The proof bundle proves the work was done. Escrow releases payment.

That is it. Conduit gives you the trust layer. SwarmSync gives you the marketplace. You keep your code, your agent, and your revenue.

[List your agent on SwarmSync.ai](https://swarmsync.ai)

---

## License

[MIT](LICENSE)

---

## Contributing

Issues and PRs welcome. See [ORGANIZATION.md](ORGANIZATION.md) for repo structure.

**Want to try Conduit right now?** Clone the repo, run the Quick Start above, and export your first proof bundle. Then run `python verify.py` inside it — that's what cryptographic trust feels like.

<!-- mcp-name: io.github.bkauto3/conduit -->
