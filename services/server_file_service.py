# services/server_file_service.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text

from shiyou_db.runtime_db import get_mysql_url, get_storage_root, get_echo_sql


FILE_TABLE_CANDIDATES = [
    "file_records",
    "files",
    "uploaded_files",
    "file_info",
    "sys_file",
]


def _engine():
    return create_engine(
        get_mysql_url(),
        echo=get_echo_sql(),
        pool_pre_ping=True,
        pool_recycle=3600,
    )


def _detect_file_table() -> str:
    engine = _engine()
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())

    for name in FILE_TABLE_CANDIDATES:
        if name in tables:
            return name

    raise RuntimeError(
        "未找到文件记录表，请确认数据库中是否存在："
        + ", ".join(FILE_TABLE_CANDIDATES)
    )


def _table_columns(table_name: str) -> set[str]:
    engine = _engine()
    with engine.connect() as conn:
        inspector = inspect(conn)
        return {col["name"] for col in inspector.get_columns(table_name)}


def resolve_storage_path(path_text: str | Path) -> Path:
    """
    把数据库里的路径转成服务端本机真实路径。

    推荐数据库存相对路径，例如：
    model_files/WC19-1D/当前模型/结构模型/用户上传/结构模型文件/sacinp.JKnew

    服务端实际读取：
    D:/shiyou_file_storage/model_files/WC19-1D/...
    """
    text_value = str(path_text or "").strip()
    if not text_value:
        raise ValueError("文件路径为空")

    text_value = text_value.replace("\\", "/")
    storage_root = Path(get_storage_root()).expanduser().resolve()

    raw = Path(text_value)

    if raw.is_absolute():
        if raw.exists():
            return raw

        marker = "shiyou_file_storage/"
        idx = text_value.lower().find(marker.lower())
        if idx >= 0:
            rel = text_value[idx + len(marker):]
            candidate = storage_root / rel
            if candidate.exists():
                return candidate.resolve()

        return raw

    return (storage_root / text_value).resolve()


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _record_path_text(record: dict[str, Any]) -> str:
    for key in (
        "storage_path",
        "relative_path",
        "file_path",
        "path",
        "absolute_path",
        "local_path",
    ):
        value = record.get(key)
        if value:
            return str(value)
    raise FileNotFoundError(f"文件记录中没有路径字段：{record}")


def record_display_name(record: dict[str, Any]) -> str:
    for key in ("file_name", "original_name", "filename", "name"):
        value = record.get(key)
        if value:
            return str(value)
    try:
        return Path(_record_path_text(record)).name
    except Exception:
        return "unknown_file"


def record_to_server_path(record: dict[str, Any]) -> Path:
    path = resolve_storage_path(_record_path_text(record))
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"数据库记录对应的服务端文件不存在：{path}")
    return path


def find_latest_file_record(
    *,
    facility_code: str,
    keyword: str = "",
    category_keywords: list[str] | None = None,
) -> dict[str, Any] | None:
    table = _detect_file_table()
    columns = _table_columns(table)

    conditions = []
    params: dict[str, Any] = {}

    code = str(facility_code or "").strip()
    if code:
        code_cols = [
            col for col in ("facility_code", "platform_code", "facility_id", "facility")
            if col in columns
        ]
        if code_cols:
            conditions.append(
                "(" + " OR ".join([f"{col} = :facility_code" for col in code_cols]) + ")"
            )
            params["facility_code"] = code

    like_parts = []

    keyword = str(keyword or "").strip()
    if keyword:
        params["kw"] = f"%{keyword}%"
        for col in (
            "file_name",
            "original_name",
            "filename",
            "name",
            "storage_path",
            "relative_path",
            "file_path",
            "path",
            "logical_path",
            "category_name",
            "file_type_code",
            "module_code",
            "remark",
        ):
            if col in columns:
                like_parts.append(f"{col} LIKE :kw")

    for i, kw in enumerate(category_keywords or []):
        kw = str(kw or "").strip()
        if not kw:
            continue
        key = f"cat_kw_{i}"
        params[key] = f"%{kw}%"
        for col in ("category_name", "file_type_code", "module_code", "logical_path", "remark"):
            if col in columns:
                like_parts.append(f"{col} LIKE :{key}")

    if like_parts:
        conditions.append("(" + " OR ".join(like_parts) + ")")

    where_sql = ""
    if conditions:
        where_sql = " AND " + " AND ".join(conditions)

    order_parts = []
    for col in ("updated_at", "created_at", "upload_time", "id"):
        if col in columns:
            order_parts.append(f"{col} DESC")

    order_sql = ", ".join(order_parts) if order_parts else ""

    sql = f"SELECT * FROM {table} WHERE 1=1 {where_sql} "
    if order_sql:
        sql += f"ORDER BY {order_sql} "
    sql += "LIMIT 1"

    with _engine().connect() as conn:
        row = conn.execute(text(sql), params).mappings().first()

    return _row_to_dict(row)


