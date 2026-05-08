"""
组合工况描述
"""

from __future__ import annotations

import re
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

# 只识别新工况首行：case + label + 后续描述
ROW_START_PATTERN = re.compile(
    r"^\s*(?P<case>\d+)\s+(?P<label>[A-Z0-9]+)\s+(?P<desc>.+?)\s*$"
)


def _is_header_line(line: str) -> bool:
    text = line.strip().upper()
    if not text:
        return True
    header_tokens = [
        "COMBINED",
        "BASIC",
        "PERCENT",
        "DESCRIPTION",
        "LOAD  LABEL",
        "LOAD CASE",
    ]
    return any(token in text for token in header_tokens)


def parse_combo_case_desc(lines: list[str]) -> list[ComboCaseDescRow]:
    """
    解析:
    ***** SEASTATE COMBINED LOAD CASES *****

    输出:
    [
        {"case": 155, "label": "OP01", "desc": "0.012 * DX00 + 0.0 * DY27"},
        ...
    ]
    """
    block = extract_block(
        lines=lines,
        start_marker=START_MARKER,
        end_markers=END_MARKERS,
        include_start=False,
    )

    rows: list[ComboCaseDescRow] = []
    for line in block:
        if _is_header_line(line):
            continue

        match = ROW_START_PATTERN.match(line)
        if match:
            rows.append(
                {
                    "case": int(match.group("case")),
                    "label": match.group("label").strip(),
                    "desc": " ".join(match.group("desc").split()),
                }
            )

    return rows
