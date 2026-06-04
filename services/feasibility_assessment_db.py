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


def _clear_feasibility_schema_ensure_cache_for_tests() -> None:
    with _SCHEMA_ENSURE_LOCK:
        _SCHEMA_ENSURED.clear()


def _engine(mysql_url: str):
    if not mysql_url:
        raise ValueError("MYSQL_URL 未配置，无法更新数据库。")
    return build_engine_from_url(mysql_url)


def _ensure_input_tables(conn) -> None:
    schema_key = "input_tables"
    if _schema_already_ensured(conn, schema_key):
        return

    ddl_list = [
        """
        CREATE TABLE IF NOT EXISTS well_slots (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            slot_no INT NOT NULL,
            x DOUBLE NULL,
            y DOUBLE NULL,
            conductor_od DOUBLE NULL,
            conductor_wt DOUBLE NULL,
            support_od DOUBLE NULL,
            support_wt DOUBLE NULL,
            top_load_fz DOUBLE NULL,
            KEY idx_ws_job_slot (job_name, slot_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS well_slot_connections (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            slot_no INT NOT NULL,
            level_z DOUBLE NULL,
            connection_type VARCHAR(50) NULL,
            KEY idx_wsc_job_slot (job_name, slot_no),
            KEY idx_wsc_job_level (job_name, level_z)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS risers (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            riser_no INT NOT NULL,
            x DOUBLE NULL,
            y DOUBLE NULL,
            riser_od DOUBLE NULL,
            riser_wt DOUBLE NULL,
            support_od DOUBLE NULL,
            support_wt DOUBLE NULL,
            batter_x DOUBLE NULL,
            batter_y DOUBLE NULL,
            KEY idx_risers_job_riser (job_name, riser_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS riser_connections (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            riser_no INT NOT NULL,
            level_z DOUBLE NULL,
            connection_type VARCHAR(50) NULL,
            KEY idx_rc_job_riser (job_name, riser_no),
            KEY idx_rc_job_level (job_name, level_z)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS topside_weights (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            weight_no INT NOT NULL,
            x DOUBLE NULL,
            y DOUBLE NULL,
            z DOUBLE NULL,
            weight_t DOUBLE NULL,
            KEY idx_tw_job_weight (job_name, weight_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
    ]
    for ddl in ddl_list:
        conn.execute(text(ddl))
    _mark_schema_ensured(conn, schema_key)


def replace_well_slots(
    mysql_url: str,
    *,
    job_name: str,
    slot_rows: list[dict[str, Any]],
    connection_rows: list[dict[str, Any]],
) -> None:
    engine = _engine(mysql_url)
    with engine.begin() as conn:
        _ensure_input_tables(conn)
        conn.execute(text("DELETE FROM well_slot_connections WHERE job_name = :job_name"), {"job_name": job_name})
        conn.execute(text("DELETE FROM well_slots WHERE job_name = :job_name"), {"job_name": job_name})

        if slot_rows:
            conn.execute(text("""
                INSERT INTO well_slots (
                    job_name, slot_no, x, y,
                    conductor_od, conductor_wt,
                    support_od, support_wt,
                    top_load_fz
                ) VALUES (
                    :job_name, :slot_no, :x, :y,
                    :conductor_od, :conductor_wt,
                    :support_od, :support_wt,
                    :top_load_fz
                )
            """), slot_rows)

        if connection_rows:
            conn.execute(text("""
                INSERT INTO well_slot_connections (
                    job_name, slot_no, level_z, connection_type
                ) VALUES (
                    :job_name, :slot_no, :level_z, :connection_type
                )
            """), connection_rows)


def replace_risers(
    mysql_url: str,
    *,
    job_name: str,
    riser_rows: list[dict[str, Any]],
    connection_rows: list[dict[str, Any]],
) -> None:
    engine = _engine(mysql_url)
    with engine.begin() as conn:
        _ensure_input_tables(conn)
        conn.execute(text("DELETE FROM riser_connections WHERE job_name = :job_name"), {"job_name": job_name})
        conn.execute(text("DELETE FROM risers WHERE job_name = :job_name"), {"job_name": job_name})

        if riser_rows:
            conn.execute(text("""
                INSERT INTO risers (
                    job_name, riser_no, x, y,
                    riser_od, riser_wt,
                    support_od, support_wt,
                    batter_x, batter_y
                ) VALUES (
                    :job_name, :riser_no, :x, :y,
                    :riser_od, :riser_wt,
                    :support_od, :support_wt,
                    :batter_x, :batter_y
                )
            """), riser_rows)

        if connection_rows:
            conn.execute(text("""
                INSERT INTO riser_connections (
                    job_name, riser_no, level_z, connection_type
                ) VALUES (
                    :job_name, :riser_no, :level_z, :connection_type
                )
            """), connection_rows)


def replace_topside_weights(
    mysql_url: str,
    *,
    job_name: str,
    rows: list[dict[str, Any]],
) -> None:
    engine = _engine(mysql_url)
    with engine.begin() as conn:
        _ensure_input_tables(conn)
        conn.execute(text("DELETE FROM topside_weights WHERE job_name = :job_name"), {"job_name": job_name})
        if rows:
            conn.execute(text("""
                INSERT INTO topside_weights (
                    job_name, weight_no, x, y, z, weight_t
                ) VALUES (
                    :job_name, :weight_no, :x, :y, :z, :weight_t
                )
            """), rows)


def empty_platform_evaluation_statistics() -> dict[str, Any]:
    return {
        "well_slot_count": 0,
        "riser_count": 0,
        "topside_weight_sum_t": 0.0,
        "well_slot_rows": [],
        "riser_rows": [],
        "topside_weight_rows": [],
    }


def load_platform_evaluation_statistics(mysql_url: str, *, job_name: str) -> dict[str, Any]:
    if not mysql_url or not job_name:
        return empty_platform_evaluation_statistics()
    engine = _engine(mysql_url)
    statistics_sql = text("""
        SELECT
            (SELECT COUNT(*) FROM well_slots WHERE job_name = :job_name) AS well_slot_count,
            (SELECT COUNT(*) FROM risers WHERE job_name = :job_name) AS riser_count,
            (SELECT COALESCE(SUM(weight_t), 0) FROM topside_weights WHERE job_name = :job_name) AS topside_weight_sum_t
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(statistics_sql, {"job_name": job_name}).mappings().first() or {}
            well_slot_rows = [
                dict(item)
                for item in conn.execute(text("""
                    SELECT slot_no, x, y, conductor_od, conductor_wt,
                           support_od, support_wt, top_load_fz
                    FROM well_slots
                    WHERE job_name = :job_name
                    ORDER BY slot_no
                """), {"job_name": job_name}).mappings()
            ]
            riser_rows = [
                dict(item)
                for item in conn.execute(text("""
                    SELECT riser_no, x, y, riser_od, riser_wt,
                           support_od, support_wt, batter_x, batter_y
                    FROM risers
                    WHERE job_name = :job_name
                    ORDER BY riser_no
                """), {"job_name": job_name}).mappings()
            ]
            topside_weight_rows = [
                dict(item)
                for item in conn.execute(text("""
                    SELECT weight_no, x, y, z, weight_t
                    FROM topside_weights
                    WHERE job_name = :job_name
                    ORDER BY weight_no
                """), {"job_name": job_name}).mappings()
            ]
    except Exception:
        return empty_platform_evaluation_statistics()

    return {
        "well_slot_count": int(row.get("well_slot_count") or 0),
        "riser_count": int(row.get("riser_count") or 0),
        "topside_weight_sum_t": float(row.get("topside_weight_sum_t") or 0.0),
        "well_slot_rows": well_slot_rows,
        "riser_rows": riser_rows,
        "topside_weight_rows": topside_weight_rows,
    }


def load_latest_wizard_workpoint(
    mysql_url: str,
    *,
    job_name: str,
    default: float = 9.1,
) -> float:
    if not mysql_url or not job_name:
        return default
    engine = _engine(mysql_url)
    try:
        with engine.begin() as conn:
            row = conn.execute(text("""
                SELECT workpoint
                FROM wizard_model_info
                WHERE job_name = :job_name
                ORDER BY id DESC
                LIMIT 1
            """), {"job_name": job_name}).mappings().first()
        if row and row.get("workpoint") is not None:
            return float(row.get("workpoint"))
    except Exception:
        return default
    return default


def load_latest_wizard_model_paths(mysql_url: str, *, job_name: str) -> dict[str, Any] | None:
    if not mysql_url or not job_name:
        return None
    engine = _engine(mysql_url)
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT model_file, new_model_file, workpoint
            FROM wizard_model_info
            WHERE job_name = :job_name
            ORDER BY id DESC
            LIMIT 1
        """), {"job_name": job_name}).mappings().first()
    return dict(row) if row else None
