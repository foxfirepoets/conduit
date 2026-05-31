# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Conduit is a headless browser engine with a cryptographic audit layer. It is designed to be embedded into a larger "Cato" agent system (`cato/tools/`), but the files in this repo live at the root without that package structure. Every browser action is written to a SHA-256 hash-chained audit log signed with an Ed25519 identity key.

Conduit's core differentiator: the `eval` action stores the full JavaScript source verbatim in the audit hash chain — cryptographic proof of exactly what code ran, not just the result.

## Running Tests

```bash
# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_browser_actions.py -v

# Run a single test class or test
pytest tests/test_audit_chain.py::TestAuditLog::test_verify_chain_true_after_sequence -v
```

Tests use `pytest-asyncio`. No real browser is launched — all Patchright page calls are mocked via `AsyncMock`.

## Architecture

### Module Map

| File | Role |
|------|------|
| `audit.py` | SHA-256 hash-chained audit log (SQLite `audit_log` table). Core tamper-evident record. |
| `receipt.py` | Generates signed billing receipts from audit log rows. |
| `replay.py` | Replays audit log sessions for forensic inspection. |
| `conduit_mcp_server.py` | Standalone stdio MCP server entry point (Glama/MCP registry). Attaches AIVS-Micro proof to every response. |
| `tools/browser.py` | `BrowserTool` — Patchright (stealth Playwright fork) Chromium automation. Direct action implementations. |
| `tools/captcha_solver.py` | `CapSolverClient` — CAPTCHA detection and solving via CapSolver API (reCAPTCHA v2, hCaptcha, Cloudflare Turnstile). Gracefully degrades when no API key configured. |
| `tools/conduit_bridge.py` | `ConduitBridge` — wraps `BrowserTool`, enforces budget cap, routes every action through `_audit()`. Agent entry point. |
| `tools/conduit_crawl.py` | `ConduitCrawler` — BFS site map discovery and bulk page extraction. Robots.txt compliant. |
| `tools/conduit_monitor.py` | `ConduitMonitor` — SHA-256 page fingerprinting, change detection, `PAGE_MUTATION` audit events. |
| `tools/conduit_proof.py` | `ConduitProof` — exports self-verifiable `.tar.gz` proof bundles with stdlib-only `verify.py`. Also: AIVS-Micro (6-field minimal proofs), bundle chaining (scan chain), Merkle trees for crawl proofs. |
| `tools/rubric.py` | `evaluate_rubric()` / `make_rubric_hash()` — sandboxed predicate evaluation engine for generative output verification. |
| `tools/web_search.py` | Multi-engine search: DuckDuckGo, Brave, Exa, Tavily, Semantic Scholar, arXiv. HTML and Wikipedia fallbacks. |
| `tools/core/models.py` | `ProductProfile`, `SessionSpec`, `SessionLease` dataclasses. |
| `tools/core/session_pool.py` | Session pool management. |
| `tools/marketplaces/` | Marketplace adapters: Amazon, Fiverr, GitHub, Google Search, HackerNews, LinkedIn, News, Reddit, Upwork. Base class in `base.py`. |
| `tools/products/general/service.py` | General-purpose browser product profile. |
| `tools/products/marketplace/service.py` | Marketplace product orchestration. |
| `tools/products/marketplace/worker_pool.py` | `MarketplaceBrowserWorkerPool` — per-proxy Patchright worker management. |
| `tools/products/marketplace/job_queue.py` | Async job queue for marketplace operations. |
| `tools/storage/marketplace_store.py` | SQLite persistence for marketplace accounts, sessions, jobs, proxies, results. |
| `skills/conduit.md` | Documentation for all actions used by agents consuming Conduit. |
| `spec/AIVS.md` | Agentic Integrity Verification Standard specification. |
| `spec/CONDUIT_SESSION_PROOF_FORMAT.md` | Session proof bundle format spec (CSPF v1.0). |

### Two-Layer Write Path

Every browser action must call `ConduitBridge._audit()` — never call `_charge()` or write to either table directly. `_audit()` writes to **both**:
1. `conduit_billing` table (cost ledger, `ConduitBillingLedger`)
2. `audit_log` table (SHA-256 hash chain, `AuditLog`)

The billing table tracks costs; the audit table is the tamper-evident record. They share the same SQLite file (`cato.db`).

### Action Dispatch Flow

Agent call → `ConduitBridge.execute(args)` → dispatches by `action` key → bridge method (e.g. `self.navigate()`) → `BrowserTool._dispatch(action, kwargs)` → concrete `_navigate()` implementation → result returned → `self._audit(...)` called.

Wave 3 actions (map, crawl, fingerprint, check_changed) instantiate `ConduitCrawler` / `ConduitMonitor` directly and call `audit_log.log()` themselves.

Wave 8 marketplace actions use `_get_marketplace_service()`, `_get_marketplace_worker_pool()`, and `_get_marketplace_job_queue()` to delegate to the product layer.

### Package Shim Pattern (Tests)

The source files use `from ..audit import AuditLog` (relative imports assuming `cato.*` package). Since there is no real package here, tests bootstrap a `sys.modules` shim:
```python
cato_pkg = types.ModuleType("cato")
cato_pkg.__path__ = [str(CONDUIT_ROOT)]
sys.modules["cato"] = cato_pkg
```
See `tests/test_audit_chain.py::_bootstrap_package()` for the canonical pattern.

### Storage Locations (runtime)

