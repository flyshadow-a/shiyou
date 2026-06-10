from __future__ import annotations

import unicodedata
import sys
from typing import Any

from services.inspection_business_db_adapter import list_facility_profiles
from services.platform_summary_source import load_platform_summary_source


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
CASCADE_GROUP_FIELDS = ("branch", "op_company", "oilfield")
PROFILE_DETAIL_FIELDS = ("facility_type", "category", "start_time", "design_life")
DEFAULT_FIELD_STRETCH = {
    "branch": 1,
    "op_company": 2,
    "oilfield": 2,
    "facility_code": 2,
    "facility_name": 3,
    "facility_type": 1,
    "category": 1,
    "start_time": 1,
    "design_life": 1,
}
_PLATFORM_PROFILES_CACHE: list[dict[str, str]] | None = None

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


def _load_platform_profiles_from_source() -> list[dict[str, str]]:
    selected_profiles: list[dict[str, str]] = []
    try:
        summary_source = load_platform_summary_source()
        selected_profiles = _normalize_profiles(summary_source.profiles)
    except Exception:
        selected_profiles = []

    if not selected_profiles:
        try:
            selected_profiles = _normalize_profiles(list_facility_profiles())
        except Exception:
            selected_profiles = []

    return selected_profiles or [dict(profile) for profile in FILE_MANAGEMENT_PLATFORMS]


def _copy_profiles(profiles: list[dict[str, str]]) -> list[dict[str, str]]:
    return [dict(profile) for profile in profiles]


def clear_platform_profiles_cache() -> None:
    global _PLATFORM_PROFILES_CACHE
    _PLATFORM_PROFILES_CACHE = None


def _clear_oilfield_top_data_cache_if_loaded() -> None:
    module = sys.modules.get("pages.oilfield_water_level_page")
    clear_cache = getattr(module, "clear_oilfield_top_data_cache", None) if module is not None else None
    if callable(clear_cache):
        clear_cache()


def refresh_platform_profiles_cache() -> list[dict[str, str]]:
    global _PLATFORM_PROFILES_CACHE
    _PLATFORM_PROFILES_CACHE = _load_platform_profiles_from_source()
    _clear_oilfield_top_data_cache_if_loaded()
    return _copy_profiles(_PLATFORM_PROFILES_CACHE)


def platform_profiles() -> list[dict[str, str]]:
    global _PLATFORM_PROFILES_CACHE
    if _PLATFORM_PROFILES_CACHE is None:
        _PLATFORM_PROFILES_CACHE = _load_platform_profiles_from_source()
    return _copy_profiles(_PLATFORM_PROFILES_CACHE)


def _normalize_profiles(raw_profiles: list[dict[str, Any]]) -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    for raw_profile in raw_profiles or []:
        profile = _normalize_profile(raw_profile)
        code = profile["facility_code"]
        if not code or code in seen_codes:
            continue
        if not profile["facility_name"]:
            profile["facility_name"] = code
        profiles.append(profile)
        seen_codes.add(code)
    return profiles


def platform_codes() -> list[str]:
    return [item["facility_code"] for item in platform_profiles()]


def platform_names() -> list[str]:
    return [item["facility_name"] for item in platform_profiles()]


def apply_platform_defaults_to_fields(
    fields: list[dict[str, Any]],
    platform: dict[str, str] | None = None,
) -> None:
    platform_defaults = dict(platform or default_platform())
    field_map = {item.get("key"): item for item in fields}
    field_values = {
        "branch": platform_defaults.get("branch", ""),
        "op_company": platform_defaults.get("op_company", ""),
        "oilfield": platform_defaults.get("oilfield", ""),
        "facility_code": platform_defaults.get("facility_code", ""),
        "facility_name": platform_defaults.get("facility_name", ""),
        "facility_type": platform_defaults.get("facility_type", ""),
        "category": platform_defaults.get("category", ""),
        "start_time": platform_defaults.get("start_time", ""),
        "design_life": platform_defaults.get("design_life", ""),
    }
    for key, value in field_values.items():
        if key == "facility_code":
            options = platform_codes()
        elif key == "facility_name":
            options = platform_names()
        else:
            options = [value] if value else []
        if value and value not in options:
            options = [value, *options]
        for target_key in FIELD_ALIASES.get(key, (key,)):
            item = field_map.get(target_key)
            if item is None:
                continue
            item["options"] = options
            item["default"] = value
            item.setdefault("stretch", DEFAULT_FIELD_STRETCH.get(key, 1))


