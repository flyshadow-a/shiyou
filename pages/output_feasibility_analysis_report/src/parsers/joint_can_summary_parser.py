"""
4.5.2 节点冲剪应力校核
"""

from __future__ import annotations

import re
from typing import TypedDict

from .block_utils import extract_block, find_first_index, find_next_index, join_block


NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"


class JointCanSummaryRow(TypedDict):
    joint: str
    orig_diameter: float
    orig_thickness: float
    orig_yld_strs: float
    orig_load_uc: float
    orig_strn_uc: float
    design_diameter: float
    design_thickness: float
    design_yld_strs: float
    design_load_uc: float
    design_strn_uc: float
    brace_joint: str
    load_case: str


class JointCanSummaryResult(TypedDict):
    section_name: str
    marker: str
    code_name: str
    raw_block: str
    rows: list[JointCanSummaryRow]


START_MARKER = "J O I N T   C A N   S U M M A R Y"
END_MARKERS = [
    "P I L E  G R O U P",
    "PILE GROUP SUMMARY",
    "P I L E   G R O U P",
]

ROW_PATTERN = re.compile(
    rf"""
    ^\s*
    (?P<joint>\S+)\s+
    (?P<orig_diameter>{NUM})\s+
    (?P<orig_thickness>{NUM})\s+
    (?P<orig_yld_strs>{NUM})\s+
    (?P<orig_load_uc>{NUM})\s+
    (?P<orig_strn_uc>{NUM})\s+
    (?P<design_diameter>{NUM})\s+
    (?P<design_thickness>{NUM})\s+
    (?P<design_yld_strs>{NUM})\s+
    (?P<design_load_uc>{NUM})\s+
    (?P<design_strn_uc>{NUM})\s+
    (?P<brace_joint>\S+)\s+
    (?P<load_case>\S+)
    \s*$
    """,
    re.VERBOSE,
)


def _to_float(value: str) -> float:
    return float(value.strip())


def _extract_code_name(block_lines: list[str]) -> str:
    """
    JOINT CAN SUMMARY 在示例片段里不一定显式带规范名。
    这里优先尝试读取包含 API/AISC/RP2A 的行，读不到则返回空字符串。
    """
    for line in block_lines[1:10]:
        text = line.strip()
        if not text:
            continue

        upper_text = text.upper()
        if "API" in upper_text or "AISC" in upper_text or "RP2A" in upper_text:
            return text

    return ""


def _is_header_or_noise(line: str) -> bool:
    text = line.strip().upper()

    if not text:
        return True

    if text.startswith("SACS CONNECT EDITION"):
        return True
    if "DATE " in text and "PAGE " in text:
        return True

    if text.startswith("(UNITY CHECK ORDER)"):
        return True
    if "ORIGINAL" in text and "LOAD DESIGN" in text:
        return True
    if text.startswith("JOINT DIAMETER THICKNESS"):
        return True
    if "(CM)" in text and "(N/MM2)" in text:
        return True
    if "LOAD    STRN" in text and "JOINT   CASE" in text:
        return True

    return False


def _parse_rows(block_lines: list[str]) -> list[JointCanSummaryRow]:
    rows: list[JointCanSummaryRow] = []

    for line in block_lines:
        if _is_header_or_noise(line):
            continue

        match = ROW_PATTERN.match(line)
        if not match:
            continue

        rows.append(
            {
                "joint": match.group("joint").strip(),
                "orig_diameter": _to_float(match.group("orig_diameter")),
                "orig_thickness": _to_float(match.group("orig_thickness")),
                "orig_yld_strs": _to_float(match.group("orig_yld_strs")),
                "orig_load_uc": _to_float(match.group("orig_load_uc")),
                "orig_strn_uc": _to_float(match.group("orig_strn_uc")),
                "design_diameter": _to_float(match.group("design_diameter")),
                "design_thickness": _to_float(match.group("design_thickness")),
                "design_yld_strs": _to_float(match.group("design_yld_strs")),
                "design_load_uc": _to_float(match.group("design_load_uc")),
                "design_strn_uc": _to_float(match.group("design_strn_uc")),
                "brace_joint": match.group("brace_joint").strip(),
                "load_case": match.group("load_case").strip(),
            }
        )

    return rows


def parse_joint_can_summary(lines: list[str]) -> JointCanSummaryResult:
    start_index = find_first_index(lines, START_MARKER)
    block_lines = extract_block(
        lines=lines,
        start_marker=START_MARKER,
        end_markers=END_MARKERS,
        include_start=True,
    )

    raw_block_lines = block_lines
    if start_index != -1:
        raw_end_index = find_next_index(lines, [START_MARKER] + END_MARKERS, start_index + 1)
        if raw_end_index != -1:
            raw_block_lines = lines[start_index:raw_end_index]

    raw_block = join_block(raw_block_lines)
    code_name = _extract_code_name(block_lines)
    rows = _parse_rows(block_lines)

    return {
        "section_name": "joint_can_summary",
        "marker": START_MARKER,
        "code_name": code_name,
        "raw_block": raw_block,
        "rows": rows,
    }
