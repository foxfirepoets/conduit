# HKO-Truth-Audit Report: Conduit Browser Package
**Date:** 2026-04-23
**Severity threshold:** HIGH
**OTA mode:** DESIGN-TIME (no transcript available)
**Code path:** C:\Users\Administrator\Desktop\Conduit
**Skill path:** skills/conduit.md

---

## Findings

### CAUSAL LINK Findings (fix these first)

**[CRITICAL] [HK+OTA] [CAUSAL LINK] CL-1 — SSRF partial bypass in browser._navigate()**
- **Location:** `tools/browser.py:542-548`
- **Description:** `_navigate()` blocks literal IP addresses but does NOT resolve hostnames. A URL like `http://internal-host/` that resolves to `192.168.x.x` bypasses the check. The bridge-layer `_block_private_ip()` (conduit_bridge.py:166) correctly resolves hostnames via `socket.getaddrinfo`, but `BrowserTool._navigate()` does not. Any caller that bypasses the bridge (direct BrowserTool use, tests, future consumers) is exposed.
- **OTA contract violated:** `skills/conduit.md:29` — "URL is validated (http/https only, no private IPs)"
- **Evidence:** `tools/browser.py:542-548` (scheme check present, hostname resolution absent); `conduit_bridge.py:166-195` (hostname resolution present)

**[HIGH] [HK+OTA] [CAUSAL LINK] CL-2 — Budget cap `or True` logic bug makes ledger errors silently bypass cap**
- **Location:** `tools/conduit_bridge.py:504`
- **Description:** `if self._ledger._conn is not None or True:` — the `or True` makes the branch unconditional. If the ledger connection is broken, `session_total_cents()` raises, the exception is swallowed, and the stale `_session_cost_cents_total` in-memory counter is used instead. This counter resets to 0 on each new ConduitBridge instance, so budget enforcement depends on ledger availability.
- **OTA contract violated:** `skills/conduit.md` — "enforced against the session budget cap before execution"
- **Evidence:** `conduit_bridge.py:504` (`or True`), `conduit_bridge.py:528-537` (budget check queries ledger)

---

### HIGH Findings

**[HIGH] [HK] F3 — Rubric sandbox exposes `re` module enabling potential escape**
- **Location:** `tools/rubric.py:79-88`, `tools/rubric.py:142`
- **Description:** `re` module is injected into `_SAFE_GLOBALS` for custom_check eval. Python's `re.compile` returns an object with `__class__.__mro__` accessible via attribute chains. The AST checker blocks `.__class__` (dunder block at line 115), but attribute chains via `re.compile(...).scanner` and other non-dunder paths may permit introspection. This is the widest attack surface remaining in the otherwise solid sandbox.
- **Evidence:** `rubric.py:88` (`"re": re` in `_SAFE_LOCALS`); `rubric.py:114-116` (dunder block); tests `test_verify_rubric.py:307,319` confirm `__import__` and `exec` are blocked but do not test `re`-based escape

**[HIGH] [MULTI: HK+OTA+RIO] MULTI-1 — Documentation drift: ~/.cato paths remain after portability fix**
- **Locations:** `skills/conduit.md:62`, `tools/browser.py:9`, `tools/browser.py:124`
- **Description:** The portability refactor correctly moved all code to use `conduit_platform.get_data_dir()`, but three documentation strings still advertise `~/.cato/...` paths. Agents consuming `skills/conduit.md` will receive incorrect path information. Users reading `browser.py` docstrings will be misled about where data is stored.
- **Evidence:**
  - `skills/conduit.md:62`: "Saved to `~/.cato/workspace/screenshots/`"
  - `tools/browser.py:9`: "persistent profile at `~/.cato/browser_profile/`"
  - `tools/browser.py:124`: "persistent browser profile at `~/.cato/browser_profile/`"
  - `conduit_platform.py`: actual path on Windows is `%LOCALAPPDATA%\Conduit`

---

### MEDIUM Findings

