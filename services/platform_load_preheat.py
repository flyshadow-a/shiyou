# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from threading import Event, RLock
from typing import Dict

from pages.file_management_platforms import default_platform
from services.file_db_adapter import list_rebuild_directories
from services.inspection_business_db_adapter import (
    load_facility_profile,
    load_platform_load_information_items,
)

_PLATFORM_LOAD_DATA_CACHE: Dict[str, Dict[str, object]] = {}
_PLATFORM_LOAD_DATA_CACHE_LOCK = RLock()
_PLATFORM_LOAD_DATA_PREHEAT_DONE = Event()
_PLATFORM_LOAD_DATA_PREHEAT_IN_PROGRESS = False


def load_platform_load_payload(facility_code: str, defaults: Dict[str, str]) -> Dict[str, object]:
    profile = load_facility_profile(facility_code, defaults=defaults)
    rows = load_platform_load_information_items(facility_code)
    rebuild_error = ""
    try:
        rebuild_projects = list_rebuild_directories(
            facility_code,
            project_type="history_rebuild",
        )
    except Exception as exc:
        rebuild_projects = []
        rebuild_error = str(exc)

    return {
        "facility_code": facility_code,
        "profile": profile,
        "rows": rows,
        "rebuild_projects": rebuild_projects,
        "rebuild_error": rebuild_error,
    }


def clear_platform_load_data_cache() -> None:
    global _PLATFORM_LOAD_DATA_PREHEAT_IN_PROGRESS

    with _PLATFORM_LOAD_DATA_CACHE_LOCK:
        _PLATFORM_LOAD_DATA_CACHE.clear()
        _PLATFORM_LOAD_DATA_PREHEAT_IN_PROGRESS = False
        _PLATFORM_LOAD_DATA_PREHEAT_DONE.clear()


def get_platform_load_data_cache(facility_code: str) -> Dict[str, object] | None:
    code = str(facility_code or "").strip()
    if not code:
        return None
    with _PLATFORM_LOAD_DATA_CACHE_LOCK:
        payload = _PLATFORM_LOAD_DATA_CACHE.get(code)
        return deepcopy(payload) if payload is not None else None


def store_platform_load_data_cache(payload: Dict[str, object]) -> None:
    code = str(payload.get("facility_code") or "").strip()
    if not code:
        return
    with _PLATFORM_LOAD_DATA_CACHE_LOCK:
        _PLATFORM_LOAD_DATA_CACHE[code] = deepcopy(payload)


def preheat_platform_load_data(force: bool = False) -> bool:
    global _PLATFORM_LOAD_DATA_PREHEAT_IN_PROGRESS

    platform_defaults = dict(default_platform())
    facility_code = str(platform_defaults.get("facility_code") or "").strip()
    if not facility_code:
        return False

    with _PLATFORM_LOAD_DATA_CACHE_LOCK:
        if facility_code in _PLATFORM_LOAD_DATA_CACHE and not force:
            return True
        if _PLATFORM_LOAD_DATA_PREHEAT_IN_PROGRESS and not force:
            should_wait = True
        else:
            should_wait = False
            _PLATFORM_LOAD_DATA_PREHEAT_IN_PROGRESS = True
            _PLATFORM_LOAD_DATA_PREHEAT_DONE.clear()

    if should_wait:
        return _PLATFORM_LOAD_DATA_PREHEAT_DONE.wait(3)

    try:
        payload = load_platform_load_payload(facility_code, platform_defaults)
        store_platform_load_data_cache(payload)
        return True
    except Exception:
        return False
    finally:
        with _PLATFORM_LOAD_DATA_CACHE_LOCK:
            _PLATFORM_LOAD_DATA_PREHEAT_IN_PROGRESS = False
            _PLATFORM_LOAD_DATA_PREHEAT_DONE.set()
