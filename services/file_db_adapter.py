from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent
REPO_DB_DIR = PROJECT_ROOT / "shiyou_db"
LEGACY_DB_DIR = PROJECT_PARENT / "shiyou_db"
DEFAULT_DB_CONFIG = (REPO_DB_DIR if REPO_DB_DIR.exists() else LEGACY_DB_DIR) / "db_config.json"


class FileBackendError(RuntimeError):
    pass


_UNSET = object()


def _ensure_import_path() -> None:
    for path in (PROJECT_PARENT, PROJECT_ROOT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def is_file_db_configured(config_path: str | None = None) -> bool:
    path = Path(config_path) if config_path else DEFAULT_DB_CONFIG
    return path.exists()


@lru_cache(maxsize=4)
def _load_settings(config_path: str | None = None):
    _ensure_import_path()
    try:
        from shiyou_db import load_settings
    except Exception as exc:
        raise FileBackendError(f"Cannot import package shiyou_db: {exc}") from exc

    resolved = str(Path(config_path).resolve()) if config_path else None
    try:
        return load_settings(resolved)
    except Exception as exc:
        raise FileBackendError(f"Cannot load file database settings: {exc}") from exc


@lru_cache(maxsize=4)
def _get_service(config_path: str | None = None):
    _ensure_import_path()
    try:
        from shiyou_db import FileMetadataService
    except Exception as exc:
        raise FileBackendError(f"Cannot import package shiyou_db: {exc}") from exc

    resolved = str(Path(config_path).resolve()) if config_path else None
    try:
        service = FileMetadataService.from_config(resolved)
        service.seed_file_types()
        return service
    except Exception as exc:
        raise FileBackendError(f"Cannot initialize file database service: {exc}") from exc


def configured_storage_root(config_path: str | None = None) -> str:
    path = Path(config_path) if config_path else DEFAULT_DB_CONFIG
    if not path.exists():
        return ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        value = str(raw.get("storage_root") or "").strip()
        if not value:
            return ""
        return str(Path(value).resolve())
    except Exception:
        return ""


def shared_storage_dir(name: str, *, config_path: str | None = None) -> str:
    storage_root = configured_storage_root(config_path)
    if not storage_root:
        return ""
    return str((Path(storage_root).parent / name).resolve())


def _safe_segment(text: str) -> str:
    filtered: list[str] = []
    for ch in str(text or "").strip():
        if ch.isalnum() or ch in ("-", "_", "."):
            filtered.append(ch)
        else:
            filtered.append("_")
    return "".join(filtered).strip("._") or "default"


def resolve_storage_path(row: dict[str, Any], *, config_path: str | None = None) -> str:
    raw_storage = str(row.get("storage_path") or "").strip()
    raw_path = os.path.normpath(raw_storage) if raw_storage else ""
    raw_rel = str(row.get("storage_rel_path") or "").replace("\\", "/").strip().strip("/")

    storage_root = configured_storage_root(config_path)
    module_code = str(row.get("module_code") or "").strip()
    logical_path = str(row.get("logical_path") or "").replace("\\", "/").strip().strip("/")
    stored_name = str(row.get("stored_name") or "").strip()

    if storage_root and raw_rel:
        rel_candidate = Path(storage_root) / Path(*[seg for seg in raw_rel.split("/") if seg])
        return os.path.normpath(str(rel_candidate))

    # 兼容旧数据：stored_name 缺失时，尝试从原始路径里补一个文件名
    if not stored_name and raw_path:
        guessed_name = os.path.basename(raw_path)
        if guessed_name and guessed_name not in (".", ".."):
            stored_name = guessed_name

    # 缺关键字段时，只在原始路径真实存在的情况下返回它；否则返回空串
    if not storage_root or not module_code or not stored_name:
        if raw_path and raw_path not in (".", "..") and os.path.exists(raw_path):
            return raw_path
        return ""

    safe_module = _safe_segment(module_code or "general")
    logical_segments = [_safe_segment(seg) for seg in logical_path.split("/") if seg]
    base_dir = Path(storage_root) / safe_module / Path(*logical_segments)

    direct_candidate = base_dir / stored_name
    if direct_candidate.exists():
        return os.path.normpath(str(direct_candidate))

    date_candidates: list[str] = []
    for dt in (row.get("uploaded_at"), row.get("source_modified_at"), row.get("updated_at")):
        if hasattr(dt, "strftime"):
            date_candidates.append(dt.strftime("%Y%m%d"))

    for day in date_candidates:
        candidate = base_dir / day / stored_name
        if candidate.exists():
            return os.path.normpath(str(candidate))

    if base_dir.is_dir():
        try:
            for day_dir in base_dir.iterdir():
                if not day_dir.is_dir():
                    continue
                candidate = day_dir / stored_name
                if candidate.exists():
                    return os.path.normpath(str(candidate))
        except Exception:
            pass

    if raw_path and raw_path not in (".", "..") and os.path.exists(raw_path):
        return raw_path
    return ""

def list_files(
    *,
    file_type_code: str | None = None,
    module_code: str | None = None,
    logical_path: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    return _get_service(config_path).list_files(
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path=logical_path,
        facility_code=facility_code,
    )


def list_storage_paths(
    *,
    file_type_code: str | None = None,
    module_code: str | None = None,
    logical_path: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> list[str]:
    rows = list_files(
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path=logical_path,
        facility_code=facility_code,
        config_path=config_path,
    )
    results: list[str] = []
    for row in rows:
        resolved = resolve_storage_path(row, config_path=config_path)
        if resolved:
            results.append(resolved)
    return results


def list_files_by_prefix(
    *,
    file_type_code: str | None = None,
    module_code: str | None = None,
    logical_path_prefix: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    rows = list_files(
        file_type_code=file_type_code,
        module_code=module_code,
        facility_code=facility_code,
        config_path=config_path,
    )
    prefix = str(logical_path_prefix or "").replace("\\", "/").strip().strip("/")
    if not prefix:
        return rows
    prefix_lower = prefix.lower()
    return [
        row for row in rows
        if str(row.get("logical_path") or "").replace("\\", "/").strip().strip("/").lower().startswith(prefix_lower)
    ]


def list_storage_paths_by_prefix(
    *,
    file_type_code: str | None = None,
    module_code: str | None = None,
    logical_path_prefix: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> list[str]:
    rows = list_files_by_prefix(
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path_prefix=logical_path_prefix,
        facility_code=facility_code,
        config_path=config_path,
    )
    results: list[str] = []
    for row in rows:
        resolved = resolve_storage_path(row, config_path=config_path)
        if resolved:
            results.append(resolved)
    return results


def upload_file(
    local_path: str,
    *,
    file_type_code: str,
    module_code: str,
    logical_path: str | None = None,
    facility_code: str | None = None,
    category_name: str | None = None,
    work_condition: str | None = None,
    remark: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    return _get_service(config_path).upload_file(
        local_path,
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path=logical_path,
        facility_code=facility_code,
        category_name=category_name,
        work_condition=work_condition,
        remark=remark,
    )


def soft_delete_record(record_id: int, *, config_path: str | None = None) -> None:
    _get_service(config_path).soft_delete(int(record_id))


def hard_delete_record(record_id: int, *, config_path: str | None = None) -> None:
    _get_service(config_path).hard_delete(int(record_id))


def update_file_record(
    record_id: int,
    *,
    category_name: str | object = _UNSET,
    work_condition: str | object = _UNSET,
    remark: str | object = _UNSET,
    config_path: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if category_name is not _UNSET:
        kwargs["category_name"] = category_name
    if work_condition is not _UNSET:
        kwargs["work_condition"] = work_condition
    if remark is not _UNSET:
        kwargs["remark"] = remark
    return _get_service(config_path).update_file_record(int(record_id), **kwargs)


def soft_delete_storage_path(
    storage_path: str,
    *,
    file_type_code: str | None = None,
    module_code: str | None = None,
    logical_path: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> bool:
    if not storage_path:
        return False
    target = os.path.normcase(os.path.normpath(storage_path))
    rows = list_files(
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path=logical_path,
        facility_code=facility_code,
        config_path=config_path,
    )
    for row in rows:
        path = resolve_storage_path(row, config_path=config_path)
        if not path:
            continue
        current = os.path.normcase(os.path.normpath(str(path)))
        if current == target:
            row_id = row.get("id")
            if row_id is not None:
                _get_service(config_path).soft_delete(int(row_id))
                return True
    return False


def hard_delete_storage_path(
    storage_path: str,
    *,
    file_type_code: str | None = None,
    module_code: str | None = None,
    logical_path: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> bool:
    if not storage_path:
        return False
    target = os.path.normcase(os.path.normpath(storage_path))
    rows = list_files(
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path=logical_path,
        facility_code=facility_code,
        config_path=config_path,
    )
    for row in rows:
        path = resolve_storage_path(row, config_path=config_path)
        if not path:
            continue
        current = os.path.normcase(os.path.normpath(str(path)))
        if current == target:
            row_id = row.get("id")
            if row_id is not None:
                _get_service(config_path).hard_delete(int(row_id))
                return True
    return False


def soft_delete_files_by_prefix(
    *,
    module_code: str,
    logical_path_prefix: str,
    facility_code: str | None = None,
    file_type_code: str | None = None,
    config_path: str | None = None,
) -> int:
    rows = list_files_by_prefix(
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path_prefix=logical_path_prefix,
        facility_code=facility_code,
        config_path=config_path,
    )
    deleted = 0
    for row in rows:
        row_id = row.get("id")
        if row_id is None:
            continue
        _get_service(config_path).soft_delete(int(row_id))
        deleted += 1
    return deleted


DOC_MAN_MODULE_CODE = "doc_man"


def build_docman_logical_path(path_segments: list[str], row_index: int) -> str:
    parts = [segment.strip("/\\") for segment in path_segments if str(segment).strip("/\\")]
    parts.append(f"row_{int(row_index)}")
    return "/".join(parts)


def build_docman_logical_prefix(path_segments: list[str]) -> str:
    parts = [segment.strip("/\\") for segment in path_segments if str(segment).strip("/\\")]
    return "/".join(parts)


def _extract_docman_row_index(logical_path: str | None) -> int:
    text = str(logical_path or "").replace("\\", "/").strip().strip("/")
    tail = text.rsplit("/", 1)[-1] if text else ""
    if tail.startswith("row_"):
        try:
            return int(tail.split("_", 1)[1])
        except Exception:
            return 0
    return 0


def infer_file_type_code(local_path: str, category: str | None = None) -> str:
    suffix = Path(local_path).suffix.lower().lstrip(".")
    category_text = (category or "").lower()
    if any(word in category_text for word in ("地震", "seismic")) or suffix in {"dyninp", "dyrinp", "lst"}:
        return "seismic"
    if any(word in category_text for word in ("疲劳", "fatigue")) or suffix in {"ftginp", "ftglst", "wvrinp", "wit", "wjt", "d"}:
        return "fatigue"
    if any(word in category_text for word in ("倒塌", "collapse")) or suffix in {"clpinp", "clplog", "clplst", "clprst"}:
        return "collapse"
    if any(word in category_text for word in ("图纸", "dwg", "设计图")) or suffix in {"dwg", "dxf"}:
        return "drawing"
    if suffix in {"sacinp", "seainp", "psiinp", "inp", "jknew"}:
        return "model"
    if suffix in {"doc", "docx", "pdf"}:
        return "inspection_doc"
    return "other"


def load_docman_records(
    path_segments: list[str],
    records: list[dict[str, Any]],
    *,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row_index, source in enumerate(records, start=1):
        rec = dict(source)
        logical_path = build_docman_logical_path(path_segments, row_index)
        rows = list_files(
            module_code=DOC_MAN_MODULE_CODE,
            logical_path=logical_path,
            facility_code=facility_code,
            config_path=config_path,
        )
        if rows:
            latest = rows[0]
            rec["record_id"] = latest.get("id")
            rec["path"] = resolve_storage_path(latest, config_path=config_path) or rec.get("path", "")
            rec["filename"] = latest.get("original_name") or rec.get("filename", "")
            rec["fmt"] = (latest.get("file_ext") or rec.get("fmt", "")).upper()
            rec["category"] = latest.get("category_name") or rec.get("category", "")
            rec["work_condition"] = latest.get("work_condition") or rec.get("work_condition", "")
            rec["remark"] = latest.get("remark") if latest.get("remark") is not None else rec.get("remark", "")
            rec["logical_path"] = latest.get("logical_path") or rec.get("logical_path", "")
            dt = latest.get("source_modified_at") or latest.get("uploaded_at")
            if dt is not None:
                rec["mtime"] = dt.strftime("%Y/%m/%d %H:%M")
        merged.append(rec)
    return merged


def load_docman_record_list(
    path_segments: list[str],
    *,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    prefix = build_docman_logical_prefix(path_segments)
    rows = list_files_by_prefix(
        module_code=DOC_MAN_MODULE_CODE,
        logical_path_prefix=prefix,
        facility_code=facility_code,
        config_path=config_path,
    )
    ordered = sorted(
        rows,
        key=lambda row: (
            _extract_docman_row_index(row.get("logical_path")),
            str(row.get("original_name") or ""),
        ),
    )
    records: list[dict[str, Any]] = []
    for index, row in enumerate(ordered, start=1):
        dt = row.get("source_modified_at") or row.get("uploaded_at")
        records.append(
            {
                "index": index,
                "checked": False,
                "category": row.get("category_name") or row.get("file_type_name") or "",
                "work_condition": row.get("work_condition") or "",
                "fmt": str(row.get("file_ext") or "").upper(),
                "filename": row.get("original_name") or "",
                "mtime": dt.strftime("%Y/%m/%d %H:%M") if dt else "",
                "path": resolve_storage_path(row, config_path=config_path),
                "remark": row.get("remark") or "",
                "record_id": row.get("id"),
                "logical_path": row.get("logical_path") or "",
            }
        )
    return records


def append_docman_file(
    local_path: str,
    *,
    path_segments: list[str],
    category: str,
    work_condition: str | None = None,
    remark: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    prefix = build_docman_logical_prefix(path_segments)
    rows = list_files_by_prefix(
        module_code=DOC_MAN_MODULE_CODE,
        logical_path_prefix=prefix,
        facility_code=facility_code,
        config_path=config_path,
    )
    next_index = 1
    if rows:
        next_index = max(_extract_docman_row_index(row.get("logical_path")) for row in rows) + 1
    logical_path = build_docman_logical_path(path_segments, next_index)
    return upload_file(
        local_path,
        file_type_code=infer_file_type_code(local_path, category),
        module_code=DOC_MAN_MODULE_CODE,
        logical_path=logical_path,
        facility_code=facility_code,
        category_name=category,
        work_condition=work_condition,
        remark=remark,
        config_path=config_path,
    )


def replace_docman_list_file(
    local_path: str,
    *,
    logical_path: str,
    record_id: int | None = None,
    category: str,
    work_condition: str | None = None,
    remark: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    service = _get_service(config_path)
    if record_id is not None:
        service.hard_delete(int(record_id))
    return upload_file(
        local_path,
        file_type_code=infer_file_type_code(local_path, category),
        module_code=DOC_MAN_MODULE_CODE,
        logical_path=logical_path,
        facility_code=facility_code,
        category_name=category,
        work_condition=work_condition,
        remark=remark,
        config_path=config_path,
    )


def replace_docman_file(
    local_path: str,
    *,
    path_segments: list[str],
    row_index: int,
    category: str,
    work_condition: str | None = None,
    remark: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    logical_path = build_docman_logical_path(path_segments, row_index)
    service = _get_service(config_path)
    existing = list_files(
        module_code=DOC_MAN_MODULE_CODE,
        logical_path=logical_path,
        facility_code=facility_code,
        config_path=config_path,
    )
    for row in existing:
        row_id = row.get("id")
        if row_id is not None:
            service.hard_delete(int(row_id))
    return upload_file(
        local_path,
        file_type_code=infer_file_type_code(local_path, category),
        module_code=DOC_MAN_MODULE_CODE,
        logical_path=logical_path,
        facility_code=facility_code,
        category_name=category,
        work_condition=work_condition,
        remark=remark,
        config_path=config_path,
    )
