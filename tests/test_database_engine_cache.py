from __future__ import annotations

from shiyou_db.config import DatabasePoolSettings
from shiyou_db.database import _clear_engine_cache_for_tests
from shiyou_db.database import _build_engine_kwargs
from shiyou_db.database import build_engine_from_url


def test_build_engine_from_url_reuses_engine_for_same_url_and_echo():
    try:
        first = build_engine_from_url("sqlite:///:memory:")
        second = build_engine_from_url("sqlite:///:memory:")
        with_echo = build_engine_from_url("sqlite:///:memory:", echo=True)

        assert first is second
        assert first is not with_echo
    finally:
        _clear_engine_cache_for_tests()


def test_mysql_engine_kwargs_keep_pool_pre_ping_and_configured_pool_limits():
    kwargs = _build_engine_kwargs(
        "mysql+pymysql://db_user:secret_password@10.177.19.121:3306/shiyou?charset=utf8mb4",
        echo=False,
        pool=DatabasePoolSettings(
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
            pool_timeout=10,
            connect_timeout=7,
        ),
    )

    assert kwargs["future"] is True
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_recycle"] == 1800
    assert kwargs["pool_timeout"] == 10
    assert kwargs["connect_args"] == {"connect_timeout": 7}
