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

## What's New

### Element Ref Map — Stable Selectors Across Snapshots

Conduit now assigns short stable references (`e1`, `e2`, `e3` ...) to every interactable element in the accessibility snapshot. Refs survive DOM churn — you don't need a CSS selector if you have the ref.

```python
# Get the snapshot — every interactable element gets a ref
snap = await bridge.execute({"action": "accessibility_snapshot"})
# snap["nodes"][0] → {"role": "button", "name": "Submit", "ref": "e3", ...}

# Use the ref directly in click, type, or hover
await bridge.execute({"action": "click", "selector": "e3"})
await bridge.execute({"action": "type",  "selector": "e7", "text": "hello"})
```

Refs reset on each new snapshot call so they always reflect the current page state. No bridge config needed — works automatically.

---

### Paginated Accessibility Snapshots

Large pages can return thousands of accessibility nodes. Pass `offset` and `limit` to page through them:

```python
# First 50 nodes
page1 = await bridge.execute({"action": "accessibility_snapshot", "offset": 0, "limit": 50})
# page1["total_nodes"] → 312

# Next 50
page2 = await bridge.execute({"action": "accessibility_snapshot", "offset": 50, "limit": 50})
```

`total_nodes` is always returned so you know how many pages remain.

---

### YouTube Transcript Extraction

Pull transcripts from any YouTube video — no API key required:

```python
result = await bridge.execute({
    "action": "youtube_transcript",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "lang": "en",   # optional, defaults to "en"
})
# result["transcript"] → plain text
# result["source"]     → "yt-dlp" or "browser_timedtext"
```

Primary path uses `yt-dlp` (30s timeout). Falls back to the browser's own timedtext endpoint if `yt-dlp` is not installed or times out. Both paths are audited and written to the hash chain.

---

### Download Capture

Click a link, capture what downloads, save it to a configurable directory:

```python
result = await bridge.execute({
    "action": "capture_download",
    "selector": "a.download-btn",
    "timeout": 30000,
})
# result["path"]     → absolute path to saved file
# result["filename"] → suggested filename from server
# result["url"]      → original download URL

# List all captured downloads
files = await bridge.execute({"action": "get_downloads"})
# files["downloads"] → [{filename, path, size, modified}, ...]
```

Download directory defaults to `~/.cato/workspace/downloads/` but is fully configurable at init:

```python
from pathlib import Path
bridge = ConduitBridge(download_dir=Path("/your/custom/path"))
```

---

### Deliverable Verification + SwarmSync Escrow Integration

Two new actions close the loop between browser execution and payment release — designed specifically for agent-to-agent task markets.

**`verify_deliverable`** fetches any URL, computes its SHA-256, compares it against an expected hash, and writes the result to the audit chain. If the hash matches, `deliverable_verified: true` is set in the audit log. SwarmSync escrow release queries this field directly:

```python
result = await bridge.execute({
    "action": "verify_deliverable",
    "url": "https://cdn.example.com/report.pdf",
    "expected_hash": "a3f9c2...",
    "request_id": "job-7821"
})
# result["deliverable_verified"] → True/False
# result["source"] → "python_fetch" or "browser_eval"
```

Two fetch paths: a streaming Python `urllib` fetch (works on any binary file — PDFs, audio, images, large archives) and a browser `crypto.subtle.digest` fallback for auth-gated resources that require a live authenticated session.

**`verify_rubric`** evaluates a pre-committed rubric against delivered content. The rubric is hashed *before* work begins — the hash is stored. When work is delivered, the same rubric is re-hashed and must match. This proves evaluation criteria were locked before the seller started.

```python
from tools.rubric import make_rubric_hash

rubric = {
    "min_word_count": 800,
    "must_contain": ["executive summary", "risk analysis"],
    "must_not_contain": ["lorem ipsum"],
    "language": "en",
}
rubric_hash = make_rubric_hash(rubric)  # commit this before work starts

# After delivery — verify inline content directly, no URL required
result = await bridge.execute({
    "action": "verify_rubric",
    "rubric": rubric,
    "rubric_hash": rubric_hash,
    "request_id": "job-7821",
    "inline_content": delivered_text,   # or use "url" for URL-addressable artifacts
})
# result["rubric_pass"] → True/False
# result["predicate_results"] → per-predicate breakdown
```

