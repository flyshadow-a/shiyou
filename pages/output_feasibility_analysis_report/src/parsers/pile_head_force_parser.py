"""
解析桩头力结果块。

说明：
1. 甲方更正后读取 `FINAL PILE HEAD FORCES` 下的 `PILE HEAD COORDINATES` 数据。
2. 其中 `FORCE(X)` 被视为轴向力，原始符号即业务含义：
   - 负数代表压力 compression
   - 正数代表拉力 tension
"""

from __future__ import annotations

from typing import TypedDict


class PileHeadForceRow(TypedDict):
    load_case: str
    pile_head_id: str
    batter_joint_id: str
    axial_force_kn: float


class PileHeadForceResult(TypedDict):
    section_name: str
    rows: list[PileHeadForceRow]


TITLE_PREFIX = "FINAL PILE HEAD FORCES"
PILE_HEAD_MARKER = "PILE HEAD COORDINATES"
NON_TARGET_TITLE_PREFIXES = (
    "INTERNAL FORCES ON STRUCTURE",
)


def _extract_case_name(line: str) -> str:
    marker = "FOR LOAD CASE"
    upper_line = line.upper()
    index = upper_line.find(marker)
    if index < 0:
        return ""
    return line[index + len(marker) :].strip()


def _parse_row(line: str, load_case: str) -> PileHeadForceRow | None:
    parts = line.split()
    if len(parts) < 8:
        return None
    if "P" not in parts[0].upper():
        return None

    try:
        axial_force_kn = float(parts[2])
    except ValueError:
        return None

    return {
        "load_case": load_case,
        "pile_head_id": parts[0].strip(),
        "batter_joint_id": parts[1].strip(),
        "axial_force_kn": axial_force_kn,
    }


def parse_pile_head_forces(lines: list[str]) -> PileHeadForceResult:
    rows: list[PileHeadForceRow] = []
    current_case = ""
    current_block_is_target = False
    reading_pile_head_rows = False

    for line in lines:
        upper_line = line.upper()

        if TITLE_PREFIX in upper_line and "FOR LOAD CASE" in upper_line:
            current_case = _extract_case_name(line)
            current_block_is_target = True
            reading_pile_head_rows = False
            continue
        if any(prefix in upper_line for prefix in NON_TARGET_TITLE_PREFIXES):
            current_case = ""
            current_block_is_target = False
            reading_pile_head_rows = False
            continue

        if not current_case or not current_block_is_target:
            continue

        if PILE_HEAD_MARKER in upper_line:
            reading_pile_head_rows = True
            continue

        if not reading_pile_head_rows:
            continue

        if not line.strip():
            continue
        if "PILE   BATTER" in upper_line:
            continue
        if "JOINT  JOINT" in upper_line and "FORCE(X)" in upper_line:
            continue
        if "FINAL PILE HEAD FORCES" in upper_line or "STRUCTURAL COORDINATES" in upper_line:
            reading_pile_head_rows = False
            continue

        parsed = _parse_row(line, current_case)
        if parsed is None:
            continue
        rows.append(parsed)

    return {
        "section_name": "pile_head_force",
        "rows": rows,
    }
