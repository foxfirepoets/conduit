# Kraken Verification: Agent-Marketing Features
## Date: 2026-03-12
## Confidence: 92/100
## Verdict: VERIFIED (with one noted gap)

---

## Verification Scope

Three claims were evaluated:

1. Every MCP response now carries an AIVS-Micro proof (`_conduit_proof` key) via `_attach_micro_proof()` in `conduit_bridge.py`
2. Every proof bundle now contains `agent_discovery` metadata in `manifest.json`
3. Version bumped to 0.2.1 in `pyproject.toml` and the proof bundle manifest

---

## Claim 1: `_conduit_proof` in MCP responses

### Source inspection: PASS

`tools/conduit_bridge.py:1101-1138` — `_attach_micro_proof(self, result, action)` is implemented and does exactly what is claimed:
- Skips proof-export actions (`export_proof`, `export_micro`) correctly
- Skips responses that contain an `error` key
- Computes a SHA-256 hash of the result dict as the `dom_hash`
- Constructs a `ConduitProof` with the bridge's `_identity` and `_audit_log`
- Calls `export_micro(scan_origin="mcp_response")`
- Attaches the 6-field `micro_proof` dict to `result["_conduit_proof"]`
- Wraps the entire operation in a bare `except Exception` with `logger.debug` — so failures are silent

The call site is `tools/conduit_bridge.py:1428-1429`:
```python
if isinstance(result, dict):
    result = self._attach_micro_proof(result, action)
```
This is inside `execute()`, after the action coroutine resolves, before `json.dumps(result)`. The integration point is correct.

### Test execution: PASS

`python -m pytest tests/test_marketing_features.py -v` — 22/22 tests passed.

Tests cover:
- `test_micro_proof_attached_to_navigate_result` — verifies 6 fields present and `_conduit_proof` key set
- `test_micro_proof_has_six_fields` — asserts exact key set
- `test_micro_proof_scan_origin_is_mcp_response` — asserts `scan_origin` value
- `test_error_result_skips_proof` — asserts error gate logic is correct
- `test_proof_signature_is_ed25519` — asserts signature prefix
- `test_content_hash_deterministic` — determinism of content hashing
- `test_micro_proof_overhead_under_500_bytes` — size constraint

### Live verification: PASS

Kraken verification script (`scripts/kraken_live_verify.py`) ran 34 checks, all passed.

Micro-proof size at runtime: **349 bytes** (target was ~200, limit is 500 — within budget).

### Gap Noted (Medium severity)

The `test_browser_actions.py::TestExecuteInterface::test_execute_returns_string` test calls `execute()` and parses the JSON result, but does NOT assert that `_conduit_proof` is present in the parsed dict. This means the end-to-end integration path through `execute()` is not directly asserted in any test. The logic is verified by unit-level tests, but an execute-level regression test for `_conduit_proof` is absent.

This is a Medium gap — not a failure, but a future regression could be introduced silently.

---

## Claim 2: `agent_discovery` in proof bundles

### Source inspection: PASS

`tools/conduit_proof.py:358-388` — the `agent_discovery` block is present in the manifest dict built by `export()`. The 8 required fields are all present:

| Field | Value |
|---|---|
| `tool_name` | `"conduit-browser"` |
| `install_command` | `"pip install conduit-browser"` |
| `mcp_config` | `{"command": "python", "args": ["-m", "conduit_browser"]}` |
| `capabilities` | list of 9 entries |
| `proof_features` | dict with 6 sub-fields |
| `source_url` | `"https://github.com/bkauto3/Conduit"` |
| `pypi_url` | `"https://pypi.org/project/conduit-browser/"` |
| `license` | `"MIT"` |

### Test execution: PASS

11 tests in `TestAgentDiscoveryMetadata` cover every required field individually (tool_name, install_command, mcp_config, capabilities list, key capability entries, proof_features sub-fields, source_url, pypi_url, license, and backward compatibility of original manifest fields). All 11 passed.

