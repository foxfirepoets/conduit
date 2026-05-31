"""
tests/test_audit_helpers_and_receipt.py

Net-new tests for:
  - audit.py helper functions (_digest, _truncate, _sanitize_inputs)
  - AuditLog.export_session(), get_session_rows(), session_summary() edge cases
  - AuditLog.archive_old_rows()
  - Schema migration idempotency
  - receipt.py ReceiptWriter (generate, export_text, export_jsonl)

All tests use isolated tmp SQLite files. No browser launched.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sqlite3
import sys
import time
import types
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — same pattern as test_audit_chain.py
# ---------------------------------------------------------------------------

CONDUIT_ROOT = Path(__file__).parent.parent


def _bootstrap_package(tmp_db: Path) -> None:
    """Install minimal sys.modules shims so relative imports resolve."""
    cato_pkg = types.ModuleType("cato")
    cato_pkg.__path__ = [str(CONDUIT_ROOT)]
    cato_pkg.__package__ = "cato"
    sys.modules.setdefault("cato", cato_pkg)

    platform_mod = types.ModuleType("cato.platform")
    platform_mod.get_data_dir = lambda: tmp_db.parent
    sys.modules["cato.platform"] = platform_mod
    cato_pkg.platform = platform_mod  # type: ignore[attr-defined]
    sys.modules["cato.conduit_platform"] = platform_mod
    cato_pkg.conduit_platform = platform_mod  # type: ignore[attr-defined]

    if "cato.audit" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.audit",
            str(CONDUIT_ROOT / "audit.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        audit_mod = importlib.util.module_from_spec(spec)
        audit_mod.__package__ = "cato"
        sys.modules["cato.audit"] = audit_mod
        spec.loader.exec_module(audit_mod)  # type: ignore[union-attr]
        cato_pkg.audit = audit_mod  # type: ignore[attr-defined]

    if "cato.receipt" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "cato.receipt",
            str(CONDUIT_ROOT / "receipt.py"),
            submodule_search_locations=[],
        )
        assert spec and spec.loader
        receipt_mod = importlib.util.module_from_spec(spec)
        receipt_mod.__package__ = "cato"
        sys.modules["cato.receipt"] = receipt_mod
        spec.loader.exec_module(receipt_mod)  # type: ignore[union-attr]
        cato_pkg.receipt = receipt_mod  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("helpers_receipt_test") / "cato.db"
    _bootstrap_package(db)
    return db


@pytest.fixture(scope="module")
def audit_mod(tmp_db):
    return sys.modules["cato.audit"]


@pytest.fixture(scope="module")
def receipt_mod(tmp_db):
    return sys.modules["cato.receipt"]


@pytest.fixture(scope="module")
def AuditLog(audit_mod):
    return audit_mod.AuditLog


@pytest.fixture(scope="module")
def ReceiptWriter(receipt_mod):
    return receipt_mod.ReceiptWriter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_log(AuditLog, tmp_db: Path):
    log = AuditLog(db_path=tmp_db)
    log.connect()
    return log


def _populate_session(log, session_id: str, n: int = 3) -> list:
    row_ids = []
    for i in range(n):
        rid = log.log(
            session_id=session_id,
            action_type="tool_call",
            tool_name=f"browser.step{i}",
            inputs={"step": i},
            outputs={"ok": True},
            cost_cents=i + 1,
        )
        row_ids.append(rid)
    return row_ids


# ===========================================================================
# TestDigestHelper
# ===========================================================================

class TestDigestHelper:
    """Unit tests for the _digest() helper function. [C1]"""

    def test_digest_empty_string_returns_empty_string(self, audit_mod):
        # [P0] [C1 — Interface contract] [BOUNDARY]
        result = audit_mod._digest("")
        assert result == "", f"Expected '' for empty input, got {result!r}"

    def test_digest_returns_64_char_hex_string(self, audit_mod):
        # [P0] [C1 — Interface contract] [POSITIVE]
        result = audit_mod._digest("hello world")
        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert len(result) == 64, f"Expected 64-char hex digest, got len={len(result)}"
        assert all(c in "0123456789abcdef" for c in result), \
            f"Expected lowercase hex, got {result!r}"

    def test_digest_is_deterministic_for_same_input(self, audit_mod):
        # [P0] [C1 — Idempotency contract] [POSITIVE]
        text = "the same input every time"
        assert audit_mod._digest(text) == audit_mod._digest(text), \
            "_digest() must return the same value for the same input"

    def test_digest_differs_for_different_inputs(self, audit_mod):
        # [P0] [C1 — Interface contract] [NEGATIVE]
        d1 = audit_mod._digest("input_a")
        d2 = audit_mod._digest("input_b")
        assert d1 != d2, \
            f"_digest() must return different values for different inputs, got same: {d1!r}"

    def test_digest_matches_stdlib_sha256(self, audit_mod):
        # [P0] [C1 — Interface contract] [POSITIVE] — pins implementation to stdlib sha256
        text = "verify against stdlib"
        expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
        result = audit_mod._digest(text)
        assert result == expected, \
            f"Expected stdlib sha256 {expected!r}, got {result!r}"


# ===========================================================================
# TestTruncateHelper
# ===========================================================================

class TestTruncateHelper:
    """Unit tests for the _truncate() helper function. [C2]"""

    def test_truncate_short_text_returned_unchanged(self, audit_mod):
        # [P1] [C2 — Interface contract] [POSITIVE]
        text = "short"
        result = audit_mod._truncate(text, limit=2000)
        assert result == text, f"Expected unchanged text, got {result!r}"

    def test_truncate_text_at_exact_limit_returned_unchanged(self, audit_mod):
        # [P1] [C2 — Interface contract] [BOUNDARY]
        text = "x" * 2000
        result = audit_mod._truncate(text, limit=2000)
        assert result == text, \
            f"Text exactly at limit must not be truncated, got len={len(result)}"

    def test_truncate_text_one_over_limit_is_truncated(self, audit_mod):
        # [P1] [C2 — Interface contract] [BOUNDARY]
        text = "x" * 2001
        result = audit_mod._truncate(text, limit=2000)
        assert result.startswith("x" * 2000), \
            "First 2000 chars must be preserved after truncation"
        assert "truncated" in result, \
            f"Expected 'truncated' in suffix, got {result[-60:]!r}"

    def test_truncate_suffix_reports_correct_char_count(self, audit_mod):
        # [P1] [C2 — Data shape contract] [POSITIVE]
        text = "x" * 2100
        result = audit_mod._truncate(text, limit=2000)
        assert "100" in result, \
            f"Suffix must report 100 truncated chars, got {result[-60:]!r}"

    def test_truncate_with_custom_limit(self, audit_mod):
        # [P1] [C2 — Interface contract] [POSITIVE]
        text = "abcdefghij"
        result = audit_mod._truncate(text, limit=5)
        assert result.startswith("abcde"), \
            f"Expected first 5 chars preserved, got {result!r}"
        assert "truncated" in result, \
            "Expected truncation suffix when over custom limit"


# ===========================================================================
# TestSanitizeInputs
# ===========================================================================

class TestSanitizeInputs:
    """Unit tests for _sanitize_inputs(). [C3, C14]"""

    def test_non_sensitive_keys_passed_through_unchanged(self, audit_mod):
        # [P0] [C3 — Interface contract] [POSITIVE]
        inputs = {"url": "https://example.com", "selector": "#btn"}
        result = audit_mod._sanitize_inputs(inputs)
        assert result["url"] == "https://example.com", \
            f"url key must not be redacted, got {result['url']!r}"
        assert result["selector"] == "#btn", \
            f"selector key must not be redacted, got {result['selector']!r}"

    def test_exact_sensitive_key_redacted(self, audit_mod):
        # [P0] [C3 — Authorization contract] [NEGATIVE]
        sensitive_keys = [
            "password", "api_key", "token", "secret", "authorization",
            "bearer", "credential", "passwd", "passphrase", "key",
        ]
        for k in sensitive_keys:
            result = audit_mod._sanitize_inputs({k: "super_secret"})
            assert result[k] == "[REDACTED]", \
                f"Key '{k}' must be redacted, got {result[k]!r}"

    def test_partial_match_sensitive_key_redacted(self, audit_mod):
        # [P0] [C14 — Authorization contract] [NEGATIVE]
        inputs = {"api_key_v2": "should-be-redacted", "user_password_hash": "also-redacted"}
        result = audit_mod._sanitize_inputs(inputs)
        assert result["api_key_v2"] == "[REDACTED]", \
            "Partial-match key 'api_key_v2' must be redacted"
        assert result["user_password_hash"] == "[REDACTED]", \
            "Partial-match key 'user_password_hash' must be redacted"

    def test_non_dict_input_returns_empty_dict(self, audit_mod):
        # [P0] [C3 — Error contract] [NEGATIVE]
        for bad_input in [None, "string", 42, ["list"], True]:
            result = audit_mod._sanitize_inputs(bad_input)
            assert result == {}, \
                f"Non-dict input {bad_input!r} must return {{}}, got {result!r}"

    def test_empty_dict_returns_empty_dict(self, audit_mod):
        # [P0] [C3 — Interface contract] [BOUNDARY]
        result = audit_mod._sanitize_inputs({})
        assert result == {}, f"Empty dict must return empty dict, got {result!r}"

    def test_mixed_sensitive_and_clean_keys(self, audit_mod):
        # [P0] [C3 — Interface contract] [POSITIVE]
        inputs = {"url": "https://example.com", "token": "abc123", "selector": "#x"}
        result = audit_mod._sanitize_inputs(inputs)
        assert result["url"] == "https://example.com", \
            "Clean key 'url' must pass through"
        assert result["token"] == "[REDACTED]", \
            "Sensitive key 'token' must be redacted"
        assert result["selector"] == "#x", \
            "Clean key 'selector' must pass through"


# ===========================================================================
# TestExportSession
# ===========================================================================

class TestExportSession:
    """Unit tests for AuditLog.export_session(). [C4]"""

    def test_export_jsonl_contains_correct_row_count(self, AuditLog, tmp_db):
        # [P1] [C4 — Data shape contract] [POSITIVE]
        sid = f"export-jsonl-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=3)

        output = log.export_session(sid, fmt="jsonl")
        lines = [l for l in output.strip().split("\n") if l]
        assert len(lines) == 3, \
            f"Expected 3 JSONL lines for 3 rows, got {len(lines)}"

    def test_export_jsonl_each_line_is_valid_json(self, AuditLog, tmp_db):
        # [P1] [C4 — Data shape contract] [POSITIVE]
        sid = f"export-jsonl-valid-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=2)

        output = log.export_session(sid, fmt="jsonl")
        for i, line in enumerate(output.strip().split("\n")):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"Line {i} is not valid JSON: {exc}\n  line={line!r}"
                )
            assert "session_id" in obj, \
                f"Line {i} missing 'session_id' field, got keys: {list(obj.keys())}"

    def test_export_csv_has_header_row(self, AuditLog, tmp_db):
        # [P1] [C4 — Data shape contract] [POSITIVE]
        sid = f"export-csv-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=2)

        output = log.export_session(sid, fmt="csv")
        lines = output.strip().split("\n")
        header = lines[0]
        assert "session_id" in header, \
            f"CSV first row must be header containing 'session_id', got {header!r}"
        assert "action_type" in header, \
            f"CSV header must contain 'action_type', got {header!r}"

    def test_export_csv_row_count_matches_logged_rows(self, AuditLog, tmp_db):
        # [P1] [C4 — Data shape contract] [POSITIVE]
        sid = f"export-csv-count-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=4)

        output = log.export_session(sid, fmt="csv")
        lines = [l for l in output.strip().split("\n") if l]
        assert len(lines) == 5, \
            f"Expected 5 CSV lines (1 header + 4 data), got {len(lines)}"

    def test_export_empty_session_returns_empty_string(self, AuditLog, tmp_db):
        # [P1] [C4 — Error contract] [NEGATIVE]
        log = _make_log(AuditLog, tmp_db)
        output = log.export_session("nonexistent-session-xyz", fmt="jsonl")
        assert output == "", \
            f"Empty session must return empty string, got {output!r}"


# ===========================================================================
# TestGetSessionRows
# ===========================================================================

class TestGetSessionRows:
    """Unit tests for AuditLog.get_session_rows(). [C5]"""

    def test_get_session_rows_returns_list_of_dicts(self, AuditLog, tmp_db):
        # [P1] [C5 — Interface contract] [POSITIVE]
        sid = f"get-rows-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=3)

        rows = log.get_session_rows(sid)
        assert isinstance(rows, list), \
            f"Expected list, got {type(rows)}"
        assert len(rows) == 3, \
            f"Expected 3 rows, got {len(rows)}"
        assert all(isinstance(r, dict) for r in rows), \
            "Every row must be a plain dict"

    def test_get_session_rows_each_row_has_required_fields(self, AuditLog, tmp_db):
        # [P1] [C5 — Data shape contract] [POSITIVE]
        sid = f"get-rows-fields-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=1)

        rows = log.get_session_rows(sid)
        required_fields = {
            "id", "session_id", "action_type", "tool_name",
            "inputs_json", "outputs_json", "cost_cents",
            "error", "timestamp", "prev_hash", "row_hash",
        }
        for field in required_fields:
            assert field in rows[0], \
                f"Row missing required field '{field}', got keys: {list(rows[0].keys())}"

    def test_get_session_rows_unknown_session_returns_empty_list(self, AuditLog, tmp_db):
        # [P1] [C5 — Error contract] [NEGATIVE]
        log = _make_log(AuditLog, tmp_db)
        rows = log.get_session_rows("totally-unknown-session-id-xyz")
        assert rows == [], \
            f"Unknown session must return empty list, got {rows!r}"

    def test_get_session_rows_ordered_by_id(self, AuditLog, tmp_db):
        # [P1] [C5 — Ordering contract] [POSITIVE]
        sid = f"get-rows-order-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=5)

        rows = log.get_session_rows(sid)
        ids = [r["id"] for r in rows]
        assert ids == sorted(ids), \
            f"Rows must be ordered by id ascending, got {ids}"


# ===========================================================================
# TestSessionSummaryEdgeCases
# ===========================================================================

class TestSessionSummaryEdgeCases:
    """Edge cases for AuditLog.session_summary(). [C6, C15]"""

    def test_session_summary_empty_session_returns_zero_counts(self, AuditLog, tmp_db):
        # [P1] [C6 — Error contract] [NEGATIVE]
        log = _make_log(AuditLog, tmp_db)
        summary = log.session_summary("nonexistent-session-summary-xyz")
        assert summary["action_count"] == 0, \
            f"Empty session action_count must be 0, got {summary['action_count']}"
        assert summary["count"] == 0, \
            f"Empty session count alias must be 0, got {summary['count']}"
        assert summary["total_cost_cents"] == 0, \
            f"Empty session total_cost_cents must be 0, got {summary['total_cost_cents']}"
        assert summary["errors"] == 0, \
            f"Empty session errors must be 0, got {summary['errors']}"
        assert summary["start_ts"] is None, \
            f"Empty session start_ts must be None, got {summary['start_ts']}"
        assert summary["end_ts"] is None, \
            f"Empty session end_ts must be None, got {summary['end_ts']}"
        assert summary["tools_used"] == [], \
            f"Empty session tools_used must be [], got {summary['tools_used']}"

    def test_session_summary_action_count_and_count_alias_match(self, AuditLog, tmp_db):
        # [P1] [C15 — Data shape contract] [POSITIVE]
        sid = f"summary-alias-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=4)

        summary = log.session_summary(sid)
        assert summary["action_count"] == summary["count"], \
            f"action_count ({summary['action_count']}) and count ({summary['count']}) must be equal"
        assert summary["action_count"] == 4, \
            f"Expected action_count=4, got {summary['action_count']}"

    def test_session_summary_error_rows_counted_correctly(self, AuditLog, tmp_db):
        # [P1] [C6 — Error contract] [NEGATIVE]
        sid = f"summary-errors-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        log.log(session_id=sid, action_type="tool_call", tool_name="browser.navigate",
                inputs={}, outputs={}, error="")
        log.log(session_id=sid, action_type="tool_call", tool_name="browser.click",
                inputs={}, outputs={}, error="Element not found")
        log.log(session_id=sid, action_type="tool_call", tool_name="browser.type",
                inputs={}, outputs={}, error="Timeout")

        summary = log.session_summary(sid)
        assert summary["errors"] == 2, \
            f"Expected 2 error rows, got {summary['errors']}"
        assert summary["action_count"] == 3, \
            f"Expected action_count=3, got {summary['action_count']}"

    def test_session_summary_tools_used_is_sorted_and_unique(self, AuditLog, tmp_db):
        # [P1] [C6 — Data shape contract] [POSITIVE]
        sid = f"summary-tools-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        for tool in ["browser.navigate", "browser.click", "browser.navigate"]:
            log.log(session_id=sid, action_type="tool_call", tool_name=tool,
                    inputs={}, outputs={})

        summary = log.session_summary(sid)
        tools = summary["tools_used"]
        assert sorted(set(tools)) == tools, \
            f"tools_used must be sorted and unique, got {tools}"
        assert "browser.navigate" in tools, "browser.navigate must appear in tools_used"
        assert "browser.click" in tools, "browser.click must appear in tools_used"
        assert tools.count("browser.navigate") == 1, \
            "browser.navigate must appear exactly once even though logged twice"


# ===========================================================================
# TestArchiveOldRows
# ===========================================================================

class TestArchiveOldRows:
    """Unit tests for AuditLog.archive_old_rows(). [C7]"""

    def test_archive_returns_zero_when_no_rows_qualify(self, AuditLog, tmp_db):
        # [P2] [C7 — Interface contract] [NEGATIVE]
        sid = f"archive-none-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=2)

        result = log.archive_old_rows(days_older_than=30)
        assert result == {"archived_rows": 0}, \
            f"Fresh rows must not be archived, got {result!r}"

    def test_archive_moves_old_rows_and_creates_gz_file(self, AuditLog, tmp_db, tmp_path):
        # [P2] [C7 — State contract] [POSITIVE]
        sid = f"archive-old-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=3)

        old_ts = time.time() - 60 * 86400
        conn = sqlite3.connect(str(tmp_db))
        conn.execute("UPDATE audit_log SET timestamp = ? WHERE session_id = ?", (old_ts, sid))
        conn.commit()
        conn.close()

        archive_dir = str(tmp_path / "archive")
        result = log.archive_old_rows(days_older_than=30, archive_dir=archive_dir)

        assert result["archived_rows"] >= 3, \
            f"Expected >= 3 archived rows, got {result['archived_rows']}"
        assert "archive_path" in result, \
            f"Result must contain 'archive_path', got {result!r}"

        archive_path = Path(result["archive_path"])
        assert archive_path.exists(), \
            f"Archive file must exist at {archive_path}"
        assert archive_path.suffix == ".gz", \
            f"Archive must be a .gz file, got suffix {archive_path.suffix!r}"

    def test_archive_deletes_rows_from_live_table(self, AuditLog, tmp_db, tmp_path):
        # [P2] [C7 — State contract] [NEGATIVE] — rows must not remain after archive
        sid = f"archive-delete-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=2)

        old_ts = time.time() - 60 * 86400
        conn = sqlite3.connect(str(tmp_db))
        conn.execute("UPDATE audit_log SET timestamp = ? WHERE session_id = ?", (old_ts, sid))
        conn.commit()
        conn.close()

        archive_dir = str(tmp_path / "archive_delete")
        log.archive_old_rows(days_older_than=30, archive_dir=archive_dir)

        remaining = log.get_session_rows(sid)
        assert remaining == [], \
            f"Archived rows must be deleted from live table, got {len(remaining)} remaining"

    def test_archive_gz_file_contains_valid_jsonl(self, AuditLog, tmp_db, tmp_path):
        # [P2] [C7 — Data shape contract] [POSITIVE]
        sid = f"archive-jsonl-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=2)

        old_ts = time.time() - 60 * 86400
        conn = sqlite3.connect(str(tmp_db))
        conn.execute("UPDATE audit_log SET timestamp = ? WHERE session_id = ?", (old_ts, sid))
        conn.commit()
        conn.close()

        archive_dir = str(tmp_path / "archive_jsonl")
        result = log.archive_old_rows(days_older_than=30, archive_dir=archive_dir)
        archive_path = result["archive_path"]

        with gzip.open(archive_path, "rt", encoding="utf-8") as fh:
            lines = [l.strip() for l in fh if l.strip()]

        assert len(lines) >= 2, \
            f"Expected >= 2 JSONL lines in archive, got {len(lines)}"
        for i, line in enumerate(lines):
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise AssertionError(f"Archive line {i} is not valid JSON: {exc}")


# ===========================================================================
# TestSchemaMigrationIdempotency
# ===========================================================================

class TestSchemaMigrationIdempotency:
    """Schema migration must be idempotent on existing v2 databases. [C8]"""

    def test_connect_twice_on_same_db_does_not_raise(self, AuditLog, tmp_db):
        # [P0] [C8 — Idempotency contract] [POSITIVE]
        log = AuditLog(db_path=tmp_db)
        log.connect()
        try:
            log.connect()
        except Exception as exc:
            raise AssertionError(
                f"Second connect() on existing v2 db raised {type(exc).__name__}: {exc}"
            )

    def test_connect_on_fresh_db_creates_v2_schema_columns(self, tmp_path, AuditLog):
        # [P0] [C8 — State contract] [POSITIVE]
        fresh_db = tmp_path / "fresh_test.db"
        log = AuditLog(db_path=fresh_db)
        log.connect()

        conn = sqlite3.connect(str(fresh_db))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)")}
        conn.close()

        assert "schema_version" in cols, \
            f"schema_version column must exist after connect(), got columns: {cols}"
        assert "inputs_digest" in cols, \
            f"inputs_digest column must exist after connect(), got columns: {cols}"
        assert "outputs_digest" in cols, \
            f"outputs_digest column must exist after connect(), got columns: {cols}"


# ===========================================================================
# TestReceiptWriterGenerate
# ===========================================================================

class TestReceiptWriterGenerate:
    """Unit tests for ReceiptWriter.generate(). [C9, C10, C13]"""

    def test_generate_returns_receipt_with_correct_total_cents(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P0] [C9 — Interface contract] [POSITIVE]
        sid = f"receipt-total-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        log.log(session_id=sid, action_type="tool_call", tool_name="browser.navigate",
                inputs={}, outputs={}, cost_cents=3)
        log.log(session_id=sid, action_type="tool_call", tool_name="browser.click",
                inputs={}, outputs={}, cost_cents=5)

        writer = ReceiptWriter()
        receipt = writer.generate(sid, log)

        assert receipt.total_cents == 8, \
            f"Expected total_cents=8 (3+5), got {receipt.total_cents}"

    def test_generate_returns_correct_action_count(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P0] [C9 — Data shape contract] [POSITIVE]
        sid = f"receipt-count-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=4)

        writer = ReceiptWriter()
        receipt = writer.generate(sid, log)

        assert len(receipt.actions) == 4, \
            f"Expected 4 ReceiptLines, got {len(receipt.actions)}"

    def test_generate_signed_hash_is_64_char_hex(self, AuditLog, ReceiptWriter, tmp_db):
        # [P0] [C9 — Data shape contract] [POSITIVE]
        sid = f"receipt-hash-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=2)

        writer = ReceiptWriter()
        receipt = writer.generate(sid, log)

        assert len(receipt.signed_hash) == 64, \
            f"Expected 64-char signed_hash, got len={len(receipt.signed_hash)}"
        assert all(c in "0123456789abcdef" for c in receipt.signed_hash), \
            f"signed_hash must be lowercase hex, got {receipt.signed_hash!r}"

    def test_generate_empty_session_returns_zero_total_and_empty_hash(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C10 — Error contract] [NEGATIVE]
        log = _make_log(AuditLog, tmp_db)
        writer = ReceiptWriter()
        receipt = writer.generate("nonexistent-receipt-session-xyz", log)

        assert receipt.total_cents == 0, \
            f"Empty session must have total_cents=0, got {receipt.total_cents}"
        assert receipt.signed_hash == "", \
            f"Empty session must have signed_hash='', got {receipt.signed_hash!r}"
        assert receipt.actions == [], \
            f"Empty session must have no actions, got {receipt.actions!r}"
        assert receipt.start_ts is None, \
            f"Empty session must have start_ts=None, got {receipt.start_ts}"

    def test_generate_error_count_reflects_rows_with_error_field(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C13 — Error contract] [NEGATIVE]
        sid = f"receipt-errors-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        log.log(session_id=sid, action_type="tool_call", tool_name="browser.navigate",
                inputs={}, outputs={}, error="")
        log.log(session_id=sid, action_type="tool_call", tool_name="browser.click",
                inputs={}, outputs={}, error="Timeout")
        log.log(session_id=sid, action_type="tool_call", tool_name="browser.type",
                inputs={}, outputs={}, error="Not found")

        writer = ReceiptWriter()
        receipt = writer.generate(sid, log)

        assert receipt.error_count == 2, \
            f"Expected error_count=2, got {receipt.error_count}"

    def test_generate_receipt_lines_indexed_from_one(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C9 — Data shape contract] [POSITIVE]
        sid = f"receipt-index-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=3)

        writer = ReceiptWriter()
        receipt = writer.generate(sid, log)

        indices = [a.index for a in receipt.actions]
        assert indices == [1, 2, 3], \
            f"ReceiptLine indices must start at 1 and increment, got {indices}"

    def test_generate_start_ts_is_min_and_end_ts_is_max(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C9 — State contract] [POSITIVE]
        sid = f"receipt-ts-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=3)

        rows = log.get_session_rows(sid)
        ts_values = [r["timestamp"] for r in rows]

        writer = ReceiptWriter()
        receipt = writer.generate(sid, log)

        assert receipt.start_ts == min(ts_values), \
            f"start_ts must be min timestamp, expected {min(ts_values)}, got {receipt.start_ts}"
        assert receipt.end_ts == max(ts_values), \
            f"end_ts must be max timestamp, expected {max(ts_values)}, got {receipt.end_ts}"

    def test_generate_signed_hash_changes_when_rows_differ(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P0] [C9 — Idempotency contract] [NEGATIVE]
        sid_a = f"receipt-hash-a-{uuid.uuid4().hex[:8]}"
        sid_b = f"receipt-hash-b-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid_a, n=2)
        _populate_session(log, sid_b, n=3)

        writer = ReceiptWriter()
        receipt_a = writer.generate(sid_a, log)
        receipt_b = writer.generate(sid_b, log)

        assert receipt_a.signed_hash != receipt_b.signed_hash, \
            "Different sessions must produce different signed_hash values"


# ===========================================================================
# TestReceiptWriterExportText
# ===========================================================================

class TestReceiptWriterExportText:
    """Unit tests for ReceiptWriter.export_text(). [C11]"""

    def _make_receipt(self, AuditLog, ReceiptWriter, tmp_db):
        sid = f"export-text-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=2)
        writer = ReceiptWriter()
        return writer.generate(sid, log), sid, writer

    def test_export_text_contains_session_id(self, AuditLog, ReceiptWriter, tmp_db):
        # [P1] [C11 — Data shape contract] [POSITIVE]
        receipt, sid, writer = self._make_receipt(AuditLog, ReceiptWriter, tmp_db)
        text = writer.export_text(receipt)
        assert sid in text, \
            f"export_text() must include session ID '{sid}', got text[:200]={text[:200]!r}"

    def test_export_text_contains_banner_dividers(self, AuditLog, ReceiptWriter, tmp_db):
        # [P1] [C11 — Data shape contract] [POSITIVE]
        receipt, sid, writer = self._make_receipt(AuditLog, ReceiptWriter, tmp_db)
        text = writer.export_text(receipt)
        assert "=" * 64 in text, \
            "export_text() must contain 64-char banner dividers"

    def test_export_text_contains_total_cost_line(self, AuditLog, ReceiptWriter, tmp_db):
        # [P1] [C11 — Data shape contract] [POSITIVE]
        receipt, sid, writer = self._make_receipt(AuditLog, ReceiptWriter, tmp_db)
        text = writer.export_text(receipt)
        assert "Total:" in text, \
            f"export_text() must contain 'Total:' cost summary line, got text[-200:]={text[-200:]!r}"

    def test_export_text_contains_signed_hash_prefix(self, AuditLog, ReceiptWriter, tmp_db):
        # [P1] [C11 — Data shape contract] [POSITIVE]
        receipt, sid, writer = self._make_receipt(AuditLog, ReceiptWriter, tmp_db)
        text = writer.export_text(receipt)
        assert "Signed:" in text, \
            f"export_text() must contain 'Signed:' line, got text[-200:]={text[-200:]!r}"

    def test_export_text_empty_receipt_shows_no_actions_message(
        self, receipt_mod, ReceiptWriter
    ):
        # [P1] [C11 — Error contract] [NEGATIVE]
        Receipt = receipt_mod.Receipt
        empty_receipt = Receipt(session_id="empty-text-receipt")
        writer = ReceiptWriter()
        text = writer.export_text(empty_receipt)
        assert "no actions" in text.lower(), \
            f"Empty receipt must show 'no actions' message, got {text!r}"

    def test_export_text_error_rows_show_err_prefix(self, AuditLog, ReceiptWriter, tmp_db):
        # [P1] [C11 — Data shape contract] [NEGATIVE]
        sid = f"export-text-err-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        log.log(session_id=sid, action_type="tool_call", tool_name="browser.click",
                inputs={}, outputs={}, error="Element not found")

        writer = ReceiptWriter()
        receipt = writer.generate(sid, log)
        text = writer.export_text(receipt)
        assert "ERR:" in text, \
            f"Error rows must show 'ERR:' prefix in export_text(), got text={text!r}"


# ===========================================================================
# TestReceiptWriterExportJsonl
# ===========================================================================

class TestReceiptWriterExportJsonl:
    """Unit tests for ReceiptWriter.export_jsonl(). [C12]"""

    def _make_receipt_and_jsonl(self, AuditLog, ReceiptWriter, tmp_db, n=3):
        sid = f"export-jsonl-receipt-{uuid.uuid4().hex[:8]}"
        log = _make_log(AuditLog, tmp_db)
        _populate_session(log, sid, n=n)
        writer = ReceiptWriter()
        receipt = writer.generate(sid, log)
        return writer.export_jsonl(receipt), receipt

    def test_export_jsonl_first_line_is_session_header(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C12 — Data shape contract] [POSITIVE]
        output, _ = self._make_receipt_and_jsonl(AuditLog, ReceiptWriter, tmp_db)
        lines = [l for l in output.strip().split("\n") if l]
        header = json.loads(lines[0])
        assert header["type"] == "session_header", \
            f"First JSONL line must have type='session_header', got {header.get('type')!r}"
        assert "session_id" in header, \
            f"session_header must contain 'session_id', got keys: {list(header.keys())}"

    def test_export_jsonl_action_lines_have_correct_type(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C12 — Data shape contract] [POSITIVE]
        output, receipt = self._make_receipt_and_jsonl(AuditLog, ReceiptWriter, tmp_db, n=3)
        lines = [json.loads(l) for l in output.strip().split("\n") if l]
        action_lines = [l for l in lines if l["type"] == "action"]
        assert len(action_lines) == 3, \
            f"Expected 3 action lines, got {len(action_lines)}"

    def test_export_jsonl_last_line_is_session_summary(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C12 — Data shape contract] [POSITIVE]
        output, _ = self._make_receipt_and_jsonl(AuditLog, ReceiptWriter, tmp_db)
        lines = [l for l in output.strip().split("\n") if l]
        summary = json.loads(lines[-1])
        assert summary["type"] == "session_summary", \
            f"Last JSONL line must have type='session_summary', got {summary.get('type')!r}"
        assert "signed_hash" in summary, \
            f"session_summary must contain 'signed_hash', got keys: {list(summary.keys())}"

    def test_export_jsonl_summary_total_cents_matches_receipt(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C12 — Data shape contract] [POSITIVE]
        output, receipt = self._make_receipt_and_jsonl(AuditLog, ReceiptWriter, tmp_db)
        lines = [l for l in output.strip().split("\n") if l]
        summary = json.loads(lines[-1])
        assert summary["total_cents"] == receipt.total_cents, \
            (f"JSONL summary total_cents ({summary['total_cents']}) must match "
             f"receipt.total_cents ({receipt.total_cents})")

    def test_export_jsonl_summary_signed_hash_matches_receipt(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C12 — Data shape contract] [POSITIVE]
        output, receipt = self._make_receipt_and_jsonl(AuditLog, ReceiptWriter, tmp_db)
        lines = [l for l in output.strip().split("\n") if l]
        summary = json.loads(lines[-1])
        assert summary["signed_hash"] == receipt.signed_hash, \
            (f"JSONL summary signed_hash must match receipt.signed_hash. "
             f"Got {summary['signed_hash']!r} vs {receipt.signed_hash!r}")

    def test_export_jsonl_all_lines_are_valid_json(
        self, AuditLog, ReceiptWriter, tmp_db
    ):
        # [P1] [C12 — Data shape contract] [POSITIVE]
        output, _ = self._make_receipt_and_jsonl(AuditLog, ReceiptWriter, tmp_db)
        for i, line in enumerate(output.strip().split("\n")):
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"JSONL line {i} is not valid JSON: {exc}\n  line={line!r}"
                )

    def test_export_jsonl_empty_receipt_has_header_and_summary_only(
        self, receipt_mod, ReceiptWriter
    ):
        # [P1] [C12 — Error contract] [NEGATIVE]
        Receipt = receipt_mod.Receipt
        empty = Receipt(session_id="empty-jsonl-receipt")
        writer = ReceiptWriter()
        output = writer.export_jsonl(empty)
        lines = [json.loads(l) for l in output.strip().split("\n") if l]
        types = [l["type"] for l in lines]
        assert "session_header" in types, \
            f"Empty receipt JSONL must have session_header, got types: {types}"
        assert "session_summary" in types, \
            f"Empty receipt JSONL must have session_summary, got types: {types}"
        action_lines = [l for l in lines if l["type"] == "action"]
        assert action_lines == [], \
            f"Empty receipt JSONL must have no action lines, got {action_lines!r}"
