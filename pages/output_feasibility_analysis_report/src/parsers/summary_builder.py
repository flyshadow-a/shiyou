"""
分析汇总信息装配
"""

from __future__ import annotations

from typing import Any, Mapping
from typing import TypedDict


class AnalysisSummaryItem(TypedDict):
    key: str
    check_item: str
    position: str
    value: str
    case: str
    is_pass: str


class AnalysisSummary(TypedDict):
    items: list[AnalysisSummaryItem]


def _normalize_item(key: str, summary_table_row: Mapping[str, Any]) -> AnalysisSummaryItem:
    return {
        "key": key,
        "check_item": str(summary_table_row.get("check_item", "")),
        "position": str(summary_table_row.get("position", "")),
        "value": str(summary_table_row.get("value", "")),
        "case": str(summary_table_row.get("case", "")),
        "is_pass": str(summary_table_row.get("is_pass", "")),
    }


def build_analysis_summary(
    *,
    member_summary: Mapping[str, Any],
    joint_can_summary: Mapping[str, Any],
    pile_stress_summary: Mapping[str, Any],
    pile_axial_capacity_summary: Mapping[str, Any],
) -> AnalysisSummary:
    ordered_items = [
        ("member_uc", member_summary.get("summary_table_row", {})),
        ("joint_uc", joint_can_summary.get("summary_table_row", {})),
        ("pile_stress_uc", pile_stress_summary.get("summary_table_row", {})),
        (
            "pile_comp_op",
            pile_axial_capacity_summary.get("operation_compression", {}).get(
                "summary_table_row", {}
            ),
        ),
        (
            "pile_tens_op",
            pile_axial_capacity_summary.get("operation_tension", {}).get(
                "summary_table_row", {}
            ),
        ),
        (
            "pile_comp_ext",
            pile_axial_capacity_summary.get("extreme_compression", {}).get(
                "summary_table_row", {}
            ),
        ),
        (
            "pile_tens_ext",
            pile_axial_capacity_summary.get("extreme_tension", {}).get(
                "summary_table_row", {}
            ),
        ),
    ]

    return {
        "items": [_normalize_item(key, row) for key, row in ordered_items],
    }
