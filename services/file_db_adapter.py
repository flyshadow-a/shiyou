from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from shiyou_db.config import resolve_config_path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PARENT = PROJECT_ROOT.parent
REPO_DB_DIR = PROJECT_ROOT / "shiyou_db"
LEGACY_DB_DIR = PROJECT_PARENT / "shiyou_db"
DEFAULT_DB_CONFIG = resolve_config_path()


class FileBackendError(RuntimeError):
    pass


_UNSET = object()
_LIST_FILES_CACHE: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
_REBUILD_DIRECTORIES_CACHE: dict[tuple[Any, ...], list[dict[str, Any]]] = {}


def _cache_config_key(config_path: str | None = None) -> str:
    return str(Path(config_path).resolve()) if config_path else ""


def _copy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _invalidate_file_list_cache() -> None:
    _LIST_FILES_CACHE.clear()


def _invalidate_rebuild_directory_cache() -> None:
    _REBUILD_DIRECTORIES_CACHE.clear()


def _invalidate_platform_load_cache() -> None:
    try:
        from services import platform_load_preheat

        platform_load_preheat.clear_platform_load_data_cache()
    except Exception:
        pass


def clear_file_list_cache() -> None:
    _invalidate_file_list_cache()


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
        if hasattr(service, "seed_document_categories"):
            service.seed_document_categories()
        return service
    except Exception as exc:
        raise FileBackendError(f"Cannot initialize file database service: {exc}") from exc


@lru_cache(maxsize=8)
def configured_storage_root(config_path: str | None = None) -> str:
    path = Path(config_path) if config_path else DEFAULT_DB_CONFIG
    if not path.exists():
        return ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        value = str(raw.get("storage_root") or "").strip()
        if not value:
            return ""
        return os.path.abspath(os.path.expanduser(value))
    except Exception:
        return ""


@lru_cache(maxsize=32)
def shared_storage_dir(name: str, *, config_path: str | None = None) -> str:
    storage_root = configured_storage_root(config_path)
    if not storage_root:
        return ""
    return os.path.abspath(os.path.join(os.path.dirname(storage_root), name))


def _safe_segment(text: str) -> str:
    filtered: list[str] = []
    for ch in str(text or "").strip():
        if ch.isalnum() or ch in ("-", "_", "."):
            filtered.append(ch)
        else:
            filtered.append("_")
    return "".join(filtered).strip("._") or "default"


def _storage_parts(text: str) -> list[str]:
    return [
        seg
        for seg in str(text or "").replace("\\", "/").strip().strip("/").split("/")
        if seg and seg not in (".", "..")
    ]


def _path_exists(path: str | Path) -> bool:
    try:
        return Path(path).exists()
    except (OSError, RuntimeError):
        return False


def _path_is_dir(path: str | Path) -> bool:
    try:
        return Path(path).is_dir()
    except (OSError, RuntimeError):
        return False


def _map_to_configured_storage_root(raw_path: str, storage_root: str) -> str:
    if not raw_path or not storage_root:
        return ""

    raw_norm = os.path.normpath(os.path.expanduser(str(raw_path)))
    root_norm = os.path.normpath(os.path.expanduser(str(storage_root)))
    if raw_norm in ("", ".", "..") or root_norm in ("", ".", ".."):
        return ""

    try:
        raw_abs = os.path.abspath(raw_norm)
        root_abs = os.path.abspath(root_norm)
        root_key = os.path.normcase(root_abs).rstrip("\\/")
        raw_key = os.path.normcase(raw_abs)
        if raw_key == root_key or raw_key.startswith(root_key + os.sep):
            return os.path.normpath(raw_abs)
    except Exception:
        pass

    root_parts = _storage_parts(root_norm)
    if not root_parts:
        return ""
    marker = root_parts[-1]

    parts = _storage_parts(raw_norm)

    for index, part in enumerate(parts):
        if part.casefold() != marker.casefold():
            continue
        rel_parts = parts[index + 1:]
        return os.path.normpath(str(Path(root_norm, *rel_parts)))

    return ""


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

    mapped_raw_path = _map_to_configured_storage_root(raw_path, storage_root)
    if mapped_raw_path:
        return mapped_raw_path

    # 兼容旧数据：stored_name 缺失时，尝试从原始路径里补一个文件名
    if not stored_name and raw_path:
        guessed_name = os.path.basename(raw_path)
        if guessed_name and guessed_name not in (".", ".."):
            stored_name = guessed_name

    # 缺关键字段时，只在原始路径真实存在的情况下返回它；否则返回空串
    if not storage_root or not module_code or not stored_name:
        if raw_path and raw_path not in (".", "..") and _path_exists(raw_path):
            return raw_path
        return ""

    safe_module = _safe_segment(module_code or "general")
    logical_segments = [_safe_segment(seg) for seg in logical_path.split("/") if seg]
    base_dir = Path(storage_root) / safe_module / Path(*logical_segments)

    direct_candidate = base_dir / stored_name
    if _path_exists(direct_candidate):
        return os.path.normpath(str(direct_candidate))

    date_candidates: list[str] = []
    for dt in (row.get("uploaded_at"), row.get("source_modified_at"), row.get("updated_at")):
        if hasattr(dt, "strftime"):
            date_candidates.append(dt.strftime("%Y%m%d"))

    for day in date_candidates:
        candidate = base_dir / day / stored_name
        if _path_exists(candidate):
            return os.path.normpath(str(candidate))

    if _path_is_dir(base_dir):
        try:
            for day_dir in base_dir.iterdir():
                if not _path_is_dir(day_dir):
                    continue
                candidate = day_dir / stored_name
                if _path_exists(candidate):
                    return os.path.normpath(str(candidate))
        except Exception:
            pass

    if raw_path and raw_path not in (".", "..") and _path_exists(raw_path):
        return raw_path
    return os.path.normpath(str(direct_candidate))