Supported rubric predicates: `min_word_count`, `max_word_count`, `must_contain`, `must_not_contain`, `min_length_chars`, `max_length_chars`, `language` (ISO 639-1), `content_type_hint`, `custom_checks` (sandboxed Python expressions).

---

### Three-Tier Selector Healing

Conduit no longer fails on stale CSS selectors. When a `click`, `type`, or `hover` action fails, it automatically escalates through two fallback tiers before returning an error:

- **Tier 1** — Original CSS selector (existing behavior)
- **Tier 2** — ARIA accessibility tree search — finds elements by role and semantic name
- **Tier 3** — Text content search — finds DOM elements whose `innerText` contains the selector as a substring

Every healing event is written to the audit chain with the original selector, the tier that succeeded, and the resolved selector. All three tiers are enabled by default with no configuration required.

---

### Provenance-Wrapped Extraction

`extract_main` now supports `provenance_mode=True`. Every field in the result is wrapped with a provenance envelope:

```python
result = await bridge.execute({
    "action": "extract_main",
    "fmt": "md",
    "provenance_mode": True,
})
# result["text"] → {
#   "value": "actual content...",
#   "provenance": {
#     "audit_row_id": 47,
#     "session_pubkey": "a3f9...",
#     "url": "https://example.com",
#     "url_hash": "7b1a3f...",
#     "extracted_at": 1741564800.123,
#     "chain_verified": false
#   }
# }
```

Useful when you need to pass extracted content downstream and prove where it came from.

---

### AIVS-Micro: 6-Field Proof on Every MCP Response

Every tool call through the MCP server now includes an `_conduit_proof` field — a compact ~200-byte proof containing:

```json
{
  "session_id": "sess-abc123",
  "action": "navigate",
  "row_hash": "7b1a3f...",
  "prev_hash": "e8d2c4...",
  "timestamp": 1741564800.123,
  "pubkey": "a3f9c2..."
}
```

This is AIVS-Micro (Agentic Integrity Verification Standard — Micro profile). Any downstream consumer can verify that a specific action actually ran in a specific audited session without pulling the full proof bundle. Full specification: [spec/AIVS.md](spec/AIVS.md).

---

### VOIX Protocol: Clean Output for Agent Pipelines

All extracted content (navigate, extract, extract_main, eval) automatically strips `<tool>...</tool>` and `<context>...</context>` tags before returning to the caller. This prevents leakage of agent metadata into downstream content processing without any configuration.

---

### Standalone MCP Server

Conduit now ships a single-file `conduit_mcp_server.py` — a stdio MCP server ready for registration on Glama, the MCP registry, or any MCP-compatible host.

```bash
python conduit_mcp_server.py
```

Add to your MCP config:

```json
{
  "mcpServers": {
    "conduit": {
      "command": "python",
      "args": ["conduit_mcp_server.py"],
      "env": {}
    }
  }
}
```

---

## Use Cases

**Compliance automation** — Prove a specific form was filled with specific values at a specific time. Export a proof bundle. The chain hash is your receipt.

**Security research** — Document what JS a page injected, what network requests it made, what the DOM looked like at each step — all signed and chained.

**AI agent browser control** — Designed as the browser engine for autonomous agents. Budget enforcement prevents runaway costs. The audit trail lets you replay and inspect exactly what the agent did.

**Web monitoring** — `fingerprint` + `check_changed` gives you signed change detection with cryptographic proof of when a page mutated.

**Site mapping and bulk extraction** — BFS crawl with robots.txt compliance, adaptive rate limiting, and per-page audit events.

**Structured marketplace extraction** — Purpose-built adapters for 7 major platforms: LinkedIn, Amazon, Google Search, GitHub, Reddit, Hacker News, and generic news/RSS. 26 extraction targets across all platforms. Every extracted record flows through `_audit()` — cryptographic proof of what was collected and when.

