from __future__ import annotations

import json
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent
REPO_DB_DIR = PROJECT_ROOT / "shiyou_db"
LEGACY_DB_DIR = PROJECT_PARENT / "shiyou_db"
DEFAULT_DB_CONFIG = (REPO_DB_DIR if REPO_DB_DIR.exists() else LEGACY_DB_DIR) / "db_config.json"


class SpecialStrategyStateError(RuntimeError):
    pass


def _ensure_import_path() -> None:
    for path in (PROJECT_ROOT, PROJECT_PARENT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


@lru_cache(maxsize=2)
def _get_engine(config_path: str | None = None):
    _ensure_import_path()
    try:
        from shiyou_db.config import load_settings
        from shiyou_db.database import build_engine
    except Exception as exc:
        raise SpecialStrategyStateError(f"Cannot import package shiyou_db: {exc}") from exc

    resolved = str(Path(config_path).resolve()) if config_path else str(DEFAULT_DB_CONFIG.resolve())
    try:
        settings = load_settings(resolved)
        return build_engine(settings)
    except Exception as exc:
        raise SpecialStrategyStateError(f"Cannot initialize strategy state database engine: {exc}") from exc


def is_strategy_state_db_configured(config_path: str | None = None) -> bool:
    path = Path(config_path) if config_path else DEFAULT_DB_CONFIG
    return path.exists()


def ensure_strategy_run_table(config_path: str | None = None) -> None:
    engine = _get_engine(config_path)
    ddl = """
    CREATE TABLE IF NOT EXISTS special_strategy_runs (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        facility_code VARCHAR(100) NOT NULL,
        params_json LONGTEXT NULL,
        metadata_json LONGTEXT NULL,
        inputs_json LONGTEXT NULL,
        intermediate_workbook VARCHAR(500) NOT NULL,
        output_report VARCHAR(500) NULL,
        config_path VARCHAR(500) NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'completed',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        report_generated_at DATETIME NULL
    )
    """
    index_sql = [
        "CREATE INDEX IF NOT EXISTS ix_special_strategy_runs_facility ON special_strategy_runs (facility_code)",
        "CREATE INDEX IF NOT EXISTS ix_special_strategy_runs_facility_updated ON special_strategy_runs (facility_code, updated_at)",
    ]
    with engine.begin() as conn:
        conn.execute(text(ddl))
        for sql in index_sql:
            try:
                conn.execute(text(sql))
            except Exception:
                # Fallback for older MySQL versions without IF NOT EXISTS on indexes.
                pass


def ensure_strategy_result_table(config_path: str | None = None) -> None:
    engine = _get_engine(config_path)
    ddl = """
    CREATE TABLE IF NOT EXISTS special_strategy_result_snapshots (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        run_id BIGINT NULL,
        facility_code VARCHAR(100) NOT NULL,
        result_json LONGTEXT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
    """
    index_sql = [
        "CREATE INDEX IF NOT EXISTS ix_special_strategy_result_facility ON special_strategy_result_snapshots (facility_code)",
        "CREATE INDEX IF NOT EXISTS ix_special_strategy_result_facility_updated ON special_strategy_result_snapshots (facility_code, updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_special_strategy_result_run_id ON special_strategy_result_snapshots (run_id)",
    ]
    with engine.begin() as conn:
        conn.execute(text(ddl))
        for sql in index_sql:
            try:
                conn.execute(text(sql))
            except Exception:
                pass


def _json_dumps(value: Any) -> str | None:
    if value in (None, "", {}):
        return None
    return json.dumps(value, ensure_ascii=False, indent=2)


def save_strategy_run(
    *,
    facility_code: str,
    params: dict[str, Any] | None,
    metadata: dict[str, Any] | None,
    inputs: dict[str, Any] | None,
    intermediate_workbook: str,
    output_report: str | None,
    config_path: str | None,
    status: str = "completed",
    config_db_path: str | None = None,
) -> int:
    ensure_strategy_run_table(config_db_path)
    engine = _get_engine(config_db_path)
    sql = text(
        """
        INSERT INTO special_strategy_runs (
            facility_code,
            params_json,
            metadata_json,
            inputs_json,
            intermediate_workbook,
            output_report,
            config_path,
            status
        ) VALUES (
            :facility_code,
            :params_json,
            :metadata_json,
            :inputs_json,
            :intermediate_workbook,
            :output_report,
            :config_path,
            :status
        )
        """
    )
    with engine.begin() as conn:
        result = conn.execute(
            sql,
            {
                "facility_code": facility_code,
                "params_json": _json_dumps(params),
                "metadata_json": _json_dumps(metadata),
                "inputs_json": _json_dumps(inputs),
                "intermediate_workbook": intermediate_workbook,
                "output_report": output_report,
                "config_path": config_path,
                "status": status,
            },
        )
        return int(result.lastrowid or 0)


def load_latest_strategy_run(facility_code: str, config_path: str | None = None) -> dict[str, Any] | None:
    if not is_strategy_state_db_configured(config_path):
        return None
    ensure_strategy_run_table(config_path)
    engine = _get_engine(config_path)
    sql = text(
        """
        SELECT *
        FROM special_strategy_runs
        WHERE facility_code = :facility_code
        ORDER BY id DESC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"facility_code": facility_code}).mappings().first()
    if row is None:
        return None
    return _deserialize_run_payload(row)


def _deserialize_run_payload(row: Any) -> dict[str, Any]:
    payload = dict(row)
    for key in ("params_json", "metadata_json", "inputs_json"):
        raw = payload.get(key)
        if raw:
            try:
                payload[key] = json.loads(raw)
            except Exception:
                payload[key] = None
        else:
            payload[key] = None
    return payload


def load_strategy_run_by_id(run_id: int, config_path: str | None = None) -> dict[str, Any] | None:
    if not is_strategy_state_db_configured(config_path):
        return None
    ensure_strategy_run_table(config_path)
    engine = _get_engine(config_path)
    sql = text(
        """
        SELECT *
        FROM special_strategy_runs
        WHERE id = :run_id
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"run_id": int(run_id)}).mappings().first()
    if row is None:
        return None
    return _deserialize_run_payload(row)


