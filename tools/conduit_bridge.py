"""
cato/tools/conduit_bridge.py — Opt-in browser engine backed by local billing ledger.

Drop-in replacement for browser.py when conduit_enabled=true in config.
Uses the same action interface as BrowserTool but tracks per-action costs
in a local SQLite ledger (no external server required).

Ed25519 identity key is stored in {data_dir}/conduit_identity.key for audit
trail integrity. Billing is recorded in cato.db table conduit_billing.

Action costs:
    All actions = 0 cents (billing disabled for local Cato use)

VOIX protocol: strips <tool>...</tool> and <context>...</context> tags
from extracted HTML/text content before returning to agent.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import logging
import re
import socket
import sqlite3
import time
import urllib.request as _urllib_req
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

# Consumers load this module standalone via importlib.util.spec_from_file_location
# (Conduit is "a sibling project, not a pip package" — see google-workspace's
# browser.py), which gives it no parent package, so the package-relative imports
# below raise "attempted relative import with no known parent package". Fall back
# to path-based absolute imports, adding this file's directory and its parent
# (the Conduit root) to sys.path so `audit` and `rubric` resolve either way.
try:
    from ..audit import AuditLog
    from .rubric import evaluate_rubric, make_rubric_hash
except ImportError:
    import sys as _sys

    _here = Path(__file__).resolve().parent
    for _p in (_here.parent, _here):
        if str(_p) not in _sys.path:
            _sys.path.insert(0, str(_p))
    from audit import AuditLog
    from rubric import evaluate_rubric, make_rubric_hash

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTION_COSTS: dict[str, int] = {
    # Wave 0
    "navigate":               0,
    "click":                  0,
    "type":                   0,
    "fill":                   0,
    "extract":                0,
    "screenshot":             0,
    # Wave 1
    "scroll":                 0,
    "wait":                   0,
    "wait_for":               0,
    "key_press":              0,
    "hover":                  0,
    "select_option":          0,
    "handle_dialog":          0,
    "navigate_back":          0,
    "console_messages":       0,
    # Wave 2
    "eval":                   0,
    "extract_main":           0,
    "extract_structured":     0,
    "js_delta":               0,
    "output_to_file":         0,
    "accessibility_snapshot": 0,
    "network_requests":       0,
    # Wave 3
    "map":                    0,
    "crawl":                  0,
    "fingerprint":            0,
    "check_changed":          0,
    "export_proof":           0,
    "export_micro":           0,
    "login":                  0,
    "check_session":          0,
    "save_cookies":           0,
    "load_cookies":           0,
    "search":                 0,
    # Wave 4: CAPTCHA
    "detect_captcha":         0,
    "solve_captcha":          0,
    "solve_captcha_vision":   0,
    # Wave 5: Proxy
    "rotate_proxy":           0,
    # Wave 6: Web Search
    "web_search":             0,
    "academic_search":        0,
    # Wave 8: Marketplace product
    "marketplace_list":       0,
    "marketplace_targets":    0,
    "marketplace_plan":       0,
    "marketplace_create_job": 0,
    "marketplace_get_job":    0,
    "marketplace_list_jobs":  0,
    "marketplace_create_account": 0,
    "marketplace_list_accounts":  0,
    "marketplace_create_proxy":   0,
    "marketplace_list_proxies":   0,
    "marketplace_get_proxy":      0,
    "marketplace_test_proxy":     0,
    "marketplace_save_session":   0,
    "marketplace_get_session":    0,
    "marketplace_list_sessions":  0,
    "marketplace_bootstrap_session": 0,
    "marketplace_execute_job":    0,
    "marketplace_enqueue_job":    0,
    "marketplace_queue_status":   0,
    "marketplace_get_result":     0,
    "marketplace_list_results":   0,
    "marketplace_export_result":  0,
    # Wave 9: Downloads
    "capture_download":       2,
    "get_downloads":          0,
    # Wave 10: YouTube
    "youtube_transcript":     3,
    # Internal events
    "selector_healing":       0,
    "verify_deliverable":     0,
    "verify_rubric":          0,
}

_VOIX_TAGS_RE = re.compile(r"<(tool|context)>.*?</(tool|context)>", re.DOTALL)


def _validate_against_schema(data: Any, schema: dict) -> tuple[bool, str]:
    """Simple validation: required keys present, types match. Returns (ok, error_message)."""
    if not isinstance(data, dict):
        return False, "response is not a dict"
    required = schema.get("required", [])
    for k in required:
        if k not in data:
            return False, f"missing required key: {k!r}"
    props = schema.get("properties", {})
    for k, v in data.items():
        if k in props and props[k]:
            t = props[k].get("type")
            if t == "string" and not isinstance(v, str):
                return False, f"{k!r} should be string"
            if t == "number" and not isinstance(v, (int, float)):
                return False, f"{k!r} should be number"
            if t == "integer" and not isinstance(v, int):
                return False, f"{k!r} should be integer"
            if t == "boolean" and not isinstance(v, bool):
                return False, f"{k!r} should be boolean"
            if t == "array" and not isinstance(v, list):
                return False, f"{k!r} should be array"
            if t == "object" and not isinstance(v, dict):
                return False, f"{k!r} should be object"
    return True, ""

_BILLING_SCHEMA = """
CREATE TABLE IF NOT EXISTS conduit_billing (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    cost_cents  INTEGER NOT NULL DEFAULT 0,
    timestamp   REAL    NOT NULL,
    url_or_sel  TEXT    NOT NULL DEFAULT '',
    success     INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_conduit_session ON conduit_billing(session_id);
"""


# ---------------------------------------------------------------------------
# Security helpers (used by verify_deliverable and verify_rubric)
# ---------------------------------------------------------------------------

def _block_private_ip(url: str) -> str:
    """Return an error string if the hostname resolves to a private/loopback IP, or empty string if safe."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return f"Blocked URL scheme: {parsed.scheme}. Only http/https allowed."
        host = parsed.hostname or ""
        # First check if host is already a literal IP
        try:
            addr = ipaddress.ip_address(host)
            if addr.is_private or addr.is_link_local or addr.is_loopback:
                return f"Blocked internal IP: {host}"
        except ValueError:
            pass  # Not a literal IP — resolve it
        # Resolve hostname and check all returned addresses
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                raw_ip = info[4][0]
                try:
                    addr = ipaddress.ip_address(raw_ip)
                    if addr.is_private or addr.is_link_local or addr.is_loopback:
                        return f"Blocked internal IP resolved from hostname: {host} -> {raw_ip}"
                except ValueError:
                    pass
        except OSError:
            pass  # DNS failure — let urllib raise its own error
    except Exception as exc:
        return f"IP validation error: {exc}"
    return ""


class _SafeRedirectHandler(_urllib_req.HTTPRedirectHandler):
    """Re-run private-IP check on every redirect target to prevent SSRF via 302."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        err = _block_private_ip(newurl)
        if err:
            raise ValueError(f"Blocked redirect: {err}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class BudgetExceededError(RuntimeError):
    """Raised when a Conduit action would exceed the per-session budget."""


class MarketplaceExecutionError(RuntimeError):
    def __init__(self, message: str, *, failure_class: str, artifact_path: str = "") -> None:
        super().__init__(message)
        self.failure_class = failure_class
        self.artifact_path = artifact_path


# ---------------------------------------------------------------------------
# Ed25519 identity (local keypair)
# ---------------------------------------------------------------------------

class ConduitIdentity:
    """
    Manages a local Ed25519 keypair stored in {data_dir}/conduit_identity.key.

    The key is used to sign audit receipts — it never leaves the local machine.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        from ..conduit_platform import get_data_dir
        self._key_path = (data_dir or get_data_dir()) / "conduit_identity.key"
        self._private_key: Optional[bytes] = None
        self._public_key: Optional[bytes] = None

    def _load_or_create(self) -> None:
        """Load existing keypair or generate a new one (private implementation)."""
        if self._private_key is not None:
            return

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import (
                Encoding, PrivateFormat, NoEncryption, PublicFormat,
            )

            if self._key_path.exists():
                raw = self._key_path.read_bytes()
                private_key = Ed25519PrivateKey.from_private_bytes(raw)
            else:
                private_key = Ed25519PrivateKey.generate()
                raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
                self._key_path.parent.mkdir(parents=True, exist_ok=True)
                self._key_path.write_bytes(raw)
                self._key_path.chmod(0o600)
                logger.info("ConduitIdentity: new Ed25519 keypair generated at %s", self._key_path)

            self._private_key = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            pub = private_key.public_key()
            self._public_key = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)

        except ImportError:
            logger.warning("cryptography library unavailable — identity signing disabled")
            self._private_key = b"\x00" * 32
            self._public_key = b"\x00" * 32

    # Public alias so callers don't need to know the underscore convention
    def load_or_create(self) -> None:
        """Public alias for _load_or_create — load or generate the Ed25519 keypair."""
        self._load_or_create()

    @property
    def public_key_hex(self) -> str:
        """Return the public key as a 64-character hex string (property)."""
        self._load_or_create()
        return (self._public_key or b"").hex()

    def public_key_hex_method(self) -> str:
        """Backward-compat method form — prefer the property."""
        return self.public_key_hex

    def sign(self, payload: bytes) -> bytes:
        """Sign payload with the Ed25519 private key."""
        self._load_or_create()
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            pk = Ed25519PrivateKey.from_private_bytes(self._private_key)
            return pk.sign(payload)
        except Exception as exc:
            logger.warning("Ed25519 signing failed: %s", exc)
            return b""


# ---------------------------------------------------------------------------
# Billing ledger
# ---------------------------------------------------------------------------

