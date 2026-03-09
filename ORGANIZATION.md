# Conduit Repository Organization

## Core Runtime (Root Level)

These files are essential to Conduit's operation and are tracked in git:

- **`audit.py`** - SHA-256 hash-chained audit log system (SQLite). Core tamper-evident record.
- **`receipt.py`** - Generates signed billing receipts from audit log.
- **`replay.py`** - Audit log replay and verification utilities.
- **`CLAUDE.md`** - Project instructions for Claude Code.

## Active Codebase

### `/tools/` - Core Conduit Modules
The main browser automation and agent interface:
- `browser.py` - Patchright (stealth Playwright) automation
- `conduit_bridge.py` - Agent entry point (budget enforcement, audit routing)
- `conduit_crawl.py` - BFS site discovery and bulk page extraction
- `conduit_monitor.py` - Page fingerprinting and change detection
- `conduit_proof.py` - Self-verifiable proof bundle export
- `captcha_solver.py` - CAPTCHA solving via CapSolver API
- `web_search.py` - Multi-engine web search (DDG, Brave, Exa, Tavily)

### `/tests/` - Active Test Suite
Comprehensive test coverage for all modules:
- `conftest.py` - pytest configuration and package shimming
- `test_browser_actions.py` - Core browser action tests
- `test_audit_chain.py` - Audit log integrity and chain verification
- `test_conduit_crawl.py` - Crawler functionality
- `test_conduit_monitor.py` - Page fingerprinting and change detection
- `test_conduit_proof.py` - Proof bundle generation and verification
- `test_captcha.py` - CAPTCHA solver integration
- `test_stealth.py` - Stealth detection and bypass
- `test_web_search.py` - Web search integration
- `test_extraction_actions.py` - Content extraction
- `test_e2e_live.py` - End-to-end live testing
- `test_ideabrowser_live.py` - IdeaBrowser integration test

### `/scripts/` - Utility Scripts
Operational and debugging scripts:
- `live_audit.py` - Live audit log monitoring
- `live_audit_v2.py`, `live_final.py`, `live_final_v2.py` - Audit testing variants
- `live_audit_dns_bypass.py` - DNS workaround for Windows Server
- `_audit_tmp/` - Temporary audit test artifacts
- `_audit_tmp_dns/` - Temporary DNS bypass tests

### `/skills/` - Agent Integration
- `conduit.md` - Complete Conduit action reference for agents (v2.0.0)

## Documentation

### `/docs/`
- `CLAUDE.md` - Copy of project instructions
- `AGENTS.md` - Agent integration notes

### This File
- `ORGANIZATION.md` - Repository structure guide (you are here)

## Archive

### `/archive/` - Non-Essential Files
Separated from active codebase for clean git history:

- **`brainstorms/`** - Multi-agent brainstorming and gap analysis documents
- **`planning/`** - Implementation plans, task breakdowns, feature specs
  - `CONDUIT_UPGRADE_SPEC.md`
  - `IMPLEMENTATION_PLAN.md`
  - `TASKS_*.md` - Task assignments
  - `PROMPT_*.md` - Planning prompts
  - `Firecrawl.md` - Research notes
- **`tests/`** - Legacy test files (not part of active suite)
  - `audit_live_test.py`, `audit_live_test2.py`
  - `test_dns_fix.py`
  - `audit_results*.json`
- **`scripts/`** - Old utility experiments
  - `_dns_test*.py` - Deprecated DNS workarounds

## Git Ignore Configuration

The `.gitignore` file excludes:
- All archive files (planning, brainstorms, legacy tests)
- Python cache and build artifacts
- IDE/editor config (`.cursor/`, `.vscode/`, `.idea/`)
- Test caches and coverage reports
- OS-specific files (`.DS_Store`, `Thumbs.db`)

**Tracked in git:**
- `/tools/` - Core modules
- `/tests/` - Test suite
- `/scripts/` - Active utility scripts
- `/skills/` - Agent documentation
- Core runtime files (`audit.py`, `receipt.py`, `replay.py`, `CLAUDE.md`)

## Quick Start

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_browser_actions.py -v

# Check git status (shows only tracked files)
git status

# View git diff (excludes archive changes)
git diff
```

## Key Design Principles

1. **Core Conduit** lives in `/tools/` — small, focused modules
2. **Every action** routes through `ConduitBridge._audit()` for cryptographic proof
3. **Tests are comprehensive** — 100% coverage of all action types
4. **Archive is separate** — planning and brainstorms don't clutter git history
5. **Documentation is clear** — `skills/conduit.md` is the agent reference

---

Last updated: 2026-03-09
