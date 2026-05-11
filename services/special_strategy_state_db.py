from __future__ import annotations

import json
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import text
from shiyou_db.config import resolve_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent
REPO_DB_DIR = PROJECT_ROOT / "shiyou_db"
LEGACY_DB_DIR = PROJECT_PARENT / "shiyou_db"
DEFAULT_DB_CONFIG = resolve_config_path()


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


# =========================
# 特检策略立面/风险图图片记录
# =========================
def ensure_strategy_risk_image_table(config_path: str | None = None) -> None:
    """创建特检策略图片记录表。

    用于保存页面自动导出的图片路径及其关联信息：平台、run_id、页面、年份、立面等。
    """
    engine = _get_engine(config_path)
    ddl = """
    CREATE TABLE IF NOT EXISTS special_strategy_risk_images (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        run_id BIGINT NULL,
        facility_code VARCHAR(100) NOT NULL,
        page_code VARCHAR(100) NOT NULL,
        image_type VARCHAR(80) NOT NULL,
        year_label VARCHAR(50) NULL,
        row_name VARCHAR(100) NOT NULL,
        image_path VARCHAR(1000) NOT NULL,
        image_name VARCHAR(255) NOT NULL,
        remark VARCHAR(255) NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    )
    """
    index_sql = [
        "CREATE INDEX IF NOT EXISTS ix_ss_risk_images_facility ON special_strategy_risk_images (facility_code)",
        "CREATE INDEX IF NOT EXISTS ix_ss_risk_images_run ON special_strategy_risk_images (run_id)",
        "CREATE INDEX IF NOT EXISTS ix_ss_risk_images_page ON special_strategy_risk_images (page_code)",
    ]
    with engine.begin() as conn:
        conn.execute(text(ddl))
        for sql in index_sql:
            try:
                conn.execute(text(sql))
            except Exception:
                # 兼容不支持 CREATE INDEX IF NOT EXISTS 的 MySQL 版本。
                pass


def save_strategy_risk_image(
    *,
    facility_code: str,
    page_code: str,
    image_type: str,
    row_name: str,
    image_path: str,
    image_name: str,
    run_id: int | None = None,
    year_label: str | None = None,
    remark: str | None = None,
    config_path: str | None = None,
) -> int:
    """保存一张特检策略图片记录。

    同一平台、同一 run_id、同一页面、同一年份、同一立面图只保留一条最新记录，
    避免页面刷新或切换后重复插入大量相同记录。
    """
    ensure_strategy_risk_image_table(config_path)
    engine = _get_engine(config_path)

    normalized_run_id = int(run_id) if run_id else None
    params = {
        "run_id": normalized_run_id,
        "facility_code": str(facility_code or "").strip(),
        "page_code": str(page_code or "").strip(),
        "image_type": str(image_type or "").strip(),
        "year_label": str(year_label or "").strip() or None,
        "row_name": str(row_name or "").strip(),
        "image_path": str(image_path or "").strip(),
        "image_name": str(image_name or "").strip(),
        "remark": str(remark or "").strip() or None,
    }

    delete_sql = text(
        """
        DELETE FROM special_strategy_risk_images
        WHERE facility_code = :facility_code
          AND page_code = :page_code
          AND image_type = :image_type
          AND row_name = :row_name
          AND ((year_label IS NULL AND :year_label IS NULL) OR year_label = :year_label)
          AND ((run_id IS NULL AND :run_id IS NULL) OR run_id = :run_id)
        """
    )
    insert_sql = text(
        """
        INSERT INTO special_strategy_risk_images (
            run_id,
            facility_code,
            page_code,
            image_type,
            year_label,
            row_name,
            image_path,
            image_name,
            remark
        ) VALUES (
            :run_id,
            :facility_code,
            :page_code,
            :image_type,
            :year_label,
            :row_name,
            :image_path,
            :image_name,
            :remark
        )
        """
    )
    with engine.begin() as conn:
        conn.execute(delete_sql, params)
        result = conn.execute(insert_sql, params)
        return int(result.lastrowid or 0)


def list_strategy_risk_images(
    facility_code: str,
    *,
    run_id: int | None = None,
    page_code: str | None = None,
    limit: int = 200,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    """查询已保存的特检策略图片记录，供后续历史查看或报告插图使用。"""
    if not is_strategy_state_db_configured(config_path):
        return []
    ensure_strategy_risk_image_table(config_path)
    engine = _get_engine(config_path)

    clauses = ["facility_code = :facility_code"]
    params: dict[str, Any] = {
        "facility_code": str(facility_code or "").strip(),
        "limit_count": max(1, int(limit)),
    }
    if run_id is not None:
        clauses.append("run_id = :run_id")
        params["run_id"] = int(run_id)
    if page_code:
        clauses.append("page_code = :page_code")
        params["page_code"] = str(page_code).strip()

    sql = text(
        f"""
        SELECT *
        FROM special_strategy_risk_images
        WHERE {' AND '.join(clauses)}
        ORDER BY updated_at DESC, id DESC
        LIMIT :limit_count
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return [dict(row) for row in rows]