**[MEDIUM] [HK] F5 — MCP server shim sets attribute named `"platform"` on cato package**
- **Location:** `conduit_mcp_server.py:36`
- **Description:** `setattr(sys.modules["cato"], _alias.split(".")[-1], _pmod)` sets `cato.platform` as an attribute. This creates a `cato.platform` attribute that returns our `conduit_platform.py` module, which could mislead any code that accesses `cato.platform` expecting Python's stdlib `platform` module.
- **Evidence:** `conduit_mcp_server.py:28-36`

**[MEDIUM] [HK] F6 — conduit_platform.py passes Path object as `os.environ.get()` default**
- **Location:** `conduit_platform.py:41`
- **Description:** `os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")` — `os.environ.get()` is typed to accept `str` as default. Passing a `Path` works at runtime due to Python duck-typing, but is technically incorrect. In a strict type-checking environment or future Python version this could raise.
- **Evidence:** `conduit_platform.py:41`

**[MEDIUM] [RIO] F7 — Individual test bootstrap functions install only `cato.platform`, not `cato.conduit_platform`**
- **Location:** 10+ test files (`test_audit_chain.py:44-48`, `test_browser_actions.py:41-45`, `test_verify_rubric.py:43-46`, etc.)
- **Description:** Each test file's private `_bootstrap()` function installs `cato.platform` shim but not `cato.conduit_platform`. This works when run via pytest (conftest.py installs both first), but will fail if any test file is ever run directly (`python tests/test_audit_chain.py`) or in a test runner that doesn't honor conftest.py loading order.
- **Evidence:** `tests/test_audit_chain.py:44-47` (only `cato.platform`); `tests/conftest.py:37-43` (both aliases installed by conftest)

---

## Task Status Table

| Task | Status | Note |
|------|--------|------|
| Create conduit_platform.py | implemented | File exists, all 4 OS branches correct |
| Rename .platform → .conduit_platform imports (5 sites) | implemented | All confirmed via grep |
| Remove hardcoded ~/.cato/workspace/.conduit in browser.py | implemented | browser.py:845 uses `_CATO_DIR` |
| Remove hardcoded ~/.cato/proofs in conduit_proof.py | implemented | conduit_proof.py:323-326 uses get_data_dir() |
| Fix conduit_mcp_server.py bootstrap shim | implemented | Lines 16-44 operational |
| Fix conftest.py tempdir | implemented | Uses tempfile.gettempdir() |
| Fix test_conduit_proof.py patch string | implemented | Matches .conduit_platform |
| Update skills/conduit.md to remove ~/.cato references | partial | Line 62 still shows ~/.cato/workspace/screenshots/ |
| Update browser.py docstrings | partial | Lines 9, 124 still show ~/.cato/browser_profile/ |
| Individual test bootstrap functions: install cato.conduit_platform | partial | Only cato.platform installed in 10+ files |
| Marketplace tests (fiverr/upwork) | broken (pre-existing) | Confirmed pre-dates portability changes via git stash |

---

## Deduplication Log

- `{HK-2, OTA-cosmetic, RIO-partial(docs)}` → merged as MULTI-1 "Documentation drift: ~/.cato paths" at HIGH. Three layers all flag the same root cause: documentation surfaces were not updated during the portability refactor.

---

## Causal Links

1. **CL-1:** Code bug at `tools/browser.py:542-548` (SSRF hostname non-resolution) causes OTA contract violation at `skills/conduit.md:29` ("no private IPs"). The SSRF block in the bridge layer cannot protect callers who use BrowserTool directly.

2. **CL-2:** Code bug at `conduit_bridge.py:504` (`or True` budget bypass) causes OTA contract violation — budget cap enforcement relies on ledger availability but silently degrades to unverified in-memory counter on error.

---

## Crux

The portability contract (no hardcoded paths) is correctly implemented in all code paths but incompletely applied to documentation surfaces — `skills/conduit.md` and `browser.py` docstrings still advertise `~/.cato/` paths, creating a drift between what the code does and what agents and developers are told to expect. Two pre-existing security issues (SSRF partial bypass in BrowserTool and budget cap logic error) are present independently of the portability work.

---

## Remediation Plan

### Priority 1: CAUSAL LINKs