def _record_text(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    return " ".join(str(record.get(key) or "") for key in keys).strip()


def _current_sacinp_score(record: dict[str, Any], facility_code: str) -> int:
    path_text = _record_text(
        record,
        (
            "storage_path",
            "relative_path",
            "file_path",
            "path",
            "absolute_path",
            "local_path",
        ),
    )
    name_text = _record_text(record, ("file_name", "original_name", "filename", "name"))
    logical_path = str(record.get("logical_path") or "")
    module_code = str(record.get("module_code") or "")

    display_name = (name_text or Path(path_text).name).strip()
    name_low = display_name.lower()
    path_low = path_text.lower().replace("\\", "/")
    logical_low = logical_path.lower().replace("\\", "/")
    code_low = str(facility_code or "").strip().lower()

    if not name_low.startswith("sacinp"):
        return -1
    if name_low.startswith("seainp"):
        return -1
    if name_low == "sacinp.m1" or path_low.endswith("/sacinp.m1"):
        return -1
    if "历史改造" in logical_path or "自动计算" in logical_path or "/结果/" in logical_low:
        return -1

    score = 0
    if module_code == "model_files":
        score += 200
    if code_low and (code_low in path_low or code_low in logical_low):
        score += 300
    if "当前模型" in logical_path:
        score += 500
    if "结构模型" in logical_path:
        score += 300
    if "用户上传" in logical_path:
        score += 50
    if name_low == "sacinp.jknew":
        score += 1000
    elif name_low.startswith("sacinp"):
        score += 400
    return score


def get_current_sacinp_record(facility_code: str) -> dict[str, Any]:
    """返回当前平台当前原模型结构文件，避免误选历史改造 M1 或结果目录文件。"""
    table = _detect_file_table()
    columns = _table_columns(table)

    conditions = []
    params: dict[str, Any] = {}

    code = str(facility_code or "").strip()
    if code:
        code_cols = [
            col for col in ("facility_code", "platform_code", "facility_id", "facility")
            if col in columns
        ]
        if code_cols:
            conditions.append(
                "(" + " OR ".join([f"{col} = :facility_code" for col in code_cols]) + ")"
            )
            params["facility_code"] = code

    sacinp_parts = []
    params["sacinp_kw"] = "%sacinp%"
    for col in (
        "file_name",
        "original_name",
        "filename",
        "name",
        "storage_path",
        "relative_path",
        "file_path",
        "path",
        "absolute_path",
        "local_path",
    ):
        if col in columns:
            sacinp_parts.append(f"{col} LIKE :sacinp_kw")
    if sacinp_parts:
        conditions.append("(" + " OR ".join(sacinp_parts) + ")")

    if "module_code" in columns:
        conditions.append("(module_code = :module_code OR module_code IS NULL OR module_code = '')")
        params["module_code"] = "model_files"

    where_sql = ""
    if conditions:
        where_sql = " AND " + " AND ".join(conditions)

    order_parts = []
    for col in ("updated_at", "created_at", "upload_time", "id"):
        if col in columns:
            order_parts.append(f"{col} DESC")
    order_sql = ", ".join(order_parts) if order_parts else ""

    sql = f"SELECT * FROM {table} WHERE 1=1 {where_sql} "
    if order_sql:
        sql += f"ORDER BY {order_sql} "
    sql += "LIMIT 200"

    with _engine().connect() as conn:
        rows = [dict(row) for row in conn.execute(text(sql), params).mappings().all()]

    candidates: list[tuple[int, dict[str, Any]]] = []
    for record in rows:
        score = _current_sacinp_score(record, code)
        if score >= 0:
            candidates.append((score, record))

    if not candidates:
        raise FileNotFoundError(
            f"未在数据库中找到平台 {facility_code} 的当前原模型 sacinp 文件记录。"
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def get_latest_sacinp_record(facility_code: str) -> dict[str, Any]:
    record = find_latest_file_record(
        facility_code=facility_code,
        keyword="sacinp",
        category_keywords=["模型文件", "结构模型"],
    )
    if not record:
        raise FileNotFoundError(
            f"未在数据库中找到平台 {facility_code} 的 sacinp 模型文件记录。"
        )
    return record


def get_latest_sacinp_path(facility_code: str) -> Path:
    return record_to_server_path(get_latest_sacinp_record(facility_code))


def get_latest_seainp_record(facility_code: str) -> dict[str, Any] | None:
    return find_latest_file_record(
        facility_code=facility_code,
        keyword="seainp",
        category_keywords=["环境文件", "海洋环境", "SEA"],
    )


def get_latest_seainp_path(facility_code: str) -> Path | None:
    record = get_latest_seainp_record(facility_code)
    if not record:
        return None
    return record_to_server_path(record)
