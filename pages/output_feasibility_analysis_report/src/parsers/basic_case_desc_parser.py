"""
基本工况描述
"""

from __future__ import annotations

import re
from typing import TypedDict

from .block_utils import extract_block


class BasicCaseDescRow(TypedDict):
    case: int
    label: str
    desc: str


START_MARKER = "SEASTATE BASIC LOAD CASE DESCRIPTIONS"
END_MARKERS = [
    "SEASTATE BASIC LOAD CASE SUMMARY",
    "SEASTATE COMBINED LOAD CASES",
]

ROW_PATTERN = re.compile(
    r"^\s*(?P<case>\d+)\s+(?P<label>[A-Z0-9]+)\s+(?P<desc>.+?)\s*$"
)


def parse_basic_case_desc(lines: list[str]) -> list[BasicCaseDescRow]:
    """
    解析:
    ** SEASTATE BASIC LOAD CASE DESCRIPTIONS **

    输出:
    [
        {"case": 1, "label": "CR01", "desc": "USER GENERATED LOADS"},
        ...
    ]
    """
    block = extract_block(
        lines=lines,
        start_marker=START_MARKER,
        end_markers=END_MARKERS,
        include_start=False,
    )

    rows: list[BasicCaseDescRow] = []

    for line in block:
        # 跳过表头
        if "LOAD" in line and "DESCRIPTION" in line:
            continue
        if "CASE" in line and "LABEL" in line:
            continue
        if not line.strip():
            continue

        match = ROW_PATTERN.match(line)
        if not match:
            continue

        rows.append(
            {
                "case": int(match.group("case")),
                "label": match.group("label").strip(),
                "desc": match.group("desc").strip(),
            }
        )

    return rows