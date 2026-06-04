from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import AppSettings, DatabasePoolSettings, load_settings

Base = declarative_base()


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


def build_engine(settings: AppSettings):
    sqlalchemy_url = settings.database.sqlalchemy_url
    return create_engine(
        sqlalchemy_url,
        **_build_engine_kwargs(sqlalchemy_url, echo=settings.echo_sql, pool=settings.pool),
    )


def build_engine_from_url(
    sqlalchemy_url: str,
    *,
    echo: bool = False,
    pool: DatabasePoolSettings | None = None,
):
    return create_engine(
        sqlalchemy_url,
        **_build_engine_kwargs(sqlalchemy_url, echo=echo, pool=pool),
    )


def build_session_factory(settings: AppSettings):
    engine = build_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