**Agent escrow settlement** — `verify_deliverable` and `verify_rubric` connect Conduit's audit chain directly to payment release. Agents prove work was done. Escrow releases automatically.

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
| Deliverable hash verification | Yes | No | No | No |
| Pre-committed rubric evaluation | Yes | No | No | No |
| Three-tier selector healing | Yes | No | No | No |
| AIVS-Micro proof on every MCP response | Yes | No | No | No |
| Escrow-ready audit outputs | Yes | No | No | No |
| Stable element refs (eN) across snapshots | Yes | No | No | No |
| Paginated accessibility snapshots | Yes | No | No | No |
| YouTube transcript extraction (no API key) | Yes | No | No | No |
| Download capture with configurable directory | Yes | No | No | No |

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

## Action Reference

### Wave 0 — Core Browser
`navigate` · `click` · `type` · `fill` · `extract` · `screenshot`

### Wave 1 — Interaction
`scroll` · `wait` · `wait_for` · `key_press` · `hover` · `select_option` · `handle_dialog` · `navigate_back` · `console_messages`

### Wave 2 — Extraction (Conduit-Exclusive)
- **`eval`** — Execute JavaScript. Full source stored in hash chain.
- **`extract_main`** — Readability-style extraction, strips nav/ads/footers. Optional Markdown output. `provenance_mode=True` wraps every field with audit metadata.
- **`extract_structured`** — Main content + JSON schema validation. Accepts an optional async model extractor.
- **`js_delta`** — Diff the DOM against a previous snapshot.
- **`output_to_file`** — Write to workspace. Path-safe (no directory traversal).
- **`accessibility_snapshot`** — Full Playwright accessibility tree with stable `eN` element refs and `offset`/`limit` pagination. Returns `total_nodes`.
- **`network_requests`** — Accumulated network log since last call.
- **`capture_download`** — Click a selector, wait for the browser download, save file to configurable `download_dir`. Returns path, filename, and source URL.
- **`get_downloads`** — List all files saved in the download directory.
- **`youtube_transcript`** — Extract transcript from any YouTube URL. yt-dlp primary, browser timedtext fallback.

### Wave 3 — Advanced (Conduit-Exclusive)
- **`map`** — BFS site discovery, robots.txt compliant. Returns all reachable URLs.
- **`crawl`** — Bulk BFS extraction up to `max_depth`. Per-page: title, text, depth.
- **`fingerprint`** — SHA-256 page fingerprint (normalizes timestamps/nonces to avoid false positives).
- **`check_changed`** — Re-fingerprint URL. If changed, logs signed `PAGE_MUTATION` event.
- **`login`** — Credential-based login with session persistence.
- **`check_session`** — Check whether a saved session is still authenticated.
- **`save_cookies` / `load_cookies`** — Persist and restore authenticated browser state by label.
- **`export_proof`** — Generate self-verifiable `.tar.gz` proof bundle.
- **`export_micro`** — Export AIVS-Micro 6-field proof (~200 bytes).

### Wave 4 — CAPTCHA
`detect_captcha` · `solve_captcha` · `solve_captcha_vision`

Powered by CapSolver API (reCAPTCHA v2, hCaptcha, Cloudflare Turnstile). Gracefully degrades when no API key is configured.

### Wave 5 — Proxy
`rotate_proxy`

### Wave 6 — Web Search (Built-In)
- **`web_search`** — Multi-engine: DuckDuckGo, Brave, Exa, Tavily. Query-type routing (code → exa+ddg, news → tavily+ddg, general → tavily+exa), with Brave and HTML/Wikipedia as later fallbacks when the primary engines are unavailable.
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
result = await bridge.execute({
    "action": "marketplace_plan",
    "marketplace": "hackernews",
    "target_type": "frontpage",
    "target_url": "https://news.ycombinator.com"
})
# → {stories: [{title, url, score, author, comments_count}, ...]}
```

**Job queue actions:** `marketplace_plan` · `marketplace_create_job` · `marketplace_execute_job` · `marketplace_enqueue_job` · `marketplace_queue_status` · `marketplace_get_result` · `marketplace_list_results` · `marketplace_export_result`

**Account & session actions:** `marketplace_create_account` · `marketplace_list_accounts` · `marketplace_save_session` · `marketplace_get_session` · `marketplace_list_sessions` · `marketplace_bootstrap_session`

**Proxy actions:** `marketplace_create_proxy` · `marketplace_test_proxy` · `marketplace_list_proxies` · `marketplace_get_proxy`

Results export as JSON (`.jsonl`) or CSV. All data stored in `~/.cato/cato.db` — no separate database needed.

### Verification Actions

- **`verify_deliverable`** — Fetch any URL, compute SHA-256, compare against expected hash. Primary path: streaming Python fetch. Fallback: browser `crypto.subtle.digest` for auth-gated resources. Audit output includes `deliverable_verified` (bool) — the field SwarmSync escrow queries for payment release.
- **`verify_rubric`** — Evaluate a pre-committed rubric against delivered content. Accepts `url` or `inline_content`. Rubric hash must match pre-committed hash or the action fails immediately.

---

## Architecture

```
Agent / Your Code
        │
        ▼
  ConduitBridge          ← single entry point, Ed25519 signing, budget enforcement
        │
   ┌────┴────────────────────────┐
   │                             │
