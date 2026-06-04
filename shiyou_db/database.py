from __future__ import annotations

from threading import RLock

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import AppSettings, DatabasePoolSettings, load_settings

Base = declarative_base()

_ENGINE_CACHE: dict[tuple[str, bool, tuple[int, int, int, int, int] | None], object] = {}
_ENGINE_CACHE_LOCK = RLock()


def _clear_engine_cache_for_tests() -> None:
    with _ENGINE_CACHE_LOCK:
        engines = list(_ENGINE_CACHE.values())
        _ENGINE_CACHE.clear()

    for engine in engines:
        engine.dispose()


def _is_sqlite_url(sqlalchemy_url: str) -> bool:
    return str(sqlalchemy_url).lower().startswith("sqlite")


def _resolve_pool_settings(pool: DatabasePoolSettings | None) -> DatabasePoolSettings:
    if pool is not None:
        return pool
    try:
        return load_settings().pool
    except Exception:
        return DatabasePoolSettings()


def _build_engine_kwargs(
    sqlalchemy_url: str,
    *,
    echo: bool = False,
    pool: DatabasePoolSettings | None = None,
) -> dict:
    kwargs = {
        "echo": echo,
        "future": True,
        "pool_pre_ping": True,
    }
    if _is_sqlite_url(sqlalchemy_url):
        return kwargs

    pool_settings = _resolve_pool_settings(pool)
    kwargs.update(
        pool_size=pool_settings.pool_size,
        max_overflow=pool_settings.max_overflow,
        pool_recycle=pool_settings.pool_recycle,
        pool_timeout=pool_settings.pool_timeout,
    )

    if str(sqlalchemy_url).lower().startswith("mysql"):
        kwargs["connect_args"] = {"connect_timeout": pool_settings.connect_timeout}

    return kwargs


def _engine_create_kwargs(sqlalchemy_url: str, *, echo: bool) -> dict:
    return _build_engine_kwargs(sqlalchemy_url, echo=echo)


def _pool_cache_key(pool: DatabasePoolSettings | None) -> tuple[int, int, int, int, int] | None:
    if pool is None:
        return None
    return (
        pool.pool_size,
        pool.max_overflow,
        pool.pool_recycle,
        pool.pool_timeout,
        pool.connect_timeout,
    )


def _get_or_create_engine(
    sqlalchemy_url: str,
    *,
    echo: bool = False,
    pool: DatabasePoolSettings | None = None,
):
    cache_key = (sqlalchemy_url, bool(echo), _pool_cache_key(pool))
    with _ENGINE_CACHE_LOCK:
        engine = _ENGINE_CACHE.get(cache_key)
        if engine is not None:
            return engine

        engine = create_engine(sqlalchemy_url, **_build_engine_kwargs(sqlalchemy_url, echo=echo, pool=pool))
        _ENGINE_CACHE[cache_key] = engine
        return engine


def build_engine(settings: AppSettings):
    return _get_or_create_engine(
        settings.database.sqlalchemy_url,
        echo=settings.echo_sql,
        pool=settings.pool,
    )


def build_engine_from_url(
    sqlalchemy_url: str,
    *,
    echo: bool = False,
    pool: DatabasePoolSettings | None = None,
):
    return _get_or_create_engine(sqlalchemy_url, echo=echo, pool=pool)


def build_session_factory(settings: AppSettings):
    engine = build_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
