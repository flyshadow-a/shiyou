"""
组合工况描述
"""

from __future__ import annotations

from typing import TypedDict

from .block_utils import extract_block


class ComboCaseDescRow(TypedDict):
    case: int
    label: str
    desc: str


START_MARKER = "SEASTATE COMBINED LOAD CASES"
END_MARKERS = [
    "SEASTATE COMBINED LOAD CASE SUMMARY",
    "M E M B E R  G R O U P  S U M M A R Y",
    "J O I N T   C A N   S U M M A R Y",
]


def _is_new_case_line(line: str) -> bool:
    return line[:12].strip().isdigit()


def _parse_new_case_line(line: str) -> tuple[int, str]:
    return int(line[:12].strip()), line[14:18].strip()


def _parse_vba_detail_part(line: str) -> str:
    load_label = line[:27].strip()
    percent_text = line[32:38].strip()
    if not load_label or line[:12].strip():
        return ""
    if line.strip()[-1:].isdigit():
        return ""
    if not percent_text:
        return ""
    try:
        factor = float(percent_text) / 100
    except ValueError:
        return ""
    return f"{load_label}*{factor:.3f}"


def parse_combo_case_desc(lines: list[str]) -> list[ComboCaseDescRow]:
    """
    解析 SACS 的 SEASTATE COMBINED LOAD CASES 块。

    这里按 ReadPSIlist.xlsm 中 LCComb 的 VBA 规则读取：
    - 前 12 列为数字时开始一个新组合工况；
    - 后续缩进行按前 27 列基本工况名、33-38 列百分比拼接描述；
    - 百分比除以 100 后保留三位小数，多个基本工况用 + 连接。
    """
    block = extract_block(
        lines=lines,
        start_marker=START_MARKER,
        end_markers=END_MARKERS,
        include_start=False,
    )

    rows: list[ComboCaseDescRow] = []
    current_row: ComboCaseDescRow | None = None
    for line in block:
        if _is_new_case_line(line):
            case, label = _parse_new_case_line(line)
            current_row = {
                "case": case,
                "label": label,
                "desc": "",
            }
            rows.append(current_row)
            continue

        if current_row is None:
            continue

        detail_part = _parse_vba_detail_part(line)
        if not detail_part:
            continue
        if current_row["desc"]:
            current_row["desc"] += "+" + detail_part
        else:
            current_row["desc"] = detail_part

    return rows
