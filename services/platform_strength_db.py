from __future__ import annotations

from threading import RLock
from typing import Any

from sqlalchemy import text

from shiyou_db.database import build_engine_from_url

_SCHEMA_ENSURE_LOCK = RLock()
_SCHEMA_ENSURED: set[tuple[int, str]] = set()


def _schema_cache_key(conn, schema_key: str) -> tuple[int, str]:
    return (id(conn.engine), schema_key)


def _schema_already_ensured(conn, schema_key: str) -> bool:
    with _SCHEMA_ENSURE_LOCK:
        return _schema_cache_key(conn, schema_key) in _SCHEMA_ENSURED


def _mark_schema_ensured(conn, schema_key: str) -> None:
    with _SCHEMA_ENSURE_LOCK:
        _SCHEMA_ENSURED.add(_schema_cache_key(conn, schema_key))


def _clear_strength_schema_ensure_cache_for_tests() -> None:
    with _SCHEMA_ENSURE_LOCK:
        _SCHEMA_ENSURED.clear()


def _engine(mysql_url: str):
    if not mysql_url:
        raise ValueError("MYSQL_URL 未配置，无法更新数据库。")
    return build_engine_from_url(mysql_url)


def _ensure_strength_custom_tables(conn) -> None:
    schema_key = "strength_custom_tables"
    if _schema_already_ensured(conn, schema_key):
        return

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS platform_strength_structure_model_info (
            profile_id BIGINT NOT NULL,
            facility_code VARCHAR(128) NOT NULL,
            mud_level_m DOUBLE NULL,
            workpoint_m DOUBLE NULL,
            level_threshold INT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (profile_id, facility_code)
        )
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS platform_strength_horizontal_level_items (
            profile_id BIGINT NOT NULL,
            facility_code VARCHAR(128) NOT NULL,
            sort_order INT NOT NULL,
            z_m DOUBLE NULL,
            node_count INT NULL,
            selected TINYINT DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (profile_id, facility_code, sort_order)
        )
    """))
    _mark_schema_ensured(conn, schema_key)


def load_structure_model_info(
    mysql_url: str,
    *,
    profile_id: int,
    facility_code: str,
) -> dict[str, Any] | None:
    engine = _engine(mysql_url)
    with engine.begin() as conn:
        _ensure_strength_custom_tables(conn)
        row = conn.execute(text("""
            SELECT mud_level_m, workpoint_m, level_threshold
            FROM platform_strength_structure_model_info
            WHERE profile_id=:profile_id AND facility_code=:facility_code
            LIMIT 1
        """), {"profile_id": profile_id, "facility_code": facility_code}).mappings().first()
    return dict(row) if row else None


def save_structure_model_info(
    mysql_url: str,
    *,
    profile_id: int,
    facility_code: str,
    mud_level_m: float | None,
    workpoint_m: float | None,
    level_threshold: int,
) -> None:
    engine = _engine(mysql_url)
    with engine.begin() as conn:
        _ensure_strength_custom_tables(conn)
        conn.execute(text("""
            DELETE FROM platform_strength_structure_model_info
            WHERE profile_id=:profile_id AND facility_code=:facility_code
        """), {"profile_id": profile_id, "facility_code": facility_code})
        conn.execute(text("""
            INSERT INTO platform_strength_structure_model_info
                (profile_id, facility_code, mud_level_m, workpoint_m, level_threshold)
            VALUES
                (:profile_id, :facility_code, :mud_level_m, :workpoint_m, :level_threshold)
        """), {
            "profile_id": profile_id,
            "facility_code": facility_code,
            "mud_level_m": mud_level_m,
            "workpoint_m": workpoint_m,
            "level_threshold": int(level_threshold or 40),
        })


def load_horizontal_levels(
    mysql_url: str,
    *,
    profile_id: int,
    facility_code: str,
) -> list[dict[str, Any]]:
    engine = _engine(mysql_url)
    with engine.begin() as conn:
        _ensure_strength_custom_tables(conn)
        rows = conn.execute(text("""
            SELECT z_m, node_count, selected
            FROM platform_strength_horizontal_level_items
            WHERE profile_id=:profile_id AND facility_code=:facility_code
            ORDER BY sort_order ASC
        """), {"profile_id": profile_id, "facility_code": facility_code}).mappings().all()
    return [dict(row) for row in rows]


def save_horizontal_levels(
    mysql_url: str,
    *,
    profile_id: int,
    facility_code: str,
    levels: list[tuple[float, int, bool]],
    level_threshold: int,
    mud_level_m: float | None,
    workpoint_m: float | None,
) -> None:
    engine = _engine(mysql_url)
    with engine.begin() as conn:
        _ensure_strength_custom_tables(conn)
        conn.execute(text("""
            DELETE FROM platform_strength_horizontal_level_items
            WHERE profile_id=:profile_id AND facility_code=:facility_code
        """), {"profile_id": profile_id, "facility_code": facility_code})
        for idx, (z, occ, selected) in enumerate(levels, start=1):
            conn.execute(text("""
                INSERT INTO platform_strength_horizontal_level_items
                    (profile_id, facility_code, sort_order, z_m, node_count, selected)
                VALUES
                    (:profile_id, :facility_code, :sort_order, :z_m, :node_count, :selected)
            """), {
                "profile_id": profile_id,
                "facility_code": facility_code,
                "sort_order": idx,
                "z_m": float(z),
                "node_count": int(occ or 0),
                "selected": 1 if selected else 0,
            })

        conn.execute(text("""
            DELETE FROM platform_strength_structure_model_info
            WHERE profile_id=:profile_id AND facility_code=:facility_code
        """), {"profile_id": profile_id, "facility_code": facility_code})
        conn.execute(text("""
            INSERT INTO platform_strength_structure_model_info
                (profile_id, facility_code, mud_level_m, workpoint_m, level_threshold)
            VALUES
                (:profile_id, :facility_code, :mud_level_m, :workpoint_m, :level_threshold)
        """), {
            "profile_id": profile_id,
            "facility_code": facility_code,
            "mud_level_m": mud_level_m,
            "workpoint_m": workpoint_m,
            "level_threshold": int(level_threshold or 40),
        })
