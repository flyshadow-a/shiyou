# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.inspection_business_db_adapter import (
    list_facility_profiles,
    load_platform_summary_snapshot,
)


@dataclass(frozen=True)
class PlatformSummarySource:
    source: str
    profiles: list[dict[str, Any]]
    snapshot: dict[str, Any] | None = None


PROFILE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "facility_code": ("设施编码", "设施编号", "平台编码", "平台编号", "编码"),
    "facility_name": ("设施名称", "平台名称"),
    "branch": ("分公司", "所属分公司"),
    "op_company": ("作业公司", "所属作业单元", "所属作业公司", "作业单元", "作业单位"),
    "oilfield": ("油气田", "所属油（气）田", "所属油气田"),
    "facility_type": ("设施类型", "平台类型"),
    "category": ("分类", "平台分类"),
    "start_time": ("投产时间", "投产日期", "投产年月"),
    "design_life": ("设计年限", "设计寿命"),
}


def snapshot_has_rows(snapshot: dict[str, Any] | None) -> bool:
    if not snapshot:
        return False
    columns = snapshot.get("columns") or []
    rows = snapshot.get("rows") or []
    return bool(columns and rows)


def profiles_from_platform_summary_snapshot(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not snapshot_has_rows(snapshot):
        return []

    columns = [str(col or "").strip() for col in (snapshot or {}).get("columns") or []]
    profiles: list[dict[str, Any]] = []
    for row in (snapshot or {}).get("rows") or []:
        values = list(row) if isinstance(row, list) else []
        source = {
            columns[index]: str(values[index] or "").strip()
            for index in range(min(len(columns), len(values)))
        }
        profile = {
            field_name: _snapshot_value(source, aliases)
            for field_name, aliases in PROFILE_FIELD_ALIASES.items()
        }
        if any(str(value or "").strip() for value in profile.values()):
            profiles.append(profile)
    return profiles


def load_platform_summary_source(*, snapshot_key: str = "latest") -> PlatformSummarySource:
    snapshot = load_platform_summary_snapshot(snapshot_key=snapshot_key)
    if snapshot_has_rows(snapshot):
        return PlatformSummarySource(
            source="snapshot",
            snapshot=snapshot,
            profiles=profiles_from_platform_summary_snapshot(snapshot),
        )
    return PlatformSummarySource(
        source="facility_profiles",
        snapshot=None,
        profiles=list_facility_profiles(),
    )


def _snapshot_value(source: dict[str, str], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        value = str(source.get(alias) or "").strip()
        if value:
            return value
    return ""
