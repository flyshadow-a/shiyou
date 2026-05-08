"""
当joint_can_summary_parser数据提取好后，整体封装起来
"""

from __future__ import annotations

from typing import Any, Mapping
from typing import TypedDict


class JointCanSummaryBuilt(TypedDict):
    code_name: str
    max_uc: float
    max_joint: str
    max_case: str
    max_position: str
    is_pass: bool
    is_pass_text: str
    summary_text: str
    summary_table_row: dict


def build_joint_can_summary(joint_can_summary: Mapping[str, Any]) -> JointCanSummaryBuilt:
    """
    基于 joint_can_summary_parser 的输出，生成 4.5.2 摘要信息。

    当前默认采用 design_load_uc 作为“节点冲剪UC”的统计口径。
    若后续确认应使用其他列，可在此统一调整。
    """
    rows = joint_can_summary.get("rows", [])
    code_name = joint_can_summary.get("code_name", "").strip()

    if not rows:
        return {
            "code_name": code_name,
            "max_uc": 0.0,
            "max_joint": "",
            "max_case": "",
            "max_position": "",
            "is_pass": False,
            "is_pass_text": "无数据",
            "summary_text": "未读取到节点冲剪应力校核结果，无法生成摘要。",
            "summary_table_row": {
                "check_item": "节点冲剪",
                "position": "",
                "value": "",
                "case": "",
                "is_pass": "无数据",
            },
        }

    # 口径：优先 design_load_uc
    max_row = max(rows, key=lambda x: x["design_load_uc"])
    max_uc = float(max_row["design_load_uc"])
    max_joint = max_row["joint"]
    max_case = max_row["load_case"]
    max_position = max_joint

    is_pass = max_uc < 1.0
    is_pass_text = "满足" if is_pass else "不满足"

    if code_name:
        summary_text = (
            f"根据{code_name}进行冲剪应力校核。"
            f"节点冲剪应力校核最大UC值为{max_uc:.3f}，"
            f"对应位置为{max_position}，"
            f"对应工况为{max_case}，{is_pass_text}UC小于1.0的要求。"
        )
    else:
        summary_text = (
            f"节点冲剪应力校核最大UC值为{max_uc:.3f}，"
            f"对应位置为{max_position}，"
            f"对应工况为{max_case}，{is_pass_text}UC小于1.0的要求。"
        )

    return {
        "code_name": code_name,
        "max_uc": max_uc,
        "max_joint": max_joint,
        "max_case": max_case,
        "max_position": max_position,
        "is_pass": is_pass,
        "is_pass_text": is_pass_text,
        "summary_text": summary_text,
        "summary_table_row": {
            "check_item": "节点冲剪",
            "position": max_position,
            "value": f"{max_uc:.3f}",
            "case": max_case,
            "is_pass": is_pass_text,
        },
    }
