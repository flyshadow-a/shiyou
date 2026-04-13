from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_PARENT = PROJECT_ROOT.parent
REPO_DB_DIR = PROJECT_ROOT / "shiyou_db"
LEGACY_DB_DIR = PROJECT_PARENT / "shiyou_db"
DEFAULT_DB_CONFIG = (REPO_DB_DIR if REPO_DB_DIR.exists() else LEGACY_DB_DIR) / "db_config.json"


class BusinessBackendError(RuntimeError):
    pass


def _ensure_import_path() -> None:
    for path in (PROJECT_ROOT, PROJECT_PARENT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


@lru_cache(maxsize=4)
def _get_service(config_path: str | None = None):
    _ensure_import_path()
    try:
        from shiyou_db import FileMetadataService
    except Exception as exc:
        raise BusinessBackendError(f"Cannot import package shiyou_db: {exc}") from exc

    resolved = str(Path(config_path).resolve()) if config_path else None
    try:
        return FileMetadataService.from_config(resolved)
    except Exception as exc:
        raise BusinessBackendError(f"Cannot initialize business database service: {exc}") from exc


def is_business_db_configured(config_path: str | None = None) -> bool:
    path = Path(config_path) if config_path else DEFAULT_DB_CONFIG
    return path.exists()


def load_facility_profile(
    facility_code: str,
    *,
    defaults: dict[str, Any] | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    values = dict(defaults or {})
    row = _get_service(config_path).get_facility_profile(facility_code)
    if row:
        values.update({k: v for k, v in row.items() if v not in (None, "")})
    values["facility_code"] = facility_code
    return values


def save_facility_profile(
    facility_code: str,
    payload: dict[str, Any],
    *,
    config_path: str | None = None,
) -> dict[str, Any]:
    return _get_service(config_path).upsert_facility_profile(facility_code, **payload)


def list_inspection_projects(
    facility_code: str,
    project_type: str,
    *,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    return _get_service(config_path).list_inspection_projects(
        facility_code=facility_code,
        project_type=project_type,
    )


def create_inspection_project(
    *,
    facility_code: str,
    project_type: str,
    project_name: str,
    project_year: str | None = None,
    event_date: str | None = None,
    summary_text: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    return _get_service(config_path).create_inspection_project(
        facility_code=facility_code,
        project_type=project_type,
        project_name=project_name,
        project_year=project_year,
        event_date=event_date,
        summary_text=summary_text,
    )


def update_inspection_project(
    project_id: int,
    *,
    project_name: str | None = None,
    project_year: str | None = None,
    event_date: str | None = None,
    summary_text: str | None = None,
    sort_order: int | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if project_name is not None:
        payload["project_name"] = project_name
    if project_year is not None:
        payload["project_year"] = project_year
    if event_date is not None:
        payload["event_date"] = event_date
    if summary_text is not None:
        payload["summary_text"] = summary_text
    if sort_order is not None:
        payload["sort_order"] = sort_order
    return _get_service(config_path).update_inspection_project(int(project_id), **payload)


def soft_delete_inspection_project(
    project_id: int,
    *,
    config_path: str | None = None,
) -> None:
    _get_service(config_path).soft_delete_inspection_project(int(project_id))


def list_inspection_findings(project_id: int, *, config_path: str | None = None) -> list[dict[str, Any]]:
    return _get_service(config_path).list_inspection_findings(int(project_id))


def replace_inspection_findings(
    project_id: int,
    rows: list[dict[str, Any]],
    *,
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    return _get_service(config_path).replace_inspection_findings(int(project_id), rows)
