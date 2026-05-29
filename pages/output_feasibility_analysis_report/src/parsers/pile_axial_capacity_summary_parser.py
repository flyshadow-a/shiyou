"""
4.5.3 桩基承载力校核
"""

from __future__ import annotations

from typing import TypedDict

from .block_utils import extract_block, join_block


class PileAxialCapacitySummaryRow(TypedDict):
    pile_head_id: str
    group_id: str
    od_cm: float
    thk_cm: float
    pile_weight_kn: float
    penetration_m: float
    comp_capacity_kn: float
    comp_max_load_kn: float
    comp_critical_load_kn: float
    comp_case: str
    comp_sf: float
    tens_capacity_kn: float
    tens_max_load_kn: float
    tens_critical_load_kn: float
    tens_case: str
    tens_sf: float
    max_unity_check: float
    unity_case: str


class PileAxialCapacitySummaryResult(TypedDict):
    section_name: str
    marker: str
    raw_block: str
    rows: list[PileAxialCapacitySummaryRow]


START_MARKER = "S O I L  M A X I M U M  A X I A L  C A P A C I T Y  S U M M A R Y"
END_MARKERS = [
    "***** SACS LOAD CASE REPORT *****",
    "SACS LOAD CASE REPORT",
]


def _to_float(value: str) -> float:
    return float(value.strip())


def _is_header_or_noise(line: str) -> bool:
    text = line.strip().upper()

    if not text:
        return True

    if text.startswith("SACS CONNECT EDITION"):
        return True
    if "DATE " in text and "PAGE " in text:
        return True

    if "PILE GRP" in text and "COMPRESSION" in text and "TENSION" in text:
        return True
    if "PILEHEAD" in text and "CAPACITY" in text and "CRITICAL CONDITION" in text:
        return True
    if text.startswith("O.D.") or "UNITY LOAD" in text:
        return True
    if text.startswith("CM") or text.startswith("KN"):
        return True

    return False


def _parse_row(line: str) -> PileAxialCapacitySummaryRow | None:
    parts = line.split()
    if len(parts) != 18:
        return None

    if "P" not in parts[0].upper():
        return None

    return {
        "pile_head_id": parts[0].strip(),
        "group_id": parts[1].strip(),
        "od_cm": _to_float(parts[2]),
        "thk_cm": _to_float(parts[3]),
        "pile_weight_kn": _to_float(parts[4]),
        "penetration_m": _to_float(parts[5]),
        "comp_capacity_kn": _to_float(parts[6]),
        "comp_max_load_kn": _to_float(parts[7]),
        "comp_critical_load_kn": _to_float(parts[8]),
        "comp_case": parts[9].strip(),
        "comp_sf": _to_float(parts[10]),
        "tens_capacity_kn": _to_float(parts[11]),
        "tens_max_load_kn": _to_float(parts[12]),
        "tens_critical_load_kn": _to_float(parts[13]),
        "tens_case": parts[14].strip(),
        "tens_sf": _to_float(parts[15]),
        "max_unity_check": _to_float(parts[16]),
        "unity_case": parts[17].strip(),
    }


def _parse_rows(block_lines: list[str]) -> list[PileAxialCapacitySummaryRow]:
    rows: list[PileAxialCapacitySummaryRow] = []

    for line in block_lines:
        if _is_header_or_noise(line):
            continue

        row = _parse_row(line)
        if row is None:
            continue

        rows.append(row)

    return rows


def parse_pile_axial_capacity_summary(lines: list[str]) -> PileAxialCapacitySummaryResult:
    block_lines = extract_block(
        lines=lines,
        start_marker=START_MARKER,
        end_markers=END_MARKERS,
        include_start=True,
    )

    raw_block = join_block(block_lines)
    rows = _parse_rows(block_lines)

    return {
        "section_name": "pile_axial_capacity_summary",
        "marker": START_MARKER,
        "raw_block": raw_block,
        "rows": rows,
    }
