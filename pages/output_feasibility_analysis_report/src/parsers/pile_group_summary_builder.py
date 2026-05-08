"""
当pile_group_summary_builder.py数据提取后 ，在此装配
"""

from __future__ import annotations

from typing import Any, Mapping
from typing import TypedDict


class PileGroupSummaryBuilt(TypedDict):
    group_id: str
    max_uc: float
    max_pile_head_id: str
    max_case: str
    max_distance_from_pilehead: float
    max_position: str
    is_pass: bool
    is_pass_text: str
    summary_text: str
    summary_table_row: dict


def build_pile_group_summary(pile_group_summary: Mapping[str, Any]) -> PileGroupSummaryBuilt:
    rows = pile_group_summary.get("rows", [])
    group_id = pile_group_summary.get("group_id", "").strip()

    if not rows:
        return {
            "group_id": group_id,
            "max_uc": 0.0,
            "max_pile_head_id": "",
            "max_case": "",
            "max_distance_from_pilehead": 0.0,
            "max_position": "",
            "is_pass": False,
            "is_pass_text": "无数据",
            "summary_text": "未读取到桩应力校核结果，无法生成摘要。",
            "summary_table_row": {
                "check_item": "桩应力",
                "position": "",
                "value": "",
                "case": "",
                "is_pass": "无数据",
            },
        }

    max_row = max(rows, key=lambda x: x["maximum_unity_check"])
    max_uc = float(max_row["maximum_unity_check"])
    max_pile_head_id = max_row["pile_head_id"]
    max_case = max_row["critical_load_case"]
    max_distance_from_pilehead = float(max_row["distance_from_pilehead"])

    # 位置先只显示桩号，和你前面“位置只显示 L541-L542 / U535”的风格保持一致
    max_position = max_pile_head_id

    is_pass = max_uc < 1.0
    is_pass_text = "满足" if is_pass else "不满足"

    if group_id:
        summary_text = (
            f"桩应力校核最大UC值为{max_uc:.3f}，"
            f"对应位置为{max_position}，"
            f"对应工况为{max_case}，"
            f"所属桩组为{group_id}，{is_pass_text}UC小于1.0的要求。"
        )
    else:
        summary_text = (
            f"桩应力校核最大UC值为{max_uc:.3f}，"
            f"对应位置为{max_position}，"
            f"对应工况为{max_case}，{is_pass_text}UC小于1.0的要求。"
        )

    return {
        "group_id": group_id,
        "max_uc": max_uc,
        "max_pile_head_id": max_pile_head_id,
        "max_case": max_case,
        "max_distance_from_pilehead": max_distance_from_pilehead,
        "max_position": max_position,
        "is_pass": is_pass,
        "is_pass_text": is_pass_text,
        "summary_text": summary_text,
        "summary_table_row": {
            "check_item": "桩应力",
            "position": max_position,
            "value": f"{max_uc:.3f}",
            "case": max_case,
            "is_pass": is_pass_text,
        },
    }
