from __future__ import annotations

import json

import pytest

from services.special_strategy_state_db import _create_index_if_missing
import services.special_strategy_state_db as state_db


class _ScalarResult:
    def __init__(self, value: int):
        self._value = value

    def scalar(self) -> int:
        return self._value


class _RecordingConn:
    def __init__(self, existing_count: int):
        self.existing_count = existing_count
        self.calls: list[tuple[str, dict | None]] = []

    def execute(self, statement, params: dict | None = None):
        sql = " ".join(str(statement).split())
        self.calls.append((sql, params))
        if "information_schema.statistics" in sql:
            return _ScalarResult(self.existing_count)
        return _ScalarResult(0)


def test_create_index_if_missing_uses_mysql_compatible_check_then_create():
    conn = _RecordingConn(existing_count=0)

    _create_index_if_missing(
        conn,
        table_name="special_strategy_risk_images",
        index_name="ix_ss_risk_images_facility",
        columns=("facility_code",),
    )

    assert len(conn.calls) == 2
    assert "information_schema.statistics" in conn.calls[0][0]
    assert conn.calls[0][1] == {
        "table_name": "special_strategy_risk_images",
        "index_name": "ix_ss_risk_images_facility",
    }
    assert conn.calls[1][0] == (
        "CREATE INDEX ix_ss_risk_images_facility "
        "ON special_strategy_risk_images (facility_code)"
    )
    assert "IF NOT EXISTS" not in conn.calls[1][0]


def test_create_index_if_missing_skips_existing_index():
    conn = _RecordingConn(existing_count=1)

    _create_index_if_missing(
        conn,
        table_name="special_strategy_runs",
        index_name="ix_special_strategy_runs_facility",
        columns=("facility_code",),
    )

    assert len(conn.calls) == 1
    assert "information_schema.statistics" in conn.calls[0][0]


def test_create_index_if_missing_rejects_unsafe_identifier():
    conn = _RecordingConn(existing_count=0)

    with pytest.raises(ValueError):
        _create_index_if_missing(
            conn,
            table_name="special_strategy_runs; DROP TABLE x",
            index_name="ix_bad",
            columns=("facility_code",),
        )


class _MappingResult:
    def __init__(self, row: dict | None):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _ValueResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _SnapshotConn:
    def __init__(self, result_json_text: str):
        self.result_json_text = result_json_text
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params: dict | None = None):
        sql = " ".join(str(statement).split())
        self.calls.append(sql)
        if "SELECT * FROM special_strategy_result_snapshots" in sql:
            raise RuntimeError("Out of memory")
        if "CHAR_LENGTH(result_json)" in sql:
            return _ValueResult(len(self.result_json_text))
        if "SUBSTRING(result_json" in sql:
            start = int((params or {}).get("start_pos", 1)) - 1
            chunk_size = int((params or {}).get("chunk_size", 0))
            return _ValueResult(self.result_json_text[start:start + chunk_size])
        if "FROM special_strategy_result_snapshots" in sql and "WHERE run_id" in sql:
            return _MappingResult(
                {
                    "id": 7,
                    "run_id": 129,
                    "facility_code": "WC19-1D",
                    "created_at": "2026-06-17 10:00:00",
                    "updated_at": "2026-06-17 10:00:00",
                }
            )
        raise AssertionError(f"unexpected SQL: {sql}")


class _SnapshotEngine:
    def __init__(self, conn: _SnapshotConn):
        self.conn = conn

    def connect(self):
        return self.conn


def test_load_result_snapshot_by_run_reads_large_json_in_chunks(monkeypatch):
    result_payload = {"context": {"platform_name": "WC19-1D"}, "member_risk_rows_full": [{"JointA": "A001"}]}
    result_json_text = json.dumps(result_payload, ensure_ascii=False)
    conn = _SnapshotConn(result_json_text)

    monkeypatch.setattr(state_db, "is_strategy_state_db_configured", lambda _config_path=None: True)
    monkeypatch.setattr(state_db, "ensure_strategy_result_table", lambda _config_path=None: None)
    monkeypatch.setattr(state_db, "_get_engine", lambda _config_path=None: _SnapshotEngine(conn))

    snapshot = state_db.load_strategy_result_snapshot_by_run(129)

    assert snapshot["id"] == 7
    assert snapshot["run_id"] == 129
    assert snapshot["result_json"] == result_payload
    assert all("SELECT * FROM special_strategy_result_snapshots" not in sql for sql in conn.calls)
    assert any("SUBSTRING(result_json" in sql for sql in conn.calls)