def list_strategy_runs(
    facility_code: str,
    *,
    limit: int = 50,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    if not is_strategy_state_db_configured(config_path):
        return []
    ensure_strategy_run_table(config_path)
    engine = _get_engine(config_path)
    sql = text(
        """
        SELECT *
        FROM special_strategy_runs
        WHERE facility_code = :facility_code
        ORDER BY id DESC
        LIMIT :limit_count
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            sql,
            {
                "facility_code": facility_code,
                "limit_count": max(1, int(limit)),
            },
        ).mappings().all()
    return [_deserialize_run_payload(row) for row in rows]


def update_strategy_report(
    run_id: int,
    *,
    output_report: str,
    config_path: str | None = None,
) -> None:
    ensure_strategy_run_table(config_path)
    engine = _get_engine(config_path)
    sql = text(
        """
        UPDATE special_strategy_runs
        SET output_report = :output_report,
            report_generated_at = :report_generated_at,
            updated_at = :updated_at
        WHERE id = :run_id
        """
    )
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            sql,
            {
                "run_id": int(run_id),
                "output_report": output_report,
                "report_generated_at": now,
                "updated_at": now,
            },
        )


def save_strategy_result_snapshot(
    *,
    facility_code: str,
    result_payload: dict[str, Any],
    run_id: int | None = None,
    config_path: str | None = None,
) -> int:
    ensure_strategy_result_table(config_path)
    engine = _get_engine(config_path)
    sql = text(
        """
        INSERT INTO special_strategy_result_snapshots (
            run_id,
            facility_code,
            result_json
        ) VALUES (
            :run_id,
            :facility_code,
            :result_json
        )
        """
    )
    with engine.begin() as conn:
        result = conn.execute(
            sql,
            {
                "run_id": int(run_id) if run_id else None,
                "facility_code": facility_code,
                "result_json": json.dumps(result_payload, ensure_ascii=False, default=str),
            },
        )
        return int(result.lastrowid or 0)


def load_latest_strategy_result_snapshot(
    facility_code: str,
    config_path: str | None = None,
) -> dict[str, Any] | None:
    if not is_strategy_state_db_configured(config_path):
        return None
    ensure_strategy_result_table(config_path)
    engine = _get_engine(config_path)
    sql = text(
        """
        SELECT *
        FROM special_strategy_result_snapshots
        WHERE facility_code = :facility_code
        ORDER BY id DESC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"facility_code": facility_code}).mappings().first()
    if row is None:
        return None
    payload = dict(row)
    raw = payload.get("result_json")
    try:
        payload["result_json"] = json.loads(raw) if raw else None
    except Exception:
        payload["result_json"] = None
    return payload


def load_strategy_result_snapshot_by_run(
    run_id: int,
    config_path: str | None = None,
) -> dict[str, Any] | None:
    if not is_strategy_state_db_configured(config_path):
        return None
    ensure_strategy_result_table(config_path)
    engine = _get_engine(config_path)
    sql = text(
        """
        SELECT *
        FROM special_strategy_result_snapshots
        WHERE run_id = :run_id
        ORDER BY id DESC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"run_id": int(run_id)}).mappings().first()
    if row is None:
        return None
    payload = dict(row)
    raw = payload.get("result_json")
    try:
        payload["result_json"] = json.loads(raw) if raw else None
    except Exception:
        payload["result_json"] = None
    return payload