def list_files(
    *,
    file_type_code: str | None = None,
    module_code: str | None = None,
    logical_path: str | None = None,
    logical_path_prefix: str | None = None,
    logical_path_prefixes: list[str] | None = None,
    facility_code: str | None = None,
    document_code_query: str | None = None,
    document_title_query: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    prefix = str(logical_path_prefix or "").replace("\\", "/").strip().strip("/")
    prefixes = tuple(
        str(item or "").replace("\\", "/").strip().strip("/")
        for item in (logical_path_prefixes or [])
        if str(item or "").replace("\\", "/").strip().strip("/")
    )
    code_query = str(document_code_query or "").strip()
    title_query = str(document_title_query or "").strip()
    key = (
        _cache_config_key(config_path),
        file_type_code or "",
        module_code or "",
        logical_path or "",
        prefix,
        prefixes,
        facility_code or "",
        code_query,
        title_query,
        "" if limit is None else int(limit),
        "" if offset is None else int(offset),
    )
    cached = _LIST_FILES_CACHE.get(key)
    if cached is not None:
        return _copy_rows(cached)

    rows = _get_service(config_path).list_files(
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path=logical_path,
        logical_path_prefix=prefix or None,
        logical_path_prefixes=list(prefixes) or None,
        facility_code=facility_code,
        document_code_query=code_query or None,
        document_title_query=title_query or None,
        limit=limit,
        offset=offset,
    )
    _LIST_FILES_CACHE[key] = _copy_rows(rows)
    return _copy_rows(rows)


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
    document_code_query: str | None = None,
    document_title_query: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    prefix = str(logical_path_prefix or "").replace("\\", "/").strip().strip("/")
    return list_files(
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path_prefix=prefix or None,
        facility_code=facility_code,
        document_code_query=document_code_query,
        document_title_query=document_title_query,
        limit=limit,
        offset=offset,
        config_path=config_path,
    )


def count_files(
    *,
    file_type_code: str | None = None,
    module_code: str | None = None,
    logical_path: str | None = None,
    logical_path_prefix: str | None = None,
    logical_path_prefixes: list[str] | None = None,
    facility_code: str | None = None,
    document_code_query: str | None = None,
    document_title_query: str | None = None,
    config_path: str | None = None,
) -> int:
    prefix = str(logical_path_prefix or "").replace("\\", "/").strip().strip("/")
    prefixes = [
        str(item or "").replace("\\", "/").strip().strip("/")
        for item in (logical_path_prefixes or [])
        if str(item or "").replace("\\", "/").strip().strip("/")
    ]
    return int(
        _get_service(config_path).count_files(
            file_type_code=file_type_code,
            module_code=module_code,
            logical_path=logical_path,
            logical_path_prefix=prefix or None,
            logical_path_prefixes=prefixes or None,
            facility_code=facility_code,
            document_code_query=(document_code_query or None),
            document_title_query=(document_title_query or None),
        )
        or 0
    )


def count_files_by_prefix(
    *,
    file_type_code: str | None = None,
    module_code: str | None = None,
    logical_path_prefix: str | None = None,
    facility_code: str | None = None,
    document_code_query: str | None = None,
    document_title_query: str | None = None,
    config_path: str | None = None,
) -> int:
    prefix = str(logical_path_prefix or "").replace("\\", "/").strip().strip("/")
    return count_files(
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path_prefix=prefix or None,
        facility_code=facility_code,
        document_code_query=document_code_query,
        document_title_query=document_title_query,
        config_path=config_path,
    )


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
    result = _get_service(config_path).upload_file(
        local_path,
        file_type_code=file_type_code,
        module_code=module_code,
        logical_path=logical_path,
        facility_code=facility_code,
        category_name=category_name,
        work_condition=work_condition,
        remark=remark,
    )
    _invalidate_file_list_cache()
    return result


def soft_delete_record(record_id: int, *, config_path: str | None = None) -> None:
    _get_service(config_path).soft_delete(int(record_id))
    _invalidate_file_list_cache()


def hard_delete_record(record_id: int, *, config_path: str | None = None) -> None:
    _get_service(config_path).hard_delete(int(record_id))
    _invalidate_file_list_cache()


def update_file_record(
    record_id: int,
    *,
    category_name: str | object = _UNSET,
    work_condition: str | object = _UNSET,
    remark: str | object = _UNSET,
    expected_updated_at: object = _UNSET,
    config_path: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if category_name is not _UNSET:
        kwargs["category_name"] = category_name
    if work_condition is not _UNSET:
        kwargs["work_condition"] = work_condition
    if remark is not _UNSET:
        kwargs["remark"] = remark
    if expected_updated_at is not _UNSET:
        kwargs["expected_updated_at"] = expected_updated_at
    try:
        result = _get_service(config_path).update_file_record(int(record_id), **kwargs)
    except Exception as exc:
        raise FileBackendError(str(exc)) from exc
    _invalidate_file_list_cache()
    return result


def list_document_categories(
    scope_code: str | None = None,
    *,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    return _get_service(config_path).list_document_categories(scope_code)


def list_rebuild_directories(
    facility_code: str,
    *,
    project_type: str | None = None,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    key = (_cache_config_key(config_path), facility_code or "", project_type or "")
    cached = _REBUILD_DIRECTORIES_CACHE.get(key)
    if cached is not None:
        return _copy_rows(cached)
    rows = _get_service(config_path).list_rebuild_directories(facility_code, project_type)
    _REBUILD_DIRECTORIES_CACHE[key] = _copy_rows(rows)
    return _copy_rows(rows)


def create_rebuild_directory(
    facility_code: str,
    *,
    project_type: str | None = None,
    directory_name: str | None = None,
    project_name: str | None = None,
    project_year: str | None = None,
    summary_text: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    result = _get_service(config_path).create_rebuild_directory(
        facility_code,
        project_type=project_type,
        directory_name=directory_name,
        project_name=project_name,
        project_year=project_year,
        summary_text=summary_text,
    )
    _invalidate_rebuild_directory_cache()
    _invalidate_platform_load_cache()
    return result


def update_rebuild_directory(
    directory_id: int,
    *,
    directory_name: str | None = None,
    project_name: str | None = None,
    project_year: str | None = None,
    summary_text: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    result = _get_service(config_path).update_rebuild_directory(
        int(directory_id),
        directory_name=directory_name,
        project_name=project_name,
        project_year=project_year,
        summary_text=summary_text,
    )
    _invalidate_rebuild_directory_cache()
    _invalidate_platform_load_cache()
    return result


def delete_rebuild_directory(
    directory_id: int,
    *,
    config_path: str | None = None,
) -> None:
    _get_service(config_path).delete_rebuild_directory(int(directory_id))
    _invalidate_rebuild_directory_cache()
    _invalidate_platform_load_cache()


def delete_rebuild_directory_with_files(
    directory_id: int,
    *,
    module_code: str,
    logical_path_prefix: str,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> int:
    deleted = _get_service(config_path).delete_rebuild_directory_with_files(
        int(directory_id),
        module_code=module_code,
        logical_path_prefix=logical_path_prefix,
        facility_code=facility_code,
    )
    _invalidate_rebuild_directory_cache()
    _invalidate_platform_load_cache()
    _invalidate_file_list_cache()
    return deleted


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
                _invalidate_file_list_cache()
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
                _invalidate_file_list_cache()
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
    deleted = _get_service(config_path).soft_delete_files_by_prefix(
        module_code=module_code,
        logical_path_prefix=logical_path_prefix,
        facility_code=facility_code,
        file_type_code=file_type_code,
    )
    if deleted:
        _invalidate_file_list_cache()
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
            for meta_key in (
                "document_code",
                "document_title",
                "design_stage_code",
                "design_stage_name",
                "discipline_code",
                "discipline_name",
                "file_class_code",
                "file_class_name",
                "recognition_status",
                "recognition_message",
            ):
                rec[meta_key] = latest.get(meta_key) or rec.get(meta_key, "")
            dt = latest.get("uploaded_at") or latest.get("source_modified_at") or latest.get("updated_at")
            if dt is not None:
                rec["mtime"] = dt.strftime("%Y/%m/%d %H:%M")
            rec["_lock_updated_at"] = latest.get("lock_updated_at")
        merged.append(rec)
    return merged


def load_docman_record_list(
    path_segments: list[str],
    *,
    facility_code: str | None = None,
    document_code_query: str | None = None,
    document_title_query: str | None = None,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    prefix = build_docman_logical_prefix(path_segments)
    rows = list_files_by_prefix(
        module_code=DOC_MAN_MODULE_CODE,
        logical_path_prefix=prefix,
        facility_code=facility_code,
        document_code_query=document_code_query,
        document_title_query=document_title_query,
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
        records.append(_docman_record_from_file_row(row, index, config_path=config_path))
    return records


def load_docman_record_page(
    path_segments: list[str],
    *,
    page: int = 0,
    page_size: int = 30,
    facility_code: str | None = None,
    document_code_query: str | None = None,
    document_title_query: str | None = None,
    logical_path_prefixes: list[str] | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    prefix = build_docman_logical_prefix(path_segments)
    prefixes = [
        str(item or "").replace("\\", "/").strip().strip("/")
        for item in (logical_path_prefixes or [])
        if str(item or "").replace("\\", "/").strip().strip("/")
    ]
    safe_page = max(0, int(page or 0))
    requested_page_size = 30 if page_size is None else int(page_size)
    if prefixes:
        total = count_files(
            module_code=DOC_MAN_MODULE_CODE,
            logical_path_prefixes=prefixes,
            facility_code=facility_code,
            document_code_query=document_code_query,
            document_title_query=document_title_query,
            config_path=config_path,
        )
    else:
        total = count_files_by_prefix(
            module_code=DOC_MAN_MODULE_CODE,
            logical_path_prefix=prefix,
            facility_code=facility_code,
            document_code_query=document_code_query,
            document_title_query=document_title_query,
            config_path=config_path,
        )
    if requested_page_size <= 0:
        safe_page_size = max(1, total)
        safe_page = 0
    else:
        safe_page_size = max(1, requested_page_size)
        max_page = max(0, (total - 1) // safe_page_size) if total else 0
        safe_page = min(safe_page, max_page)
    offset = safe_page * safe_page_size
    if prefixes:
        rows = list_files(
            module_code=DOC_MAN_MODULE_CODE,
            logical_path_prefixes=prefixes,
            facility_code=facility_code,
            document_code_query=document_code_query,
            document_title_query=document_title_query,
            limit=safe_page_size,
            offset=offset,
            config_path=config_path,
        )
    else:
        rows = list_files_by_prefix(
            module_code=DOC_MAN_MODULE_CODE,
            logical_path_prefix=prefix,
            facility_code=facility_code,
            document_code_query=document_code_query,
            document_title_query=document_title_query,
            limit=safe_page_size,
            offset=offset,
            config_path=config_path,
        )
    records = [
        _docman_record_from_file_row(row, offset + index, config_path=config_path)
        for index, row in enumerate(rows, start=1)
    ]
    return {
        "records": records,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
    }


def _docman_record_from_file_row(
    row: dict[str, Any],
    index: int,
    *,
    config_path: str | None = None,
) -> dict[str, Any]:
    dt = row.get("uploaded_at") or row.get("source_modified_at") or row.get("updated_at")
    return {
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
        "document_code": row.get("document_code") or "",
        "document_title": row.get("document_title") or "",
        "design_stage_code": row.get("design_stage_code") or "",
        "design_stage_name": row.get("design_stage_name") or "",
        "discipline_code": row.get("discipline_code") or "",
        "discipline_name": row.get("discipline_name") or "",
        "file_class_code": row.get("file_class_code") or "",
        "file_class_name": row.get("file_class_name") or "",
        "recognition_status": row.get("recognition_status") or "",
        "recognition_message": row.get("recognition_message") or "",
        "_lock_updated_at": row.get("lock_updated_at"),
    }


def append_docman_file(
    local_path: str,
    *,
    path_segments: list[str],
    category: str | None = None,
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
    category: str | None = None,
    work_condition: str | None = None,
    remark: str | None = None,
    facility_code: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    service = _get_service(config_path)
    if record_id is not None:
        service.hard_delete(int(record_id))
        _invalidate_file_list_cache()
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
    category: str | None = None,
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
            _invalidate_file_list_cache()
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