**CL-1 [CRITICAL, code_fix, `tools/browser.py:542-548`]**
Add hostname resolution to `_navigate()` matching `_block_private_ip()` in conduit_bridge.py:
```python
# In _navigate(), after scheme check, before page.goto():
import socket
host = parsed.hostname or ""
try:
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_link_local or addr.is_loopback:
            return {"error": f"Blocked internal IP: {host}"}
    except ValueError:
        for info in socket.getaddrinfo(host, None):
            raw_ip = info[4][0]
            try:
                addr = ipaddress.ip_address(raw_ip)
                if addr.is_private or addr.is_link_local or addr.is_loopback:
                    return {"error": f"Blocked internal IP resolved from hostname: {host} -> {raw_ip}"}
            except ValueError:
                pass
except OSError:
    pass  # DNS failure — let page.goto() raise
```

**CL-2 [HIGH, code_fix, `tools/conduit_bridge.py:504`]**
Remove `or True` from budget property:
```python
# Change:
if self._ledger._conn is not None or True:
# To:
if self._ledger._conn is not None:
```

### Priority 2: HIGH (non-causal)

**F3 [HIGH, code_fix, `tools/rubric.py:88`]**
Remove `re` from `_SAFE_LOCALS`. Existing `must_contain`/`must_not_contain` predicates call `re.search()` directly in `evaluate_rubric()`, not via `eval()`:
```python
_SAFE_LOCALS: dict[str, Any] = {
    "len": len, "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict,
}
```

**MULTI-1 [HIGH, integration_fix]**
Update three documentation strings:
- `skills/conduit.md:62`: `~/.cato/workspace/screenshots/` → `{data_dir}/workspace/screenshots/ (see conduit_platform.py)`
- `tools/browser.py:9`: `~/.cato/browser_profile/` → `{data_dir}/browser_profile/`
- `tools/browser.py:124`: `~/.cato/browser_profile/` → `{data_dir}/browser_profile/`

### Priority 3: MEDIUM

**F6 [MEDIUM, code_fix, `conduit_platform.py:41`]**
```python
# Change:
base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
# To:
base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))
```

**F5 [MEDIUM, code_fix, `conduit_mcp_server.py:36`]**
Use explicit attribute name to avoid `cato.platform` shadowing the stdlib:
```python
# Change:
setattr(sys.modules["cato"], _alias.split(".")[-1], _pmod)
# To:
attr_name = "conduit_platform" if "conduit_platform" in _alias else "platform"
setattr(sys.modules["cato"], attr_name, _pmod)
```

**F7 [MEDIUM, integration_fix, `tests/`]**
In every `_bootstrap()` function that installs `cato.platform`, add a matching `cato.conduit_platform` entry:
```python
for _alias in ("cato.platform", "cato.conduit_platform"):
    if _alias not in sys.modules:
        mod = types.ModuleType(_alias)
        mod.get_data_dir = lambda: tmp_db.parent
        sys.modules[_alias] = mod
        setattr(cato_pkg, _alias.split(".")[-1], mod)
```
Affected files: test_audit_chain.py, test_browser_actions.py, test_verify_rubric.py, test_conduit_crawl.py, test_conduit_monitor.py, test_captcha.py, test_e2e_live.py, test_extraction_actions.py, test_stealth.py, test_verify_deliverable.py, test_web_search.py, test_aivs_live.py.

---

## Verification Summary

| Command | Result | Scope | Note |
|---------|--------|-------|------|
| `pytest tests/test_audit_chain.py tests/test_conduit_proof.py tests/test_browser_actions.py` | passed (96 tests) | in-scope | Core portability tests pass |
| `pytest tests/` (full suite, non-live) | 528 passed, 17 failed, 10 errors | in-scope | All failures pre-exist; confirmed via git stash |
| `git stash → pytest test_marketplace_service.py` | 14 failed before portability changes | in-scope | Marketplace failures pre-date this work |
| `python -c "audit.py load without cato.conduit_platform"` | passed | in-scope | Lazy imports prevent failure when test bootstrap is incomplete |
