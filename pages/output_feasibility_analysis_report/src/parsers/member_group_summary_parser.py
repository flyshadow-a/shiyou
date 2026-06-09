"""
4.5.1构件名义应力校核
"""

from __future__ import annotations

import re
from typing import TypedDict

from .block_utils import extract_block, join_block


NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"


class MemberGroupSummaryRow(TypedDict):
    group_id: str
    member: str
    cond: str
    unity_check: float
    from_end: float
    axial: float
    bend_y: float
    bend_z: float
    crit_cond: str


class MemberGroupSummaryResult(TypedDict):
    section_name: str
    marker: str
    code_name: str
    raw_block: str
    rows: list[MemberGroupSummaryRow]


START_MARKER = "M E M B E R  G R O U P  S U M M A R Y"
END_MARKERS = [
    "J O I N T   C A N   S U M M A R Y",
    "P I L E  G R O U P",
]

# 示例行：
# 1A1 601L-611L OP17   0.43   0.9    -54.5   33.1    1.8   .2E+03 .6E+06 .3E+03 .3E+03   HYDRO    0.92   0.92   0.85   0.85
ROW_PATTERN = re.compile(
    rf"""
    ^\s*
    (?P<group_id>\S+)\s+
    (?P<member>\S+)\s+
    (?P<cond>\S+)\s+
    (?P<unity_check>{NUM})\s+
    (?P<from_end>{NUM})\s+
    (?P<axial>{NUM})\s+
    (?P<bend_y>{NUM})\s+
    (?P<bend_z>{NUM})\s+
    (?P<allow_axial>{NUM})\s+
    (?P<allow_euler>{NUM})\s+
    (?P<allow_bend_y>{NUM})\s+
    (?P<allow_bend_z>{NUM})\s+
    (?P<crit_cond>\S+)\s+
    (?P<kly>{NUM})\s+
    (?P<klz>{NUM})\s+
    (?P<cm_y>{NUM})\s+
    (?P<cm_z>{NUM})
    \s*$
    """,
    re.VERBOSE,
)


def _to_float(value: str) -> float:
    return float(value.strip())


def _extract_code_name(block_lines: list[str]) -> str:
    if not block_lines:
        return ""

    for line in block_lines[1:]:
        text = line.strip()
        if not text:
            continue

        upper_text = text.upper()

        if "MAX." in upper_text and "UNITY" in upper_text:
            continue
        if "GRUP" in upper_text and "CRITICAL" in upper_text:
            continue
        if "N/MM2" in upper_text:
            continue
        if upper_text.startswith("* * *"):
            continue
        if upper_text.startswith("SACS CONNECT EDITION"):
            continue
        if "DATE " in upper_text and "PAGE " in upper_text:
            continue

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

    if "MAX." in text and "UNITY" in text:
        return True
    if "GRUP" in text and "CRITICAL" in text:
        return True
    if text.startswith("ID   MEMBER") or text.startswith("ID MEMBER"):
        return True
    if "N/MM2" in text:
        return True
    if "APPLIED STRESSES" in text:
        return True
    if "ALLOWABLE STRESSES" in text:
        return True
    if "EFFECTIVE" in text and "CM" in text:
        return True
    if "LENGTHS" in text and "VALUES" in text:
        return True

    return False


def _parse_rows(block_lines: list[str]) -> list[MemberGroupSummaryRow]:
    rows: list[MemberGroupSummaryRow] = []

    for line in block_lines:
        if _is_header_or_noise(line):
            continue

        match = ROW_PATTERN.match(line)
        if not match:
            continue

        rows.append(
            {
                "group_id": match.group("group_id").strip(),
                "member": match.group("member").strip(),
                "cond": match.group("cond").strip(),
                "unity_check": _to_float(match.group("unity_check")),
                "from_end": _to_float(match.group("from_end")),
                "axial": _to_float(match.group("axial")),
                "bend_y": _to_float(match.group("bend_y")),
                "bend_z": _to_float(match.group("bend_z")),
                "crit_cond": match.group("crit_cond").strip(),
            }
        )

    return rows


def parse_member_group_summary(lines: list[str]) -> MemberGroupSummaryResult:
    block_lines = extract_block(
        lines=lines,
        start_marker=START_MARKER,
        end_markers=END_MARKERS,
        include_start=True,
    )

    raw_block = join_block(block_lines)
    code_name = _extract_code_name(block_lines)
    rows = _parse_rows(block_lines)

    return {
        "section_name": "member_group_summary",
        "marker": START_MARKER,
        "code_name": code_name,
        "raw_block": raw_block,
        "rows": rows,
    }
