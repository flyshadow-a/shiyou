from __future__ import annotations

import pytest

from pages.sacs_import_service import _clear_sacs_schema_ensure_cache_for_tests
from pages.sacs_import_service import ensure_dummy_table
from pages.sacs_import_service import ensure_model_tables
from services.feasibility_assessment_db import _clear_feasibility_schema_ensure_cache_for_tests
from services.feasibility_assessment_db import _ensure_input_tables
from services.platform_strength_db import _clear_strength_schema_ensure_cache_for_tests
from services.platform_strength_db import _ensure_strength_custom_tables


class _BeginContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, conn):
        self.conn = conn

    def begin(self):
        self.conn.engine = self
        return _BeginContext(self.conn)


class _RecordingConn:
    def __init__(self, *, fail_once: bool = False):
        self.engine = object()
        self.fail_once = fail_once
        self.calls: list[str] = []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.calls.append(sql)
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("ddl failed")
        return None


def test_sacs_model_tables_are_checked_once_per_engine():
    conn = _RecordingConn()
    engine = _FakeEngine(conn)

    try:
        ensure_model_tables(engine)
        first_count = len(conn.calls)
        ensure_model_tables(engine)

        assert first_count == 8
        assert len(conn.calls) == first_count
    finally:
        _clear_sacs_schema_ensure_cache_for_tests()


def test_sacs_dummy_table_failure_is_not_cached():
    conn = _RecordingConn(fail_once=True)
    engine = _FakeEngine(conn)

    try:
        with pytest.raises(RuntimeError):
            ensure_dummy_table(engine)
        ensure_dummy_table(engine)

        assert len(conn.calls) == 2
    finally:
        _clear_sacs_schema_ensure_cache_for_tests()


def test_platform_strength_tables_are_checked_once_per_engine():
    conn = _RecordingConn()

    try:
        _ensure_strength_custom_tables(conn)
        first_count = len(conn.calls)
        _ensure_strength_custom_tables(conn)

        assert first_count == 2
        assert len(conn.calls) == first_count
    finally:
        _clear_strength_schema_ensure_cache_for_tests()


def test_platform_strength_table_failure_is_not_cached():
    conn = _RecordingConn(fail_once=True)

    try:
        with pytest.raises(RuntimeError):
            _ensure_strength_custom_tables(conn)
        _ensure_strength_custom_tables(conn)

        assert len(conn.calls) == 3
    finally:
        _clear_strength_schema_ensure_cache_for_tests()


def test_feasibility_input_tables_are_checked_once_per_engine():
    conn = _RecordingConn()

    try:
        _ensure_input_tables(conn)
        first_count = len(conn.calls)
        _ensure_input_tables(conn)

        assert first_count == 5
        assert len(conn.calls) == first_count
    finally:
        _clear_feasibility_schema_ensure_cache_for_tests()
