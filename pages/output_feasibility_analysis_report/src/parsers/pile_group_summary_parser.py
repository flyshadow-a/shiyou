"""
4.5.3 桩承载力及桩应力校核
"""

from __future__ import annotations

import re
from typing import TypedDict

from .block_utils import extract_block, join_block


NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"


class PileGroupSummaryRow(TypedDict):
    distance_from_pilehead: float
    lateral_deflection_cm: float
    axial_deflection_cm: float
    rotation_rad: float
    bending_moment_knm: float
    shear_kn: float
    axial_load_kn: float
    bending_stress: float
    axial_stress: float
    shear_stress: float
    combined_stress: float
    pile_head_id: str
    critical_load_case: str
    maximum_unity_check: float


class PileGroupSummaryResult(TypedDict):
    section_name: str
    marker: str
    group_id: str
    raw_block: str
    rows: list[PileGroupSummaryRow]


START_MARKER = "P I L E  G R O U P  S U M M A R Y"
END_MARKERS = [
    "P I L E H E A D  C O M P A R I S O N",
    "M E M B E R  G R O U P  S U M M A R Y",
    "J O I N T   C A N   S U M M A R Y",
]

ROW_PATTERN = re.compile(
    rf"""
    ^\s*
    (?P<distance_from_pilehead>{NUM})\s+
    (?P<lateral_deflection_cm>{NUM})\s+
    (?P<axial_deflection_cm>{NUM})\s+
    (?P<rotation_rad>{NUM})\s+
    (?P<bending_moment_knm>{NUM})\s+
    (?P<shear_kn>{NUM})\s+
    (?P<axial_load_kn>{NUM})\s+
    (?P<bending_stress>{NUM})\s+
    (?P<axial_stress>{NUM})\s+
    (?P<shear_stress>{NUM})\s+
    (?P<combined_stress>{NUM})\s+
    (?P<pile_head_id>\S+)\s+
    (?P<critical_load_case>\S+)\s+
    (?P<maximum_unity_check>{NUM})
    \s*$
    """,
    re.VERBOSE,
)

GROUP_ID_PATTERN = re.compile(r"GROUP ID\s*=\s*(?P<group_id>\S+)")


def _to_float(value: str) -> float:
    return float(value.strip())


def _extract_group_id(block_lines: list[str]) -> str:
    for line in block_lines[:10]:
        match = GROUP_ID_PATTERN.search(line)
        if match:
            return match.group("group_id").strip()
    return ""


def _is_header_or_noise(line: str) -> bool:
    text = line.strip().upper()

    if not text:
        return True

    if text.startswith("SACS CONNECT EDITION"):
        return True
    if "DATE " in text and "PAGE " in text:
        return True

    if "GROUP ID" in text:
        return True
    if "DISTANCE" in text and "DEFLECTIONS" in text:
        return True
    if "PILEHEAD" in text and "LATERAL" in text and "AXIAL" in text:
        return True
    if "BENDING" in text and "SHEAR" in text and "COMB." in text:
        return True
    if text.startswith("M ") or text.startswith("KN "):
        return True
    if "N/MM2" in text:
        return True

    return False


def _parse_rows(block_lines: list[str]) -> list[PileGroupSummaryRow]:
    rows: list[PileGroupSummaryRow] = []

    for line in block_lines:
        if _is_header_or_noise(line):
            continue

        match = ROW_PATTERN.match(line)
        if not match:
            continue

        rows.append(
            {
                "distance_from_pilehead": _to_float(match.group("distance_from_pilehead")),
                "lateral_deflection_cm": _to_float(match.group("lateral_deflection_cm")),
                "axial_deflection_cm": _to_float(match.group("axial_deflection_cm")),
                "rotation_rad": _to_float(match.group("rotation_rad")),
                "bending_moment_knm": _to_float(match.group("bending_moment_knm")),
                "shear_kn": _to_float(match.group("shear_kn")),
                "axial_load_kn": _to_float(match.group("axial_load_kn")),
                "bending_stress": _to_float(match.group("bending_stress")),
                "axial_stress": _to_float(match.group("axial_stress")),
                "shear_stress": _to_float(match.group("shear_stress")),
                "combined_stress": _to_float(match.group("combined_stress")),
                "pile_head_id": match.group("pile_head_id").strip(),
                "critical_load_case": match.group("critical_load_case").strip(),
                "maximum_unity_check": _to_float(match.group("maximum_unity_check")),
            }
        )

    return rows


def parse_pile_group_summary(lines: list[str]) -> PileGroupSummaryResult:
    block_lines = extract_block(
        lines=lines,
        start_marker=START_MARKER,
        end_markers=END_MARKERS,
        include_start=True,
    )

    raw_block = join_block(block_lines)
    group_id = _extract_group_id(block_lines)
    rows = _parse_rows(block_lines)

    return {
        "section_name": "pile_group_summary",
        "marker": START_MARKER,
        "group_id": group_id,
        "raw_block": raw_block,
        "rows": rows,
    }