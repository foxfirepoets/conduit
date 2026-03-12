# Hudson Audit: Agent-Marketing Features
## Date: 2026-03-12
## Verdict: APPROVED WITH NOTES
## Test Results: 270/270 passed (100%)
## Auditor: Hudson (Senior Code Review Agent)

---

## Executive Summary

The three agent-marketing features — AIVS-Micro proof attachment to every MCP response, `agent_discovery` metadata in proof bundle manifests, and the version bump to 0.2.1 — are correctly implemented, well-integrated with the existing cryptographic infrastructure, and do not introduce regressions. All 270 tests pass.

Two issues are flagged for follow-up: a documentation inaccuracy in the `mcp_config` command that would prevent agents from actually using the advertised install path, and a per-call file I/O operation inside the hot MCP response path. Neither blocks shipping but both should be addressed before the agent-discovery marketing claim is considered production-accurate.

---

## Test Results

```
Platform: win32, Python 3.13.2, pytest 9.0.2
Command: python -m pytest tests/ -v
         --ignore=tests/test_e2e_live.py
         --ignore=tests/test_ideabrowser_live.py
         --ignore=tests/test_aivs_live.py

Result: 270 passed, 0 failed, 97 warnings in 227.59s
```

The 97 warnings are pre-existing `DeprecationWarning: 'count' is passed as positional argument` from `re.sub()` calls in `tools/browser.py`. These are unrelated to this PR and do not affect correctness.

New tests from `tests/test_marketing_features.py`: 22 tests, all passing.

---

## Feature 1: `_conduit_proof` (AIVS-Micro) in every MCP response

### What was reviewed
- `tools/conduit_bridge.py`, lines 1097–1138: `_attach_micro_proof()` method
- `tools/conduit_bridge.py`, lines 1427–1429: call site inside `execute()`

### Assessment

The implementation is correct and fits cleanly into the existing architecture. `_attach_micro_proof` is a pure decorator on successful tool-call results — it never mutates the audit chain, never writes to the billing ledger, and never blocks action execution because the entire computation is wrapped in a broad `except Exception` that degrades gracefully to a `logger.debug` log.

The guard logic `if action in ("export_proof", "export_micro")` is correct — those actions already return proof structures and should not be recursively wrapped. The secondary guard `result.get("error")` exploits Python's truthiness: empty string `''` and `None` are falsy, so an action result with `"error": ""` (the convention for successful actions in this codebase) will correctly receive a proof.

The content hash uses `json.dumps(result, sort_keys=True, default=str)`, which is deterministic for identical inputs. The `default=str` fallback handles non-JSON-serializable types (datetime objects, custom classes). For genuine circular references, `json.dumps` raises a `ValueError`, which is caught by the surrounding `except Exception`, causing the proof to be silently skipped — this is the correct production behavior.

The `scan_origin="mcp_response"` annotation accurately distinguishes auto-attached proofs from manually exported micro-proofs, which is valuable for downstream consumers of the proof.

### Issues

**[LOW] Documentation accuracy: claimed proof size is ~200 bytes, actual is ~380-430 bytes**

The module docstring in `conduit_proof.py` and the `_attach_micro_proof` docstring in `conduit_bridge.py` both describe the AIVS-Micro proof as "~200 bytes." Measurement shows otherwise:

```
Minimal proof (unsigned, short URL):  313 bytes
With Ed25519 signature:               401 bytes
Typical proof (real URL, signed):     ~420-450 bytes
```

The 500-byte test threshold in `test_micro_proof_overhead_under_500_bytes` is correctly set and the implementation passes it. But the "~200 bytes" figure in both docstrings is inaccurate by roughly 2x. This matters for agents that use the proof-size claim in their evaluation of whether to adopt Conduit.

**[MEDIUM] Per-call file system read in hot MCP path**

Inside `export_micro()` (called on every MCP tool-call response), `conduit_proof.py` reads its own source file from disk on every invocation:

