from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import AppSettings

Base = declarative_base()


def build_engine(settings: AppSettings):
    return create_engine(
        settings.database.sqlalchemy_url,
        echo=settings.echo_sql,
        future=True,
        pool_pre_ping=True,
    )


def build_session_factory(settings: AppSettings):
    engine = build_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
