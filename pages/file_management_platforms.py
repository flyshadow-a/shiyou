from __future__ import annotations

from typing import Any

from services.inspection_business_db_adapter import list_facility_profiles


ALLOWED_FACILITY_CODES = ("WC19-1D", "WC9-7")
FIELD_ALIASES = {
    "branch": ("branch", "division"),
    "op_company": ("op_company", "company"),
    "oilfield": ("oilfield", "field"),
    "design_life": ("design_life", "design_years"),
}
ALIAS_TO_FIELD = {
    alias: field
    for field, aliases in FIELD_ALIASES.items()
    for alias in aliases
}

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


def _normalize_profile(raw_profile: dict[str, Any]) -> dict[str, str]:
    return {
        "facility_code": str(raw_profile.get("facility_code") or "").strip(),
        "facility_name": str(raw_profile.get("facility_name") or "").strip(),
        "branch": str(raw_profile.get("branch") or "").strip(),
        "op_company": str(raw_profile.get("op_company") or "").strip(),
        "oilfield": str(raw_profile.get("oilfield") or "").strip(),
        "facility_type": str(raw_profile.get("facility_type") or "").strip(),
        "category": str(raw_profile.get("category") or "").strip(),
        "start_time": str(raw_profile.get("start_time") or "").strip(),
        "design_life": str(raw_profile.get("design_life") or "").strip(),
    }


def platform_profiles() -> list[dict[str, str]]:
    fallback_by_code = {
        profile["facility_code"]: dict(profile)
        for profile in FILE_MANAGEMENT_PLATFORMS
    }
    selected_by_code: dict[str, dict[str, str]] = {}

    try:
        db_profiles = list_facility_profiles()
    except Exception:
        db_profiles = []

    for raw_profile in db_profiles:
        profile = _normalize_profile(raw_profile)
        code = profile["facility_code"]
        if code in ALLOWED_FACILITY_CODES:
            selected_by_code[code] = {
                **fallback_by_code.get(code, {}),
                **{key: value for key, value in profile.items() if value},
            }

    for code in ALLOWED_FACILITY_CODES:
        if code not in selected_by_code and code in fallback_by_code:
            selected_by_code[code] = dict(fallback_by_code[code])

    return [
        selected_by_code[code]
        for code in ALLOWED_FACILITY_CODES
        if code in selected_by_code
    ]


def platform_codes() -> list[str]:
    return [item["facility_code"] for item in platform_profiles()]


def platform_names() -> list[str]:
    return [item["facility_name"] for item in platform_profiles()]


def default_platform() -> dict[str, str]:
    profiles = platform_profiles()
    return dict(profiles[0] if profiles else FILE_MANAGEMENT_PLATFORMS[0])


def find_platform(*, facility_code: str | None = None, facility_name: str | None = None) -> dict[str, str]:
    code = (facility_code or "").strip().lower()
    name = (facility_name or "").strip().lower()
    for item in platform_profiles():
        if code and item["facility_code"].lower() == code:
            return dict(item)
        if name and item["facility_name"].lower() == name:
            return dict(item)
    return default_platform()


def _dropdown_value(dropdown_bar: Any, key: str) -> str:
    try:
        return str(dropdown_bar.get_value(key) or "").strip()
    except Exception:
        return ""


def _find_platform_by_field(field_key: str, value: str) -> dict[str, str] | None:
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    for profile in platform_profiles():
        if str(profile.get(field_key) or "").strip().lower() == normalized:
            return dict(profile)
    return None


def _select_platform(dropdown_bar: Any, changed_key: str | None) -> dict[str, str]:
    if changed_key == "facility_name":
        return find_platform(facility_name=_dropdown_value(dropdown_bar, "facility_name"))

    profile_key = ALIAS_TO_FIELD.get(changed_key or "", changed_key or "")
    if profile_key in {"branch", "op_company", "oilfield", "facility_type", "category", "start_time", "design_life"}:
        changed_value = _dropdown_value(dropdown_bar, changed_key or "")
        matched = _find_platform_by_field(profile_key, changed_value)
        if matched is not None:
            return matched

    return find_platform(facility_code=_dropdown_value(dropdown_bar, "facility_code"))


def _unique_profile_values(key: str) -> list[str]:
    values: list[str] = []
    seen = set()
    for profile in platform_profiles():
        value = str(profile.get(key) or "").strip()
        if (not value) or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _set_profile_field_options(dropdown_bar: Any, key: str, default: str, aliases: tuple[str, ...] = ()) -> None:
    options = _unique_profile_values(key)
    if default and default not in options:
        options.insert(0, default)
    for target_key in aliases or (key,):
        dropdown_bar.set_options(target_key, options or ([default] if default else []), default)


def sync_platform_dropdowns(dropdown_bar: Any, *, changed_key: str | None = None) -> dict[str, str]:
    platform = _select_platform(dropdown_bar, changed_key)

    dropdown_bar.set_options("facility_code", platform_codes(), platform["facility_code"])
    dropdown_bar.set_options("facility_name", platform_names(), platform["facility_name"])

    for key in ("branch", "op_company", "oilfield", "facility_type", "category", "start_time", "design_life"):
        if key in platform:
            _set_profile_field_options(dropdown_bar, key, platform[key], FIELD_ALIASES.get(key, (key,)))
    return platform
