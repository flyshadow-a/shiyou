"""
组合工况载荷值
"""

from __future__ import annotations

import re
from typing import TypedDict

from .block_utils import extract_block


class ComboCaseLoadRow(TypedDict):
    case: int
    label: str
    fx: float
    fy: float
    fz: float
    mx: float
    my: float
    mz: float


START_MARKER = "SEASTATE COMBINED LOAD CASE SUMMARY"
END_MARKERS = [
    "SEASTATE LOAD CASE CENTER REPORT",
    "SACS-IV   MEMBER UNITY CHECK RANGE SUMMARY",
    "M E M B E R  G R O U P  S U M M A R Y",
    "J O I N T   C A N   S U M M A R Y",
]

NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"

ROW_PATTERN = re.compile(
    rf"""
    ^\s*
    (?P<case>\d+)\s+
    (?P<label>[A-Z0-9]+)\s+
    (?P<fx>{NUM})\s+
    (?P<fy>{NUM})\s+
    (?P<fz>{NUM})\s+
    (?P<mx>{NUM})\s+
    (?P<my>{NUM})\s+
    (?P<mz>{NUM})
    \s*$
    """,
    re.VERBOSE,
)


def _to_float(value: str) -> float:
    return float(value.strip())


def parse_combo_case_loads(lines: list[str]) -> list[ComboCaseLoadRow]:
    block = extract_block(
        lines=lines,
        start_marker=START_MARKER,
        end_markers=END_MARKERS,
        include_start=False,
    )


    rows: list[ComboCaseLoadRow] = []

    for line in block:
        text = line.upper().strip()

        if not text:
            continue

        # 跳过表头和单位行
        if "LOAD" in text and "FX" in text and "FY" in text:
            continue
        if "CASE" in text and "LABEL" in text:
            continue
        if "(KN)" in text or "(KN-M)" in text:
            continue
        if "RELATIVE TO MUDLINE ELEVATION" in text:
            continue

        match = ROW_PATTERN.match(line)
        if not match:
            continue

        rows.append(
            {
                "case": int(match.group("case")),
                "label": match.group("label").strip(),
                "fx": _to_float(match.group("fx")),
                "fy": _to_float(match.group("fy")),
                "fz": _to_float(match.group("fz")),
                "mx": _to_float(match.group("mx")),
                "my": _to_float(match.group("my")),
                "mz": _to_float(match.group("mz")),
            }
        )

    return rows


def validate_combo_case_loads_against_desc(lines: list[str]) -> None:
    from .combo_case_desc_parser import parse_combo_case_desc

    desc_rows = parse_combo_case_desc(lines)
    load_rows = parse_combo_case_loads(lines)

    desc_keys = {(row["case"], row["label"]) for row in desc_rows}
    load_keys = {(row["case"], row["label"]) for row in load_rows}

    if desc_keys != load_keys:
        only_desc = sorted(desc_keys - load_keys)
        only_loads = sorted(load_keys - desc_keys)
        raise ValueError(
            "combo case mismatch: "
            f"desc={len(desc_rows)}, loads={len(load_rows)}, "
            f"only_desc={only_desc[:10]}, only_loads={only_loads[:10]}"
        )
