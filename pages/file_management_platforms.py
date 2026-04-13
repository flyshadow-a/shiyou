from __future__ import annotations

from typing import Any


FILE_MANAGEMENT_PLATFORMS: list[dict[str, str]] = [
    {
        "facility_code": "WC19-1D",
        "facility_name": "WC19-1D平台",
        "branch": "湛江分公司",
        "op_company": "中海石油(中国)有限公司湛江分公司",
        "oilfield": "WC19-1油田",
        "facility_type": "平台",
        "category": "油气生产平台",
        "start_time": "2013-07-15",
        "design_life": "15",
    },
    {
        "facility_code": "WC9-7",
        "facility_name": "WC9-7平台",
        "branch": "湛江分公司",
        "op_company": "中海石油(中国)有限公司湛江分公司",
        "oilfield": "WC9-7油田",
        "facility_type": "平台",
        "category": "油气生产平台",
        "start_time": "2013-07-15",
        "design_life": "15",
    },
]


def platform_codes() -> list[str]:
    return [item["facility_code"] for item in FILE_MANAGEMENT_PLATFORMS]


def platform_names() -> list[str]:
    return [item["facility_name"] for item in FILE_MANAGEMENT_PLATFORMS]


def default_platform() -> dict[str, str]:
    return dict(FILE_MANAGEMENT_PLATFORMS[0])


def find_platform(*, facility_code: str | None = None, facility_name: str | None = None) -> dict[str, str]:
    code = (facility_code or "").strip().lower()
    name = (facility_name or "").strip().lower()
    for item in FILE_MANAGEMENT_PLATFORMS:
        if code and item["facility_code"].lower() == code:
            return dict(item)
        if name and item["facility_name"].lower() == name:
            return dict(item)
    return default_platform()


def _set_if_present(dropdown_bar: Any, key: str, value: str) -> None:
    try:
        current = dropdown_bar.get_value(key)
    except Exception:
        current = ""
    dropdown_bar.set_options(key, [value], value if value else current)


def sync_platform_dropdowns(dropdown_bar: Any, *, changed_key: str | None = None) -> dict[str, str]:
    current_code = dropdown_bar.get_value("facility_code")
    current_name = dropdown_bar.get_value("facility_name")
    platform = find_platform(
        facility_code=current_code if changed_key != "facility_name" else None,
        facility_name=current_name if changed_key == "facility_name" else None,
    )

    dropdown_bar.set_options("facility_code", platform_codes(), platform["facility_code"])
    dropdown_bar.set_options("facility_name", platform_names(), platform["facility_name"])

    for key in ("branch", "op_company", "oilfield", "facility_type", "category", "start_time", "design_life"):
        if key in platform:
            _set_if_present(dropdown_bar, key, platform[key])
    return platform