def default_platform() -> dict[str, str]:
    profiles = platform_profiles()
    return dict(profiles[0] if profiles else FILE_MANAGEMENT_PLATFORMS[0])


def find_platform(*, facility_code: str | None = None, facility_name: str | None = None) -> dict[str, str]:
    code = _match_key(facility_code)
    name = _match_key(facility_name)
    for item in platform_profiles():
        if code and _match_key(item["facility_code"]) == code:
            return dict(item)
        if name and _match_key(item["facility_name"]) == name:
            return dict(item)
    return default_platform()


def _dropdown_value(dropdown_bar: Any, key: str) -> str:
    try:
        return str(dropdown_bar.get_value(key) or "").strip()
    except Exception:
        return ""


def _match_key(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.strip().lower().split())


def _canonical_field(key: str | None) -> str:
    return ALIAS_TO_FIELD.get(key or "", key or "")


def _profile_default(profiles: list[dict[str, str]]) -> dict[str, str]:
    return dict(profiles[0] if profiles else FILE_MANAGEMENT_PLATFORMS[0])


def _field_aliases(field_key: str) -> tuple[str, ...]:
    return FIELD_ALIASES.get(field_key, (field_key,))


def _dropdown_value_for_field(dropdown_bar: Any, field_key: str, changed_key: str | None = None) -> str:
    if changed_key and _canonical_field(changed_key) == field_key:
        changed_value = _dropdown_value(dropdown_bar, changed_key)
        if changed_value:
            return changed_value

    for target_key in _field_aliases(field_key):
        value = _dropdown_value(dropdown_bar, target_key)
        if value:
            return value
    return ""


def _profile_matches(profile: dict[str, str], criteria: dict[str, str]) -> bool:
    for key, expected in criteria.items():
        normalized_expected = _match_key(expected)
        if not normalized_expected:
            continue
        actual = _match_key(profile.get(key))
        if actual != normalized_expected:
            return False
    return True


def _filter_profiles(profiles: list[dict[str, str]], criteria: dict[str, str]) -> list[dict[str, str]]:
    return [profile for profile in profiles if _profile_matches(profile, criteria)]


def _find_first_profile(profiles: list[dict[str, str]], criteria: dict[str, str]) -> dict[str, str] | None:
    for profile in profiles:
        if _profile_matches(profile, criteria):
            return dict(profile)
    return None


def _find_platform_by_field(
    profiles: list[dict[str, str]],
    field_key: str,
    value: str,
) -> dict[str, str] | None:
    normalized = _match_key(value)
    if not normalized:
        return None
    for profile in profiles:
        if _match_key(profile.get(field_key)) == normalized:
            return dict(profile)
    return None


def _select_platform(
    dropdown_bar: Any,
    changed_key: str | None,
    profiles: list[dict[str, str]],
) -> dict[str, str]:
    default = _profile_default(profiles)
    canonical_key = _canonical_field(changed_key)

    if canonical_key == "facility_name":
        value = _dropdown_value_for_field(dropdown_bar, "facility_name", changed_key)
        return _find_platform_by_field(profiles, "facility_name", value) or default

    if canonical_key == "facility_code":
        value = _dropdown_value_for_field(dropdown_bar, "facility_code", changed_key)
        return _find_platform_by_field(profiles, "facility_code", value) or default

    if canonical_key in CASCADE_GROUP_FIELDS:
        criteria: dict[str, str] = {}
        for field_key in CASCADE_GROUP_FIELDS:
            criteria[field_key] = _dropdown_value_for_field(dropdown_bar, field_key, changed_key)
            if field_key == canonical_key:
                break

        matched = _find_first_profile(profiles, criteria)
        if matched is not None:
            return matched

        changed_value = criteria.get(canonical_key, "")
        if changed_value:
            matched = _find_platform_by_field(profiles, canonical_key, changed_value)
            if matched is not None:
                return matched

    current_code = _dropdown_value_for_field(dropdown_bar, "facility_code")
    matched = _find_platform_by_field(profiles, "facility_code", current_code)
    if matched is not None:
        return matched

    current_name = _dropdown_value_for_field(dropdown_bar, "facility_name")
    matched = _find_platform_by_field(profiles, "facility_name", current_name)
    if matched is not None:
        return matched

    hierarchy = {
        field_key: _dropdown_value_for_field(dropdown_bar, field_key)
        for field_key in CASCADE_GROUP_FIELDS
    }
    matched = _find_first_profile(profiles, hierarchy)
    if matched is not None:
        return matched

    return default


