from __future__ import annotations

import pytest

from services.special_strategy_state_db import _create_index_if_missing


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
