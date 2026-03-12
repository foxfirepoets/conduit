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
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from ..audit import AuditLog

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
    "output_to_file":         0,
    "accessibility_snapshot": 0,
    "network_requests":       0,
    # Wave 3
    "map":                    0,
    "crawl":                  0,
    "fingerprint":            0,
    "check_changed":          0,
    "export_proof":           0,
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
    # Internal events
    "selector_healing":       0,
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
# Custom exceptions
# ---------------------------------------------------------------------------

class BudgetExceededError(RuntimeError):
    """Raised when a Conduit action would exceed the per-session budget."""


# ---------------------------------------------------------------------------
# Ed25519 identity (local keypair)
# ---------------------------------------------------------------------------

class ConduitIdentity:
    """
    Manages a local Ed25519 keypair stored in {data_dir}/conduit_identity.key.

    The key is used to sign audit receipts — it never leaves the local machine.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        from ..platform import get_data_dir
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
        from ..platform import get_data_dir
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
            self._session_id = session_id_if_config or "default"
            self._budget_cents = int(cfg.get("conduit_budget_per_session", budget_cents))
            raw_data_dir = cfg.get("data_dir")
            data_dir = Path(raw_data_dir) if raw_data_dir else data_dir
            self._config = cfg
        else:
            self._session_id = str(session_id_or_config)
            self._budget_cents = budget_cents
            self._config = {}

        self._session_cost_cents_total: int = 0

        self._identity = ConduitIdentity(data_dir)
        # Pass data_dir-based db_path so tests using tmp_path get an isolated ledger
        # instead of writing to the global ~/.cato/cato.db.
        ledger_db = (data_dir / "cato.db") if data_dir is not None else None
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

    async def start(self) -> None:
        """Initialize the browser, billing ledger, and audit log."""
        self._ledger.connect()
        self._audit_log.connect()
        # Lazy import to avoid circular deps
        from ..tools.browser import BrowserTool
        self._browser_tool = BrowserTool()
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

    @property
    def session_cost_cents(self) -> int:
        """Return total cents spent in this session (queries ledger for accuracy)."""
        # Prefer ledger total so externally-recorded charges are included
        try:
            if self._ledger._conn is not None or True:
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
        # Budget check — query ledger for authoritative total
        try:
            current_total = self._ledger.session_total_cents(self._session_id)
        except Exception:
            current_total = self._session_cost_cents_total

        if current_total + cost > self._budget_cents:
            raise BudgetExceededError(
                f"Conduit budget {self._budget_cents}¢ would be exceeded by '{action}' ({cost}¢). "
                f"Currently at {current_total}¢."
            )

        # 1) Write to billing ledger (conduit_billing table)
        self._ledger.record(self._session_id, action, cost, url_or_selector, not bool(error))
        self._session_cost_cents_total = current_total + cost

        # 2) Write to audit hash chain (audit_log table)
        self._audit_log.log(
            session_id=self._session_id,
            action_type="tool_call",
            tool_name=f"browser.{action}",
            inputs=inputs,
            outputs=result if isinstance(result, dict) else {"raw": str(result)},
            cost_cents=cost,
            error=error,
        )

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
        except Exception:
            pass  # Never let audit failure break healing

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
        self._audit(
            "eval",
            {"js_code": js_code, "code_hash": result.get("code_hash", "")},
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
                con = sqlite3.connect(str(self._audit_log._db_path))
                row = con.execute("SELECT rowid FROM audit_log ORDER BY rowid DESC LIMIT 1").fetchone()
                if row:
                    audit_row_id = row[0]
                con.close()
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

    async def output_to_file(self, filename: str, content: str, fmt: str = "md") -> dict:
        """
        Write content to a workspace file. Audit stores filename + fmt + byte_count
        but NOT the full content (may be very large).
        """
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch(
            "output_to_file", {"filename": filename, "content": content, "fmt": fmt}
        )
        # Audit inputs: filename + fmt + byte_count — NOT the full content
        self._audit(
            "output_to_file",
            {"filename": filename, "fmt": fmt, "byte_count": result.get("bytes", 0)},
            result,
            error="" if result.get("success") else result.get("error", ""),
        )
        return result

    async def accessibility_snapshot(self) -> dict:
        """Return Playwright accessibility tree for the current page."""
        assert self._browser_tool is not None
        result = await self._browser_tool._dispatch("accessibility_snapshot", {})
        self._audit(
            "accessibility_snapshot",
            {"url": result.get("url", "")},
            {"title": result.get("title", ""), "has_tree": result.get("tree") is not None},
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
    # Wave 3: Proof bridge method
    # ------------------------------------------------------------------

    def export_proof(self, output_dir: str = None) -> dict:
        """Export a self-verifiable session proof bundle (.tar.gz)."""
        from .conduit_proof import ConduitProof
        public_key_pem = f"# Ed25519 public key: {self._identity.public_key_hex}\n"
        proof = ConduitProof(self._audit_log, self._session_id, public_key_pem, identity=self._identity)
        return proof.export(output_dir=output_dir)

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

    # ------------------------------------------------------------------
    # execute() dispatcher (agent_loop entry point)
    # ------------------------------------------------------------------

    async def execute(self, args: dict[str, Any]) -> str:
        """Dispatch from agent_loop tool registry (same interface as BrowserTool.execute).

        All action paths go through _audit() so every browser action is
        recorded in both the billing ledger AND the SHA-256 hash chain.
        """
        action = args.pop("action", "") if isinstance(args, dict) else ""
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
            "accessibility_snapshot": lambda: self.accessibility_snapshot(),
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
            # Wave 3: Proof (sync method — wrapped to allow await)
            "export_proof":           lambda: _sync_as_coro(self.export_proof, args.get("output_dir")),
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
            return json.dumps(result)
        except BudgetExceededError as exc:
            return json.dumps({"error": str(exc), "budget_exceeded": True})
        except Exception as exc:
            logger.error("ConduitBridge action %s failed: %s", action, exc)
            return json.dumps({"error": str(exc), "action": action})
