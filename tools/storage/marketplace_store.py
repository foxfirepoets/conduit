from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from cryptography.fernet import Fernet as _Fernet
    _FERNET_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FERNET_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "cryptography package not installed — credential fields will NOT be encrypted. "
        "Install with: pip install cryptography"
    )

_log = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS marketplace_accounts (
    id             TEXT PRIMARY KEY,
    marketplace    TEXT NOT NULL,
    display_name   TEXT NOT NULL,
    credential_key TEXT NOT NULL DEFAULT '',
    proxy_label    TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'active',
    metadata_json  TEXT NOT NULL DEFAULT '{}',
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_marketplace_accounts_marketplace
    ON marketplace_accounts(marketplace);

CREATE TABLE IF NOT EXISTS marketplace_saved_sessions (
    id            TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL,
    label         TEXT NOT NULL,
    cookie_path   TEXT NOT NULL DEFAULT '',
    state         TEXT NOT NULL DEFAULT 'fresh',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_marketplace_saved_sessions_account
    ON marketplace_saved_sessions(account_id);

CREATE TABLE IF NOT EXISTS marketplace_proxies (
    id                 TEXT PRIMARY KEY,
    label              TEXT NOT NULL UNIQUE,
    host               TEXT NOT NULL,
    port               INTEGER NOT NULL,
    username           TEXT NOT NULL DEFAULT '',
    password           TEXT NOT NULL DEFAULT '',
    protocol           TEXT NOT NULL DEFAULT 'http',
    kind               TEXT NOT NULL DEFAULT 'http',
    state              TEXT NOT NULL DEFAULT 'active',
    cooldown_until     REAL NOT NULL DEFAULT 0,
    last_failure_class TEXT NOT NULL DEFAULT '',
    metadata_json      TEXT NOT NULL DEFAULT '{}',
    created_at         REAL NOT NULL,
    updated_at         REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_marketplace_proxies_state
    ON marketplace_proxies(state);

CREATE TABLE IF NOT EXISTS marketplace_jobs (
    id            TEXT PRIMARY KEY,
    marketplace   TEXT NOT NULL,
    target_type   TEXT NOT NULL,
    target_url    TEXT NOT NULL,
    status        TEXT NOT NULL,
    account_id    TEXT NOT NULL DEFAULT '',
    proxy_label   TEXT NOT NULL DEFAULT '',
    session_id    TEXT NOT NULL DEFAULT '',
    request_json  TEXT NOT NULL DEFAULT '{}',
    plan_json     TEXT NOT NULL DEFAULT '{}',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    created_at    REAL NOT NULL,
    updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_marketplace_jobs_marketplace
    ON marketplace_jobs(marketplace);
CREATE INDEX IF NOT EXISTS idx_marketplace_jobs_status
    ON marketplace_jobs(status);

CREATE TABLE IF NOT EXISTS marketplace_results (
    id                TEXT PRIMARY KEY,
    job_id            TEXT NOT NULL,
    records_json      TEXT NOT NULL DEFAULT '[]',
    proof_bundle_path TEXT NOT NULL DEFAULT '',
    artifact_path     TEXT NOT NULL DEFAULT '',
    created_at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_marketplace_results_job
    ON marketplace_results(job_id);
"""


def _json_loads(raw: str, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


class MarketplaceStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._fernet = None

    # ------------------------------------------------------------------
    # F5: Field-level encryption helpers
    # ------------------------------------------------------------------

    def _get_fernet(self) -> "_Fernet":  # type: ignore[name-defined]
        if self._fernet is not None:
            return self._fernet
        key_path = Path.home() / ".cato" / "store.key"
        if not key_path.exists():
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(_Fernet.generate_key())
            key_path.chmod(0o600)
        self._fernet = _Fernet(key_path.read_bytes())
        return self._fernet

    def _encrypt(self, value: str) -> str:
        if not value:
            return value
        if not _FERNET_AVAILABLE:
            return value
        return self._get_fernet().encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        if not value:
            return value
        if not _FERNET_AVAILABLE:
            return value
        try:
            return self._get_fernet().decrypt(value.encode()).decode()
        except Exception:
            return value  # already plaintext (backward compat)

    def connect(self) -> None:
        if self._conn is not None:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _ensure_connected(self) -> None:
        if self._conn is None:
            self.connect()

    def create_account(
        self,
        marketplace: str,
        display_name: str,
        credential_key: str = "",
        proxy_label: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_connected()
        assert self._conn is not None
        now = time.time()
        account_id = uuid.uuid4().hex
        payload = metadata or {}
        self._conn.execute(
            """
            INSERT INTO marketplace_accounts
              (id, marketplace, display_name, credential_key, proxy_label, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (
                account_id,
                marketplace,
                display_name,
                self._encrypt(credential_key),
                proxy_label,
                json.dumps(payload, ensure_ascii=True),
                now,
                now,
            ),
        )
        self._conn.commit()
        return self.get_account(account_id) or {}

    def save_proxy(
        self,
        label: str,
        host: str,
        port: int,
        *,
        protocol: str = "http",
        username: str = "",
        password: str = "",
        kind: str = "http",
        state: str = "active",
        cooldown_until: float = 0.0,
        last_failure_class: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_connected()
        assert self._conn is not None
        now = time.time()
        existing = self.get_proxy_by_label(label, include_secret=True)
        payload = metadata or {}
        if existing is None:
            proxy_id = uuid.uuid4().hex
            self._conn.execute(
                """
                INSERT INTO marketplace_proxies
                  (id, label, host, port, username, password, protocol, kind, state,
                   cooldown_until, last_failure_class, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proxy_id,
                    label,
                    host,
                    port,
                    username,
                    self._encrypt(password),
                    protocol,
                    kind,
                    state,
                    cooldown_until,
                    last_failure_class,
                    json.dumps(payload, ensure_ascii=True),
                    now,
                    now,
                ),
            )
        else:
            next_metadata = {**existing["metadata"], **payload}
            self._conn.execute(
                """
                UPDATE marketplace_proxies
                SET host = ?, port = ?, username = ?, password = ?, protocol = ?, kind = ?,
                    state = ?, cooldown_until = ?, last_failure_class = ?, metadata_json = ?, updated_at = ?
                WHERE label = ?
                """,
                (
                    host,
                    port,
                    username,
                    self._encrypt(password),
                    protocol,
                    kind,
                    state,
                    cooldown_until,
                    last_failure_class,
                    json.dumps(next_metadata, ensure_ascii=True),
                    now,
                    label,
                ),
            )
        self._conn.commit()
        return self.get_proxy_by_label(label) or {}

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM marketplace_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "marketplace": row["marketplace"],
            "display_name": row["display_name"],
            "credential_key": self._decrypt(row["credential_key"]),
            "proxy_label": row["proxy_label"],
            "status": row["status"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_proxy(
        self,
        row: sqlite3.Row,
        *,
        include_secret: bool = False,
    ) -> dict[str, Any]:
        proxy = {
            "id": row["id"],
            "label": row["label"],
            "host": row["host"],
            "port": row["port"],
            "protocol": row["protocol"],
            "kind": row["kind"],
            "state": row["state"],
            "cooldown_until": row["cooldown_until"],
            "last_failure_class": row["last_failure_class"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "has_auth": bool(row["username"] or row["password"]),
        }
        if include_secret:
            proxy["username"] = row["username"]
            proxy["password"] = self._decrypt(row["password"])
        return proxy

    def get_proxy(self, proxy_id: str, *, include_secret: bool = False) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM marketplace_proxies WHERE id = ?",
            (proxy_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_proxy(row, include_secret=include_secret)

    def get_proxy_by_label(self, label: str, *, include_secret: bool = False) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM marketplace_proxies WHERE label = ?",
            (label,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_proxy(row, include_secret=include_secret)

    def list_proxies(self, state: str | None = None) -> list[dict[str, Any]]:
        self._ensure_connected()
        assert self._conn is not None
        query = "SELECT * FROM marketplace_proxies WHERE 1=1"
        params: list[Any] = []
        if state:
            query += " AND state = ?"
            params.append(state)
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_proxy(row) for row in rows]

    def update_proxy_state(
        self,
        proxy_id: str,
        *,
        state: str,
        cooldown_until: float | None = None,
        last_failure_class: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        old_isolation = self._conn.isolation_level
        self._conn.isolation_level = None
        try:
            self._conn.execute("BEGIN EXCLUSIVE")
            row = self._conn.execute(
                "SELECT metadata_json, cooldown_until FROM marketplace_proxies WHERE id = ?",
                (proxy_id,),
            ).fetchone()
            if row is None:
                self._conn.execute("ROLLBACK")
                return None
            next_metadata = _json_loads(row["metadata_json"], {})
            if metadata:
                next_metadata = {**next_metadata, **metadata}
            effective_cooldown = row["cooldown_until"] if cooldown_until is None else cooldown_until
            self._conn.execute(
                """
                UPDATE marketplace_proxies
                SET state = ?, cooldown_until = ?, last_failure_class = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    state,
                    effective_cooldown,
                    last_failure_class,
                    json.dumps(next_metadata, ensure_ascii=True),
                    time.time(),
                    proxy_id,
                ),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        finally:
            self._conn.isolation_level = old_isolation
        return self.get_proxy(proxy_id)

    def _row_to_account_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "marketplace": row["marketplace"],
            "display_name": row["display_name"],
            "credential_key": self._decrypt(row["credential_key"]),
            "proxy_label": row["proxy_label"],
            "status": row["status"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_accounts(self, marketplace: str | None = None) -> list[dict[str, Any]]:
        self._ensure_connected()
        assert self._conn is not None
        query = "SELECT * FROM marketplace_accounts WHERE 1=1"
        params: list[Any] = []
        if marketplace:
            query += " AND marketplace = ?"
            params.append(marketplace)
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_account_dict(row) for row in rows]

    def update_account_status(
        self,
        account_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        old_isolation = self._conn.isolation_level
        self._conn.isolation_level = None
        try:
            self._conn.execute("BEGIN EXCLUSIVE")
            row = self._conn.execute(
                "SELECT metadata_json FROM marketplace_accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
            if row is None:
                self._conn.execute("ROLLBACK")
                return None
            next_metadata = _json_loads(row["metadata_json"], {})
            if metadata:
                next_metadata = {**next_metadata, **metadata}
            self._conn.execute(
                """
                UPDATE marketplace_accounts
                SET status = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(next_metadata, ensure_ascii=True),
                    time.time(),
                    account_id,
                ),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        finally:
            self._conn.isolation_level = old_isolation
        return self.get_account(account_id)

    def save_session(
        self,
        account_id: str,
        label: str,
        cookie_path: str,
        state: str = "fresh",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._ensure_connected()
        assert self._conn is not None
        now = time.time()
        session_id = uuid.uuid4().hex
        payload = metadata or {}
        self._conn.execute(
            """
            INSERT INTO marketplace_saved_sessions
              (id, account_id, label, cookie_path, state, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                account_id,
                label,
                cookie_path,
                state,
                json.dumps(payload, ensure_ascii=True),
                now,
                now,
            ),
        )
        self._conn.commit()
        return self.get_saved_session(session_id) or {}

    def get_saved_session(self, session_id: str) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM marketplace_saved_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "account_id": row["account_id"],
            "label": row["label"],
            "cookie_path": row["cookie_path"],
            "state": row["state"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_session_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "account_id": row["account_id"],
            "label": row["label"],
            "cookie_path": row["cookie_path"],
            "state": row["state"],
            "metadata": _json_loads(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_saved_sessions(
        self,
        marketplace: str | None = None,
        account_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_connected()
        assert self._conn is not None
        query = """
        SELECT ms.*
        FROM marketplace_saved_sessions ms
        JOIN marketplace_accounts ma ON ma.id = ms.account_id
        WHERE 1=1
        """
        params: list[Any] = []
        if marketplace:
            query += " AND ma.marketplace = ?"
            params.append(marketplace)
        if account_id:
            query += " AND ms.account_id = ?"
            params.append(account_id)
        query += " ORDER BY ms.created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_session_dict(row) for row in rows]

    def get_latest_saved_session(self, account_id: str) -> dict[str, Any] | None:
        sessions = self.list_saved_sessions(account_id=account_id)
        return sessions[0] if sessions else None

    def update_saved_session_state(
        self,
        session_id: str,
        state: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        old_isolation = self._conn.isolation_level
        self._conn.isolation_level = None
        try:
            self._conn.execute("BEGIN EXCLUSIVE")
            row = self._conn.execute(
                "SELECT metadata_json FROM marketplace_saved_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                self._conn.execute("ROLLBACK")
                return None
            next_metadata = _json_loads(row["metadata_json"], {})
            if metadata:
                next_metadata = {**next_metadata, **metadata}
            self._conn.execute(
                """
                UPDATE marketplace_saved_sessions
                SET state = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    state,
                    json.dumps(next_metadata, ensure_ascii=True),
                    time.time(),
                    session_id,
                ),
            )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        finally:
            self._conn.isolation_level = old_isolation
        return self.get_saved_session(session_id)

    def create_job(
        self,
        marketplace: str,
        target_type: str,
        target_url: str,
        request_payload: dict[str, Any],
        plan: dict[str, Any],
        account_id: str = "",
        proxy_label: str = "",
        session_id: str = "",
        status: str = "queued",
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        self._ensure_connected()
        assert self._conn is not None
        now = time.time()
        job_id = uuid.uuid4().hex
        self._conn.execute(
            """
            INSERT INTO marketplace_jobs
              (id, marketplace, target_type, target_url, status, account_id, proxy_label, session_id,
               request_json, plan_json, warnings_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                marketplace,
                target_type,
                target_url,
                status,
                account_id,
                proxy_label,
                session_id,
                json.dumps(request_payload, ensure_ascii=True),
                json.dumps(plan, ensure_ascii=True),
                json.dumps(warnings or [], ensure_ascii=True),
                now,
                now,
            ),
        )
        self._conn.commit()
        return self.get_job(job_id) or {}

    def update_job_status(self, job_id: str, status: str, warnings: list[str] | None = None) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        existing = self.get_job(job_id)
        if existing is None:
            return None
        merged_warnings = existing["warnings"]
        if warnings:
            merged_warnings = [*merged_warnings, *warnings]
        self._conn.execute(
            """
            UPDATE marketplace_jobs
            SET status = ?, warnings_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, json.dumps(merged_warnings, ensure_ascii=True), time.time(), job_id),
        )
        self._conn.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM marketplace_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "marketplace": row["marketplace"],
            "target_type": row["target_type"],
            "target_url": row["target_url"],
            "status": row["status"],
            "account_id": row["account_id"] or None,
            "proxy_label": row["proxy_label"] or None,
            "session_id": row["session_id"] or None,
            "request": _json_loads(row["request_json"], {}),
            "plan": _json_loads(row["plan_json"], {}),
            "warnings": _json_loads(row["warnings_json"], []),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_job_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "marketplace": row["marketplace"],
            "target_type": row["target_type"],
            "target_url": row["target_url"],
            "status": row["status"],
            "account_id": row["account_id"] or None,
            "proxy_label": row["proxy_label"] or None,
            "session_id": row["session_id"] or None,
            "request": _json_loads(row["request_json"], {}),
            "plan": _json_loads(row["plan_json"], {}),
            "warnings": _json_loads(row["warnings_json"], []),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_jobs(self, marketplace: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        self._ensure_connected()
        assert self._conn is not None
        query = "SELECT * FROM marketplace_jobs WHERE 1=1"
        params: list[Any] = []
        if marketplace:
            query += " AND marketplace = ?"
            params.append(marketplace)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_job_dict(row) for row in rows]

    def save_result(
        self,
        job_id: str,
        records: list[dict[str, Any]],
        proof_bundle_path: str = "",
        artifact_path: str = "",
    ) -> dict[str, Any]:
        self._ensure_connected()
        assert self._conn is not None
        result_id = uuid.uuid4().hex
        self._conn.execute(
            """
            INSERT INTO marketplace_results
              (id, job_id, records_json, proof_bundle_path, artifact_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                result_id,
                job_id,
                json.dumps(records, ensure_ascii=True),
                proof_bundle_path,
                artifact_path,
                time.time(),
            ),
        )
        self._conn.commit()
        return self.get_result(result_id) or {}

    def get_result(self, result_id: str) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT * FROM marketplace_results WHERE id = ?",
            (result_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "records": _json_loads(row["records_json"], []),
            "proof_bundle_path": row["proof_bundle_path"],
            "artifact_path": row["artifact_path"],
            "created_at": row["created_at"],
        }

    def _row_to_result_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "records": _json_loads(row["records_json"], []),
            "proof_bundle_path": row["proof_bundle_path"],
            "artifact_path": row["artifact_path"],
            "created_at": row["created_at"],
        }

    def list_results(self, job_id: str | None = None) -> list[dict[str, Any]]:
        self._ensure_connected()
        assert self._conn is not None
        query = "SELECT * FROM marketplace_results WHERE 1=1"
        params: list[Any] = []
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_result_dict(row) for row in rows]