```python
scanner_version_hash = hashlib.sha256(
    Path(__file__).read_bytes()
).hexdigest()
```

Benchmarked cost on this machine: **0.44ms per call** (1000 iterations, 16,810-byte file). For interactive browsing sessions this is negligible. For high-frequency automated pipelines executing dozens of actions per second, this adds measurable latency and unnecessary I/O. The hash value is constant for a given deployment — it only changes when the file changes.

This is not a bug, but it is a missed optimization opportunity. The file hash could be computed once at module load and cached as a module-level constant.

**[LOW] Weak test coverage for error-response skip behavior**

`test_error_result_skips_proof` in `tests/test_marketing_features.py` (line 212–217) does not actually exercise `_attach_micro_proof`. It creates a dict with an `"error"` key and asserts only that `"error" in result` is True. The test would pass even if `_attach_micro_proof` was deleted entirely. The guard logic inside the method is never invoked by this test.

The logic itself is correct, but a more meaningful test would call `_attach_micro_proof` directly with an error-result dict and assert that `"_conduit_proof"` is absent from the returned dict.

---

## Feature 2: `agent_discovery` metadata in proof bundle manifests

### What was reviewed
- `tools/conduit_proof.py`, lines 344–395: `agent_discovery` block inside `manifest` dict in `export()`

### Assessment

The `agent_discovery` block is structurally sound and well-positioned. It sits inside the bundle manifest alongside `session_id`, `chain_hash`, `generator_url`, and `ecosystem` — all of which were preserved without regression (confirmed by `test_existing_manifest_fields_preserved`).

The 9 capability strings are accurate for the current codebase. `proof_features` correctly describes the cryptographic stack in use. `source_url` and `pypi_url` match the actual repository and package names. `license` is MIT, matching `pyproject.toml` and `LICENSE`.

The design goal is sound: every proof bundle exported by any Conduit instance becomes a self-contained discovery artifact. This is a low-cost, high-value marketing play that requires no external service calls.

### Issues

**[HIGH] `mcp_config.args` command does not work after `pip install conduit-browser`**

The advertised MCP configuration is:

```json
"mcp_config": {
    "command": "python",
    "args": ["-m", "conduit_browser"]
}
```

This command will fail after `pip install conduit-browser` because:

1. The installed wheel ships files at the root (`audit.py`, `tools/browser.py`, etc.) with no `conduit_browser` package directory and no `conduit_browser/__main__.py`.
2. The wheel defines no `console_scripts` entry point.
3. There is no `conduit_browser.py` module at the root of the package.

Verified by inspecting the built wheel (`dist/conduit_browser-0.2.1-py3-none-any.whl`):
- No `entry_points.txt` in `dist-info`
- No `conduit_browser/__main__.py`
- No `conduit_browser.py`

The README shows the correct command for development use: `python -m tools.conduit_bridge`. The `server.json` uses the PyPI package name but relies on the transport type `stdio` without specifying a command (deferred to the MCP client).

An agent that reads a proof bundle and follows `mcp_config` literally will fail to start the server. This undermines the agent-discovery marketing value proposition — the entire point of embedding `agent_discovery` is to let an agent self-bootstrap its toolchain, and the advertised command does not work.

This is the most important issue in this PR.

---

## Feature 3: Version bump to 0.2.1

### What was reviewed
- `tools/conduit_proof.py`, line 350: `"conduit_version": "0.2.1"`
- `pyproject.toml`, line 6: `version = "0.2.1"`
- `server.json`, line 9: `"version": "0.2.1"`

### Assessment

Version is consistent across all three locations. `TestVersionBump` verifies both `pyproject.toml` and the manifest output. The built wheel in `dist/` is `conduit_browser-0.2.1-py3-none-any.whl`, confirming the version was already bumped before the wheel was built. No issues.

---

## Pre-existing Issues Noted (Not Introduced by This PR)

