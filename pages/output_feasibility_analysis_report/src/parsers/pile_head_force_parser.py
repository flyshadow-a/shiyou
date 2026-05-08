"""
解析桩头力结果块。

说明：
1. VBA `ReadList` 读取的是 `INTERNAL FORCES ON STRUCTURE` 下的 `PILE HEAD COORDINATES` 数据。
2. 其中桩局部坐标系的 `FORCE(X)` 被视为轴向力，并在写入 Excel 时取相反数：
   - 压缩为负值
   - 拉伸为正值
3. 这里保持与 VBA 同口径，直接输出 `axial_force_kn = -FORCE(X)`。
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


TITLE_PREFIX = "INTERNAL FORCES ON STRUCTURE"
PILE_HEAD_MARKER = "PILE HEAD COORDINATES"


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
    if not parts[0].startswith("P"):
        return None

    return {
        "load_case": load_case,
        "pile_head_id": parts[0].strip(),
        "batter_joint_id": parts[1].strip(),
        "axial_force_kn": -float(parts[2]),
    }


def parse_pile_head_forces(lines: list[str]) -> PileHeadForceResult:
    rows: list[PileHeadForceRow] = []
    current_case = ""
    reading_pile_head_rows = False

    for line in lines:
        upper_line = line.upper()

        if TITLE_PREFIX in upper_line and "FOR LOAD CASE" in upper_line:
            current_case = _extract_case_name(line)
            reading_pile_head_rows = False
            continue

        if not current_case:
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
        if TITLE_PREFIX in upper_line or "STRUCTURAL COORDINATES" in upper_line:
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
