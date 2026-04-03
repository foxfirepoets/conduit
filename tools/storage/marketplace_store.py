from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


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
                credential_key,
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
                    password,
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
                    password,
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
            "credential_key": row["credential_key"],
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
            proxy["password"] = row["password"]
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
        if state:
            rows = self._conn.execute(
                "SELECT id FROM marketplace_proxies WHERE state = ? ORDER BY created_at DESC",
                (state,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id FROM marketplace_proxies ORDER BY created_at DESC",
            ).fetchall()
        proxies: list[dict[str, Any]] = []
        for row in rows:
            proxy = self.get_proxy(row["id"])
            if proxy is not None:
                proxies.append(proxy)
        return proxies

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
        existing = self.get_proxy(proxy_id, include_secret=True)
        if existing is None:
            return None
        next_metadata = existing["metadata"]
        if metadata:
            next_metadata = {**next_metadata, **metadata}
        self._conn.execute(
            """
            UPDATE marketplace_proxies
            SET state = ?, cooldown_until = ?, last_failure_class = ?, metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                state,
                existing["cooldown_until"] if cooldown_until is None else cooldown_until,
                last_failure_class,
                json.dumps(next_metadata, ensure_ascii=True),
                time.time(),
                proxy_id,
            ),
        )
        self._conn.commit()
        return self.get_proxy(proxy_id)

    def list_accounts(self, marketplace: str | None = None) -> list[dict[str, Any]]:
        self._ensure_connected()
        assert self._conn is not None
        if marketplace:
            rows = self._conn.execute(
                "SELECT id FROM marketplace_accounts WHERE marketplace = ? ORDER BY created_at DESC",
                (marketplace,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id FROM marketplace_accounts ORDER BY created_at DESC",
            ).fetchall()
        accounts: list[dict[str, Any]] = []
        for row in rows:
            account = self.get_account(row["id"])
            if account is not None:
                accounts.append(account)
        return accounts

    def update_account_status(
        self,
        account_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        self._ensure_connected()
        assert self._conn is not None
        existing = self.get_account(account_id)
        if existing is None:
            return None
        next_metadata = existing["metadata"]
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
        self._conn.commit()
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

    def list_saved_sessions(
        self,
        marketplace: str | None = None,
        account_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_connected()
        assert self._conn is not None
        query = """
        SELECT ms.id
        FROM marketplace_saved_sessions ms
        JOIN marketplace_accounts ma ON ma.id = ms.account_id
        """
        params: list[str] = []
        clauses: list[str] = []
        if marketplace:
            clauses.append("ma.marketplace = ?")
            params.append(marketplace)
        if account_id:
            clauses.append("ms.account_id = ?")
            params.append(account_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY ms.created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        sessions: list[dict[str, Any]] = []
        for row in rows:
            session = self.get_saved_session(row["id"])
            if session is not None:
                sessions.append(session)
        return sessions

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
        existing = self.get_saved_session(session_id)
        if existing is None:
            return None
        next_metadata = existing["metadata"]
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
        self._conn.commit()
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

    def list_jobs(self, marketplace: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        self._ensure_connected()
        assert self._conn is not None
        query = "SELECT id FROM marketplace_jobs"
        params: list[str] = []
        clauses: list[str] = []
        if marketplace:
            clauses.append("marketplace = ?")
            params.append(marketplace)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        jobs: list[dict[str, Any]] = []
        for row in rows:
            job = self.get_job(row["id"])
            if job is not None:
                jobs.append(job)
        return jobs

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

    def list_results(self, job_id: str | None = None) -> list[dict[str, Any]]:
        self._ensure_connected()
        assert self._conn is not None
        if job_id:
            rows = self._conn.execute(
                "SELECT id FROM marketplace_results WHERE job_id = ? ORDER BY created_at DESC",
                (job_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id FROM marketplace_results ORDER BY created_at DESC",
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            result = self.get_result(row["id"])
            if result is not None:
                results.append(result)
        return results
