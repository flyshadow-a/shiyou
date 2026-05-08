"""
解析 `LOAD CASE STATUS REPORT`。

说明：
1. 该块会给出每个工况的 `AMOD FACTOR`。
2. 当前项目按原 VBA 逻辑处理时，应优先使用这里的真实分类结果：
   - `AMOD FACTOR = 1.33` 视为极端工况
   - 其他值默认视为操作工况
3. 后续 4.5.3 桩基承载力摘要应优先依赖这里的分类，而不是只靠工况名前缀猜测。
"""

from __future__ import annotations

from typing import Literal, TypedDict


ConditionType = Literal["operation", "extreme"]


class LoadCaseStatusRow(TypedDict):
    case_no: int
    load_id: str
    load_factor: float
    amod_factor: float
    condition_type: ConditionType


class LoadCaseStatusResult(TypedDict):
    section_name: str
    marker: str
    rows: list[LoadCaseStatusRow]
    case_type_map: dict[str, ConditionType]


MARKER = "LOAD CASE STATUS REPORT"


def _to_float(value: str) -> float:
    return float(value.strip())


def _classify_condition(amod_factor: float) -> ConditionType:
    return "extreme" if abs(amod_factor - 1.33) < 1e-9 else "operation"


def _parse_row(line: str) -> LoadCaseStatusRow | None:
    parts = line.split()
    if len(parts) < 7:
        return None
    if not parts[0].isdigit():
        return None

    try:
        case_no = int(parts[0])
        load_id = parts[1].strip()
        load_factor = _to_float(parts[-2])
        amod_factor = _to_float(parts[-1])
    except Exception:
        return None

    return {
        "case_no": case_no,
        "load_id": load_id,
        "load_factor": load_factor,
        "amod_factor": amod_factor,
        "condition_type": _classify_condition(amod_factor),
    }


def parse_load_case_status(lines: list[str]) -> LoadCaseStatusResult:
    rows: list[LoadCaseStatusRow] = []
    active = False

    for line in lines:
        upper_line = line.upper()
        if MARKER in upper_line:
            active = True
            continue

        if not active:
            continue

        if not line.strip():
            continue
        if "LOAD   LOAD   PRINT" in upper_line:
            continue
        if "CASE    ID    OPTION" in upper_line:
            continue

        parsed = _parse_row(line)
        if parsed is not None:
            rows.append(parsed)
            continue

        if rows and (
            "SACS CONNECT EDITION" in upper_line
            or "APPLIED LOAD SUMMARY" in upper_line
            or "SACS PROBLEM DESCRIPTION" in upper_line
            or "CONTENTS FOR " in upper_line
        ):
            active = False

    return {
        "section_name": "load_case_status",
        "marker": MARKER,
        "rows": rows,
        "case_type_map": {
            row["load_id"]: row["condition_type"]
            for row in rows
            if row.get("load_id")
        },
    }