- SQLite database: `~/.cato/cato.db` (tables: `audit_log`, `conduit_billing`, `marketplace_accounts`, `marketplace_saved_sessions`, `marketplace_jobs`, `marketplace_proxies`, `marketplace_results`)
- Ed25519 identity key: `~/.cato/conduit_identity.key` (chmod 600)
- Screenshots: `~/.cato/workspace/screenshots/`
- File outputs: `~/.cato/workspace/.conduit/`
- Proof bundles: `~/.cato/proofs/`
- Browser profile: `~/.cato/browser_profile/` (persistent Chromium profile)
- Cookie files: `~/.cato/cookies/<label>.json`

## Key Design Constraints

- **`_audit()` is the only write point.** Never call `_ledger.record()` or `_audit_log.log()` directly from bridge action methods.
- **`extract_main()` must clone the DOM** before removing noise elements — never mutate the live DOM (audit integrity: screenshots/evals after `extract_main` must see the original page).
- **`_navigate()` blocks RFC-1918 / loopback IPs** and non-http(s) schemes. Any new navigation must go through this validation. The same SSRF block applies to `verify_deliverable` and `verify_rubric` URL fetches.
- **Sensitive input keys are auto-redacted** in audit inputs: `password`, `token`, `api_key`, `secret`, `key`, `authorization`, `bearer`, `credential`, `passwd`, `passphrase`.
- **`output_to_file` filename is sanitized** via `Path(filename).name` — no directory traversal.
- **Crawlers are always bounded** by a `limit` parameter and always check `robots.txt` before each URL.
- **VOIX protocol:** strips `<tool>...</tool>` and `<context>...</context>` tags from extracted HTML/text content before returning to agent.
- **AIVS-Micro proof** is attached to every MCP response via `_attach_micro_proof()`.
- **Selector healing is enabled by default** (`_selector_healing_enabled = True`). Three-tier fallback: CSS → ARIA → text for click/type/hover actions.
- **Rubric pre-commitment:** `make_rubric_hash(rubric)` must be called before generating content. `verify_rubric` rejects any rubric whose hash doesn't match `rubric_hash`, proving evaluation criteria weren't altered after work started.

## Action Waves

- **Wave 0 (core):** navigate, click, type/fill, extract, screenshot, pdf, search
- **Wave 1 (interaction):** scroll, wait, wait_for, key_press, hover, select_option, handle_dialog, navigate_back, console_messages
- **Wave 2 (extraction):** eval, extract_main, extract_structured, js_delta, output_to_file, accessibility_snapshot, network_requests
- **Wave 3 (advanced):** map, crawl, fingerprint, check_changed, export_proof, export_micro, login, check_session, save_cookies, load_cookies
- **Wave 4 (CAPTCHA):** detect_captcha, solve_captcha, solve_captcha_vision
- **Wave 5 (proxy):** rotate_proxy
- **Wave 6 (web search):** web_search, academic_search
- **Wave 7 (marketplace adapters):** browser-layer adapters for Amazon, Fiverr, GitHub, Google Search, HackerNews, LinkedIn, News, Reddit, Upwork
- **Wave 8 (marketplace product):** marketplace_list, marketplace_targets, marketplace_plan, marketplace_create_job, marketplace_get_job, marketplace_list_jobs, marketplace_create_account, marketplace_list_accounts, marketplace_create_proxy, marketplace_list_proxies, marketplace_get_proxy, marketplace_test_proxy, marketplace_save_session, marketplace_get_session, marketplace_list_sessions, marketplace_bootstrap_session, marketplace_execute_job, marketplace_enqueue_job, marketplace_queue_status, marketplace_get_result, marketplace_list_results, marketplace_export_result
- **Verification:** verify_deliverable, verify_rubric (SwarmSync escrow integration)
- **Selector healing:** selector_healing (automatic, not a direct action — fires on click/type/hover failure)

## Verification System

Two verification actions support SwarmSync escrow release:

**`verify_deliverable`** — Fetches an artifact URL, computes SHA-256, compares against `expected_hash`.
- Primary path: Python urllib fetch (streams in 64 KB chunks, works on binary/PDF/audio).
- Fallback path: Browser `fetch()` + `crypto.subtle.digest` (for auth-gated resources).
- Audit outputs always include `deliverable_verified` (bool). SwarmSync queries: `WHERE action='verify_deliverable' AND outputs_json->>'deliverable_verified' = 'true'`.

**`verify_rubric`** — Evaluates a pre-committed rubric against delivered content.
- Rubric predicates: `min_word_count`, `max_word_count`, `must_contain`, `must_not_contain`, `min_length_chars`, `max_length_chars`, `language`, `content_type_hint`, `custom_checks`.
- Content sources: `url` (HTTP fetch) or `inline_content` (Option C — direct text, no network required).
- `rubric_hash` mismatch fails immediately — tamper-proof evaluation criteria.

## AIVS (Agentic Integrity Verification Standard)

Full spec in `spec/AIVS.md`. Two proof sizes:

- **Full proof bundle** (`export_proof`): `.tar.gz` with audit log subset, `verify.py` (stdlib-only verifier), Merkle tree for crawl proofs, Ed25519 signature.
- **AIVS-Micro** (`export_micro`): ~200-byte 6-field minimal proof. Automatically attached to every MCP response via `_attach_micro_proof()`.

Session proof bundle format: `spec/CONDUIT_SESSION_PROOF_FORMAT.md` (CSPF v1.0).
