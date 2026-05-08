"""
基本工况载荷值
"""

from __future__ import annotations

import re
from typing import TypedDict

from .block_utils import extract_block


class BasicCaseLoadRow(TypedDict):
    case: int
    label: str
    fx: float
    fy: float
    fz: float
    mx: float
    my: float
    mz: float
    dead_load: float
    buoyancy: float


START_MARKER = "SEASTATE BASIC LOAD CASE SUMMARY"
END_MARKERS = [
    "SEASTATE COMBINED LOAD CASES",
    "SEASTATE COMBINED LOAD CASE SUMMARY",
    "M E M B E R  G R O U P  S U M M A R Y",
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
    (?P<mz>{NUM})\s+
    (?P<dead_load>{NUM})\s+
    (?P<buoyancy>{NUM})
    \s*$
    """,
    re.VERBOSE,
)


def _to_float(value: str) -> float:
    return float(value.strip())


def parse_basic_case_loads(lines: list[str]) -> list[BasicCaseLoadRow]:
    """
    解析:
    ****** SEASTATE BASIC LOAD CASE SUMMARY ******

    输出:
    [
        {
            "case": 1,
            "label": "CR01",
            "fx": 290.0,
            "fy": 0.0,
            ...
        }
    ]
    """
    block = extract_block(
        lines=lines,
        start_marker=START_MARKER,
        end_markers=END_MARKERS,
        include_start=False,
    )

    rows: list[BasicCaseLoadRow] = []

    for line in block:
        # 跳过表头 / 单位行
        if "LOAD" in line and "FX" in line and "FY" in line:
            continue
        if "(KN)" in line or "(KN-M)" in line:
            continue
        if "RELATIVE TO MUDLINE ELEVATION" in line:
            continue
        if "MARINE METHOD" in line:
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
                "fx": _to_float(match.group("fx")),
                "fy": _to_float(match.group("fy")),
                "fz": _to_float(match.group("fz")),
                "mx": _to_float(match.group("mx")),
                "my": _to_float(match.group("my")),
                "mz": _to_float(match.group("mz")),
                "dead_load": _to_float(match.group("dead_load")),
                "buoyancy": _to_float(match.group("buoyancy")),
            }
        )

    return rows


def validate_basic_case_loads_against_desc(lines: list[str]) -> None:
    from .basic_case_desc_parser import parse_basic_case_desc

    desc_rows = parse_basic_case_desc(lines)
    load_rows = parse_basic_case_loads(lines)

    desc_keys = {(row["case"], row["label"]) for row in desc_rows}
    load_keys = {(row["case"], row["label"]) for row in load_rows}

    if desc_keys != load_keys:
        only_desc = sorted(desc_keys - load_keys)
        only_loads = sorted(load_keys - desc_keys)
        raise ValueError(
            "basic case mismatch: "
            f"desc={len(desc_rows)}, loads={len(load_rows)}, "
            f"only_desc={only_desc[:10]}, only_loads={only_loads[:10]}"
        )
