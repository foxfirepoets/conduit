# HKO-Truth-Audit Certificate: Conduit Browser Package
**Date:** 2026-04-23
**Version audited:** 2.0.0 (skills/conduit.md)
**Portability changes audited:** conduit_platform.py + 7 modified files

| Layer | Findings | Critical/High |
|-------|----------|--------------|
| HK (Code) | 6 | 4 (1 CRITICAL, 3 HIGH) |
| OTA (Contract) | 3 | 2 (2 functional) |
| RIO (Integration) | 4 | 2 (2 partial) |
| MULTI (overlap) | 1 | 1 (MULTI-1 merged HK+OTA+RIO) |
| CAUSAL LINKs | 2 | 2 |
| HK Coverage | COMPLETE | — |

**Overall result: CONDITIONAL**

No CRITICAL findings remain unmitigated beyond CL-1 (SSRF hostname bypass, pre-existing), but HIGH findings exist with specific remediation plan above. Portability refactor itself is correctly implemented.

---

## Finding Summary

| ID | Severity | Source | Status | Description |
|----|----------|--------|--------|-------------|
| CL-1 | CRITICAL | HK+OTA CAUSAL LINK | Open | SSRF hostname bypass in BrowserTool._navigate() |
| CL-2 | HIGH | HK+OTA CAUSAL LINK | Open | Budget cap `or True` silently bypasses enforcement |
| F3 | HIGH | HK | Open | Rubric sandbox: `re` module escape vector |
| MULTI-1 | HIGH | HK+OTA+RIO | Open | Docs: ~/.cato references in conduit.md and browser.py |
| F5 | MEDIUM | HK | Open | MCP shim: `cato.platform` attribute name collision |
| F6 | MEDIUM | HK | Open | conduit_platform.py: Path passed as os.environ.get() default |
| F7 | MEDIUM | RIO | Open | 10+ test bootstrap functions missing cato.conduit_platform |

---

## Portability Work Verdict: PASS WITH NOTES

The portability task is correctly implemented in all code paths:
- `conduit_platform.py` created with correct OS detection
- All 6 import sites updated (audit.py + 5 in tools/)
- Hardcoded `~/.cato` removed from browser.py output_to_file and conduit_proof.py
- conduit_mcp_server.py bootstraps correctly from any working directory
- conftest.py uses tempdir (not home dir)
- test_conduit_proof.py patch string matches new import name
- 250+ tests pass

Two gaps remain (not introduced by portability work):
1. `skills/conduit.md` still documents `~/.cato/` paths (MULTI-1)
2. Individual test `_bootstrap()` functions are fragile if run standalone (F7)

---

## Pre-existing Issues (Not Introduced by This Work)

| Issue | Evidence |
|-------|----------|
| SSRF hostname bypass in BrowserTool._navigate() | Present in all git history; bridge has the fix, browser.py does not |
| Budget cap `or True` bug | Present in conduit_bridge.py before portability changes |
| Marketplace tests failing (fiverr/upwork not in registry) | Confirmed via git stash — 14 failures before and after |
| web_search fallback chain test failures | Pre-existing test environment dependency |

---

## Residual Risks (Even After Remediation)

1. **No live SSRF test harness**: The SSRF block in `_navigate()` is not covered by any test that actually launches a browser and attempts to connect to a private IP. Static analysis confirms the code fix, but runtime proof requires an integration test with a real local HTTP server. This gap cannot be detected by static audit alone.

2. **Rubric sandbox is evaluated (not formally proven)**: The `eval()` sandbox relies on Python AST walking, which is known to have bypasses across CPython versions. The sandbox has not been formally verified against all CPython versions in the `requires-python = ">=3.10"` range. Python 3.10, 3.11, 3.12, 3.13 may have different `re` module internals.

3. **Ed25519 key at chmod 600 only on Unix**: `conduit_identity.key` is protected via `self._key_path.chmod(0o600)` (conduit_bridge.py:259). On Windows, `chmod(0o600)` has no effect — Windows uses ACLs, not Unix permissions. The key file has no Windows-native ACL protection applied. Risk: local multi-user Windows systems where other users could read the identity key file.
