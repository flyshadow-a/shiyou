"""
当member_group_summary_parser数据提取好后，整体封装起来
"""

from __future__ import annotations

from typing import Any, Mapping
from typing import TypedDict


class MemberSummary(TypedDict):
    code_name: str
    max_uc: float
    max_member: str
    max_group_id: str
    max_case: str
    max_position: str
    is_pass: bool
    is_pass_text: str
    summary_text: str
    summary_table_row: dict


def build_member_summary(member_group_summary: Mapping[str, Any]) -> MemberSummary:
    """
    基于 member_group_summary_parser 的输出，生成 4.5.1 摘要信息。
    依赖字段：
    - code_name
    - rows: [{group_id, member, cond, unity_check, ...}]
    """
    rows = member_group_summary.get("rows", [])
    code_name = member_group_summary.get("code_name", "").strip()

    if not rows:
        return {
            "code_name": code_name,
            "max_uc": 0.0,
            "max_member": "",
            "max_group_id": "",
            "max_case": "",
            "max_position": "",
            "is_pass": False,
            "is_pass_text": "无数据",
            "summary_text": "未读取到构件名义应力校核结果，无法生成摘要。",
            "summary_table_row": {
                "check_item": "构件",
                "position": "",
                "value": "",
                "case": "",
                "is_pass": "无数据",
            },
        }

    max_row = max(rows, key=lambda x: x["unity_check"])
    max_uc = float(max_row["unity_check"])
    max_member = max_row["member"]
    max_group_id = max_row["group_id"]
    max_case = max_row["cond"]

    # 这里先按 UC < 1.0 判定是否满足
    is_pass = max_uc < 1.0
    is_pass_text = "满足" if is_pass else "不满足"

    # “位置”字段你可以后续改成更想展示的形式
    max_position = max_member

    if code_name:
        summary_text = (
            f"根据{code_name}进行名义应力校核。"
            f"构件名义应力校核最大UC值为{max_uc:.2f}，"
            f"对应位置为{max_position}，"
            f"对应工况为{max_case}，{is_pass_text}UC小于1.0的要求。"
        )
    else:
        summary_text = (
            f"构件名义应力校核最大UC值为{max_uc:.2f}，"
            f"对应位置为{max_member}（组号{max_group_id}），"
            f"对应工况为{max_case}，{is_pass_text}UC小于1.0的要求。"
        )

    return {
        "code_name": code_name,
        "max_uc": max_uc,
        "max_member": max_member,
        "max_group_id": max_group_id,
        "max_case": max_case,
        "max_position": max_position,
        "is_pass": is_pass,
        "is_pass_text": is_pass_text,
        "summary_text": summary_text,
        "summary_table_row": {
            "check_item": "构件",
            "position": max_position,
            "value": f"{max_uc:.2f}",
            "case": max_case,
            "is_pass": is_pass_text,
        },
    }
