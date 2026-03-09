# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
| `tools/browser.py` | `BrowserTool` — Patchright (stealth Playwright fork) Chromium automation. Direct action implementations. |
| `tools/conduit_bridge.py` | `ConduitBridge` — wraps `BrowserTool`, enforces budget cap, routes every action through `_audit()`. Agent entry point. |
| `tools/conduit_crawl.py` | `ConduitCrawler` — BFS site map discovery and bulk page extraction. Robots.txt compliant. |
| `tools/conduit_monitor.py` | `ConduitMonitor` — SHA-256 page fingerprinting, change detection, `PAGE_MUTATION` audit events. |
| `tools/conduit_proof.py` | `ConduitProof` — exports self-verifiable `.tar.gz` proof bundles with stdlib-only `verify.py`. |
| `skills/conduit.md` | Documentation for all actions used by agents consuming Conduit. |

### Two-Layer Write Path

Every browser action must call `ConduitBridge._audit()` — never call `_charge()` or write to either table directly. `_audit()` writes to **both**:
1. `conduit_billing` table (cost ledger, `ConduitBillingLedger`)
2. `audit_log` table (SHA-256 hash chain, `AuditLog`)

The billing table tracks costs; the audit table is the tamper-evident record. They share the same SQLite file (`cato.db`).

### Action Dispatch Flow

Agent call → `ConduitBridge.execute(args)` → dispatches by `action` key → bridge method (e.g. `self.navigate()`) → `BrowserTool._dispatch(action, kwargs)` → concrete `_navigate()` implementation → result returned → `self._audit(...)` called.

Wave 3 actions (map, crawl, fingerprint, check_changed) instantiate `ConduitCrawler` / `ConduitMonitor` directly and call `audit_log.log()` themselves.

### Package Shim Pattern (Tests)

The source files use `from ..audit import AuditLog` (relative imports assuming `cato.*` package). Since there is no real package here, tests bootstrap a `sys.modules` shim:
```python
cato_pkg = types.ModuleType("cato")
cato_pkg.__path__ = [str(CONDUIT_ROOT)]
sys.modules["cato"] = cato_pkg
```
See `tests/test_audit_chain.py::_bootstrap_package()` for the canonical pattern.

### Storage Locations (runtime)

- SQLite database: `~/.cato/cato.db` (tables: `audit_log`, `conduit_billing`)
- Ed25519 identity key: `~/.cato/conduit_identity.key` (chmod 600)
- Screenshots: `~/.cato/workspace/screenshots/`
- File outputs: `~/.cato/workspace/.conduit/`
- Proof bundles: `~/.cato/proofs/`
- Browser profile: `~/.cato/browser_profile/` (persistent Chromium profile)

## Key Design Constraints

- **`_audit()` is the only write point.** Never call `_ledger.record()` or `_audit_log.log()` directly from bridge action methods.
- **`extract_main()` must clone the DOM** before removing noise elements — never mutate the live DOM (audit integrity: screenshots/evals after `extract_main` must see the original page).
- **`_navigate()` blocks RFC-1918 / loopback IPs** and non-http(s) schemes. Any new navigation must go through this validation.
- **Sensitive input keys are auto-redacted** in audit inputs: `password`, `token`, `api_key`, `secret`, `key`, `authorization`, `bearer`, `credential`, `passwd`, `passphrase`.
- **`output_to_file` filename is sanitized** via `Path(filename).name` — no directory traversal.
- **Crawlers are always bounded** by a `limit` parameter and always check `robots.txt` before each URL.

## Action Waves

- **Wave 0 (core):** navigate, click, type/fill, extract, screenshot, pdf, search
- **Wave 1 (interaction):** scroll, wait, wait_for, key_press, hover, select_option, handle_dialog, navigate_back, console_messages
- **Wave 2 (extraction):** eval, extract_main, output_to_file, accessibility_snapshot, network_requests
- **Wave 3 (advanced):** map, crawl, fingerprint, check_changed, export_proof