class ConduitBillingLedger:
    """Append-only SQLite billing ledger stored in cato.db."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        from ..conduit_platform import get_data_dir
        self._db_path = db_path or (get_data_dir() / "cato.db")
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_BILLING_SCHEMA)
        self._conn.commit()

    def record(
        self,
        session_id: str,
        action: str,
        cost_cents: int,
        url_or_selector: str = "",
        identity_or_success: "Any" = True,
    ) -> None:
        """Record one billing event.

        The 5th argument accepts either:
        - bool / int — success flag (original internal usage)
        - ConduitIdentity — identity object passed by audit spec callers (ignored;
          the local ledger does not need to verify the identity signature)
        """
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        # Normalize the 5th arg: if it's a bool/int use it; otherwise treat as success=True
        if isinstance(identity_or_success, (bool, int)):
            success_flag = int(bool(identity_or_success))
        else:
            success_flag = 1  # identity object passed — default success
        self._conn.execute(
            "INSERT INTO conduit_billing (session_id, action, cost_cents, timestamp, url_or_sel, success)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, action, cost_cents, time.time(), url_or_selector, success_flag),
        )
        self._conn.commit()

    def session_total(self, session_id: str) -> int:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT COALESCE(SUM(cost_cents), 0) FROM conduit_billing WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row[0]) if row else 0

    def session_total_cents(self, session_id: str) -> int:
        """Alias for session_total — returns total cents spent in session."""
        return self.session_total(session_id)


# ---------------------------------------------------------------------------
# VOIX helpers
# ---------------------------------------------------------------------------

def _strip_voix_tags(html: str) -> str:
    """Remove <tool>...</tool> and <context>...</context> tags from extracted content."""
    return _VOIX_TAGS_RE.sub("", html).strip()


async def _sync_as_coro(fn, *args, **kwargs):
    """Wrap a synchronous callable so it can be awaited in the execute() dispatcher."""
    return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# ConduitBridge
# ---------------------------------------------------------------------------

class ConduitBridge:
    """
    Opt-in browser engine with per-action cost tracking.

    Implements the same async interface as BrowserTool but charges per action
    and enforces a per-session budget cap.

    Two supported constructor styles::

        # Style 1 — keyword args (preferred):
        bridge = ConduitBridge(session_id="sess-001", budget_cents=100)

        # Style 2 — config dict + session_id positional (used by agent_loop/CLI):
        bridge = ConduitBridge({"conduit_budget_per_session": 100, "data_dir": "/tmp"}, "sess-001")

        await bridge.start()
        result = await bridge.navigate("https://example.com")
        await bridge.stop()
    """

    def __init__(
        self,
        session_id_or_config: "str | dict" = "default",
        session_id_if_config: str = "",
        budget_cents: int = 100,
        data_dir: Optional[Path] = None,
    ) -> None:
        # Support both call styles:
        #   ConduitBridge("sess-id", budget_cents=100)
        #   ConduitBridge({"conduit_budget_per_session": 100, "data_dir": ...}, "sess-id")
        if isinstance(session_id_or_config, dict):
            cfg = session_id_or_config
            _caller_session_id = session_id_if_config or ""
            self._budget_cents = int(cfg.get("conduit_budget_per_session", budget_cents))
            raw_data_dir = cfg.get("data_dir")
            data_dir = Path(raw_data_dir) if raw_data_dir else data_dir
            self._config = cfg
        else:
            _caller_session_id = str(session_id_or_config) if session_id_or_config != "default" else ""
            self._budget_cents = budget_cents
            self._config = {}

        # F27: validate budget_cents
        if self._budget_cents < 0:
            raise ValueError(f"budget_cents must be >= 0, got {self._budget_cents}")

        # F19: always generate a fresh session_id per instantiation so billing
        # costs never accumulate across restarts. Callers that pass an explicit
        # non-default session_id (e.g. test fixtures) keep their id.
        self._session_id = _caller_session_id if _caller_session_id and _caller_session_id != "default" else str(uuid.uuid4())

        self._session_cost_cents_total: int = 0

        from ..conduit_platform import get_data_dir
        from .core.session_pool import BrowserSessionPool

        self._data_dir = data_dir or get_data_dir()
        self._ledger_db_path = self._data_dir / "cato.db"

        self._identity = ConduitIdentity(self._data_dir)
        # Pass data_dir-based db_path so tests using tmp_path get an isolated ledger
        # instead of writing to the global ~/.cato/cato.db.
        ledger_db = self._ledger_db_path
        self._ledger = ConduitBillingLedger(db_path=ledger_db)
        # AuditLog shares the same db file as the billing ledger so both tables
        # live in one SQLite file (cato.db).  This is what feeds the SHA-256
        # hash chain used by verify_chain() / ReceiptWriter.
        self._audit_log = AuditLog(db_path=ledger_db)

        # Underlying browser (lazy init)
        self._browser_tool: Optional[Any] = None

        # Track last navigated URL so extract() can re-navigate if needed
        self._current_url: str = ""

        # Self-healing selectors: try ARIA + text fallbacks when CSS selector fails
        self._selector_healing_enabled: bool = True
        self._session_pool = BrowserSessionPool()
        self._marketplace_service: Optional[Any] = None
        self._marketplace_worker_pool: Optional[Any] = None
        self._marketplace_job_queue: Optional[Any] = None

    # ------------------------------------------------------------------
    # Public accessors for identity and ledger (used by audit/test code)
    # ------------------------------------------------------------------

    @property
    def identity(self) -> ConduitIdentity:
        return self._identity

    @identity.setter
    def identity(self, value: ConduitIdentity) -> None:
        self._identity = value

    @property
    def ledger(self) -> ConduitBillingLedger:
        return self._ledger

    @ledger.setter
    def ledger(self, value: ConduitBillingLedger) -> None:
        self._ledger = value

    async def start(self, headless: bool = True) -> None:
        """Initialize the browser, billing ledger, and audit log."""
        self._ledger.connect()
        self._audit_log.connect()
        # F29: rotate browser profile if session counter threshold reached
        self._maybe_rotate_browser_profile()
        # Lazy import to avoid circular deps
        from ..tools.browser import BrowserTool
        self._browser_tool = BrowserTool(headless=headless)
        logger.info(
            "ConduitBridge started — session=%s budget=%dc identity=%s",
            self._session_id, self._budget_cents, self._identity.public_key_hex[:16] + "...",
        )

    async def stop(self) -> None:
        """Gracefully close the browser."""
        if self._browser_tool:
            try:
                await self._browser_tool.close()
            except Exception as exc:
                logger.debug("ConduitBridge stop: %s", exc)
            self._browser_tool = None
        if self._marketplace_worker_pool:
            try:
                await self._marketplace_worker_pool.close_all()
            except Exception as exc:
                logger.debug("ConduitBridge marketplace worker stop: %s", exc)
            self._marketplace_worker_pool = None

    @property
    def session_cost_cents(self) -> int:
        """Return total cents spent in this session (queries ledger for accuracy)."""
        # Prefer ledger total so externally-recorded charges are included
        try:
            if self._ledger._conn is not None:
                ledger_total = self._ledger.session_total_cents(self._session_id)
                # Keep in-memory counter in sync
                self._session_cost_cents_total = ledger_total
                return ledger_total
        except Exception:
            pass
        return self._session_cost_cents_total

    def _audit(
        self,
        action: str,
        inputs: dict,
        result: Any,
        url_or_selector: str = "",
        error: str = "",
    ) -> None:
        """Unified accounting method: writes to BOTH billing ledger AND AuditLog hash chain.

        This is the ONLY method that should be called for new bridge actions.
        Every browser action is reflected in the SHA-256 chain AND the billing table.
        """
        cost = ACTION_COSTS.get(action.lower(), 0)

        # F6: atomically check budget AND record billing in a single EXCLUSIVE
        # transaction so concurrent calls cannot both pass the budget check
        # before either has been billed.
        if self._ledger._conn is None:
            self._ledger.connect()
        assert self._ledger._conn is not None
        conn = self._ledger._conn
        try:
            conn.execute("BEGIN EXCLUSIVE")
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_cents), 0) FROM conduit_billing WHERE session_id = ?",
                (self._session_id,),
            ).fetchone()
            current_total = int(row[0]) if row else 0
            if current_total + cost > self._budget_cents:
                conn.execute("ROLLBACK")
                raise BudgetExceededError(
                    f"Conduit budget {self._budget_cents}¢ would be exceeded by '{action}' ({cost}¢). "
                    f"Currently at {current_total}¢."
                )
            conn.execute(
                "INSERT INTO conduit_billing (session_id, action, cost_cents, timestamp, url_or_sel, success)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (self._session_id, action, cost, time.time(), url_or_selector, int(not bool(error))),
            )
            conn.execute("COMMIT")
        except BudgetExceededError:
            raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        self._session_cost_cents_total = current_total + cost

        # 2) Write to audit hash chain (audit_log table)
        # F2: audit failures are logged at ERROR and re-raised — an action
        # without an audit record is a broken invariant.
        try:
            self._audit_log.log(
                session_id=self._session_id,
                action_type="tool_call",
                tool_name=f"browser.{action}",
                inputs=inputs,
                outputs=result if isinstance(result, dict) else {"raw": str(result)},
                cost_cents=cost,
                error=error,
            )
        except Exception as exc:
            logger.error(
                "AUDIT WRITE FAILURE for action '%s': %s", action, exc, exc_info=True
            )
            raise

    # ------------------------------------------------------------------
    # Bridge action methods — all go through _audit() (not _charge())
    # ------------------------------------------------------------------

    async def navigate(self, url: str, retry_on_auth: bool = True) -> dict:
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("navigate", {"url": url})
        if "text" in result:
            result["text"] = _strip_voix_tags(result["text"])
        self._current_url = result.get("url", url)
        self._audit("navigate", {"url": url}, result, url_or_selector=url,
                    error=result.get("error", ""))
        if retry_on_auth and self._is_auth_wall(result.get("url", "")):
            cfg = getattr(self, "_config", {}) or {}
            vault = cfg.get("vault")
            if isinstance(vault, dict):
                from urllib.parse import urlparse
                domain = urlparse(url).netloc or url
                cred_key = cfg.get("session_credential_key", {}).get(domain) or cfg.get("login_credential_key")
                if cred_key:
                    login_result = await self.login(url, cred_key, vault=vault)
                    if login_result.get("success"):
                        result = await self._browser_tool._dispatch("navigate", {"url": url})
                        if "text" in result:
                            result["text"] = _strip_voix_tags(result["text"])
                        self._current_url = result.get("url", url)
                        self._audit("navigate", {"url": url, "after_login": True}, result, url_or_selector=url, error=result.get("error", ""))
            return result
        return result

    def _is_auth_wall(self, url: str) -> bool:
        """True if URL suggests an auth wall (login/signin/auth in path or query)."""
        u = (url or "").lower()
        return "login" in u or "signin" in u or "auth" in u

    async def check_session(self, url: str) -> dict:
        """Return {ok: true} if current page does not appear to be an auth wall."""
        assert self._browser_tool is not None
        current = self._current_url or (await self._browser_tool._dispatch("navigate", {"url": url})).get("url", "")
        ok = not self._is_auth_wall(current)
        self._audit("check_session", {"url": url}, {"ok": ok}, url_or_selector=url, error="" if ok else "auth_wall")
        return {"ok": ok}

    async def login(self, url: str, credential_key: str, vault: Any = None) -> dict:
        """
        Retrieve credentials from vault, navigate to url, fill login form, submit, store session cookies.
        Only credential_key (not values) is logged in the audit chain.
        vault: dict-like with .get(key) and .set(key, value). If None, uses config vault.
        """
        assert self._browser_tool is not None
        v = vault if vault is not None else (getattr(self, "_config", {}) or {}).get("vault")
        if not v or not hasattr(v, "get"):
            self._audit("login", {"url": url, "credential_key": credential_key}, {"success": False, "error": "no vault"}, error="no vault")
            return {"success": False, "error": "no vault"}
        creds = v.get(credential_key) if callable(getattr(v, "get", None)) else (v.get(credential_key) if isinstance(v, dict) else None)
        if not isinstance(creds, dict):
            self._audit("login", {"url": url, "credential_key": credential_key}, {"success": False, "error": "no credentials"}, error="no credentials")
            return {"success": False, "error": "no credentials"}
        username = creds.get("username") or creds.get("user") or ""
        password = creds.get("password") or creds.get("passwd") or ""
        if not username or not password:
            self._audit("login", {"url": url, "credential_key": credential_key}, {"success": False, "error": "missing username or password"}, error="missing credentials")
            return {"success": False, "error": "missing username or password"}
        result = await self._browser_tool._dispatch("navigate", {"url": url})
        if result.get("error"):
            self._audit("login", {"url": url, "credential_key": credential_key}, {"success": False, "error": result["error"]}, error=result["error"])
            return {"success": False, "error": result["error"]}
        # Try common login form selectors: fill username then password then submit
        user_sel = "input[type='email'], input[name='username'], input[name='email'], input[type='text']"
        pass_sel = "input[type='password']"
        submit_sel = "button[type='submit'], input[type='submit']"
        try:
            await self._browser_tool._page.wait_for_selector(pass_sel, timeout=5000)
        except Exception:
            pass
        await self._browser_tool._dispatch("fill", {"selector": user_sel, "text": username})
        await self._browser_tool._dispatch("fill", {"selector": pass_sel, "text": password})
        await self._browser_tool._dispatch("click", {"selector": submit_sel})
        await asyncio.sleep(1.5)
        cookies = await self._browser_tool._get_cookies()
        from urllib.parse import urlparse
        domain = urlparse(url).netloc or "default"
        cookie_json = json.dumps([{"name": c.get("name"), "value": c.get("value"), "domain": c.get("domain")} for c in cookies])
        if hasattr(v, "set"):
            v.set(f"session_{domain}", cookie_json)
        elif isinstance(v, dict):
            v[f"session_{domain}"] = cookie_json
        self._audit("login", {"url": url, "credential_key": credential_key}, {"success": True, "domain": domain}, error="")
        return {"success": True, "domain": domain}

    async def save_cookies(self, label: str = "default") -> dict:
        """Serialize current browser context cookies to the session vault."""
        assert self._browser_tool is not None
        result = await self._browser_tool._save_cookies(label=label)
        self._audit("save_cookies", {"label": label}, result)
        return result

    async def load_cookies(self, label: str = "default") -> dict:
        """Load cookies from the session vault and install into current browser context."""
        assert self._browser_tool is not None
        result = await self._browser_tool._load_cookies(label=label)
        self._audit("load_cookies", {"label": label}, result)
        return result

    async def capture_download(self, selector: str, timeout: int = 30000) -> dict:
        """Click selector, wait for file download, save to ~/.cato/workspace/downloads/."""
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("capture_download", {"selector": selector, "timeout": timeout})
        self._audit("capture_download", {"selector": selector, "timeout": timeout}, result, url_or_selector=selector, error=result.get("error", ""))
        return result

    async def get_downloads(self) -> dict:
        """List all files saved in ~/.cato/workspace/downloads/."""
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("get_downloads", {})
        self._audit("get_downloads", {}, result, error=result.get("error", ""))
        return result

    async def _try_selector_with_healing(
        self,
        action: str,
        selector: str,
        **kwargs: Any,
    ) -> tuple[dict, str]:
        """
        Three-tier selector healing for click/type/hover actions.

        Tier 1: Original CSS selector (current behavior).
        Tier 2: ARIA tree search — scan accessibility snapshot for element matching
                role/name semantically related to the selector string.
        Tier 3: Text content search — find DOM elements whose innerText contains the
                selector value as a substring.

        Returns (result_dict, tier_used) where tier_used is "css", "aria", "text",
        or "failed".
        """
        import re as _re

        browser_tool = self._browser_tool

        tier1_method = {
            "click": browser_tool._click,
            "type":  browser_tool._type,
            "hover": browser_tool._hover,
        }.get(action)
        if tier1_method is None:
            return {"error": f"Unknown healable action: {action}"}, "none"

        # Tier 1: Original CSS selector
        result = await tier1_method(selector=selector, **kwargs)
        if result.get("success") is not False:
            return result, "css"

        # Tier 1 failed — check whether healing is enabled
        if not self._selector_healing_enabled:
            return result, "failed"

        # Tier 2: ARIA tree search
        logger.debug("Selector healing Tier 1 failed for %r — trying ARIA", selector)
        try:
            aria_result = await browser_tool._accessibility_snapshot()
            aria_tree = str(aria_result.get("tree", ""))
            hints = _re.findall(r'[#.]?([a-zA-Z][a-zA-Z0-9_-]+)', selector)
            best_match = None
            for hint in hints:
                if len(hint) < 3:
                    continue
                if hint.lower() in aria_tree.lower():
                    best_match = hint
                    break
            if best_match:
                aria_selectors = [
                    f"[aria-label*='{best_match}' i]",
                    f"[title*='{best_match}' i]",
                    f"button:has-text('{best_match}')",
                    f"a:has-text('{best_match}')",
                    f"[name='{best_match}']",
                    f"[placeholder*='{best_match}' i]",
                ]
                for aria_sel in aria_selectors:
                    try:
                        result2 = await tier1_method(selector=aria_sel, **kwargs)
                        if result2.get("success") is not False:
                            logger.info(
                                "Selector healing: Tier 2 (ARIA) succeeded with %r for original %r",
                                aria_sel, selector,
                            )
                            self._audit_healing(selector, "aria", aria_sel)
                            return result2, "aria"
                    except Exception:
                        continue
        except Exception as exc:
            logger.debug("ARIA tier failed: %s", exc)

        # Tier 3: Text content search
        logger.debug("Selector healing Tier 2 failed for %r — trying text search", selector)
        try:
            text_hint = _re.sub(r'[#.\[\]"\'=*^$~|>+,()]', ' ', selector).strip()
            text_hint = ' '.join(text_hint.split())
            if text_hint and len(text_hint) >= 2:
                text_selectors = [
                    f"text={text_hint}",
                    f":has-text('{text_hint}')",
                    f"[value*='{text_hint}' i]",
                ]
                for text_sel in text_selectors:
                    try:
                        result3 = await tier1_method(selector=text_sel, **kwargs)
                        if result3.get("success") is not False:
                            logger.info(
                                "Selector healing: Tier 3 (text) succeeded with %r for original %r",
                                text_sel, selector,
                            )
                            self._audit_healing(selector, "text", text_sel)
                            return result3, "text"
                    except Exception:
                        continue
        except Exception as exc:
            logger.debug("Text tier failed: %s", exc)

        # All tiers exhausted — return original Tier 1 error with healing metadata
        result["selector_healing_attempted"] = True
        result["tiers_tried"] = ["css", "aria", "text"]
        return result, "failed"

    def _audit_healing(self, original_selector: str, tier_used: str, resolved_selector: str) -> None:
        """Log a selector healing event to the audit chain."""
        try:
            self._audit(
                "selector_healing",
                {
                    "original_selector": original_selector,
                    "tier_used": tier_used,
                    "resolved_selector": resolved_selector,
                },
                {"healed": True},
            )
        except Exception as exc:
            logger.error(
                "AUDIT WRITE FAILURE for action 'selector_healing': %s", exc, exc_info=True
            )
            raise

    def _maybe_rotate_browser_profile(self, max_sessions: int = 100) -> None:
        """F29: Archive the browser profile after max_sessions instantiations and start fresh.

        Tracks a counter in ~/.cato/session_count.txt. When the counter reaches
        max_sessions the current browser profile directory is archived and a clean
        empty profile directory is created so the browser starts with no stored
        state (cookies, cached auth, fingerprint data).
        """
        counter_file = self._data_dir / "session_count.txt"
        try:
            count = int(counter_file.read_text(encoding="utf-8").strip()) if counter_file.exists() else 0
        except Exception:
            count = 0

        count += 1

        if count >= max_sessions:
            import shutil as _shutil

            profile_dir = self._data_dir / "browser_profile"
            if profile_dir.exists():
                timestamp = int(time.time())
                archive_dir = self._data_dir / f"browser_profile_archive_{timestamp}"
                try:
                    _shutil.move(str(profile_dir), str(archive_dir))
                    profile_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(
                        "Browser profile rotated after %d sessions — archived to %s",
                        count, archive_dir,
                    )
                except Exception as exc:
                    logger.warning("Browser profile rotation failed: %s", exc)
            count = 0

        try:
            counter_file.write_text(str(count), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not update session_count.txt: %s", exc)

    def _get_marketplace_service(self):
        if self._marketplace_service is None:
            from .products.marketplace.service import MarketplaceService
            self._marketplace_service = MarketplaceService(
                db_path=self._ledger_db_path,
                session_pool=self._session_pool,
            )
        return self._marketplace_service

    def _get_marketplace_worker_pool(self):
        if self._marketplace_worker_pool is None:
            from .products.marketplace.worker_pool import MarketplaceBrowserWorkerPool
            self._marketplace_worker_pool = MarketplaceBrowserWorkerPool(self._data_dir)
        return self._marketplace_worker_pool

    def _get_marketplace_job_queue(self):
        if self._marketplace_job_queue is None:
            from .products.marketplace.job_queue import MarketplaceJobQueue
            self._marketplace_job_queue = MarketplaceJobQueue(self.marketplace_execute_job)
        return self._marketplace_job_queue

    async def _load_cookie_file(self, browser_tool: Any, cookie_path: str) -> dict[str, Any]:
        await browser_tool._ensure_browser()
        session_file = Path(cookie_path)
        if not session_file.exists():
            return {"success": False, "error": f"Cookie file does not exist: {cookie_path}"}
        try:
            raw_cookies = json.loads(session_file.read_text(encoding="utf-8"))
            normalized = self._normalize_imported_cookies(raw_cookies)
            await browser_tool._browser.add_cookies(normalized["cookies"])
            return {
                "success": True,
                "count": len(normalized["cookies"]),
                "cookie_path": str(session_file),
                "normalized": normalized["normalized"],
                "dropped": normalized["dropped"],
                "warnings": normalized["warnings"],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "cookie_path": str(session_file)}

    @staticmethod
    def _normalize_imported_cookies(raw_cookies: Any) -> dict[str, Any]:
        if not isinstance(raw_cookies, list):
            raise ValueError("Cookie file must contain a JSON array")

        cookies: list[dict[str, Any]] = []
        warnings: list[str] = []
        dropped = 0
        normalized = 0
        same_site_map = {
            "strict": "Strict",
            "lax": "Lax",
            "none": "None",
            "no_restriction": "None",
        }

        for index, raw in enumerate(raw_cookies):
            if not isinstance(raw, dict):
                dropped += 1
                warnings.append(f"dropped_cookie[{index}]: not an object")
                continue

            name = raw.get("name")
            value = raw.get("value")
            path = raw.get("path") or "/"
            domain = raw.get("domain")
            url = raw.get("url")
            if not name or value is None:
                dropped += 1
                warnings.append(f"dropped_cookie[{index}]: missing name or value")
                continue
            if not domain and not url:
                dropped += 1
                warnings.append(f"dropped_cookie[{index}]: missing domain/url")
                continue

            cookie: dict[str, Any] = {
                "name": str(name),
                "value": str(value),
                "path": str(path),
                "httpOnly": bool(raw.get("httpOnly", False)),
                "secure": bool(raw.get("secure", False)),
            }

            if url:
                cookie["url"] = str(url)
            else:
                host_only = bool(raw.get("hostOnly", False))
                domain_value = str(domain)
                if host_only and domain_value.startswith("."):
                    domain_value = domain_value.lstrip(".")
                    normalized += 1
                cookie["domain"] = domain_value

            same_site_raw = str(raw.get("sameSite", "") or "").strip().lower()
            if same_site_raw in same_site_map:
                same_site_value = same_site_map[same_site_raw]
                if same_site_value == "None" and not cookie["secure"]:
                    normalized += 1
                    warnings.append(
                        f"cookie[{cookie['name']}]: coerced SameSite=None to Lax because secure=false"
                    )
                    same_site_value = "Lax"
                cookie["sameSite"] = same_site_value
                if same_site_raw != same_site_value.lower():
                    normalized += 1
            elif same_site_raw:
                normalized += 1
                warnings.append(f"cookie[{cookie['name']}]: dropped unsupported sameSite={raw.get('sameSite')}")

            session_cookie = bool(raw.get("session", False))
            expires = raw.get("expires", raw.get("expirationDate"))
            if expires not in (None, "") and not session_cookie:
                try:
                    cookie["expires"] = float(expires)
                    if "expires" not in raw:
                        normalized += 1
                except (TypeError, ValueError):
                    normalized += 1
                    warnings.append(f"cookie[{cookie['name']}]: invalid expirationDate dropped")

            cookies.append(cookie)

        return {
            "cookies": cookies,
            "normalized": normalized,
            "dropped": dropped,
            "warnings": warnings,
        }

    @staticmethod
    def _classify_marketplace_page(result: dict[str, Any]) -> str | None:
        title = (result.get("title") or "").lower()
        text = (result.get("text") or result.get("bodyText") or "").lower()
        combined = f"{title}\n{text}"
        if "just a moment" in combined or "cloudflare ray id" in combined:
            return "hard_block.cloudflare"
        if "it needs a human touch" in combined or "errcode pxcr" in combined:
            return "hard_block.perimeterx"
        if "loading challenge" in combined or "captcha" in combined:
            return "soft_block.challenge"
        if "sign in" in combined or "login" in combined:
            return "auth_wall"
        return None

    def _get_marketplace_proxy_config(self, proxy_label: str = "") -> dict[str, Any] | None:
        if not proxy_label:
            return None
        return self._get_marketplace_service().get_runtime_proxy(proxy_label)

    @staticmethod
    def _public_proxy_details(proxy_config: dict[str, Any] | None) -> dict[str, Any] | None:
        if not proxy_config:
            return None
        return {
            "label": proxy_config.get("label", ""),
            "host": proxy_config.get("host", ""),
            "port": proxy_config.get("port", 0),
            "protocol": proxy_config.get("protocol", "http"),
            "kind": proxy_config.get("kind", "http"),
            "state": proxy_config.get("state", "active"),
            "cooldown_until": proxy_config.get("cooldown_until", 0.0),
            "has_auth": bool(proxy_config.get("username") or proxy_config.get("password")),
        }

    @staticmethod
    def _should_retry_marketplace_failure(failure_class: str) -> bool:
        return failure_class in {
            "hard_block.cloudflare",
            "hard_block.perimeterx",
            "runtime_error",
        }

    async def _bootstrap_marketplace_session(
        self,
        account: dict[str, Any],
        adapter: Any,
        *,
        target_url: str = "",
    ) -> dict[str, Any]:
        credential_key = account.get("credential_key") or ""
        if not credential_key:
            raise RuntimeError(f"Marketplace account {account['id']} has no credential key")

        session_key = f"marketplace:{account['marketplace']}:account:{account['id']}:bootstrap"
        proxy_config = self._get_marketplace_proxy_config(account.get("proxy_label", ""))
        browser_tool = self._get_marketplace_worker_pool().acquire(session_key, proxy_config=proxy_config)
        previous_browser_tool = self._browser_tool
        previous_session_id = self._session_id
        self._browser_tool = browser_tool
        self._session_id = f"{previous_session_id}:marketplace-bootstrap:{account['id']}"
        try:
            login_result = await self._run_marketplace_login_flow(
                browser_tool=browser_tool,
                adapter=adapter,
                credential_key=credential_key,
                target_url=target_url,
            )
            if not login_result.get("success"):
                self._get_marketplace_service().update_account_status(
                    account["id"],
                    status="needs_login",
                    metadata={"last_login_error": login_result.get("error", "login failed")},
                )
                raise RuntimeError(login_result.get("error", "Marketplace login failed"))

            if target_url:
                await self.navigate(target_url, retry_on_auth=False)

            label = f"{account['marketplace']}-{account['id']}-active"
            cookie_result = await browser_tool._save_cookies(label=label)
            if not cookie_result.get("success"):
                raise RuntimeError(cookie_result.get("error", "Cookie save failed"))

            persisted = self._get_marketplace_service().save_session(
                account_id=account["id"],
                label=label,
                cookie_path=cookie_result["path"],
                state="fresh",
                metadata={
                    "credential_key": credential_key,
                    "final_url": login_result.get("final_url", ""),
                    "verified_at": time.time(),
                },
            )
            self._get_marketplace_service().update_account_status(
                account["id"],
                status="active",
                metadata={"last_bootstrap_at": time.time()},
            )
            return {
                "account": account,
                "session": persisted["session"],
                "login": login_result,
            }
        finally:
            self._session_id = previous_session_id
            self._browser_tool = previous_browser_tool
            await self._get_marketplace_worker_pool().release(session_key, keep_alive=False)

    async def _run_marketplace_login_flow(
        self,
        *,
        browser_tool: Any,
        adapter: Any,
        credential_key: str,
        target_url: str,
    ) -> dict[str, Any]:
        if adapter.slug == "upwork":
            return await self._run_upwork_login_flow(
                browser_tool=browser_tool,
                credential_key=credential_key,
                target_url=target_url,
                login_url=adapter.login_url(),
                selectors=adapter.login_selectors(),
            )

        login_selectors = adapter.login_selectors()
        return await browser_tool._dispatch(
            "login",
            {
                "url": adapter.login_url(),
                "credential_key": credential_key,
                "username_selector": login_selectors["username"],
                "password_selector": login_selectors["password"],
            },
        )

    async def _run_upwork_login_flow(
        self,
        *,
        browser_tool: Any,
        credential_key: str,
        target_url: str,
        login_url: str,
        selectors: dict[str, str],
    ) -> dict[str, Any]:
        import os

        env_key = credential_key.upper().replace("-", "_").replace(".", "_")
        username = os.environ.get(f"{env_key}_USERNAME", "")
        password = os.environ.get(f"{env_key}_PASSWORD", "")
        if not username or not password:
            return {
                "success": False,
                "error": (
                    f"Credentials not found. Set {env_key}_USERNAME and "
                    f"{env_key}_PASSWORD environment variables."
                ),
            }

        await browser_tool._ensure_browser()
        page = browser_tool._page
        await page.goto(login_url, wait_until="domcontentloaded", timeout=30000)

        username_filled = False
        for selector in selectors["username"].split(","):
            selector = selector.strip()
            try:
                await page.fill(selector, username, timeout=3000)
                username_filled = True
                break
            except Exception:
                continue
        if not username_filled:
            return {"success": False, "error": f"Could not find username field: {selectors['username']}"}

        continued = False
        for selector in ["#login_password_continue", "button:has-text('Continue')", "button[type='submit']"]:
            try:
                await page.click(selector, timeout=3000)
                continued = True
                break
            except Exception:
                continue
        if not continued:
            return {"success": False, "error": "Could not continue from Upwork username step"}

        password_filled = False
        for selector in selectors["password"].split(","):
            selector = selector.strip()
            try:
                await page.wait_for_selector(selector, timeout=10000, state="visible")
                await page.fill(selector, password, timeout=5000)
                password_filled = True
                break
            except Exception:
                continue
        if not password_filled:
            return {"success": False, "error": f"Could not find password field: {selectors['password']}"}

        submitted = False
        for selector in ["button[type='submit']", "button:has-text('Log in')", "button:has-text('Continue')"]:
            try:
                await page.click(selector, timeout=3000)
                submitted = True
                break
            except Exception:
                continue
        if not submitted:
            await page.keyboard.press("Enter")

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        if target_url:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            block_result = {
                "title": await page.title(),
                "text": await page.evaluate("(document.body && document.body.innerText || '').slice(0, 1000)"),
            }
            failure_class = self._classify_marketplace_page(block_result)
            if failure_class and failure_class != "auth_wall":
                return {
                    "success": False,
                    "credential_key": credential_key,
                    "error": f"Blocked after login: {failure_class}",
                    "final_url": page.url,
                }
        final_url = page.url
        session_check = await browser_tool._check_session()
        return {
            "success": session_check["authenticated"],
            "final_url": final_url,
            "credential_key": credential_key,
            "error": None if session_check["authenticated"] else "Login may have failed — still on auth page",
        }

    async def _run_marketplace_job(self, job: dict[str, Any], saved_session: dict[str, Any] | None) -> dict[str, Any]:
        session_key = job.get("session_id") or job.get("plan", {}).get("session", {}).get("spec", {}).get("session_key") or job["id"]
        worker_pool = self._get_marketplace_worker_pool()
        service = self._get_marketplace_service()
        adapter = service.get_adapter(job["marketplace"])
        account = None
        if job.get("account_id"):
            account = service.get_account(job["account_id"])["account"]
        proxy_label = job.get("proxy_label") or (account.get("proxy_label") if account else "") or ""
        max_attempts = 2 if proxy_label else 1
        attempt_warnings: list[str] = []
        last_error: MarketplaceExecutionError | None = None

        for attempt in range(1, max_attempts + 1):
            # F9: re-check budget before each retry attempt so a burst of
            # retries cannot push spending past the cap.
            try:
                remaining = self._budget_cents - self._ledger.session_total_cents(self._session_id)
            except Exception:
                remaining = self._budget_cents - self._session_cost_cents_total
            if remaining < 0:
                raise BudgetExceededError(
                    f"Conduit budget {self._budget_cents}¢ exceeded before marketplace retry attempt {attempt}."
                )

            proxy_config = None
            if proxy_label:
                try:
                    proxy_config = self._get_marketplace_proxy_config(proxy_label)
                except RuntimeError as exc:
                    if last_error is not None:
                        raise last_error from exc
                    raise
            browser_tool = worker_pool.acquire(session_key, proxy_config=proxy_config)
            release_keep_alive = bool(job.get("account_id") or saved_session)
            try:
                payload = await self._run_marketplace_job_once(
                    job=job,
                    saved_session=saved_session,
                    browser_tool=browser_tool,
                    adapter=adapter,
                    account=account,
                    session_key=session_key,
                    proxy_config=proxy_config,
                    extra_warnings=attempt_warnings,
                )
                if proxy_label:
                    service.update_proxy_state(
                        proxy_label,
                        state="active",
                        cooldown_until=0.0,
                        last_failure_class="",
                        metadata={
                            "last_success_at": time.time(),
                            "last_job_id": job["id"],
                        },
                    )
                return payload
            except MarketplaceExecutionError as exc:
                last_error = exc
                release_keep_alive = False
                if proxy_label:
                    cooldown_until = time.time() + 180 if self._should_retry_marketplace_failure(exc.failure_class) else 0.0
                    service.update_proxy_state(
                        proxy_label,
                        state="cooldown" if cooldown_until else "active",
                        cooldown_until=cooldown_until,
                        last_failure_class=exc.failure_class,
                        metadata={
                            "last_failure_at": time.time(),
                            "last_job_id": job["id"],
                            "last_artifact_path": exc.artifact_path,
                        },
                    )
                if attempt < max_attempts and self._should_retry_marketplace_failure(exc.failure_class):
                    attempt_warnings.append(
                        f"Retrying marketplace job after {exc.failure_class} on attempt {attempt}"
                    )
                    continue
                raise
            finally:
                await worker_pool.release(session_key, keep_alive=release_keep_alive)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Marketplace job ended without a result")

    async def _run_marketplace_job_once(
        self,
        *,
        job: dict[str, Any],
        saved_session: dict[str, Any] | None,
        browser_tool: Any,
        adapter: Any,
        account: dict[str, Any] | None,
        session_key: str,
        proxy_config: dict[str, Any] | None,
        extra_warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        warnings: list[str] = list(extra_warnings or [])
        previous_browser_tool = self._browser_tool
        previous_session_id = self._session_id
        self._session_id = f"{previous_session_id}:marketplace-job:{job['id']}"
        self._browser_tool = browser_tool

        try:
            session_load = None
            if saved_session and saved_session.get("cookie_path"):
                session_load = await self._load_cookie_file(browser_tool, saved_session["cookie_path"])
                if not session_load.get("success"):
                    warnings.append(session_load.get("error", "Failed to load saved session"))
                    if saved_session.get("id"):
                        self._get_marketplace_service().update_session_state(
                            saved_session["id"],
                            state="stale",
                            metadata={"last_error": session_load.get("error", "")},
                        )

            navigation = await self.navigate(job["target_url"])
            if navigation.get("error"):
                raise RuntimeError(navigation["error"])
            failure_class = self._classify_marketplace_page(navigation)
            if failure_class and failure_class != "auth_wall":
                failure_shot = await self.screenshot(path=f"marketplace_failure_{job['id']}.png")
                raise MarketplaceExecutionError(
                    f"Marketplace blocked before extraction: {failure_class}",
                    failure_class=failure_class,
                    artifact_path=failure_shot.get("path", ""),
                )

            login_required = bool(job.get("plan", {}).get("login_required"))
            auth_check = None
            if login_required:
                auth_check = await self.check_session(job["target_url"])
                if not auth_check.get("ok"):
                    warnings.append("Authentication wall detected during marketplace job")
                    if account and account.get("credential_key"):
                        bootstrap = await self._bootstrap_marketplace_session(
                            account,
                            adapter,
                            target_url=job["target_url"],
                        )
                        saved_session = bootstrap["session"]
                        session_load = await self._load_cookie_file(browser_tool, saved_session["cookie_path"])
                        if session_load.get("success"):
                            auth_check = await self.check_session(job["target_url"])
                        else:
                            warnings.append(session_load.get("error", "Failed to load bootstrapped session"))
                    if auth_check and not auth_check.get("ok"):
                        failure_shot = await self.screenshot(path=f"marketplace_failure_{job['id']}.png")
                        raise MarketplaceExecutionError(
                            "Authentication wall persists after session bootstrap",
                            failure_class="auth_wall",
                            artifact_path=failure_shot.get("path", ""),
                        )

            for _ in range(adapter.scroll_iterations(job["target_type"])):
                await self.scroll(direction="down", amount=1200)
                await asyncio.sleep(0.35)

            captcha = await browser_tool._dispatch("detect_captcha", {})
            if captcha.get("detected"):
                warnings.append(f"CAPTCHA detected: {captcha.get('type') or 'unknown'}")

            extraction = await self.extract_main(max_chars=12000, fmt="md")
            if extraction.get("error"):
                raise RuntimeError(extraction["error"])

            structured_eval = await self.eval(adapter.extraction_script(job["target_type"]))
            structured_payload = structured_eval.get("result") if structured_eval.get("success") else None
            if not structured_eval.get("success"):
                warnings.append(structured_eval.get("error", "Structured extraction script failed"))

            extraction_strategy = "adapter"
            try:
                record = adapter.transform_extraction(
                    target_type=job["target_type"],
                    target_url=job["target_url"],
                    structured_payload=structured_payload if isinstance(structured_payload, dict) else None,
                    main_content=extraction,
                    navigation=navigation,
                )
            except Exception as exc:
                extraction_strategy = "fallback"
                warnings.append(str(exc))
                record = {
                    "title": extraction.get("title", navigation.get("title", "")),
                    "text": extraction.get("text", ""),
                }

            screenshot = await self.screenshot(path=f"marketplace_{job['id']}.png")
            artifact_path = screenshot.get("path", "") if isinstance(screenshot, dict) else ""
            page_hashes = []
            if extraction.get("content_hash"):
                page_hashes.append(
                    {
                        "url": job["target_url"],
                        "hash": extraction["content_hash"],
                    }
                )
            proof_dir = self._data_dir / "marketplace_proofs" / job["marketplace"]
            proof_result = self.export_proof(
                output_dir=str(proof_dir),
                page_hashes=page_hashes or None,
            )
            proof_bundle_path = proof_result.get("path", "") if proof_result.get("success") else ""
            if proof_result and not proof_result.get("success"):
                warnings.append(proof_result.get("error", "Proof export failed"))

            record.update(
                {
                    "marketplace": job["marketplace"],
                    "target_type": job["target_type"],
                    "target_url": job["target_url"],
                    "content_hash": extraction.get("content_hash"),
                    "fetched_at": extraction.get("fetched_at"),
                    "http_status": extraction.get("http_status"),
                    "links_found": extraction.get("links_found"),
                    "captcha": captcha,
                    "authenticated": None if auth_check is None else auth_check.get("ok"),
                    "saved_session_id": None if saved_session is None else saved_session.get("id"),
                    "saved_session_loaded": None if session_load is None else session_load.get("success"),
                    "screenshot_path": artifact_path,
                    "worker_session_key": session_key,
                    "structured_extraction": bool(structured_payload),
                    "extraction_strategy": extraction_strategy,
                    "proof_bundle_path": proof_bundle_path,
                    "proxy": self._public_proxy_details(proxy_config),
                }
            )
            return {
                "records": [record],
                "artifact_path": artifact_path,
                "proof_bundle_path": proof_bundle_path,
                "warnings": warnings,
            }
        except MarketplaceExecutionError:
            raise
        except Exception as exc:
            failure_shot = await self.screenshot(path=f"marketplace_failure_{job['id']}.png")
            raise MarketplaceExecutionError(
                str(exc),
                failure_class="runtime_error",
                artifact_path=failure_shot.get("path", ""),
            )
        finally:
            self._session_id = previous_session_id
            self._browser_tool = previous_browser_tool

    async def marketplace_list(self) -> dict:
        result = self._get_marketplace_service().list_marketplaces()
        self._audit("marketplace_list", {}, result)
        return result

    async def marketplace_targets(self, marketplace: str) -> dict:
        result = self._get_marketplace_service().list_targets(marketplace)
        self._audit("marketplace_targets", {"marketplace": marketplace}, result)
        return result

    async def marketplace_plan(
        self,
        marketplace: str,
        target_type: str,
        target_url: str,
        account_id: str = "",
        proxy_label: str = "",
    ) -> dict:
        result = self._get_marketplace_service().build_plan(
            marketplace=marketplace,
            target_type=target_type,
            target_url=target_url,
            account_id=account_id or None,
            proxy_label=proxy_label or None,
        )
        self._audit(
            "marketplace_plan",
            {
                "marketplace": marketplace,
                "target_type": target_type,
                "target_url": target_url,
                "account_id": account_id,
                "proxy_label": proxy_label,
            },
            result,
        )
        return result

    async def marketplace_create_job(
        self,
        marketplace: str,
        target_type: str,
        target_url: str,
        account_id: str = "",
        proxy_label: str = "",
        request_payload: Optional[dict[str, Any]] = None,
    ) -> dict:
        result = self._get_marketplace_service().create_job(
            marketplace=marketplace,
            target_type=target_type,
            target_url=target_url,
            account_id=account_id or None,
            proxy_label=proxy_label or None,
            request_payload=request_payload or {},
        )
        self._audit(
            "marketplace_create_job",
            {
                "marketplace": marketplace,
                "target_type": target_type,
                "target_url": target_url,
                "account_id": account_id,
                "proxy_label": proxy_label,
                "request_payload": request_payload or {},
            },
            result,
        )
        return result

    async def marketplace_create_account(
        self,
        marketplace: str,
        display_name: str,
        credential_key: str = "",
        proxy_label: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict:
        result = self._get_marketplace_service().create_account(
            marketplace=marketplace,
            display_name=display_name,
            credential_key=credential_key,
            proxy_label=proxy_label,
            metadata=metadata or {},
        )
        self._audit(
            "marketplace_create_account",
            {
                "marketplace": marketplace,
                "display_name": display_name,
                "credential_key": credential_key,
                "proxy_label": proxy_label,
                "metadata": metadata or {},
            },
            result,
        )
        return result

    async def marketplace_list_accounts(self, marketplace: str = "") -> dict:
        result = self._get_marketplace_service().list_accounts(marketplace=marketplace or None)
        self._audit("marketplace_list_accounts", {"marketplace": marketplace}, result)
        return result

    async def marketplace_create_proxy(
        self,
        label: str,
        host: str,
        port: int,
        protocol: str = "http",
        username: str = "",
        password: str = "",
        kind: str = "http",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict:
        result = self._get_marketplace_service().create_proxy(
            label=label,
            host=host,
            port=port,
            protocol=protocol,
            username=username,
            password=password,
            kind=kind,
            metadata=metadata or {},
        )
        audited_result = {"proxy": {**result["proxy"]}}
        self._audit(
            "marketplace_create_proxy",
            {
                "label": label,
                "host": host,
                "port": port,
                "protocol": protocol,
                "username": username,
                "password": "***" if password else "",
                "kind": kind,
                "metadata": metadata or {},
            },
            audited_result,
        )
        return audited_result

    async def marketplace_list_proxies(self, state: str = "") -> dict:
        result = self._get_marketplace_service().list_proxies(state=state or None)
        self._audit("marketplace_list_proxies", {"state": state}, result)
        return result

    async def marketplace_get_proxy(self, label: str) -> dict:
        result = self._get_marketplace_service().get_proxy(label)
        self._audit("marketplace_get_proxy", {"label": label}, result)
        return result

    async def marketplace_test_proxy(self, label: str, test_url: str = "https://api.ipify.org/") -> dict:
        from .browser import BrowserTool

        proxy_config = self._get_marketplace_proxy_config(label)
        if proxy_config is None:
            raise ValueError(f"Unknown marketplace proxy label: {label}")

        safe_label = re.sub(r"[^a-zA-Z0-9._-]+", "_", label.strip()) or "proxy"
        runtime_root = self._data_dir / "marketplace_proxy_tests" / safe_label
        browser_tool = BrowserTool(
            data_dir=self._data_dir,
            profile_dir=runtime_root / "profile",
            screenshot_dir=runtime_root / "screenshots",
            pdf_dir=runtime_root / "pdfs",
            session_dir=runtime_root / "sessions",
            proxy_config=proxy_config,
        )
        try:
            navigation = await browser_tool._dispatch("navigate", {"url": test_url})
        finally:
            await browser_tool.close()

        result = {
            "label": label,
            "proxy": self._public_proxy_details(proxy_config),
            "test_url": test_url,
            "ok": not bool(navigation.get("error")),
            "navigation": navigation,
        }
        self._audit("marketplace_test_proxy", {"label": label, "test_url": test_url}, result)
        return result

    async def marketplace_save_session(
        self,
        account_id: str,
        label: str,
        cookie_path: str,
        state: str = "fresh",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict:
        result = self._get_marketplace_service().save_session(
            account_id=account_id,
            label=label,
            cookie_path=cookie_path,
            state=state,
            metadata=metadata or {},
        )
        self._audit(
            "marketplace_save_session",
            {
                "account_id": account_id,
                "label": label,
                "cookie_path": cookie_path,
                "state": state,
                "metadata": metadata or {},
            },
            result,
        )
        return result

    async def marketplace_get_session(self, session_id: str) -> dict:
        result = self._get_marketplace_service().get_session(session_id)
        self._audit("marketplace_get_session", {"session_id": session_id}, result)
        return result

    async def marketplace_bootstrap_session(self, account_id: str, target_url: str = "") -> dict:
        account = self._get_marketplace_service().get_account(account_id)["account"]
        adapter = self._get_marketplace_service().get_adapter(account["marketplace"])
        result = await self._bootstrap_marketplace_session(account, adapter, target_url=target_url)
        self._audit(
            "marketplace_bootstrap_session",
            {"account_id": account_id, "target_url": target_url},
            result,
        )
        return result

    async def marketplace_list_sessions(self, marketplace: str = "", account_id: str = "") -> dict:
        result = self._get_marketplace_service().list_sessions(
            marketplace=marketplace or None,
            account_id=account_id or None,
        )
        self._audit(
            "marketplace_list_sessions",
            {"marketplace": marketplace, "account_id": account_id},
            result,
        )
        return result

    async def marketplace_execute_job(self, job_id: str) -> dict:
        result = await self._get_marketplace_service().execute_job(
            job_id=job_id,
            runner=self._run_marketplace_job,
        )
        webhook_url = result["job"].get("request", {}).get("webhook_url", "")
        if webhook_url:
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    self._post_marketplace_webhook,
                    webhook_url,
                    result,
                )
            except Exception as exc:
                result["job"]["warnings"] = [*result["job"].get("warnings", []), f"Webhook failed: {exc}"]
        self._audit("marketplace_execute_job", {"job_id": job_id}, result)
        return result

    async def marketplace_enqueue_job(self, job_id: str) -> dict:
        result = self._get_marketplace_job_queue().enqueue(job_id)
        self._audit("marketplace_enqueue_job", {"job_id": job_id}, result)
        return result

    async def marketplace_queue_status(self, job_id: str = "") -> dict:
        queue = self._get_marketplace_job_queue()
        result = queue.get(job_id) if job_id else queue.snapshot()
        self._audit("marketplace_queue_status", {"job_id": job_id}, result)
        return result

    async def marketplace_get_result(self, result_id: str) -> dict:
        result = self._get_marketplace_service().get_result(result_id)
        self._audit("marketplace_get_result", {"result_id": result_id}, result)
        return result

    async def marketplace_list_results(self, job_id: str = "") -> dict:
        result = self._get_marketplace_service().list_results(job_id=job_id or None)
        self._audit("marketplace_list_results", {"job_id": job_id}, result)
        return result

    async def marketplace_export_result(self, result_id: str, fmt: str = "jsonl") -> dict:
        result = self._get_marketplace_service().export_result(
            result_id=result_id,
            fmt=fmt,
            output_dir=self._data_dir / "marketplace_exports",
        )
        self._audit("marketplace_export_result", {"result_id": result_id, "fmt": fmt}, result)
        return result

    async def marketplace_get_job(self, job_id: str) -> dict:
        result = self._get_marketplace_service().get_job(job_id)
        self._audit("marketplace_get_job", {"job_id": job_id}, result)
        return result

    async def marketplace_list_jobs(self, marketplace: str = "", status: str = "") -> dict:
        result = self._get_marketplace_service().list_jobs(
            marketplace=marketplace or None,
            status=status or None,
        )
        self._audit(
            "marketplace_list_jobs",
            {"marketplace": marketplace, "status": status},
            result,
        )
        return result

    def _post_marketplace_webhook(self, webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        import json as _json
        import urllib.request as _request

        # Scheme check
        if not webhook_url.startswith(("http://", "https://")):
            return {"success": False, "error": f"Invalid webhook URL scheme: {webhook_url}"}

        # SSRF check — module-level function returns "" if safe, error string if blocked
        block_err = _block_private_ip(webhook_url)
        if block_err:
            logger.warning("Webhook SSRF blocked: %s — %s", webhook_url, block_err)
            return {"success": False, "error": f"Webhook URL blocked by SSRF guard: {block_err}"}

        request = _request.Request(
            webhook_url,
            data=_json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with _request.urlopen(request, timeout=15):
            return {"success": True}

    async def _try_selector_healing(self, action: str, selector: str, **kwargs: Any) -> tuple[dict, int, str]:
        """Tier 1: direct CSS. Tier 2: ARIA role+name. Tier 3: text= selector. Returns (result, tier_used, resolved_selector)."""
        result = await self._browser_tool._dispatch(action, {"selector": selector, **kwargs})
        if not result.get("error"):
            return result, 1, selector
        cfg = getattr(self, "_config", {}) or {}
        if not cfg.get("selector_healing_enabled", False):
            return result, 1, selector
        # Tier 2: try role=button[name="..."], role=link[name="..."]
        for role in ("button", "link", "textbox", "menuitem"):
            alt = f'role={role}[name="{selector}"]'
            res = await self._browser_tool._dispatch(action, {"selector": alt, **kwargs})
            if not res.get("error"):
                return res, 2, alt
        # Tier 3: text match
        alt = f"text={selector}"
        res = await self._browser_tool._dispatch(action, {"selector": alt, **kwargs})
        if not res.get("error"):
            return res, 3, alt
        return result, 1, selector

    async def click(self, selector: str) -> dict:
        assert self._browser_tool is not None
        if self._selector_healing_enabled:
            result, _tier = await self._try_selector_with_healing("click", selector)
        else:
            result = await self._browser_tool._dispatch("click", {"selector": selector})
        self._audit("click", {"selector": selector}, result, url_or_selector=selector,
                    error=result.get("error", ""))
        return result

    async def type_text(self, selector: str, text: str) -> dict:
        assert self._browser_tool is not None
        if self._selector_healing_enabled:
            result, _tier = await self._try_selector_with_healing("type", selector, text=text)
        else:
            result = await self._browser_tool._dispatch("type", {"selector": selector, "text": text})
        self._audit("type", {"selector": selector, "text": text}, result,
                    url_or_selector=selector, error=result.get("error", ""))
        return result

    async def fill(self, selector: str, text: str) -> dict:
        """Named alias for type_text — goes through _audit() with 'fill' action name."""
        assert self._browser_tool is not None
        if self._selector_healing_enabled:
            result, _tier = await self._try_selector_with_healing("type", selector, text=text)
        else:
            result = await self._browser_tool._dispatch("fill", {"selector": selector, "text": text})
        self._audit("fill", {"selector": selector, "text": text}, result,
                    url_or_selector=selector, error=result.get("error", ""))
        return result

    async def extract(self, selector: str = "body") -> dict:
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("snapshot", {})
        if "text" in result:
            result["text"] = _strip_voix_tags(result["text"])
        result["char_count"] = len(result.get("text", ""))
        self._audit("extract", {"selector": selector}, result, url_or_selector=selector,
                    error=result.get("error", ""))
        return result

    async def screenshot(self, path: Optional[str] = None) -> dict:
        assert self._browser_tool is not None
        kwargs: dict[str, Any] = {}
        if path:
            kwargs["filename"] = path
        result = await self._browser_tool._dispatch("screenshot", kwargs)
        self._audit("screenshot", kwargs, result, error=result.get("error", ""))
        return result

    async def scroll(
        self,
        direction: str = "down",
        amount: int = 300,
        selector: Optional[str] = None,
    ) -> dict:
        assert self._browser_tool is not None
        inputs: dict[str, Any] = {"direction": direction, "amount": amount}
        if selector is not None:
            inputs["selector"] = selector
        result = await self._browser_tool._dispatch("scroll", inputs.copy())
        self._audit("scroll", inputs, result, url_or_selector=selector or "",
                    error=result.get("error", ""))
        return result

    async def wait(self, seconds: float = 1.0) -> dict:
        assert self._browser_tool is not None
        inputs = {"seconds": seconds}
        result = await self._browser_tool._dispatch("wait", inputs.copy())
        self._audit("wait", inputs, result, error=result.get("error", ""))
        return result

    async def wait_for(
        self,
        condition: str = "selector",
        value: str = "",
        timeout_ms: int = 10000,
    ) -> dict:
        assert self._browser_tool is not None
        inputs = {"condition": condition, "value": value, "timeout_ms": timeout_ms}
        result = await self._browser_tool._dispatch("wait_for", inputs.copy())
        self._audit("wait_for", inputs, result, error=result.get("error", ""))
        return result

    async def key_press(self, key: str = "Enter") -> dict:
        assert self._browser_tool is not None
        inputs = {"key": key}
        result = await self._browser_tool._dispatch("key_press", inputs.copy())
        self._audit("key_press", inputs, result, error=result.get("error", ""))
        return result

    async def _hover_with_healing(self, selector: str) -> dict:
        """Hover with optional selector healing (when selector_healing_enabled)."""
        assert self._browser_tool is not None
        if self._selector_healing_enabled:
            result, _tier = await self._try_selector_with_healing("hover", selector)
        else:
            result = await self._browser_tool._dispatch("hover", {"selector": selector})
        self._audit("hover", {"selector": selector}, result, url_or_selector=selector,
                    error=result.get("error", ""))
        return result

    async def hover(self, selector: str) -> dict:
        return await self._hover_with_healing(selector)

    async def select_option(
        self,
        selector: str,
        value: str = "",
        label: str = "",
        index: Optional[int] = None,
    ) -> dict:
        assert self._browser_tool is not None
        inputs: dict[str, Any] = {"selector": selector, "value": value, "label": label}
        if index is not None:
            inputs["index"] = index
        result = await self._browser_tool._dispatch("select_option", inputs.copy())
        self._audit("select_option", inputs, result, url_or_selector=selector,
                    error=result.get("error", ""))
        return result

    async def handle_dialog(self, action: str = "accept", text: str = "") -> dict:
        assert self._browser_tool is not None
        inputs = {"action": action, "text": text}
        result = await self._browser_tool._dispatch("handle_dialog", inputs.copy())
        self._audit("handle_dialog", inputs, result, error=result.get("error", ""))
        return result

    async def navigate_back(self) -> dict:
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("navigate_back", {})
        self._audit("navigate_back", {}, result, error=result.get("error", ""))
        return result

    async def console_messages(self) -> dict:
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("console_messages", {})
        self._audit("console_messages", {}, result, error=result.get("error", ""))
        return result

    # ------------------------------------------------------------------
    # Wave 2: Extraction bridge methods
    # ------------------------------------------------------------------

    async def eval(self, js_code: str) -> dict:
        """
        Execute js_code in page context. js_code is stored verbatim in audit inputs —
        this is Conduit's unique differentiator: cryptographic proof of exactly what code ran.
        """
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("eval", {"js_code": js_code})
        # js_code MUST be in inputs — core differentiator of Conduit.
        # Route through _audit() so the budget check is enforced like all other actions.
        # _sanitize_inputs() will NOT redact js_code (no sensitive key substring match).
        # F11: js_source_full stores the complete JS source verbatim (no truncation)
        # as the tamper-proof audit record. The display-truncated js_code field is
        # kept for backwards compatibility.
        audit_inputs = {
            "js_code": js_code,
            "code_hash": result.get("code_hash", ""),
            "js_source_full": js_code,  # untruncated — tamper-proof record
        }
        self._audit(
            "eval",
            audit_inputs,
            result,
            error="" if result.get("success") else result.get("error", ""),
        )
        return result

    async def extract_main(self, max_chars: int = 5000, fmt: str = "text", provenance_mode: bool = False) -> dict:
        """Readability-style main content extraction (strips nav/header/footer noise). fmt: 'text' or 'md'.

        When provenance_mode=True, each field in the result is wrapped with provenance metadata:
          {value, provenance: {audit_row_id, session_pubkey, url, url_hash, extracted_at, chain_verified}}
        """
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("extract_main", {"max_chars": max_chars, "fmt": fmt})
        if "text" in result:
            result["text"] = _strip_voix_tags(result["text"])
        audit_output = {
            "char_count": result.get("char_count", 0),
            "title": result.get("title", ""),
            "truncated": result.get("truncated", False),
            "content_hash": result.get("content_hash"),
            "fetched_at": result.get("fetched_at"),
            "http_status": result.get("http_status"),
            "links_found": result.get("links_found"),
        }
        self._audit(
            "extract_main",
            {"url": result.get("url", ""), "max_chars": max_chars},
            audit_output,
            error=result.get("error", ""),
        )
        if provenance_mode:
            # Get the most recent audit row id written above
            audit_row_id = None
            try:
                row = self._audit_log._conn.execute("SELECT rowid FROM audit_log ORDER BY rowid DESC LIMIT 1").fetchone()
                if row:
                    audit_row_id = row[0]
            except Exception:
                pass
            import hashlib as _hashlib
            import time as _time
            url = result.get("url", "")
            url_hash = _hashlib.sha256(url.encode()).hexdigest()[:16]
            extracted_at = result.get("fetched_at") or _time.time()
            provenance = {
                "audit_row_id": audit_row_id,
                "session_pubkey": self._identity.public_key_hex,
                "url": url,
                "url_hash": url_hash,
                "extracted_at": extracted_at,
                "chain_verified": False,  # lazy: not re-verifying full chain on every call
            }
            wrapped: dict[str, Any] = {}
            for k, v in result.items():
                wrapped[k] = {"value": v, "provenance": provenance}
            return wrapped
        return result

    async def extract_structured(self, schema: dict, max_chars: int = 5000, model_extract: Any = None) -> dict:
        """
        Extract main content then run model extraction and validate against schema.
        model_extract: optional async callable(text, schema) -> dict. When absent, returns
        {error, raw_text, schema} so caller can run model and validate (e.g. via skill_validator).
        """
        assert self._browser_tool is not None
        main = await self.extract_main(max_chars=max_chars)
        text = main.get("text", "")
        if not text:
            out = {"error": "no content", "schema": schema}
            self._audit("extract_structured", {"schema_keys": list(schema.keys())}, out, error="no content")
            return out
        if model_extract is None:
            out = {"error": "model_extract required", "raw_text": text[:2000], "schema": schema}
            self._audit("extract_structured", {"schema_keys": list(schema.keys())}, {"error": out["error"]}, error=out["error"])
            return out
        try:
            if asyncio.iscoroutinefunction(model_extract):
                result = await model_extract(text, schema)
            else:
                result = model_extract(text, schema)
        except Exception as e:
            out = {"error": str(e), "raw_text": text[:500], "schema": schema}
            self._audit("extract_structured", {"schema_keys": list(schema.keys())}, {"error": out["error"]}, error=out["error"])
            return out
        valid, err = _validate_against_schema(result, schema)
        if not valid:
            out = {"error": err or "validation failed", "raw_text": text[:500], "schema": schema, "raw_response": result}
            self._audit("extract_structured", {"schema_keys": list(schema.keys())}, {"error": out["error"]}, error=out["error"])
            return out
        self._audit("extract_structured", {"schema_keys": list(schema.keys())}, {"valid": True, "keys": list(result.keys())}, error="")
        return result

    async def js_delta(self) -> dict:
        """Capture the JS delta: diff between static HTML (pre-JS) and rendered DOM (post-JS).

        Measures how much content requires JavaScript execution to be visible.
        AI crawlers that don't execute JS miss content with high js_dependency_ratio.
        """
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("js_delta", {})
        audit_output = {
            "static_char_count": result.get("static_char_count", 0),
            "rendered_char_count": result.get("rendered_char_count", 0),
            "js_only_char_count": result.get("js_only_char_count", 0),
            "js_dependency_ratio": result.get("js_dependency_ratio", 0),
            "static_hash": result.get("static_hash", ""),
            "rendered_hash": result.get("rendered_hash", ""),
        }
        self._audit(
            "js_delta",
            {"url": result.get("url", "")},
            audit_output,
            error=result.get("error", ""),
        )
        return result

    async def output_to_file(self, filename: str, content: str, fmt: str = "md", request_id: str = "") -> dict:
        """
        Write content to a workspace file. Audit stores filename + fmt + byte_count
        but NOT the full content (may be very large).
        """
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch(
            "output_to_file", {"filename": filename, "content": content, "fmt": fmt}
        )
        # Audit inputs: filename + fmt + byte_count + request_id — NOT the full content
        self._audit(
            "output_to_file",
            {"filename": filename, "fmt": fmt, "byte_count": result.get("bytes", 0), "request_id": request_id},
            result,
            error="" if result.get("success") else result.get("error", ""),
        )
        return result

    async def verify_deliverable(
        self,
        url: str,
        expected_hash: str = "",
        request_id: str = "",
    ) -> dict:
        """
        Fetch a delivered artifact URL, compute SHA-256, and log to the audit chain.

        Action name: "verify_deliverable"

        Two-path design:
          Primary path — Python urllib.request fetch + hashlib.sha256().
            Works on any URL including binary files, PDFs, and audio without
            needing the browser to be in a navigated state. Streams the response
            in 64 KB chunks so large files never load into memory at once.
            Applies the same RFC-1918/loopback IP block as _navigate().
            Timeout: 30 seconds. Sets source="python_fetch" in result.

          Fallback path — Browser eval via fetch(window.location.href) +
            crypto.subtle.digest('SHA-256'). Runs only when the Python fetch
            fails (non-200 status, network error, timeout, or blocked IP after
            DNS resolution). Useful when the resource is gated behind an
            authenticated browser session. Sets source="browser_eval" in result.

        If expected_hash is provided, compares it against the fetched hash and
        returns hash_match: True/False. If no expected_hash is provided, records
        the content hash as delivery evidence.

        The verification JS source (fallback path) is stored verbatim in the
        audit chain via _audit(), making the verification logic itself auditable.

        Audit outputs always include:
          - deliverable_verified (bool): True if hash matched, False otherwise.
            SwarmSync escrow release logic queries this field:
            WHERE action='verify_deliverable' AND outputs_json->>'deliverable_verified' = 'true'
          - actual_hash (str): SHA-256 hex of the fetched artifact, or "" on failure.
          - expected_hash (str): The hash passed in, or "".
          - verification_source (str): "python_fetch" or "browser_eval".
          - request_id (str): The request_id passed to this method.

        Returns:
            {
                "url": str,
                "actual_hash": str,          # SHA-256 hex of the fetched artifact bytes
                "expected_hash": str,        # as provided (empty string if not given)
                "hash_match": bool | None,   # True/False if expected_hash given, None if not
                "source": str,               # "python_fetch" or "browser_eval"
                "request_id": str,
                "success": bool,
                "error": str,                # empty on success
                "deliverable_verified": bool,        # True if hash_match is True
                "verification_source": str,          # mirrors "source"
            }
        """
        assert self._browser_tool is not None

        actual_hash = ""
        error_msg = ""
        source = ""

        # ------------------------------------------------------------------
        # Primary path: Python urllib fetch + hashlib.sha256 (streaming)
        # ------------------------------------------------------------------
        block_err = _block_private_ip(url)
        if block_err:
            error_msg = block_err
        else:
            try:
                req = _urllib_req.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"
                        )
                    },
                )
                _safe_opener = _urllib_req.build_opener(_SafeRedirectHandler)
                with _safe_opener.open(req, timeout=30) as resp:
                    if resp.status != 200:
                        error_msg = f"python_fetch: HTTP {resp.status}"
                    else:
                        hasher = hashlib.sha256()
                        while True:
                            chunk = resp.read(65536)  # 64 KB chunks
                            if not chunk:
                                break
                            hasher.update(chunk)
                        actual_hash = hasher.hexdigest()
                        source = "python_fetch"
            except Exception as exc:
                error_msg = f"python_fetch failed: {exc}"

        # ------------------------------------------------------------------
        # Fallback path: browser eval (authenticated sessions, JS-only delivery)
        # ------------------------------------------------------------------
        if not actual_hash:
            verify_js = (
                "fetch(window.location.href)"
                ".then(r => r.arrayBuffer())"
                ".then(buf => crypto.subtle.digest('SHA-256', buf))"
                ".then(hash => Array.from(new Uint8Array(hash))"
                ".map(b => b.toString(16).padStart(2, '0')).join(''))"
            )

            # Navigate to the delivery URL first
            nav_result = await self._browser_tool._dispatch("navigate", {"url": url})
            if nav_result.get("error") or not nav_result.get("url"):
                nav_error = nav_result.get("error") or "navigation failed: no url returned"
                combined_error = f"{error_msg}; browser_eval: {nav_error}" if error_msg else nav_error
                result = {
                    "url": url,
                    "actual_hash": "",
                    "expected_hash": expected_hash,
                    "hash_match": None,
                    "source": "browser_eval",
                    "request_id": request_id,
                    "success": False,
                    "error": combined_error,
                    "deliverable_verified": False,
                    "verification_source": "browser_eval",
                }
                self._audit(
                    "verify_deliverable",
                    {"url": url, "expected_hash": expected_hash, "request_id": request_id},
                    result,
                    url_or_selector=url,
                    error=combined_error,
                )
                return result

            eval_result = await self._browser_tool._dispatch("eval", {"js_code": verify_js})
            browser_error = ""
            if eval_result.get("success") and isinstance(eval_result.get("result"), str):
                actual_hash = eval_result["result"]
                source = "browser_eval"
            else:
                browser_error = eval_result.get("error", "eval returned non-string result")
            if not actual_hash and not browser_error:
                browser_error = "eval returned empty hash"

            if browser_error:
                combined_error = f"{error_msg}; browser_eval: {browser_error}" if error_msg else browser_error
                error_msg = combined_error
            else:
                error_msg = ""  # browser eval succeeded — clear prior python_fetch error

            # Include verify_js in audit inputs for this path
            audit_inputs = {
                "url": url,
                "expected_hash": expected_hash,
                "request_id": request_id,
                "verify_js": verify_js,
            }
        else:
            audit_inputs = {
                "url": url,
                "expected_hash": expected_hash,
                "request_id": request_id,
            }

        hash_match: Optional[bool] = None
        if expected_hash and actual_hash:
            hash_match = (actual_hash.lower() == expected_hash.lower())

        result = {
            "url": url,
            "actual_hash": actual_hash,
            "expected_hash": expected_hash,
            "hash_match": hash_match,
            "source": source,
            "request_id": request_id,
            "success": bool(actual_hash and not error_msg),
            "error": error_msg,
            "deliverable_verified": hash_match is True,
            "verification_source": source,
        }

        self._audit(
            "verify_deliverable",
            audit_inputs,
            result,
            url_or_selector=url,
            error=error_msg,
        )
        return result

    async def verify_rubric(
        self,
        rubric: dict,
        rubric_hash: str,
        request_id: str,
        url: str = "",
        inline_content: str = "",
    ) -> dict:
        """Evaluate a pre-committed rubric against a deliverable.

        Action name: "verify_rubric"

        The rubric_hash pre-commitment is the proof mechanism — it proves the buyer
        locked the evaluation criteria before the seller started work.  The content
        to evaluate comes from one of two sources:

          url            — HTTP fetch (original path, for URL-addressable artifacts)
          inline_content — direct text (Option C, for writing/code/analysis with no URL)

        Exactly one of url or inline_content must be non-empty.
        """
        if not url and not inline_content:
            failure = {
                "success": False,
                "error": "verify_rubric requires either url or inline_content",
                "rubric_pass": False,
                "predicate_results": [],
                "request_id": request_id,
            }
            self._audit(
                "verify_rubric",
                inputs={"request_id": request_id, "audit_source": "none"},
                result=failure,
                error="missing url or inline_content",
            )
            return failure

        # 1. Verify rubric integrity before doing any content work.
        if make_rubric_hash(rubric) != rubric_hash:
            failure = {
                "success": False,
                "error": "rubric_hash mismatch — rubric may have been tampered",
                "rubric_pass": False,
                "predicate_results": [],
                "request_id": request_id,
            }
            self._audit(
                "verify_rubric",
                inputs={"request_id": request_id, "audit_source": "inline" if inline_content else url},
                result=failure,
                error="rubric_hash mismatch",
            )
            return failure

        # 2. Resolve content — inline (Option C) or URL fetch.
        audit_source = "inline" if inline_content else "python_fetch"

        if inline_content:
            # Option C: content supplied directly — no HTTP fetch, no SSRF risk.
            content = inline_content
        else:
            # URL path: fetch bytes, check SSRF, decode.
            block_err = _block_private_ip(url)
            if block_err:
                failure = {
                    "success": False,
                    "error": block_err,
                    "rubric_pass": False,
                    "predicate_results": [],
                    "request_id": request_id,
                }
                self._audit(
                    "verify_rubric",
                    inputs={"url": url, "rubric_hash": rubric_hash, "request_id": request_id},
                    result=failure,
                    error=block_err,
                )
                return failure

            raw_bytes = b""
            error_msg = ""
            try:
                req = _urllib_req.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"
                        )
                    },
                )
                _safe_opener = _urllib_req.build_opener(_SafeRedirectHandler)
                with _safe_opener.open(req, timeout=30) as resp:
                    if resp.status != 200:
                        error_msg = f"python_fetch: HTTP {resp.status}"
                    else:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            raw_bytes += chunk
            except Exception as exc:
                error_msg = f"python_fetch failed: {exc}"

            if error_msg:
                failure = {
                    "success": False,
                    "error": error_msg,
                    "rubric_pass": False,
                    "predicate_results": [],
                    "request_id": request_id,
                }
                self._audit(
                    "verify_rubric",
                    inputs={"url": url, "rubric_hash": rubric_hash, "request_id": request_id},
                    result=failure,
                    error=error_msg,
                )
                return failure

            try:
                content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = raw_bytes.decode("latin-1")

        # 3. Evaluate rubric.
        eval_result = evaluate_rubric(content, rubric)

        # 4. Build result dict.
        result = {
            "success": True,
            "url": url,
            "inline_content_length": len(inline_content) if inline_content else None,
            "source": audit_source,
            "rubric_pass": eval_result["rubric_pass"],
            "predicate_results": eval_result["predicate_results"],
            "content_length": eval_result["content_length"],
            "word_count": eval_result["word_count"],
            "rubric_hash": rubric_hash,
            "request_id": request_id,
        }

        # 5. Audit (rubric dict omitted — only hash is audited; inline content omitted — may be large).
        audit_inputs = {
            "rubric_hash": rubric_hash,
            "request_id": request_id,
            "source": audit_source,
        }
        if url:
            audit_inputs["url"] = url
        if inline_content:
            audit_inputs["inline_content_length"] = len(inline_content)
        self._audit(
            "verify_rubric",
            inputs=audit_inputs,
            result=result,
        )

        # 7. Return.
        return result

    async def accessibility_snapshot(self, offset: int = 0, limit: int = 0) -> dict:
        """Return Playwright accessibility tree for the current page.

        Args:
            offset: skip this many top-level nodes (0 = start from beginning)
            limit:  max top-level nodes to return (0 = no limit)
        """
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch(
            "accessibility_snapshot", {"offset": offset, "limit": limit}
        )
        self._audit(
            "accessibility_snapshot",
            {"url": result.get("url", ""), "offset": offset, "limit": limit},
            {
                "title": result.get("title", ""),
                "has_tree": result.get("tree") is not None,
                "total_nodes": result.get("total_nodes", 0),
            },
            error=result.get("error", ""),
        )
        return result

    async def network_requests(self) -> dict:
        """Return and clear the accumulated network request/response log."""
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("network_requests", {})
        self._audit(
            "network_requests",
            {},
            {"count": result.get("count", 0)},
            error="",
        )
        return result

    async def search(self, query: str) -> dict:
        """DuckDuckGo browser search — zero-config fallback when WebSearchTool APIs unavailable."""
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("search", {"query": query})
        self._audit(
            "search",
            {"query": query},
            {"results_count": len(result.get("results", [])), "query": result.get("query", query)},
            url_or_selector=query,
            error=result.get("error", ""),
        )
        return result

    async def _browser_search_fallback(self, query: str) -> dict:
        """Run a Chromium-backed DDG search fallback, starting BrowserTool on demand."""
        if self._browser_tool is None:
            from ..tools.browser import BrowserTool
            self._browser_tool = BrowserTool()
        return await self._browser_tool._dispatch("search", {"query": query})

    # ------------------------------------------------------------------
    # Wave 3: Crawler bridge methods
    # ------------------------------------------------------------------

    async def map_site(self, url: str, limit: int = 100, search: str = None) -> dict:
        """Breadth-first site URL discovery. Robots.txt compliant; respects Crawl-delay."""
        assert self._browser_tool is not None
        from .conduit_crawl import ConduitCrawler
        cfg = getattr(self, "_config", {}) or {}
        crawler = ConduitCrawler(
            self._browser_tool, self._audit_log, self._session_id,
            crawl_delay_sec=float(cfg.get("conduit_crawl_delay_sec", 1.0)),
            crawl_max_delay_sec=float(cfg.get("conduit_crawl_max_delay_sec", 60.0)),
        )
        return await crawler.map_site(url, limit=limit, search=search)

    async def crawl_site(
        self,
        url: str,
        max_depth: int = 2,
        include_paths: Optional[list] = None,
        exclude_paths: Optional[list] = None,
        limit: int = 20,
    ) -> dict:
        """Bulk page extraction with depth control. Every page logged to hash chain; respects Crawl-delay."""
        assert self._browser_tool is not None
        from .conduit_crawl import ConduitCrawler
        cfg = getattr(self, "_config", {}) or {}
        crawler = ConduitCrawler(
            self._browser_tool, self._audit_log, self._session_id,
            crawl_delay_sec=float(cfg.get("conduit_crawl_delay_sec", 1.0)),
            crawl_max_delay_sec=float(cfg.get("conduit_crawl_max_delay_sec", 60.0)),
        )
        return await crawler.crawl_site(
            url, max_depth=max_depth,
            include_paths=include_paths, exclude_paths=exclude_paths,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Wave 3: Monitor bridge methods
    # ------------------------------------------------------------------

    async def fingerprint(self, url: str) -> dict:
        """Navigate to URL and return a SHA-256 fingerprint (noise-stripped)."""
        assert self._browser_tool is not None
        from .conduit_monitor import ConduitMonitor
        monitor = ConduitMonitor(self._browser_tool, self._audit_log, self._session_id)
        return await monitor.fingerprint(url)

    async def check_changed(self, url: str, previous_fingerprint: str) -> dict:
        """Re-fingerprint URL, log PAGE_MUTATION event if content changed."""
        assert self._browser_tool is not None
        from .conduit_monitor import ConduitMonitor
        monitor = ConduitMonitor(self._browser_tool, self._audit_log, self._session_id)
        return await monitor.check_changed(url, previous_fingerprint)

    # ------------------------------------------------------------------
    # AIVS-Micro proof attachment (appended to every MCP response)
    # ------------------------------------------------------------------

    def _attach_micro_proof(self, result: dict, action: str) -> dict:
        """Attach an AIVS-Micro proof to a tool-call result dict.

        Every MCP response carries a ~200-byte cryptographic micro-proof
        so that receiving agents can verify the action was performed by a
        Conduit instance.  The proof is under ``_conduit_proof`` and adds
        minimal overhead.

        Skipped for proof-export actions (they already ARE proofs) and for
        error responses.
        """
        # Skip for proof actions, errors, and non-dict results
        if action in ("export_proof", "export_micro"):
            return result
        if not isinstance(result, dict) or result.get("error"):
            return result

        try:
            from .conduit_proof import ConduitProof
            url = result.get("url", self._current_url or "")
            # Hash the result payload as the dom_hash for the micro-proof
            content_hash = hashlib.sha256(
                json.dumps(result, sort_keys=True, default=str).encode()
            ).hexdigest()
            proof_obj = ConduitProof(
                self._audit_log, self._session_id,
                f"# Ed25519 public key: {self._identity.public_key_hex}\n",
                identity=self._identity,
            )
            micro = proof_obj.export_micro(
                url=url, dom_hash=content_hash, scan_origin="mcp_response",
            )
            if micro.get("success"):
                result["_conduit_proof"] = micro["micro_proof"]
        except Exception as exc:
            logger.warning("_attach_micro_proof failed: %s", exc)

        return result

    # ------------------------------------------------------------------
    # Wave 3: Proof bridge method
    # ------------------------------------------------------------------

    def export_proof(self, output_dir: str = None, previous_bundle_path: str = None, page_hashes: list = None) -> dict:
        """Export a self-verifiable session proof bundle (.tar.gz).

        Args:
            output_dir: directory for the bundle file
            previous_bundle_path: path to prior bundle for scan chain linking
            page_hashes: list of {"url": str, "hash": str} for Merkle tree
        """
        from .conduit_proof import ConduitProof
        public_key_pem = f"# Ed25519 public key: {self._identity.public_key_hex}\n"
        proof = ConduitProof(self._audit_log, self._session_id, public_key_pem, identity=self._identity)
        return proof.export(
            output_dir=output_dir,
            previous_bundle_path=previous_bundle_path,
            page_hashes=page_hashes,
        )

    def export_micro(self, url: str, dom_hash: str, scan_origin: str = "local") -> dict:
        """Export a minimal AIVS-Micro proof (~200 bytes).

        6-field cryptographic proof for continuous monitoring, embedded widgets,
        and API responses. Verifiable with just the Conduit public key.
        """
        from .conduit_proof import ConduitProof
        public_key_pem = f"# Ed25519 public key: {self._identity.public_key_hex}\n"
        proof = ConduitProof(self._audit_log, self._session_id, public_key_pem, identity=self._identity)
        result = proof.export_micro(url=url, dom_hash=dom_hash, scan_origin=scan_origin)
        # Audit the micro proof export
        self._audit(
            "export_micro",
            {"url": url, "scan_origin": scan_origin},
            {"micro_proof_keys": list(result.get("micro_proof", {}).keys())} if result.get("success") else {},
            error="" if result.get("success") else result.get("error", ""),
        )
        return result

    # ------------------------------------------------------------------
    # Wave 6: Web Search bridge method
    # ------------------------------------------------------------------

    async def web_search(self, query: str, query_type: str = None) -> dict:
        """Multi-engine web search with API-first routing and Chromium fallback."""
        # Lazy import web search tool
        import sys as _sys
        web_search_mod = _sys.modules.get("cato.tools.web_search")
        if web_search_mod is None:
            from pathlib import Path as _Path
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location(
                "cato.tools.web_search",
                str(_Path(__file__).parent / "web_search.py"),
            )
            web_search_mod = _ilu.module_from_spec(_spec)
            _sys.modules["cato.tools.web_search"] = web_search_mod
            _spec.loader.exec_module(web_search_mod)

        tool = web_search_mod.WebSearchTool()
        qt = query_type if query_type in ("code", "news", "academic", "general") else None
        results = await tool.search_async(query, query_type=qt)
        browser_fallback = None
        browser_error = ""
        if not results and (qt or web_search_mod.classify_query(query)) != "academic":
            browser_fallback = await self._browser_search_fallback(query)
            browser_error = browser_fallback.get("error", "")
            browser_results = browser_fallback.get("results", [])
            results = [
                web_search_mod.SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source_engine="ddg_browser",
                    rank=i,
                )
                for i, item in enumerate(browser_results)
                if item.get("url")
            ]
            for r in results:
                r.confidence = web_search_mod._heuristic_confidence(query, r)
            results.sort(key=lambda r: r.confidence, reverse=True)
        result_dicts = [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "source_engine": r.source_engine,
                "confidence": round(r.confidence, 3),
                "rank": r.rank,
            }
            for r in results
        ]
        output = {
            "query": query,
            "query_type": qt or web_search_mod.classify_query(query),
            "count": len(result_dicts),
            "results": result_dicts,
            "fallback_used": "ddg_browser" if result_dicts and browser_fallback is not None else None,
        }
        if browser_error:
            output["fallback_error"] = browser_error
        self._audit("web_search", {"query": query, "query_type": qt}, output)
        return output

    async def academic_search(self, query: str, source: str = "auto") -> dict:
        """Academic literature search via arXiv, Semantic Scholar, or PubMed."""
        import sys as _sys
        web_search_mod = _sys.modules.get("cato.tools.web_search")
        if web_search_mod is None:
            from pathlib import Path as _Path
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location(
                "cato.tools.web_search",
                str(_Path(__file__).parent / "web_search.py"),
            )
            web_search_mod = _ilu.module_from_spec(_spec)
            _sys.modules["cato.tools.web_search"] = web_search_mod
            _spec.loader.exec_module(web_search_mod)

        tool = web_search_mod.WebSearchTool()
        if source == "arxiv":
            results = await asyncio.get_event_loop().run_in_executor(None, tool._search_arxiv, query)
        elif source == "semantic_scholar":
            results = await asyncio.get_event_loop().run_in_executor(None, tool._search_semantic_scholar, query)
        elif source == "pubmed":
            results = await asyncio.get_event_loop().run_in_executor(None, tool._search_pubmed, query)
        else:
            results = await tool.search_async(query, query_type="academic")

        result_dicts = [
            {"title": r.title, "url": r.url, "snippet": r.snippet,
             "source_engine": r.source_engine, "confidence": round(r.confidence, 3),
             "published_date": r.published_date}
            for r in results
        ]
        output = {"query": query, "source": source, "count": len(result_dicts), "results": result_dicts}
        self._audit("academic_search", {"query": query, "source": source}, output)
        return output

    async def youtube_transcript(self, url: str, lang: str = "en") -> dict:
        """Extract YouTube video transcript via yt-dlp (primary) or browser intercept (fallback)."""
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("youtube_transcript", {"url": url, "lang": lang})
        self._audit(
            "youtube_transcript",
            {"url": url, "lang": lang},
            result,
            url_or_selector=url,
            error=result.get("error", ""),
        )
        return result

    # ------------------------------------------------------------------
    # execute() dispatcher (agent_loop entry point)
    # ------------------------------------------------------------------

    async def execute(self, args: dict[str, Any]) -> str:
        """Dispatch from agent_loop tool registry (same interface as BrowserTool.execute).

        All action paths go through _audit() so every browser action is
        recorded in both the billing ledger AND the SHA-256 hash chain.
        """
        # F26: validate required args before routing
        REQUIRED_ARGS = {
            "navigate": ["url"],
            "click": ["selector"],
            "type": ["selector", "text"],
            "fill": ["selector", "text"],
            "extract": [],
            "screenshot": [],
            "eval": ["js_code"],
            "scroll": [],
            "wait": [],
            "key_press": ["key"],
            "hover": ["selector"],
            "select_option": ["selector", "value"],
            "output_to_file": ["filename", "content"],
            "web_search": ["query"],
            "verify_deliverable": ["url", "expected_hash"],
            "verify_rubric": ["rubric", "rubric_hash"],
            "accessibility_snapshot": [],
            "capture_download": ["selector"],
            "get_downloads": [],
            "youtube_transcript": ["url"],
        }

        action = args.pop("action", "") if isinstance(args, dict) else ""
        required = REQUIRED_ARGS.get(action, [])
        missing = [k for k in required if k not in args]
        if missing:
            return json.dumps({"success": False, "error": f"Missing required args for action '{action}': {missing}"})

        _ALL_ACTIONS = [
            # Wave 0 + Wave 1
            "navigate", "click", "type", "fill", "extract", "screenshot",
            "scroll", "wait", "wait_for", "key_press", "hover",
            "select_option", "handle_dialog", "navigate_back", "console_messages",
            # Wave 2
            "eval", "extract_main", "extract_structured", "output_file", "output_to_file",
            "accessibility_snapshot", "network_requests",
            # Wave 3
            "map", "crawl", "fingerprint", "check_changed", "export_proof",
            "login", "check_session", "save_cookies", "load_cookies", "search",
            # Wave 4: CAPTCHA
            "detect_captcha", "solve_captcha", "solve_captcha_vision",
            # Wave 5: Proxy
            "rotate_proxy",
            # Wave 6: Web Search
            "web_search",
            # Wave 7: Academic Search
            "academic_search",
            # Wave 8: Marketplace product
            "marketplace_list", "marketplace_targets", "marketplace_plan",
            "marketplace_create_job", "marketplace_get_job", "marketplace_list_jobs",
            "marketplace_create_account", "marketplace_list_accounts",
            "marketplace_create_proxy", "marketplace_list_proxies", "marketplace_get_proxy", "marketplace_test_proxy",
            "marketplace_save_session", "marketplace_get_session", "marketplace_list_sessions",
            "marketplace_bootstrap_session", "marketplace_execute_job", "marketplace_enqueue_job",
            "marketplace_queue_status", "marketplace_get_result", "marketplace_list_results",
            "marketplace_export_result",
            # Wave 9: Downloads
            "capture_download", "get_downloads",
            # Wave 10: YouTube
            "youtube_transcript",
        ]
        dispatch: dict[str, Any] = {
            # Wave 0 + Wave 1
            "navigate":               lambda: self.navigate(args.get("url", "")),
            "click":                  lambda: self.click(args.get("selector", "")),
            "type":                   lambda: self.type_text(args.get("selector", ""), args.get("text", "")),
            "fill":                   lambda: self.fill(args.get("selector", ""), args.get("text", "")),
            "extract":                lambda: self.extract(args.get("selector", "body")),
            "screenshot":             lambda: self.screenshot(args.get("path")),
            "scroll":                 lambda: self.scroll(
                                          args.get("direction", "down"),
                                          args.get("amount", 300),
                                          args.get("selector"),
                                      ),
            "wait":                   lambda: self.wait(args.get("seconds", 1.0)),
            "wait_for":               lambda: self.wait_for(
                                          args.get("condition", "selector"),
                                          args.get("value", ""),
                                          args.get("timeout_ms", 10000),
                                      ),
            "key_press":              lambda: self.key_press(args.get("key", "Enter")),
            "hover":                  lambda: self._hover_with_healing(args.get("selector", "")),
            "select_option":          lambda: self.select_option(
                                          args.get("selector", ""),
                                          args.get("value", ""),
                                          args.get("label", ""),
                                          args.get("index"),
                                      ),
            "handle_dialog":          lambda: self.handle_dialog(
                                          args.get("action", "accept"),
                                          args.get("text", ""),
                                      ),
            "navigate_back":          lambda: self.navigate_back(),
            "console_messages":       lambda: self.console_messages(),
            # Wave 2: Extraction
            "eval":                   lambda: self.eval(args.get("js_code", "")),
            "extract_main":           lambda: self.extract_main(max_chars=args.get("max_chars", 5000), fmt=args.get("fmt", "text"), provenance_mode=args.get("provenance_mode", False)),
            "extract_structured":     lambda: self.extract_structured(
                                          schema=args.get("schema", {}),
                                          max_chars=args.get("max_chars", 5000),
                                          model_extract=args.get("model_extract"),
                                      ),
            "output_file":            lambda: self.output_to_file(
                                          args.get("filename", "output"),
                                          args.get("content", ""),
                                          args.get("fmt", "md"),
                                      ),
            "output_to_file":         lambda: self.output_to_file(
                                          args.get("filename", "output"),
                                          args.get("content", ""),
                                          args.get("fmt", "md"),
                                      ),
            "accessibility_snapshot": lambda: self.accessibility_snapshot(int(args.get("offset", 0)), int(args.get("limit", 0))),
            "network_requests":       lambda: self.network_requests(),
            # Wave 3: Crawler
            "map":                    lambda: self.map_site(
                                          args.get("url", ""),
                                          limit=args.get("limit", 100),
                                          search=args.get("search"),
                                      ),
            "crawl":                  lambda: self.crawl_site(
                                          args.get("url", ""),
                                          max_depth=args.get("max_depth", 2),
                                          include_paths=args.get("include_paths"),
                                          exclude_paths=args.get("exclude_paths"),
                                          limit=args.get("limit", 20),
                                      ),
            # Wave 3: Monitor
            "fingerprint":            lambda: self.fingerprint(args.get("url", "")),
            "check_changed":          lambda: self.check_changed(
                                          args.get("url", ""),
                                          args.get("previous_fingerprint", ""),
                                      ),
            # Wave 2: JS Delta
            "js_delta":               lambda: self.js_delta(),
            # Wave 3: Proof (sync methods — wrapped to allow await)
            "export_proof":           lambda: _sync_as_coro(
                                          self.export_proof,
                                          args.get("output_dir"),
                                          args.get("previous_bundle_path"),
                                          args.get("page_hashes"),
                                      ),
            "export_micro":           lambda: _sync_as_coro(
                                          self.export_micro,
                                          args.get("url", ""),
                                          args.get("dom_hash", ""),
                                          args.get("scan_origin", "local"),
                                      ),
            "login":                  lambda: self.login(args.get("url", ""), args.get("credential_key", ""), args.get("vault")),
            "check_session":          lambda: self.check_session(args.get("url", "")),
            "save_cookies":           lambda: self.save_cookies(args.get("label", "default")),
            "load_cookies":           lambda: self.load_cookies(args.get("label", "default")),
            "search":                 lambda: self.search(args.get("query", "")),
            # Wave 4: CAPTCHA — delegated directly to BrowserTool dispatch
            "detect_captcha":         lambda: self._browser_tool._dispatch("detect_captcha", {}),
            "solve_captcha":          lambda: self._browser_tool._dispatch("solve_captcha", {}),
            "solve_captcha_vision":   lambda: self._browser_tool._dispatch("solve_captcha_vision", {}),
            # Wave 5: Proxy rotation — delegated directly to BrowserTool dispatch
            "rotate_proxy":           lambda: self._browser_tool._dispatch("rotate_proxy", {}),
            # Wave 6: Web Search — no browser required
            "web_search":             lambda: self.web_search(args.get("query", ""), args.get("query_type")),
            # Wave 7: Academic Search
            "academic_search":        lambda: self.academic_search(args.get("query", ""), args.get("source", "auto")),
            # Wave 8: Marketplace product
            "marketplace_list":       lambda: self.marketplace_list(),
            "marketplace_targets":    lambda: self.marketplace_targets(args.get("marketplace", "")),
            "marketplace_plan":       lambda: self.marketplace_plan(
                                          args.get("marketplace", ""),
                                          args.get("target_type", ""),
                                          args.get("target_url", ""),
                                          args.get("account_id", ""),
                                          args.get("proxy_label", ""),
                                      ),
            "marketplace_create_job": lambda: self.marketplace_create_job(
                                          args.get("marketplace", ""),
                                          args.get("target_type", ""),
                                          args.get("target_url", ""),
                                          args.get("account_id", ""),
                                          args.get("proxy_label", ""),
                                          args.get("request_payload", {}),
                                      ),
            "marketplace_get_job":    lambda: self.marketplace_get_job(args.get("job_id", "")),
            "marketplace_list_jobs":  lambda: self.marketplace_list_jobs(
                                          args.get("marketplace", ""),
                                          args.get("status", ""),
                                      ),
            "marketplace_create_account": lambda: self.marketplace_create_account(
                                          args.get("marketplace", ""),
                                          args.get("display_name", ""),
                                          args.get("credential_key", ""),
                                          args.get("proxy_label", ""),
                                          args.get("metadata", {}),
                                      ),
            "marketplace_list_accounts": lambda: self.marketplace_list_accounts(
                                          args.get("marketplace", ""),
                                      ),
            "marketplace_create_proxy": lambda: self.marketplace_create_proxy(
                                          args.get("label", ""),
                                          args.get("host", ""),
                                          args.get("port", 0),
                                          args.get("protocol", "http"),
                                          args.get("username", ""),
                                          args.get("password", ""),
                                          args.get("kind", "http"),
                                          args.get("metadata", {}),
                                      ),
            "marketplace_list_proxies": lambda: self.marketplace_list_proxies(
                                          args.get("state", ""),
                                      ),
            "marketplace_get_proxy": lambda: self.marketplace_get_proxy(
                                          args.get("label", ""),
                                      ),
            "marketplace_test_proxy": lambda: self.marketplace_test_proxy(
                                          args.get("label", ""),
                                          args.get("test_url", "https://api.ipify.org/"),
                                      ),
            "marketplace_save_session": lambda: self.marketplace_save_session(
                                          args.get("account_id", ""),
                                          args.get("label", ""),
                                          args.get("cookie_path", ""),
                                          args.get("state", "fresh"),
                                          args.get("metadata", {}),
                                      ),
            "marketplace_get_session": lambda: self.marketplace_get_session(
                                          args.get("session_id", ""),
                                      ),
            "marketplace_list_sessions": lambda: self.marketplace_list_sessions(
                                          args.get("marketplace", ""),
                                          args.get("account_id", ""),
                                      ),
            "marketplace_bootstrap_session": lambda: self.marketplace_bootstrap_session(
                                          args.get("account_id", ""),
                                          args.get("target_url", ""),
                                      ),
            "marketplace_execute_job": lambda: self.marketplace_execute_job(
                                          args.get("job_id", ""),
                                      ),
            "marketplace_enqueue_job": lambda: self.marketplace_enqueue_job(
                                          args.get("job_id", ""),
                                      ),
            "marketplace_queue_status": lambda: self.marketplace_queue_status(
                                          args.get("job_id", ""),
                                      ),
            "marketplace_get_result": lambda: self.marketplace_get_result(
                                          args.get("result_id", ""),
                                      ),
            "marketplace_list_results": lambda: self.marketplace_list_results(
                                          args.get("job_id", ""),
                                      ),
            "marketplace_export_result": lambda: self.marketplace_export_result(
                                          args.get("result_id", ""),
                                          args.get("fmt", "jsonl"),
                                      ),
            # Wave 9: Downloads
            "capture_download":       lambda: self.capture_download(args.get("selector", ""), int(args.get("timeout", 30000))),
            "get_downloads":          lambda: self.get_downloads(),
            # Wave 10: YouTube
            "youtube_transcript":     lambda: self.youtube_transcript(args.get("url", ""), args.get("lang", "en")),
        }
        handler = dispatch.get(action)
        if handler is None:
            return json.dumps({
                "error": f"Unknown conduit action: {action!r}. Valid: {_ALL_ACTIONS}",
            })
        try:
            coro_or_val = handler()
            import asyncio as _asyncio
            if _asyncio.iscoroutine(coro_or_val):
                result = await coro_or_val
            else:
                result = coro_or_val
            # Attach AIVS-Micro proof to every MCP response
            if isinstance(result, dict):
                result = self._attach_micro_proof(result, action)
            return json.dumps(result)
        except BudgetExceededError as exc:
            return json.dumps({"error": str(exc), "budget_exceeded": True})
        except Exception as exc:
            logger.error("ConduitBridge action %s failed: %s", action, exc)
            return json.dumps({"error": str(exc), "action": action})