BrowserTool              Product Layer
(Patchright)     (marketplace workers, job queue, session pool)
   │                             │
   └───────────────┬─────────────┘
                   ▼
               _audit()          ← ONLY write point — writes to BOTH tables atomically
                   │
     ┌─────────────┴─────────────┐
     │                           │
conduit_billing            audit_log
(cost ledger)          (SHA-256 hash chain)
```

**The two-layer write path is a hard architectural constraint.** No action method ever calls `_ledger.record()` or `_audit_log.log()` directly. Everything flows through `_audit()`. This guarantees the billing ledger and audit chain are always in sync.

---

## Storage Layout

All runtime data lives under `~/.cato/`:

```
~/.cato/
├── cato.db                    # SQLite: audit_log + conduit_billing + marketplace tables
├── conduit_identity.key       # Ed25519 private key (chmod 600)
├── workspace/
│   ├── screenshots/           # PNG screenshots
│   ├── pdfs/                  # PDF exports
│   ├── downloads/             # capture_download outputs (configurable)
│   └── .conduit/              # output_to_file outputs
├── proofs/                    # Exported proof bundles (.tar.gz)
├── browser_profile/           # Persistent Chromium profile
├── cookies/                   # Saved cookie files by label
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
- Every selector healing event (original selector → resolved selector + tier used)

**Auto-redacted keys** (value replaced with `[REDACTED]` before logging):
`password` · `token` · `api_key` · `secret` · `key` · `authorization` · `bearer` · `credential` · `passwd` · `passphrase`

**Navigation restrictions:**
- HTTP/HTTPS only — no `file://`, `data://`, `javascript://` schemes
- RFC-1918 and loopback IPs blocked — no SSRF via browser or verification fetches

**Crawlers:**
- Always check `robots.txt` before visiting any URL
- Honor `Crawl-delay` directives
- Exponential backoff on 429/503, logged as `RATE_LIMITED` events

---

## Running Tests

```bash
# All tests
pytest tests/

# Verification tests
pytest tests/test_verify_deliverable.py tests/test_verify_rubric.py -v

# Marketplace adapter tests
pytest tests/test_marketplace_adapters.py -v

# Audit chain integrity
pytest tests/test_audit_chain.py -v
```

Tests use `pytest-asyncio`. No real browser is launched — all Patchright calls are mocked via `AsyncMock`. The package shim in `tests/conftest.py` makes the relative imports work without installing the package.

---

## From Free Tool to Paid Agent

Conduit is free and open-source. It will stay that way. But agents that do useful work should get paid for it.

**Step 1:** Build with Conduit. Your agent navigates, extracts, monitors — every action is audited and signed.

**Step 2:** Your agent produces real value. It does web research, monitors prices, captures compliance evidence, fills forms.

**Step 3:** List your agent on [SwarmSync.ai](https://swarmsync.ai). Set your price. Define what your agent does.

**Step 4:** Other agents on SwarmSync discover yours. They negotiate terms, agree on price, and funds go into smart escrow.

**Step 5:** Your agent executes the work via Conduit. `verify_deliverable` or `verify_rubric` proves the work was done. Escrow releases payment automatically when `deliverable_verified: true` hits the audit chain.

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