def _unique_profile_values(profiles: list[dict[str, str]], key: str) -> list[str]:
    values: list[str] = []
    seen = set()
    for profile in profiles:
        value = str(profile.get(key) or "").strip()
        if (not value) or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return values


def _field_options(profiles: list[dict[str, str]], key: str, default: str) -> list[str]:
    options = _unique_profile_values(profiles, key)
    if default and default not in options:
        options.insert(0, default)
    if (not options) and default:
        options = [default]
    return options


def _set_profile_field_options(
    dropdown_bar: Any,
    key: str,
    default: str,
    aliases: tuple[str, ...] = (),
    *,
    profiles: list[dict[str, str]],
) -> None:
    options = _field_options(profiles, key, default)
    for target_key in aliases or (key,):
        dropdown_bar.set_options(target_key, options, default)


def _contexts_for_platform(
    profiles: list[dict[str, str]],
    platform: dict[str, str],
) -> dict[str, list[dict[str, str]]]:
    branch_profiles = profiles
    company_profiles = _filter_profiles(branch_profiles, {"branch": platform.get("branch", "")})
    oilfield_profiles = _filter_profiles(
        company_profiles,
        {
            "branch": platform.get("branch", ""),
            "op_company": platform.get("op_company", ""),
        },
    )
    facility_profiles = _filter_profiles(
        oilfield_profiles,
        {
            "branch": platform.get("branch", ""),
            "op_company": platform.get("op_company", ""),
            "oilfield": platform.get("oilfield", ""),
        },
    )
    selected_profiles = _filter_profiles(
        facility_profiles,
        {
            "branch": platform.get("branch", ""),
            "op_company": platform.get("op_company", ""),
            "oilfield": platform.get("oilfield", ""),
            "facility_code": platform.get("facility_code", ""),
        },
    )
    return {
        "branch": branch_profiles,
        "op_company": company_profiles or branch_profiles,
        "oilfield": oilfield_profiles or company_profiles or branch_profiles,
        "facility_code": facility_profiles or oilfield_profiles or company_profiles or branch_profiles,
        "facility_name": selected_profiles or facility_profiles or oilfield_profiles or company_profiles or branch_profiles,
        "details": selected_profiles or facility_profiles or oilfield_profiles or company_profiles or branch_profiles,
    }


def sync_platform_dropdowns(dropdown_bar: Any, *, changed_key: str | None = None) -> dict[str, str]:
    profiles = platform_profiles()
    platform = _select_platform(dropdown_bar, changed_key, profiles)
    contexts = _contexts_for_platform(profiles, platform)

    for key in CASCADE_GROUP_FIELDS:
        if key in platform:
            _set_profile_field_options(
                dropdown_bar,
                key,
                platform[key],
                FIELD_ALIASES.get(key, (key,)),
                profiles=contexts[key],
            )

    dropdown_bar.set_options(
        "facility_code",
        _field_options(contexts["facility_code"], "facility_code", platform["facility_code"]),
        platform["facility_code"],
    )
    dropdown_bar.set_options(
        "facility_name",
        _field_options(contexts["facility_name"], "facility_name", platform["facility_name"]),
        platform["facility_name"],
    )

    for key in PROFILE_DETAIL_FIELDS:
        if key in platform:
            _set_profile_field_options(
                dropdown_bar,
                key,
                platform[key],
                FIELD_ALIASES.get(key, (key,)),
                profiles=contexts["details"],
            )
    return platform