**`export_micro` missing from `_ALL_ACTIONS` in `execute()`**

`export_micro` is correctly registered in the `dispatch` dict at line 1393 and is fully functional. However, it is absent from the `_ALL_ACTIONS` list at line 1292–1311, which is only used to populate the error message when an unknown action is received. If `execute()` is called with an unknown action, the error string `"Unknown conduit action: x. Valid: [list]"` will not mention `export_micro`. This is a cosmetic discoverability gap, not a functional bug, and pre-dates this PR.

**`re.sub` deprecation warnings in `tools/browser.py`**

Lines 84–86 pass `re.IGNORECASE` as the `count` positional argument instead of as the `flags` keyword argument. This is a pre-existing bug that generates 97 deprecation warnings across the test suite. Not introduced by this PR.

---

## Issues Summary

| Severity | Issue | File | Line |
|----------|-------|------|------|
| HIGH | `mcp_config.args: ["-m", "conduit_browser"]` does not work after `pip install` | `tools/conduit_proof.py` | 362–364 |
| MEDIUM | `scanner_version_hash` reads file from disk on every MCP call — no caching | `tools/conduit_proof.py` | 258–260 |
| LOW | Docstrings claim "~200 bytes" for micro-proof; actual measured size is ~380-430 bytes | `tools/conduit_proof.py` line 243, `tools/conduit_bridge.py` line 1107 | |
| LOW | `test_error_result_skips_proof` does not actually call `_attach_micro_proof` | `tests/test_marketing_features.py` | 212–217 |

---

## Recommendations

1. **Fix `mcp_config` before this feature is used in production marketing.** Either add a `conduit_browser/__main__.py` to the package that starts the MCP server, define a `console_scripts` entry point in `pyproject.toml` (e.g., `conduit-browser = "tools.conduit_bridge:main"`), or correct `mcp_config.args` to reflect the actual working invocation. The README's `"args": ["-m", "tools.conduit_bridge"]` is the most honest answer for the current package structure, though it requires running from the repo root. A proper entry point is the clean production solution.

2. **Cache `scanner_version_hash` at module level.** The SHA-256 of `conduit_proof.py` is a constant for any given deployment. Move the computation outside of `export_micro()` to a module-level constant or a `functools.lru_cache(maxsize=1)` wrapper. This eliminates the per-call disk read.

3. **Correct the "~200 bytes" size claim** in the `export_micro` docstring and `_attach_micro_proof` docstring to "~400 bytes" or simply "under 500 bytes," matching the test threshold.

4. **Strengthen `test_error_result_skips_proof`** to actually invoke the guard. The test framework already has a standalone `ConduitProof` import and the `_attach_micro_proof` logic is reproducible without the full `cato` package. A test that passes an error-dict through a simulated version of the guard and asserts `_conduit_proof` is absent would provide real regression protection.

5. Consider adding `export_micro` to `_ALL_ACTIONS` in `conduit_bridge.py:execute()` to keep the error-message help text complete. This is a pre-existing gap but a trivial one-line fix.

---

## Strengths

The implementation shows good production instincts throughout:

- The `except Exception` catch in `_attach_micro_proof` is exactly right for an optional marketing annotation on a latency-sensitive path. Proof attachment must never break action execution.
- `sort_keys=True, default=str` in the content hash is a thoughtful choice — it handles dict key ordering nondeterminism and gracefully degrades for non-serializable types without crashing.
- `scan_origin="mcp_response"` as a distinct value from `"local"` is a clean design that preserves the semantic difference between auto-attached proofs and explicitly exported ones.
- The `agent_discovery` block is comprehensive — 9 capabilities, 6 proof features, URLs for both GitHub and PyPI. An agent evaluating whether to adopt Conduit gets everything it needs in one place.
- Zero regression across all 270 existing tests. The manifest additions in Feature 2 are purely additive.
- Version consistency is maintained across `pyproject.toml`, `conduit_proof.py`, and `server.json`.