### Live verification: PASS

Kraken script exported an actual `.tar.gz` bundle, extracted `session_proof/manifest.json`, and verified all 8 fields plus 3 proof_features sub-fields. All passed. The bundle was produced deterministically from mock audit rows and a mock identity.

---

## Claim 3: Version 0.2.1

### Source inspection: PASS

- `pyproject.toml:7` — `version = "0.2.1"` confirmed
- `tools/conduit_proof.py:350` — `"conduit_version": "0.2.1"` confirmed

### Test execution: PASS

`TestVersionBump::test_pyproject_version` and `TestVersionBump::test_manifest_conduit_version` both passed.

### Live verification: PASS

Kraken script read `pyproject.toml` directly and extracted `manifest.json` from a real bundle. Both confirmed `"0.2.1"`.

---

## Edge Cases Tested

All 4 edge case categories passed (34/34 Kraken checks total):

| Case | Result | Notes |
|---|---|---|
| Empty `url` and `dom_hash` to `export_micro()` | PASS | Returns success=True, 6 fields present |
| Result dict with `error` key (skip condition) | PASS | Skip gate fires correctly, no `_conduit_proof` attached |
| Large result dict (100KB, 1000 keys) | PASS | Completed in 0.002s, well under 1s budget |
| `export()` with no audit rows | PASS | Returns `{"success": False, "error": "..."}` gracefully |

---

## Full Test Suite Results

```
python -m pytest tests/ --ignore=tests/test_e2e_live.py --ignore=tests/test_ideabrowser_live.py --ignore=tests/test_aivs_live.py -q
270 passed, 97 warnings in 231.02s
```

270/270 tests passed. No regressions from the marketing feature additions.

Warnings are all `DeprecationWarning: __package__ != __spec__.parent` — this is a known cosmetic issue with the package shim pattern used in tests and does not affect test validity or runtime behavior.

---

## Issues Found

### Issue 1: Execute-level integration test missing for `_conduit_proof`
- **Severity**: Medium
- **Location**: `tests/test_browser_actions.py:297-302` (`TestExecuteInterface::test_execute_returns_string`)
- **Description**: The test calls `execute({"action": "navigate", "url": "..."})`, parses the JSON response, and confirms it is a dict — but never asserts `"_conduit_proof" in parsed`. This means if `_attach_micro_proof` were silently disabled or broken, this test would still pass.
- **Impact**: A future regression in the `execute()` → `_attach_micro_proof` call site could go undetected until a live test.
- **Recommendation**: Add one assertion: `assert "_conduit_proof" in parsed` to `test_execute_returns_string`.

### Issue 2: Silent failure swallowing in `_attach_micro_proof`
- **Severity**: Low
- **Location**: `tools/conduit_bridge.py:1135-1136`
- **Description**: The entire `_attach_micro_proof` body is wrapped in `except Exception as exc: logger.debug(...)`. This means any failure (including import errors, identity attribute errors, or `ConduitProof` bugs) silently drops the proof with no warning-level log. In production, agents expecting `_conduit_proof` would silently receive responses without it.
- **Impact**: Operational visibility gap. Not a functional bug under normal conditions.
- **Recommendation**: Escalate to `logger.warning` so silent failures surface in production logs.

---

## Confidence Breakdown

- Claim 1 source code: verified, integration point correct (25/25)
- Claim 1 tests: 22/22 marketing tests pass, but execute()-level assertion absent (-5)
- Claim 2 source code + live bundle extraction: verified (25/25)
- Claim 3 both locations: verified (10/10)
- Edge case coverage: all 4 cases handled correctly (10/10)
- Full suite regression: 270/270 (5/5)
- Deduction for silent exception swallowing: (-3)

**Final: 92/100**

---

## Verdict: VERIFIED

All three claims are functionally correct. The implementation exists, is wired up correctly, produces the claimed outputs, and the full test suite passes with no regressions. The two issues identified are Medium and Low severity and do not invalidate any of the three claims.
