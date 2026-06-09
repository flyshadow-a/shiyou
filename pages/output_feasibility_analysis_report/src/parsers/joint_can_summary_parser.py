"""
4.5.2 节点冲剪应力校核
"""

from __future__ import annotations

import re
from typing import TypedDict

from .block_utils import find_next_index, join_block


NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"


class JointCanSummaryRow(TypedDict):
    joint: str
    orig_diameter: float
    orig_thickness: float
    orig_yld_strs: float
    orig_load_uc: float | None
    orig_strn_uc: float | None
    design_diameter: float
    design_thickness: float
    design_yld_strs: float
    design_load_uc: float | None
    design_strn_uc: float | None
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


def _to_optional_float(value: str) -> float | None:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _mid(line: str, start: int, length: int) -> str:
    index = max(0, start - 1)
    return line[index : index + length]


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


def _has_strength_uc_columns(block_lines: list[str]) -> bool:
    for line in block_lines[:20]:
        text = line.upper()
        if "STRN" in text and "LOAD" in text:
            return True
    return False


def _parse_rows(block_lines: list[str]) -> list[JointCanSummaryRow]:
    rows: list[JointCanSummaryRow] = []
    has_strength_uc = _has_strength_uc_columns(block_lines)

    for line in block_lines:
        if _is_header_or_noise(line):
            continue

        if has_strength_uc:
            joint = _mid(line, 1, 5).strip()
            orig_load_uc = _to_optional_float(_mid(line, 36, 6))
            orig_strn_uc = _to_optional_float(_mid(line, 44, 6))
            if not joint or orig_load_uc is None:
                continue
        else:
            joint = _mid(line, 1, 9).strip()
            orig_load_uc = _to_optional_float(_mid(line, 48, 5))
            orig_strn_uc = None
            if not joint or orig_load_uc is None:
                continue

        tokens = line.split()
        load_case = tokens[-1] if tokens else ""
        brace_joint = tokens[-2] if len(tokens) >= 2 and has_strength_uc else ""

        match = ROW_PATTERN.match(line)
        if match:
            orig_diameter = _to_float(match.group("orig_diameter"))
            orig_thickness = _to_float(match.group("orig_thickness"))
            orig_yld_strs = _to_float(match.group("orig_yld_strs"))
            design_diameter = _to_float(match.group("design_diameter"))
            design_thickness = _to_float(match.group("design_thickness"))
            design_yld_strs = _to_float(match.group("design_yld_strs"))
            design_load_uc = _to_float(match.group("design_load_uc"))
            design_strn_uc = _to_float(match.group("design_strn_uc"))
            brace_joint = match.group("brace_joint").strip()
            load_case = match.group("load_case").strip()
        else:
            orig_diameter = 0.0
            orig_thickness = 0.0
            orig_yld_strs = 0.0
            design_diameter = 0.0
            design_thickness = 0.0
            design_yld_strs = 0.0
            design_load_uc = orig_load_uc
            design_strn_uc = orig_strn_uc

        rows.append(
            {
                "joint": joint,
                "orig_diameter": orig_diameter,
                "orig_thickness": orig_thickness,
                "orig_yld_strs": orig_yld_strs,
                "orig_load_uc": orig_load_uc,
                "orig_strn_uc": orig_strn_uc,
                "design_diameter": design_diameter,
                "design_thickness": design_thickness,
                "design_yld_strs": design_yld_strs,
                "design_load_uc": design_load_uc,
                "design_strn_uc": design_strn_uc,
                "brace_joint": brace_joint,
                "load_case": load_case,
            }
        )

    return rows


def _extract_unity_check_block(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        if START_MARKER not in line:
            continue

        lookahead = lines[index + 1 : index + 4]
        if not any("(UNITY CHECK ORDER)" in item.upper() for item in lookahead):
            continue

        end_idx = find_next_index(lines, END_MARKERS, index + 1)
        if end_idx == -1:
            return lines[index:]
        return lines[index:end_idx]

    return []


def parse_joint_can_summary(lines: list[str]) -> JointCanSummaryResult:
    block_lines = _extract_unity_check_block(lines)

    raw_block = join_block(block_lines)
    code_name = _extract_code_name(block_lines)
    rows = _parse_rows(block_lines)

    return {
        "section_name": "joint_can_summary",
        "marker": START_MARKER,
        "code_name": code_name,
        "raw_block": raw_block,
        "rows": rows,
    }
