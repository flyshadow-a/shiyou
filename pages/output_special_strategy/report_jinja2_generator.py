from __future__ import annotations

import argparse
import copy
import io
import json
import math
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any

from jinja2 import Environment, StrictUndefined
from openpyxl import load_workbook
import xml.etree.ElementTree as ET


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
HYPERLINK_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
STD_NORM = NormalDist()


@dataclass(frozen=True)
class DynamicTableSpec:
    table_index: int
    header_rows: int
    context_key: str
    column_templates: list[str]


DYNAMIC_TABLE_SPECS: list[DynamicTableSpec] = [
    DynamicTableSpec(
        table_index=3,
        header_rows=2,
        context_key="fatigue_failure_rows",
        column_templates=[
            "{{ row.joint_id }}",
            "{{ row.brace }}",
            "{{ row.joint_type }}",
            "{{ row.damage }}",
            "{{ row.beta }}",
            "{{ row.pf }}",
            "{{ row.fatigue_prob_level }}",
            "{{ row.time_node }}",
        ],
    ),
    DynamicTableSpec(
        table_index=4,
        header_rows=3,
        context_key="collapse_member_rows",
        column_templates=[
            "{{ row.joint_a }}",
            "{{ row.joint_b }}",
            "{{ row.member_type }}",
            "{{ row.a }}",
            "{{ row.b }}",
            "{{ row.rm }}",
            "{{ row.vr }}",
            "{{ row.pf }}",
            "{{ row.collapse_prob_level }}",
        ],
    ),
    DynamicTableSpec(
        table_index=5,
        header_rows=2,
        context_key="collapse_joint_rows",
        column_templates=[
            "{{ row.joint_id }}",
            "{{ row.joint_type }}",
            "{{ row.a }}",
            "{{ row.b }}",
            "{{ row.rm }}",
            "{{ row.vr }}",
            "{{ row.pf }}",
            "{{ row.collapse_prob_level }}",
        ],
    ),
    DynamicTableSpec(
        table_index=7,
        header_rows=1,
        context_key="node_risk_rows_current",
        column_templates=[
            "{{ row.joint_id }}",
            "{{ row.brace }}",
            "{{ row.joint_type }}",
            "{{ row.consequence_level }}",
            "{{ row.collapse_prob_level }}",
            "{{ row.fatigue_prob_level }}",
            "{{ row.combined_prob_level }}",
            "{{ row.node_risk_level }}",
            "{{ row.time_node }}",
        ],
    ),
    DynamicTableSpec(
        table_index=8,
        header_rows=2,
        context_key="member_risk_rows",
        column_templates=[
            "{{ row.joint_a }}",
            "{{ row.joint_b }}",
            "{{ row.member_type }}",
            "{{ row.consequence_level }}",
            "{{ row.collapse_prob_level }}",
            "{{ row.member_risk_level }}",
        ],
    ),
    DynamicTableSpec(
        table_index=16,
        header_rows=1,
        context_key="member_inspection_rows",
        column_templates=[
            "{{ row.joint_a }}",
            "{{ row.joint_b }}",
            "{{ row.member_type }}",
            "{{ row.consequence_level }}",
            "{{ row.member_risk_level }}",
            "{{ row.inspect_level }}",
            "{{ row.time_node }}",
        ],
    ),
    DynamicTableSpec(
        table_index=17,
        header_rows=1,
        context_key="node_inspection_rows_future",
        column_templates=[
            "{{ row.joint_id }}",
            "{{ row.brace }}",
            "{{ row.joint_type }}",
            "{{ row.consequence_level }}",
            "{{ row.combined_prob_level }}",
            "{{ row.node_risk_level }}",
            "{{ row.inspect_level }}",
            "{{ row.time_node }}",
        ],
    ),
]


RISK_LEVEL_ORDER = ["\u4e00", "\u4e8c", "\u4e09", "\u56db", "\u4e94"]
INSPECTION_LEVEL_ORDER = ["II", "III", "IV"]
TIME_CURRENT = "\u5f53\u524d"
TIME_ORDER = [TIME_CURRENT, "\u7b2c5\u5e74", "\u7b2c10\u5e74", "\u7b2c15\u5e74", "\u7b2c20\u5e74", "\u7b2c25\u5e74"]
TIME_TO_YEAR = {
    TIME_ORDER[1]: 5,
    TIME_ORDER[2]: 10,
    TIME_ORDER[3]: 15,
    TIME_ORDER[4]: 20,
    TIME_ORDER[5]: 25,
}

DEFAULT_DYNAMIC_ROW_LIMITS = {
    "fatigue_failure_rows": 800,
    "collapse_member_rows": 80,
    "collapse_joint_rows": 80,
    "node_risk_rows_current": 250,
    "member_risk_rows": 250,
    "member_inspection_rows": 250,
    "node_inspection_rows_future": 500,
}

OPTIONAL_WORD_DETAIL_CONTEXT_KEYS = {
    "member_inspection_rows",
    "node_inspection_rows_future",
}


APPENDIX_A_HEADING = "附件A 节点风险等级计算表"
APPENDIX_B_HEADING = "附件B 构件风险等级计算表"
APPENDIX_C_MAIN_HEADING = "附件C 平台检验计划的检验节点构件"
APPENDIX_C_SUBHEADINGS = [
    "附件C.1 服役第5年的检验节点构件位置",
    "附件C.2 服役第10年的检验节点构件位置",
    "附件C.3 服役第15年的检验节点构件位置",
    "附件C.4 服役第20年的检验节点构件位置",
    "附件C.5 服役第25年的检验节点构件位置",
]
APPENDIX_IMAGE_WIDTH_INCHES = 6.2
# Lower appendix render quality to keep the final DOCX responsive when many
# PDF pages are embedded. The report body stays unchanged; only appendix image
# density/compression is reduced.
APPENDIX_RENDER_DPI = 90
APPENDIX_JPEG_QUALITY = 60


def to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value).strip()


def to_scientific_text(value: Any, digits: int = 2) -> str:
    """
    Format numeric value in scientific notation (e.g. 7.03E-42).
    Keep empty/non-numeric values unchanged.
    """
    if value is None:
        return ""
    txt = str(value).strip()
    if txt == "":
        return ""
    try:
        f = float(txt)
    except ValueError:
        return txt
    if math.isnan(f):
        return ""
    return f"{f:.{digits}E}"


def to_int_or_none(value: Any) -> int | None:
    txt = to_text(value)
    if txt == "":
        return None
    try:
        return int(float(txt))
    except ValueError:
        return None


def to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        f = float(value)
        if math.isnan(f):
            return None
        return f
    txt = str(value).strip()
    if txt == "":
        return None
    try:
        f = float(txt)
    except ValueError:
        return None
    if math.isnan(f):
        return None
    return f


def collapse_pf_from_factor(a: Any, b: Any, rm: Any, vr: Any) -> float | None:
    a_f = to_float_or_none(a)
    b_f = to_float_or_none(b)
    rm_f = to_float_or_none(rm)
    vr_f = to_float_or_none(vr)
    if a_f is None or b_f is None or rm_f is None or vr_f is None:
        return None
    if b_f == 0.0 or vr_f == 0.0:
        return None
    term1 = math.exp((a_f - rm_f) / b_f + (vr_f**2) * (rm_f**2) / (2 * (b_f**2)))
    # VBA uses NORM.DIST(..., FALSE): standard normal PDF.
    term2 = 1.0 - STD_NORM.pdf(vr_f * rm_f / b_f - 1.0 / vr_f)
    return float(term1 * term2)


def normalize_time_node(raw: Any) -> str:
    s = to_text(raw)
    if not s:
        return ""
    nums = re.findall(r"\d+", s)
    if not nums:
        return TIME_CURRENT
    return f"\u7b2c{int(nums[0])}\u5e74"


PLAN_TIME_MAP = {
    "N": TIME_CURRENT,
    "N+5": "\u7b2c5\u5e74",
    "N+10": "\u7b2c10\u5e74",
    "N+15": "\u7b2c15\u5e74",
    "N+20": "\u7b2c20\u5e74",
    "N+25": "\u7b2c25\u5e74",
}

FORECAST_YEAR_TIME_MAP = {
    1: TIME_CURRENT,
    6: "\u7b2c5\u5e74",
    11: "\u7b2c10\u5e74",
    16: "\u7b2c15\u5e74",
    21: "\u7b2c20\u5e74",
    26: "\u7b2c25\u5e74",
}

RISK_LEVEL_TO_INDEX = {lv: idx for idx, lv in enumerate(RISK_LEVEL_ORDER)}


def normalize_plan_time(raw: Any) -> str:
    s = to_text(raw).upper().replace(" ", "")
    if s in PLAN_TIME_MAP:
        return PLAN_TIME_MAP[s]
    return normalize_time_node(s)


def forecast_year_to_time_node(year: int | None) -> str:
    if year is None:
        return ""
    if year in FORECAST_YEAR_TIME_MAP:
        return FORECAST_YEAR_TIME_MAP[year]
    if year <= 1:
        return TIME_CURRENT
    return f"\u7b2c{year - 1}\u5e74"


def normalize_inspect_level(raw: Any) -> str:
    level = to_text(raw).upper()
    if level in {"II", "III", "IV"}:
        return level
    if level == "I":
        return "II"
    return "III"


def choose_higher_risk_grade(grade_a: Any, grade_b: Any) -> str:
    a = to_text(grade_a)
    b = to_text(grade_b)
    candidates = [g for g in (a, b) if g in RISK_LEVEL_TO_INDEX]
    if not candidates:
        return ""
    return min(candidates, key=lambda g: RISK_LEVEL_TO_INDEX[g])


def collapse_level_to_risk_grade(level: int | None) -> str:
    if level is None:
        return ""
    if 1 <= level <= len(RISK_LEVEL_ORDER):
        return RISK_LEVEL_ORDER[level - 1]
    return ""


def risk_rank(risk: Any) -> int:
    s = to_text(risk)
    if s in RISK_LEVEL_TO_INDEX:
        return RISK_LEVEL_TO_INDEX[s]
    return len(RISK_LEVEL_ORDER) + 1


def sorted_node_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            risk_rank(r.get("node_risk_level")),
            to_int_or_none(r.get("combined_prob_level")) or 99,
            to_int_or_none(r.get("fatigue_prob_level")) or 99,
            to_text(r.get("joint_id")),
        ),
    )


def sorted_fatigue_failure_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Table 2-5 sorting:
    1) time node ascending (第5年 -> 第10年 -> 第15年 -> 第20年 -> 第25年)
    2) joint/brace lexicographic
    3) fatigue probability level ascending
    4) node risk level ascending
    """
    return sorted(
        rows,
        key=lambda r: (
            time_node_rank(r.get("time_node")),
            to_text(r.get("joint_id")),
            to_text(r.get("brace")),
            to_int_or_none(r.get("fatigue_prob_level")) or 99,
            risk_rank(r.get("node_risk_level")),
        ),
    )


def sorted_member_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            risk_rank(r.get("member_risk_level")),
            to_int_or_none(r.get("collapse_prob_level")) or 99,
            to_text(r.get("joint_a")),
            to_text(r.get("joint_b")),
        ),
    )


def cap_rows(rows: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    if limit is None or limit <= 0 or len(rows) <= limit:
        return rows
    return rows[:limit]


def iter_data_rows(ws, min_row: int, max_col: int, key_col_index: int = 0):
    blank_run = 0
    for row in ws.iter_rows(min_row=min_row, max_col=max_col, values_only=True):
        key = row[key_col_index]
        if to_text(key) == "":
            blank_run += 1
            if blank_run > 50:
                break
            continue
        blank_run = 0
        yield row


def get_sheet_by_names_or_index(wb, names: list[str], fallback_index: int):
    for name in names:
        if name in wb.sheetnames:
            return wb[name]
    if 0 <= fallback_index < len(wb.worksheets):
        return wb.worksheets[fallback_index]
    raise KeyError(f"Sheet not found by names={names} or index={fallback_index}")


def build_collapse_overrides_from_sheet(
    ws_collapse,
    ws_members,
    node_type_by_joint: dict[str, str],
    member_level_by_pair: dict[str, str] | None,
    joint_level_by_id: dict[str, str] | None,
    collapse_a_const: Any,
    collapse_b_const: Any,
    collapse_vr_const: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    member_type_by_pair: dict[str, str] = {}
    if ws_members is not None:
        for row in iter_data_rows(ws_members, min_row=2, max_col=5):
            ja = to_text(row[0])
            jb = to_text(row[1])
            mt = to_text(row[4]) or "Other"
            if ja == "" or jb == "":
                continue
            member_type_by_pair[f"{ja}-{jb}"] = mt
            member_type_by_pair[f"{jb}-{ja}"] = mt

    collapse_member_factor: dict[str, float | None] = {}
    collapse_joint_factor: dict[str, float | None] = {}
    if ws_collapse is not None:
        for row in iter_data_rows(ws_collapse, min_row=2, max_col=5):
            fail_type = to_text(row[1])
            location = to_text(row[2])
            factor = to_float_or_none(row[3])
            if location == "":
                continue
            if fail_type.upper() == "TYPE" or location.upper() == "LOCATION":
                continue
            ft = fail_type.replace(" ", "").upper()
            is_member = ("MEMBER" in ft) or ("构件" in fail_type and "失效" in fail_type)
            is_joint = ("JOINT" in ft) or ("节点" in fail_type and "失效" in fail_type)
            if not is_member and not is_joint:
                is_member = "-" in location
                is_joint = not is_member

            if is_member:
                old = collapse_member_factor.get(location)
                if old is None or (factor is not None and factor < old):
                    collapse_member_factor[location] = factor
            elif is_joint:
                old = collapse_joint_factor.get(location)
                if old is None or (factor is not None and factor < old):
                    collapse_joint_factor[location] = factor

    collapse_member_rows_override: list[dict[str, Any]] = []
    for location, factor in sorted(
        collapse_member_factor.items(),
        key=lambda kv: (
            9999 if kv[1] is None else kv[1],
            kv[0],
        ),
    ):
        ja = ""
        jb = ""
        if "-" in location:
            ja, jb = location.split("-", 1)
        mtype = member_type_by_pair.get(location) or "Other"
        pf_val = collapse_pf_from_factor(collapse_a_const, collapse_b_const, factor, collapse_vr_const)
        level = ""
        if member_level_by_pair:
            level = to_text(member_level_by_pair.get(location))
            if level == "" and ja != "" and jb != "":
                level = to_text(member_level_by_pair.get(f"{jb}-{ja}"))

        a_txt = to_text(collapse_a_const)
        b_txt = to_text(collapse_b_const)
        a_val = to_float_or_none(collapse_a_const)
        b_val = to_float_or_none(collapse_b_const)
        if a_val is not None:
            a_txt = f"{a_val:.3f}"
        if b_val is not None:
            b_txt = f"{b_val:.3f}"

        vr_txt = to_text(collapse_vr_const)
        vr_val = to_float_or_none(collapse_vr_const)
        if vr_val is not None:
            vr_txt = f"{vr_val * 100:.0f}%"

        collapse_member_rows_override.append(
            {
                "joint_a": ja,
                "joint_b": jb,
                "member_type": mtype,
                "a": a_txt,
                "b": b_txt,
                "rm": "" if factor is None else f"{factor:g}",
                "vr": vr_txt,
                "pf": to_scientific_text(pf_val),
                "collapse_prob_level": level,
            }
        )

    collapse_joint_rows_override: list[dict[str, Any]] = []
    for joint_id, factor in sorted(
        collapse_joint_factor.items(),
        key=lambda kv: (
            9999 if kv[1] is None else kv[1],
            kv[0],
        ),
    ):
        pf_val = collapse_pf_from_factor(collapse_a_const, collapse_b_const, factor, collapse_vr_const)
        level = ""
        if joint_level_by_id:
            level = to_text(joint_level_by_id.get(joint_id))
        lv_i = to_int_or_none(level)
        if lv_i is not None and lv_i > 4:
            continue

        a_txt = to_text(collapse_a_const)
        b_txt = to_text(collapse_b_const)
        a_val = to_float_or_none(collapse_a_const)
        b_val = to_float_or_none(collapse_b_const)
        if a_val is not None:
            a_txt = f"{a_val:.3f}"
        if b_val is not None:
            b_txt = f"{b_val:.3f}"

        vr_txt = to_text(collapse_vr_const)
        vr_val = to_float_or_none(collapse_vr_const)
        if vr_val is not None:
            vr_txt = f"{vr_val * 100:.0f}%"

        collapse_joint_rows_override.append(
            {
                "joint_id": joint_id,
                "joint_type": node_type_by_joint.get(joint_id, ""),
                "a": a_txt,
                "b": b_txt,
                "rm": "" if factor is None else f"{factor:g}",
                "vr": vr_txt,
                "pf": to_scientific_text(pf_val),
                "collapse_prob_level": level,
            }
        )

    return collapse_member_rows_override, collapse_joint_rows_override


def aggregate_risk_counts(rows: list[dict[str, Any]], risk_key: str) -> dict[str, int]:
    counts = {k: 0 for k in RISK_LEVEL_ORDER}
    for row in rows:
        risk = to_text(row.get(risk_key))
        if risk in counts:
            counts[risk] += 1
    return counts


def aggregate_inspection_counts(rows: list[dict[str, Any]], risk_value: str, risk_key: str) -> dict[str, int]:
    counts = {k: 0 for k in INSPECTION_LEVEL_ORDER}
    for row in rows:
        if to_text(row.get(risk_key)) != risk_value:
            continue
        level = to_text(row.get("inspect_level"))
        if level in counts:
            counts[level] += 1
    return counts


def time_node_rank(value: Any) -> int:
    """
    Rank time node for earliest-first selection.
    """
    s = normalize_time_node(value)
    if s in TIME_ORDER:
        return TIME_ORDER.index(s)
    nums = re.findall(r"\d+", to_text(value))
    if nums:
        return int(nums[0])
    return 9999


def is_deleted_joint_by_vba_rule(joint_id: Any) -> bool:
    """
    VBA Sheet11/Sheet12 删除JOINT* rules:
    delete when A matches one of:
    - C*
    - B*
    - J*
    - O*
    - K###
    - R*
    """
    s = to_text(joint_id).upper()
    if s == "":
        return False
    if s.startswith(("C", "B", "J", "O", "R")):
        return True
    if re.fullmatch(r"K\d{3}", s):
        return True
    return False


def is_deleted_member_by_vba_rule(joint_a: Any, joint_b: Any) -> bool:
    """
    VBA Sheet10 删除MEMBER rules:
    delete row when any condition matches:
    - A Like "C*" Or B Like "C*"
    - A Like "B*" And B Like "B*"
    - A Like "J*" Or B Like "J*"
    - A Like "O*" Or B Like "O*"
    - A Like "K###" And B Like "K###"
    - A Like "R*" Or B Like "R*"
    - A Like "0*L" And B Like "0*L"
    """
    a = to_text(joint_a).upper()
    b = to_text(joint_b).upper()
    if a == "" or b == "":
        return False
    if a.startswith("C") or b.startswith("C"):
        return True
    if a.startswith("B") and b.startswith("B"):
        return True
    if a.startswith("J") or b.startswith("J"):
        return True
    if a.startswith("O") or b.startswith("O"):
        return True
    if re.fullmatch(r"K\d{3}", a) and re.fullmatch(r"K\d{3}", b):
        return True
    if a.startswith("R") or b.startswith("R"):
        return True
    if a.startswith("0") and a.endswith("L") and b.startswith("0") and b.endswith("L"):
        return True
    return False


def ratio_text(part: int, total: int) -> str:
    if total <= 0:
        return "0.00%"
    return f"{(part / total) * 100:.2f}%"


def build_context(
    node_risk_rows: list[dict[str, Any]],
    node_strategy_rows: list[dict[str, Any]],
    member_risk_rows: list[dict[str, Any]],
    member_strategy_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    row_limits: dict[str, int] | None = None,
    collapse_member_rows_override: list[dict[str, Any]] | None = None,
    collapse_joint_rows_override: list[dict[str, Any]] | None = None,
    apply_vba_delete_rules: bool = False,
    apply_vba_member_delete_rules: bool | None = None,
    apply_vba_joint_delete_rules: bool | None = None,
    apply_vba_joint_delete_rules_current: bool | None = None,
    apply_vba_joint_delete_rules_future: bool | None = None,
) -> dict[str, Any]:
    if row_limits is None:
        limits = {k: None for k in DEFAULT_DYNAMIC_ROW_LIMITS}
    else:
        limits = dict(DEFAULT_DYNAMIC_ROW_LIMITS)
        limits.update(row_limits)

    if apply_vba_member_delete_rules is None:
        apply_vba_member_delete_rules = apply_vba_delete_rules
    if apply_vba_joint_delete_rules is None:
        apply_vba_joint_delete_rules = apply_vba_delete_rules
    if apply_vba_joint_delete_rules_current is None:
        apply_vba_joint_delete_rules_current = apply_vba_joint_delete_rules
    if apply_vba_joint_delete_rules_future is None:
        apply_vba_joint_delete_rules_future = apply_vba_joint_delete_rules

    if apply_vba_joint_delete_rules_current:
        node_risk_rows_use = [r for r in node_risk_rows if not is_deleted_joint_by_vba_rule(r.get("joint_id"))]
    else:
        node_risk_rows_use = list(node_risk_rows)

    if apply_vba_joint_delete_rules_current or apply_vba_joint_delete_rules_future:
        node_strategy_rows_use = []
        for r in node_strategy_rows:
            jid = r.get("joint_id")
            if not is_deleted_joint_by_vba_rule(jid):
                node_strategy_rows_use.append(r)
                continue

            t = normalize_time_node(r.get("time_node"))
            is_current = (t == TIME_CURRENT) or (t == "")
            if is_current:
                if not apply_vba_joint_delete_rules_current:
                    node_strategy_rows_use.append(r)
            else:
                if not apply_vba_joint_delete_rules_future:
                    node_strategy_rows_use.append(r)
    else:
        node_strategy_rows_use = list(node_strategy_rows)
        node_strategy_rows_use = list(node_strategy_rows)

    if apply_vba_member_delete_rules:
        member_risk_rows_use = [
            r
            for r in member_risk_rows
            if not is_deleted_member_by_vba_rule(r.get("joint_a"), r.get("joint_b"))
        ]
        member_strategy_rows_use = [
            r
            for r in member_strategy_rows
            if not is_deleted_member_by_vba_rule(r.get("joint_a"), r.get("joint_b"))
        ]
    else:
        member_risk_rows_use = list(member_risk_rows)
        member_strategy_rows_use = list(member_strategy_rows)

    collapse_member_rows = []
    for r in member_risk_rows_use:
        lv = to_int_or_none(r["collapse_prob_level"])
        if lv is not None and lv <= 2:
            collapse_member_rows.append(r)
    if collapse_member_rows_override is not None:
        collapse_member_rows = collapse_member_rows_override

    collapse_joint_rows = []
    for r in node_risk_rows_use:
        lv = to_int_or_none(r["collapse_prob_level"])
        if lv is not None and lv <= 2:
            collapse_joint_rows.append(r)
    if collapse_joint_rows_override is not None:
        collapse_joint_rows = collapse_joint_rows_override

    # Table 2-5: keep all future rows where fatigue probability level reaches
    # failure threshold (<=2). Keep all joint types, including "Other".
    # Do not deduplicate by (JointID, Brace); keep per-time-node rows.
    fatigue_failure_rows: list[dict[str, Any]] = []
    for r in node_strategy_rows_use:
        if r["time_node"] == TIME_CURRENT:
            continue
        lv = to_int_or_none(r.get("fatigue_prob_level"))
        if lv is not None and lv <= 2:
            fatigue_failure_rows.append(r)

    if not fatigue_failure_rows:
        fatigue_failure_rows = [r for r in node_strategy_rows_use if r["time_node"] != TIME_CURRENT]

    node_risk_rows_current = [r for r in node_strategy_rows_use if r["time_node"] == TIME_CURRENT]
    # Word Table 4-4 in the reference report only lists future checkpoints that
    # require elevated inspection methods, instead of the full node strategy table.
    node_inspection_rows_future = [
        r
        for r in node_strategy_rows_use
        if r["time_node"] != TIME_CURRENT and to_text(r.get("inspect_level")) in ("III", "IV")
    ]
    # Table 2-9 (表29): future nodes with risk level 一/二.
    # Keep source sheet order for strict VBA-style output.
    node_risk_rows_table29 = [
        r for r in node_strategy_rows_use
        if r["time_node"] != TIME_CURRENT and risk_rank(r.get("node_risk_level")) <= 1
    ]
    # Fallback to combined probability <=3 (equivalent to high-risk zone in most matrices).
    if not node_risk_rows_table29:
        node_risk_rows_table29 = [
            r for r in node_strategy_rows_use
            if r["time_node"] != TIME_CURRENT and (to_int_or_none(r.get("combined_prob_level")) or 99) <= 3
        ]
    if not node_risk_rows_table29:
        node_risk_rows_table29 = [r for r in node_strategy_rows_use if r["time_node"] != TIME_CURRENT]

    member_risk_counts = aggregate_risk_counts(member_risk_rows_use, "member_risk_level")
    total_member = sum(member_risk_counts.values())
    member_risk_ratios = {k: ratio_text(v, total_member) for k, v in member_risk_counts.items()}

    node_summary_blocks = []
    for t in TIME_ORDER:
        rows_t = [r for r in node_strategy_rows_use if r["time_node"] == t]
        if not rows_t:
            continue
        counts = aggregate_risk_counts(rows_t, "node_risk_level")
        total = sum(counts.values())
        ratios = {k: ratio_text(v, total) for k, v in counts.items()}
        if t == TIME_CURRENT:
            title = "\u8282\u70b9\u710a\u7f1d\uff08\u5f53\u524d\uff09"
        else:
            year = TIME_TO_YEAR.get(t, "")
            title = f"\u8282\u70b9\u710a\u7f1d\uff08\u672a\u6765{year}\u5e74\uff09"
        node_summary_blocks.append({"time_node": t, "title": title, "counts": counts, "ratios": ratios, "total": total})

    # Word Table 4-1 summarizes the current member plan only. Future-year member
    # strategy rows are shown separately in Table 4-3.
    member_strategy_rows_current = [
        r for r in member_strategy_rows_use if normalize_time_node(r.get("time_node")) in (TIME_CURRENT, "")
    ]
    member_inspection_summary = []
    member_total = 0
    member_level_totals = {k: 0 for k in INSPECTION_LEVEL_ORDER}
    for risk in RISK_LEVEL_ORDER:
        rows_r = [r for r in member_strategy_rows_current if to_text(r["member_risk_level"]) == risk]
        risk_count = len(rows_r)
        inspect_counts = aggregate_inspection_counts(rows_r, risk, "member_risk_level")
        member_total += risk_count
        for lv in INSPECTION_LEVEL_ORDER:
            member_level_totals[lv] += inspect_counts[lv]
        member_inspection_summary.append(
            {
                "risk_level": risk,
                "count": risk_count,
                "II": inspect_counts["II"],
                "III": inspect_counts["III"],
                "IV": inspect_counts["IV"],
            }
        )

    node_inspection_blocks = []
    for t in [x for x in TIME_ORDER if x != TIME_CURRENT]:
        rows_t = [r for r in node_inspection_rows_future if r["time_node"] == t]
        if not rows_t:
            continue
        summary_rows = []
        total = len(rows_t)
        total_level_counts = {k: 0 for k in INSPECTION_LEVEL_ORDER}
        for risk in RISK_LEVEL_ORDER:
            rows_r = [r for r in rows_t if to_text(r["node_risk_level"]) == risk]
            inspect_counts = aggregate_inspection_counts(rows_r, risk, "node_risk_level")
            for lv in INSPECTION_LEVEL_ORDER:
                total_level_counts[lv] += inspect_counts[lv]
            summary_rows.append(
                {
                    "risk_level": risk,
                    "count": len(rows_r),
                    "II": inspect_counts["II"],
                    "III": inspect_counts["III"],
                    "IV": inspect_counts["IV"],
                }
            )
        node_inspection_blocks.append(
            {
                "time_node": t,
                "summary_rows": summary_rows,
                "total_count": total,
                "total_II": total_level_counts["II"],
                "total_III": total_level_counts["III"],
                "total_IV": total_level_counts["IV"],
            }
        )

    # Keep source-table order for strict VBA alignment; only apply row caps.
    collapse_member_rows_disp = cap_rows(collapse_member_rows, limits.get("collapse_member_rows"))
    collapse_joint_rows_disp = cap_rows(collapse_joint_rows, limits.get("collapse_joint_rows"))
    fatigue_failure_rows_disp = cap_rows(
        sorted_fatigue_failure_rows(fatigue_failure_rows),
        limits.get("fatigue_failure_rows"),
    )
    table29_limit = limits.get("node_risk_rows_current")
    if table29_limit is None or table29_limit <= 0 or len(node_risk_rows_table29) <= table29_limit:
        node_risk_rows_current_disp = list(node_risk_rows_table29)
    else:
        # Keep every future checkpoint visible under row cap:
        # distribute slots across 5/10/15/20/25 years.
        table29_groups = {
            t: [r for r in node_risk_rows_table29 if to_text(r.get("time_node")) == t]
            for t in TIME_ORDER
            if t != TIME_CURRENT
        }
        active_times = [t for t in TIME_ORDER if t != TIME_CURRENT and len(table29_groups.get(t, [])) > 0]
        if not active_times:
            node_risk_rows_current_disp = cap_rows(node_risk_rows_table29, table29_limit)
        else:
            per_time = max(1, table29_limit // len(active_times))
            picked: dict[str, int] = {}
            used = 0
            for t in active_times:
                take = min(len(table29_groups[t]), per_time)
                picked[t] = take
                used += take
            remain = max(0, table29_limit - used)
            while remain > 0:
                progressed = False
                for t in active_times:
                    if picked[t] < len(table29_groups[t]):
                        picked[t] += 1
                        remain -= 1
                        progressed = True
                        if remain == 0:
                            break
                if not progressed:
                    break
            node_risk_rows_current_disp = []
            for t in active_times:
                node_risk_rows_current_disp.extend(table29_groups[t][: picked[t]])

    # Word Table 4-3 shows only future member rows that need III/IV inspection.
    member_inspection_rows = [
        r
        for r in member_strategy_rows_use
        if normalize_time_node(r.get("time_node")) not in (TIME_CURRENT, "")
        and to_text(r.get("inspect_level")) in ("III", "IV")
    ]

    member_risk_rows_disp = cap_rows(member_risk_rows_use, limits.get("member_risk_rows"))
    member_inspection_rows_disp = cap_rows(member_inspection_rows, limits.get("member_inspection_rows"))
    node_inspection_rows_future_disp = cap_rows(node_inspection_rows_future, limits.get("node_inspection_rows_future"))

    return {
        "platform_name": metadata.get("platform_name", ""),
        "report_date": metadata.get("report_date", ""),
        "fatigue_failure_rows": fatigue_failure_rows_disp,
        "collapse_member_rows": collapse_member_rows_disp,
        "collapse_joint_rows": collapse_joint_rows_disp,
        "node_risk_rows_current": node_risk_rows_current_disp,
        "member_risk_rows": member_risk_rows_disp,
        "member_inspection_rows": member_inspection_rows_disp,
        "node_inspection_rows_future": node_inspection_rows_future_disp,
        "member_risk_counts": member_risk_counts,
        "member_risk_ratios": member_risk_ratios,
        "node_summary_blocks": node_summary_blocks,
        "member_inspection_summary": member_inspection_summary,
        "member_inspection_total": member_total,
        "member_inspection_total_II": member_level_totals["II"],
        "member_inspection_total_III": member_level_totals["III"],
        "member_inspection_total_IV": member_level_totals["IV"],
        "node_inspection_blocks": node_inspection_blocks,
        "row_limits": limits,
        "row_counts": {
            "fatigue_failure_rows_total": len(fatigue_failure_rows),
            "collapse_member_rows_total": len(collapse_member_rows),
            "collapse_joint_rows_total": len(collapse_joint_rows),
            "node_risk_rows_current_total": len(node_risk_rows_table29),
            "member_risk_rows_total": len(member_risk_rows_use),
            "member_inspection_rows_total": len(member_inspection_rows),
            "node_inspection_rows_future_total": len(node_inspection_rows_future),
        },
    }


def load_context_from_legacy_workbook(
    wb,
    metadata: dict[str, Any],
    row_limits: dict[str, int] | None = None,
    apply_vba_member_delete_rules: bool = False,
    apply_vba_joint_delete_rules_current: bool = False,
    apply_vba_joint_delete_rules_future: bool = False,
) -> dict[str, Any]:
    ws_node_risk = get_sheet_by_names_or_index(wb, ["节点失效风险等级"], 9)
    ws_node_strategy = get_sheet_by_names_or_index(wb, ["节点检验策略"], 11)
    ws_member_risk = get_sheet_by_names_or_index(wb, ["构件失效风险等级"], 12)
    ws_member_strategy = get_sheet_by_names_or_index(wb, ["构件检验策略"], 13)
    ws_collapse = wb["倒塌分析结果"] if "倒塌分析结果" in wb.sheetnames else (wb.worksheets[6] if len(wb.worksheets) > 6 else None)
    ws_members = wb["Members"] if "Members" in wb.sheetnames else (wb.worksheets[17] if len(wb.worksheets) > 17 else None)

    # Re-assign with unicode escapes to avoid source-encoding corruption.
    ws_node_risk = get_sheet_by_names_or_index(wb, ["\u8282\u70b9\u5931\u6548\u98ce\u9669\u7b49\u7ea7"], 9)
    ws_node_strategy = get_sheet_by_names_or_index(wb, ["\u8282\u70b9\u68c0\u9a8c\u7b56\u7565"], 11)
    ws_member_risk = get_sheet_by_names_or_index(wb, ["\u6784\u4ef6\u5931\u6548\u98ce\u9669\u7b49\u7ea7"], 12)
    ws_member_strategy = get_sheet_by_names_or_index(wb, ["\u6784\u4ef6\u68c0\u9a8c\u7b56\u7565"], 13)
    ws_control = wb["\u63a7\u5236\u9875\u9762"] if "\u63a7\u5236\u9875\u9762" in wb.sheetnames else (wb.worksheets[1] if len(wb.worksheets) > 1 else None)
    ws_risk_matrix = wb["\u98ce\u9669\u8bc4\u7ea7\u77e9\u9635"] if "\u98ce\u9669\u8bc4\u7ea7\u77e9\u9635" in wb.sheetnames else (wb.worksheets[2] if len(wb.worksheets) > 2 else None)

    node_risk_rows: list[dict[str, Any]] = []
    node_type_by_joint: dict[str, str] = {}
    for row in iter_data_rows(ws_node_risk, min_row=3, max_col=10):
        joint_id = to_text(row[0])
        one = {
            "joint_id": joint_id,
            "brace": to_text(row[1]),
            "joint_type": to_text(row[2]),
            "consequence_level": to_text(row[3]),
            "a": to_text(row[4]),
            "b": to_text(row[5]),
            "rm": to_text(row[6]),
            "vr": to_text(row[7]),
            "pf": to_scientific_text(row[8]),
            "collapse_prob_level": to_text(row[9]),
        }
        node_risk_rows.append(one)
        if joint_id:
            node_type_by_joint[joint_id] = one["joint_type"]

    node_strategy_rows: list[dict[str, Any]] = []
    for row in iter_data_rows(ws_node_strategy, min_row=3, max_col=18):
        node_strategy_rows.append(
            {
                "joint_id": to_text(row[0]),
                "brace": to_text(row[1]),
                "joint_type": to_text(row[2]),
                "consequence_level": to_text(row[3]),
                "collapse_prob_level": to_text(row[4]),
                "damage": to_scientific_text(row[5]),
                "beta": to_text(row[11]),
                "pf": to_scientific_text(row[12]),
                "fatigue_prob_level": to_text(row[13]),
                "combined_prob_level": to_text(row[14]),
                "node_risk_level": to_text(row[15]),
                "inspect_level": normalize_inspect_level(row[16]),
                "time_node": normalize_time_node(row[17]),
            }
        )

    member_risk_rows: list[dict[str, Any]] = []
    for row in iter_data_rows(ws_member_risk, min_row=3, max_col=11):
        member_risk_rows.append(
            {
                "joint_a": to_text(row[0]),
                "joint_b": to_text(row[1]),
                "member_type": to_text(row[2]),
                "consequence_level": to_text(row[3]),
                "a": to_text(row[4]),
                "b": to_text(row[5]),
                "rm": to_text(row[6]),
                "vr": to_text(row[7]),
                "pf": to_scientific_text(row[8]),
                "collapse_prob_level": to_text(row[9]),
                "member_risk_level": to_text(row[10]),
            }
        )

    member_strategy_rows: list[dict[str, Any]] = []
    for row in iter_data_rows(ws_member_strategy, min_row=2, max_col=7):
        member_strategy_rows.append(
            {
                "joint_a": to_text(row[0]),
                "joint_b": to_text(row[1]),
                "member_type": to_text(row[2]),
                "consequence_level": to_text(row[3]),
                "member_risk_level": to_text(row[4]),
                "inspect_level": normalize_inspect_level(row[5]),
                "time_node": normalize_time_node(row[6]),
            }
        )

    member_level_by_pair: dict[str, str] = {}
    for r in member_risk_rows:
        ja = to_text(r.get("joint_a"))
        jb = to_text(r.get("joint_b"))
        lv = to_text(r.get("collapse_prob_level"))
        if ja != "" and jb != "" and lv != "":
            member_level_by_pair[f"{ja}-{jb}"] = lv
            member_level_by_pair[f"{jb}-{ja}"] = lv

    joint_level_by_id: dict[str, str] = {}
    for r in node_risk_rows:
        jid = to_text(r.get("joint_id"))
        lv = to_text(r.get("collapse_prob_level"))
        if jid != "" and lv != "":
            joint_level_by_id[jid] = lv

    collapse_a_const = None
    collapse_b_const = None
    collapse_vr_const = None
    if ws_control is not None and ws_risk_matrix is not None:
        region_name = to_text(ws_control["B45"].value)
        if region_name != "":
            for c in range(2, 30):
                if to_text(ws_risk_matrix.cell(50, c).value) == region_name:
                    collapse_a_const = ws_risk_matrix.cell(51, c).value
                    collapse_b_const = ws_risk_matrix.cell(52, c).value
                    break
    if ws_control is not None and (collapse_a_const is None or collapse_b_const is None):
        collapse_a_const = ws_control["B46"].value
        collapse_b_const = ws_control["B47"].value
    if member_risk_rows and (collapse_a_const is None or collapse_b_const is None):
        collapse_a_const = member_risk_rows[0].get("a")
        collapse_b_const = member_risk_rows[0].get("b")
    elif node_risk_rows and (collapse_a_const is None or collapse_b_const is None):
        collapse_a_const = node_risk_rows[0].get("a")
        collapse_b_const = node_risk_rows[0].get("b")
    if member_risk_rows:
        collapse_vr_const = member_risk_rows[0].get("vr")
    elif node_risk_rows:
        collapse_vr_const = node_risk_rows[0].get("vr")

    collapse_member_rows_override, collapse_joint_rows_override = build_collapse_overrides_from_sheet(
        ws_collapse=ws_collapse,
        ws_members=ws_members,
        node_type_by_joint=node_type_by_joint,
        member_level_by_pair=member_level_by_pair,
        joint_level_by_id=joint_level_by_id,
        collapse_a_const=collapse_a_const,
        collapse_b_const=collapse_b_const,
        collapse_vr_const=collapse_vr_const,
    )

    return build_context(
        node_risk_rows,
        node_strategy_rows,
        member_risk_rows,
        member_strategy_rows,
        metadata,
        row_limits=row_limits,
        collapse_member_rows_override=collapse_member_rows_override,
        collapse_joint_rows_override=collapse_joint_rows_override,
        apply_vba_member_delete_rules=apply_vba_member_delete_rules,
        apply_vba_joint_delete_rules_current=apply_vba_joint_delete_rules_current,
        apply_vba_joint_delete_rules_future=apply_vba_joint_delete_rules_future,
    )


def load_context_from_python_workbook(
    wb,
    metadata: dict[str, Any],
    row_limits: dict[str, int] | None = None,
    strict_vba_algorithms: bool = True,
) -> dict[str, Any]:
    ws_node_risk = wb["\u8282\u70b9\u5931\u6548\u98ce\u9669\u7b49\u7ea7(Python)"]
    ws_forecast = wb["\u8282\u70b9\u5931\u6548\u98ce\u9669\u7b49\u7ea7\u9884\u6d4b(\u4ec5\u75b2\u52b3Python)"]
    ws_node_plan = wb["\u8282\u70b9\u68c0\u9a8c\u7b56\u7565(Python)"]
    ws_fatigue = wb["\u75b2\u52b3\u5206\u6790\u7ed3\u679c"] if "\u75b2\u52b3\u5206\u6790\u7ed3\u679c" in wb.sheetnames else None
    ws_members = wb["Members"] if "Members" in wb.sheetnames else None
    ws_collapse = wb["\u5012\u584c\u5206\u6790\u7ed3\u679c"] if "\u5012\u584c\u5206\u6790\u7ed3\u679c" in wb.sheetnames else None

    brace_by_joint: dict[str, tuple[str, float]] = {}
    if ws_fatigue is not None:
        for row in iter_data_rows(ws_fatigue, min_row=2, max_col=13):
            joint = to_text(row[0])
            brace = to_text(row[1])
            dmax = to_float_or_none(row[12]) or 0.0
            if not joint:
                continue
            old = brace_by_joint.get(joint)
            if old is None or dmax > old[1]:
                brace_by_joint[joint] = (brace, dmax)

    node_risk_rows: list[dict[str, Any]] = []
    node_base_by_joint: dict[str, dict[str, Any]] = {}
    for row in iter_data_rows(ws_node_risk, min_row=2, max_col=15):
        joint_id = to_text(row[0])
        if joint_id == "":
            continue
        one = {
            "joint_id": joint_id,
            "brace": brace_by_joint.get(joint_id, ("", 0.0))[0],
            "joint_type": to_text(row[1]),
            "consequence_level": "3",
            "a": to_text(row[2]),
            "b": to_text(row[3]),
            "rm": to_text(row[4]),
            "vr": to_text(row[5]),
            "pf": to_text(row[6]),
            "collapse_prob_level": to_text(row[7]),
            "damage": to_text(row[8]),
            "beta": to_text(row[10]),
            "pf_fatigue": to_text(row[11]),
            "fatigue_prob_level": to_text(row[12]),
            "combined_prob_level": to_text(row[13]),
            "node_risk_level": to_text(row[14]),
        }
        node_risk_rows.append(one)
        node_base_by_joint[joint_id] = one

    collapse_a_const = None
    collapse_b_const = None
    collapse_vr_const = None
    if node_risk_rows:
        collapse_a_const = node_risk_rows[0].get("a")
        collapse_b_const = node_risk_rows[0].get("b")
        collapse_vr_const = node_risk_rows[0].get("vr")

    node_plan_map: dict[tuple[str, str], dict[str, Any]] = {}
    for row in iter_data_rows(ws_node_plan, min_row=2, max_col=5):
        joint_id = to_text(row[0])
        time_node = normalize_plan_time(row[1])
        if joint_id == "" or time_node == "":
            continue
        node_plan_map[(joint_id, time_node)] = {
            "inspect_level": normalize_inspect_level(row[3]),
            "risk_grade": to_text(row[2]),
        }

    node_strategy_rows: list[dict[str, Any]] = []
    for base in node_risk_rows:
        joint_id = base["joint_id"]
        plan_cur = node_plan_map.get((joint_id, TIME_CURRENT), {})
        node_strategy_rows.append(
            {
                "joint_id": joint_id,
                "brace": base["brace"],
                "joint_type": base["joint_type"],
                "consequence_level": base["consequence_level"],
                "collapse_prob_level": base["collapse_prob_level"],
                "damage": to_scientific_text(base["damage"]),
                "beta": base["beta"],
                "pf": to_scientific_text(base["pf_fatigue"]),
                "fatigue_prob_level": base["fatigue_prob_level"],
                "combined_prob_level": base["combined_prob_level"],
                "node_risk_level": base["node_risk_level"],
                "inspect_level": plan_cur.get("inspect_level", "III"),
                "time_node": TIME_CURRENT,
            }
        )

    forecast_headers = [to_text(ws_forecast.cell(row=1, column=c).value) for c in range(1, min(ws_forecast.max_column, 120) + 1)]
    is_long_forecast = ("Year" in forecast_headers and "D_future" in forecast_headers) or (
        len(forecast_headers) >= 7 and forecast_headers[:7] == ["JoitID", "Year", "D_future", "beta", "Pf", "PossLevel", "RiskGrade"]
    )

    if is_long_forecast:
        for row in iter_data_rows(ws_forecast, min_row=2, max_col=7):
            joint_id = to_text(row[0])
            time_node = forecast_year_to_time_node(to_int_or_none(row[1]))
            if joint_id == "" or time_node == "" or time_node == TIME_CURRENT:
                continue

            base = node_base_by_joint.get(joint_id, {})
            collapse_lv = to_int_or_none(base.get("collapse_prob_level"))
            fatigue_lv = to_int_or_none(row[5])
            if collapse_lv is None:
                combined_lv = fatigue_lv
            elif fatigue_lv is None:
                combined_lv = collapse_lv
            else:
                combined_lv = min(collapse_lv, fatigue_lv)

            plan = node_plan_map.get((joint_id, time_node), {})
            node_strategy_rows.append(
                {
                    "joint_id": joint_id,
                    "brace": to_text(base.get("brace")),
                    "joint_type": to_text(base.get("joint_type")),
                    "consequence_level": to_text(base.get("consequence_level")) or "3",
                    "collapse_prob_level": to_text(base.get("collapse_prob_level")),
                    "damage": to_scientific_text(row[2]),
                    "beta": to_text(row[3]),
                    "pf": to_scientific_text(row[4]),
                    "fatigue_prob_level": to_text(row[5]),
                    "combined_prob_level": "" if combined_lv is None else str(combined_lv),
                    "node_risk_level": to_text(row[6]) or to_text(base.get("node_risk_level")),
                    "inspect_level": plan.get("inspect_level", "III"),
                    "time_node": time_node,
                }
            )
    else:
        # VBA-wide forecast sheet:
        # [JoitID, Brace, JointType, ConsequenceLevel, CollapsePossLevel,
        #  N_*, N+5_*, N+10_*, N+15_*, N+20_*, N+25_*]
        horizon_blocks = [
            ("N", TIME_CURRENT, 5),
            ("N+5", "第5年", 16),
            ("N+10", "第10年", 27),
            ("N+15", "第15年", 38),
            ("N+20", "第20年", 49),
            ("N+25", "第25年", 60),
        ]
        for row in iter_data_rows(ws_forecast, min_row=2, max_col=71):
            joint_id = to_text(row[0])
            if joint_id == "":
                continue
            base = node_base_by_joint.get(joint_id, {})
            collapse_lv = to_int_or_none(base.get("collapse_prob_level"))

            for _, time_node, start in horizon_blocks:
                if time_node == TIME_CURRENT:
                    continue
                if len(row) <= start + 10:
                    continue

                damage = to_scientific_text(row[start + 0])
                beta = to_text(row[start + 6])
                pf = to_scientific_text(row[start + 7])
                fatigue_text = to_text(row[start + 8])
                combined_text = to_text(row[start + 9])
                risk_text = to_text(row[start + 10])

                # Skip empty block rows.
                if damage == "" and beta == "" and pf == "" and fatigue_text == "" and combined_text == "" and risk_text == "":
                    continue

                fatigue_lv = to_int_or_none(fatigue_text)
                combined_lv = to_int_or_none(combined_text)
                if combined_lv is None:
                    if collapse_lv is None:
                        combined_lv = fatigue_lv
                    elif fatigue_lv is None:
                        combined_lv = collapse_lv
                    else:
                        combined_lv = min(collapse_lv, fatigue_lv)

                plan = node_plan_map.get((joint_id, time_node), {})
                node_strategy_rows.append(
                    {
                        "joint_id": joint_id,
                        "brace": to_text(base.get("brace")) or to_text(row[1]),
                        "joint_type": to_text(base.get("joint_type")) or to_text(row[2]),
                        "consequence_level": to_text(base.get("consequence_level")) or to_text(row[3]) or "3",
                        "collapse_prob_level": to_text(base.get("collapse_prob_level")) or to_text(row[4]),
                        "damage": damage,
                        "beta": beta,
                        "pf": pf,
                        "fatigue_prob_level": fatigue_text,
                        "combined_prob_level": "" if combined_lv is None else str(combined_lv),
                        "node_risk_level": risk_text or to_text(base.get("node_risk_level")),
                        "inspect_level": plan.get("inspect_level", "III"),
                        "time_node": time_node,
                    }
                )

    member_type_by_pair: dict[str, str] = {}
    collapse_member_factor: dict[str, float | None] = {}
    collapse_joint_factor: dict[str, float | None] = {}
    if ws_collapse is not None:
        for row in iter_data_rows(ws_collapse, min_row=2, max_col=6, key_col_index=1):
            fail_type = to_text(row[1])
            location = to_text(row[2])
            factor = to_float_or_none(row[3])
            if fail_type == "\u6784\u4ef6\u5931\u6548" and location:
                old = collapse_member_factor.get(location)
                if old is None or (factor is not None and factor < old):
                    collapse_member_factor[location] = factor
            elif fail_type == "\u8282\u70b9\u5931\u6548" and location:
                old = collapse_joint_factor.get(location)
                if old is None or (factor is not None and factor < old):
                    collapse_joint_factor[location] = factor

    member_risk_rows: list[dict[str, Any]] = []
    seen_member_pairs: set[tuple[str, str]] = set()
    if ws_members is not None:
        for row in iter_data_rows(ws_members, min_row=2, max_col=7):
            joint_a = to_text(row[0])
            joint_b = to_text(row[1])
            if joint_a == "" or joint_b == "":
                continue
            pair = (joint_a, joint_b)
            if pair in seen_member_pairs:
                continue
            seen_member_pairs.add(pair)

            pair_key = f"{joint_a}-{joint_b}"
            rev_key = f"{joint_b}-{joint_a}"
            mtype = to_text(row[4]) or "Other"
            if pair_key not in member_type_by_pair:
                member_type_by_pair[pair_key] = mtype
            if rev_key not in member_type_by_pair:
                member_type_by_pair[rev_key] = mtype

            base_a = node_base_by_joint.get(joint_a, {})
            base_b = node_base_by_joint.get(joint_b, {})

            collapse_a = to_int_or_none(base_a.get("collapse_prob_level"))
            collapse_b = to_int_or_none(base_b.get("collapse_prob_level"))
            if collapse_a is None:
                collapse_lv = collapse_b
            elif collapse_b is None:
                collapse_lv = collapse_a
            else:
                collapse_lv = min(collapse_a, collapse_b)

            pf_a = to_float_or_none(base_a.get("pf"))
            pf_b = to_float_or_none(base_b.get("pf"))
            if pf_a is None:
                pf_member = pf_b
            elif pf_b is None:
                pf_member = pf_a
            else:
                pf_member = min(pf_a, pf_b)

            member_risk = choose_higher_risk_grade(base_a.get("node_risk_level"), base_b.get("node_risk_level"))
            if member_risk == "":
                member_risk = collapse_level_to_risk_grade(collapse_lv) or "\u56db"

            factor = collapse_member_factor.get(pair_key)
            if factor is None:
                factor = collapse_member_factor.get(rev_key)

            if factor is not None:
                pf_calc = collapse_pf_from_factor(collapse_a_const, collapse_b_const, factor, collapse_vr_const)
                rm_val = f"{factor:g}"
                pf_val = "" if pf_calc is None else f"{pf_calc:g}"
                collapse_level = "1"
            else:
                rm_val = to_text(base_a.get("rm")) or to_text(base_b.get("rm"))
                pf_val = "" if pf_member is None else f"{pf_member:g}"
                collapse_level = "" if collapse_lv is None else str(collapse_lv)

            member_risk_rows.append(
                {
                    "joint_a": joint_a,
                    "joint_b": joint_b,
                    "member_type": mtype,
                    "consequence_level": "3",
                    "a": to_text(base_a.get("a")) or to_text(base_b.get("a")),
                    "b": to_text(base_a.get("b")) or to_text(base_b.get("b")),
                    "rm": rm_val,
                    "vr": to_text(base_a.get("vr")) or to_text(base_b.get("vr")),
                    "pf": pf_val,
                    "collapse_prob_level": collapse_level,
                    "member_risk_level": member_risk,
                }
            )

    member_level_policy = {"\u4e00": "II", "\u4e8c": "II", "\u4e09": "III", "\u56db": "IV", "\u4e94": "IV"}
    member_strategy_rows: list[dict[str, Any]] = []
    for r in member_risk_rows:
        member_strategy_rows.append(
            {
                "joint_a": r["joint_a"],
                "joint_b": r["joint_b"],
                "member_type": r["member_type"],
                "consequence_level": r["consequence_level"],
                "member_risk_level": r["member_risk_level"],
                "inspect_level": member_level_policy.get(to_text(r["member_risk_level"]), "III"),
                "time_node": TIME_CURRENT,
            }
        )

    collapse_member_rows_override: list[dict[str, Any]] = []
    for location, factor in sorted(
        collapse_member_factor.items(),
        key=lambda kv: (
            9999 if kv[1] is None else kv[1],
            kv[0],
        ),
    ):
        joint_a = ""
        joint_b = ""
        if "-" in location:
            joint_a, joint_b = location.split("-", 1)
        mtype = member_type_by_pair.get(location) or member_type_by_pair.get(f"{joint_b}-{joint_a}") or "Other"
        pf_val = collapse_pf_from_factor(collapse_a_const, collapse_b_const, factor, collapse_vr_const)
        collapse_member_rows_override.append(
            {
                "joint_a": joint_a,
                "joint_b": joint_b,
                "member_type": mtype,
                "a": to_text(collapse_a_const),
                "b": to_text(collapse_b_const),
                "rm": "" if factor is None else f"{factor:g}",
                "vr": to_text(collapse_vr_const),
                "pf": "" if pf_val is None else f"{pf_val:g}",
                "collapse_prob_level": "1",
            }
        )

    collapse_joint_rows_override: list[dict[str, Any]] = []
    for joint_id, factor in sorted(
        collapse_joint_factor.items(),
        key=lambda kv: (
            9999 if kv[1] is None else kv[1],
            kv[0],
        ),
    ):
        base = node_base_by_joint.get(joint_id, {})
        pf_val = collapse_pf_from_factor(collapse_a_const, collapse_b_const, factor, collapse_vr_const)
        collapse_joint_rows_override.append(
            {
                "joint_id": joint_id,
                "joint_type": to_text(base.get("joint_type")),
                "a": to_text(collapse_a_const),
                "b": to_text(collapse_b_const),
                "rm": "" if factor is None else f"{factor:g}",
                "vr": to_text(collapse_vr_const),
                "pf": "" if pf_val is None else f"{pf_val:g}",
                "collapse_prob_level": to_text(base.get("collapse_prob_level")),
            }
        )

    collapse_member_override = None
    collapse_joint_override = None
    # Do not inject fallback/override rows here.
    # Report tables must be driven by real computed risk sheets.

    return build_context(
        node_risk_rows,
        node_strategy_rows,
        member_risk_rows,
        member_strategy_rows,
        metadata,
        row_limits=row_limits,
        collapse_member_rows_override=collapse_member_override,
        collapse_joint_rows_override=collapse_joint_override,
        apply_vba_member_delete_rules=strict_vba_algorithms,
        apply_vba_joint_delete_rules=strict_vba_algorithms,
    )


def load_context_from_workbook(
    workbook_path: Path,
    metadata: dict[str, Any],
    row_limits: dict[str, int] | None = None,
    strict_vba_algorithms: bool = True,
    apply_vba_member_delete_rules: bool = False,
    apply_vba_joint_delete_rules_current: bool = False,
    apply_vba_joint_delete_rules_future: bool = False,
) -> dict[str, Any]:
    wb = load_workbook(workbook_path, data_only=True, read_only=True)

    # Strict mode: always read template sheets directly (legacy-style).
    # This keeps report output aligned with VBA sheet results and avoids
    # secondary reconstruction differences.
    if strict_vba_algorithms:
        return load_context_from_legacy_workbook(
            wb,
            metadata,
            row_limits=row_limits,
            apply_vba_member_delete_rules=apply_vba_member_delete_rules,
            apply_vba_joint_delete_rules_current=apply_vba_joint_delete_rules_current,
            apply_vba_joint_delete_rules_future=apply_vba_joint_delete_rules_future,
        )

    python_sheet_names = {
        "\u8282\u70b9\u5931\u6548\u98ce\u9669\u7b49\u7ea7(Python)",
        "\u8282\u70b9\u5931\u6548\u98ce\u9669\u7b49\u7ea7\u9884\u6d4b(\u4ec5\u75b2\u52b3Python)",
        "\u8282\u70b9\u68c0\u9a8c\u7b56\u7565(Python)",
    }
    if python_sheet_names.issubset(set(wb.sheetnames)):
        return load_context_from_python_workbook(
            wb,
            metadata,
            row_limits=row_limits,
            strict_vba_algorithms=strict_vba_algorithms,
        )
    return load_context_from_legacy_workbook(
        wb,
        metadata,
        row_limits=row_limits,
        apply_vba_member_delete_rules=apply_vba_member_delete_rules,
        apply_vba_joint_delete_rules_current=apply_vba_joint_delete_rules_current,
        apply_vba_joint_delete_rules_future=apply_vba_joint_delete_rules_future,
    )


def list_appendix_files(path: Path) -> list[Path]:
    return sorted((p for p in path.rglob("*") if p.is_file()), key=lambda p: (str(p.parent), p.name.lower()))


def _text_entry(text: str) -> dict[str, Any]:
    return {"kind": "text", "text": text}


def _link_entry(text: str, target: Path) -> dict[str, Any]:
    return {"kind": "link", "text": text, "target": target.resolve().as_uri()}


def build_appendix_sections(
    appendix_a_file: str = "",
    appendix_b_file: str = "",
    appendix_c_dirs: list[str] | None = None,
) -> list[dict[str, Any]]:
    appendix_c_dirs = appendix_c_dirs or []

    def build_file_section(heading: str, path_text: str) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        if not path_text.strip():
            entries.append(_text_entry("未配置文件路径。"))
        else:
            path = Path(path_text).resolve()
            if path.exists() and path.is_file():
                entries.append(_text_entry(f"来源文件：{path}"))
                entries.append(_link_entry(f"打开文件：{path.name}", path))
            else:
                entries.append(_text_entry(f"文件不存在：{path}"))
        return {"heading": heading, "entries": entries}

    sections = [
        build_file_section(APPENDIX_A_HEADING, appendix_a_file),
        build_file_section(APPENDIX_B_HEADING, appendix_b_file),
    ]

    summary_entries: list[dict[str, Any]] = []
    if appendix_c_dirs:
        summary_entries.append(_text_entry("以下附件C子项按配置目录自动读取该目录下的全部文件。"))
        for idx, path_text in enumerate(appendix_c_dirs[: len(APPENDIX_C_SUBHEADINGS)], start=1):
            path = Path(path_text).resolve()
            if not path_text.strip():
                summary_entries.append(_text_entry(f"C.{idx}：未配置目录路径。"))
                continue
            if not path.exists() or not path.is_dir():
                summary_entries.append(_text_entry(f"C.{idx}：目录不存在：{path}"))
                continue
            files = list_appendix_files(path)
            summary_entries.append(_text_entry(f"C.{idx}：{path}（{len(files)} 个文件）"))
    else:
        summary_entries.append(_text_entry("未配置附件C目录。"))
    sections.append({"heading": APPENDIX_C_MAIN_HEADING, "entries": summary_entries})

    for heading, path_text in zip(APPENDIX_C_SUBHEADINGS, appendix_c_dirs):
        entries: list[dict[str, Any]] = []
        if not path_text.strip():
            entries.append(_text_entry("未配置目录路径。"))
            sections.append({"heading": heading, "entries": entries})
            continue
        path = Path(path_text).resolve()
        if not path.exists() or not path.is_dir():
            entries.append(_text_entry(f"目录不存在：{path}"))
            sections.append({"heading": heading, "entries": entries})
            continue
        files = list_appendix_files(path)
        entries.append(_text_entry(f"来源目录：{path}"))
        entries.append(_text_entry(f"文件数量：{len(files)}"))
        if files:
            for idx, file_path in enumerate(files, start=1):
                entries.append(_link_entry(f"{idx}. {file_path.name}", file_path))
        else:
            entries.append(_text_entry("该目录下未读取到文件。"))
        sections.append({"heading": heading, "entries": entries})

    for heading in APPENDIX_C_SUBHEADINGS[len(appendix_c_dirs) :]:
        sections.append({"heading": heading, "entries": [_text_entry("未配置目录路径。")]})

    return sections


def build_appendix_pdf_plan(
    appendix_a_file: str = "",
    appendix_b_file: str = "",
    appendix_c_dirs: list[str] | None = None,
) -> list[dict[str, Any]]:
    appendix_c_dirs = appendix_c_dirs or []

    sections: list[dict[str, Any]] = []
    for heading, path_text in [
        (APPENDIX_A_HEADING, appendix_a_file),
        (APPENDIX_B_HEADING, appendix_b_file),
    ]:
        files: list[Path] = []
        if path_text.strip():
            path = Path(path_text).resolve()
            if path.exists() and path.is_file():
                files.append(path)
        sections.append({"heading": heading, "files": files})

    sections.append({"heading": APPENDIX_C_MAIN_HEADING, "files": []})
    for heading, path_text in zip(APPENDIX_C_SUBHEADINGS, appendix_c_dirs):
        files: list[Path] = []
        if path_text.strip():
            path = Path(path_text).resolve()
            if path.exists() and path.is_dir():
                files = list_appendix_files(path)
        sections.append({"heading": heading, "files": files})

    for heading in APPENDIX_C_SUBHEADINGS[len(appendix_c_dirs) :]:
        sections.append({"heading": heading, "files": []})

    return sections


def get_table_list(document_root: ET.Element) -> list[ET.Element]:
    body = document_root.find("w:body", NS)
    if body is None:
        return []
    return [child for child in body if child.tag.endswith("tbl")]


def get_text_nodes(el: ET.Element) -> list[ET.Element]:
    return el.findall(".//w:t", NS)


def set_cell_text(tc: ET.Element, value: str) -> None:
    text_nodes = get_text_nodes(tc)
    if not text_nodes:
        p = ET.SubElement(tc, f"{{{NS['w']}}}p")
        r = ET.SubElement(p, f"{{{NS['w']}}}r")
        t = ET.SubElement(r, f"{{{NS['w']}}}t")
        t.text = value
        return
    text_nodes[0].text = value
    for t in text_nodes[1:]:
        t.text = ""


def set_paragraph_text(p: ET.Element, value: str) -> None:
    text_nodes = get_text_nodes(p)
    if not text_nodes:
        r = ET.SubElement(p, f"{{{NS['w']}}}r")
        t = ET.SubElement(r, f"{{{NS['w']}}}t")
        t.text = value
        return
    text_nodes[0].text = value
    for t in text_nodes[1:]:
        t.text = ""


def paragraph_text(p: ET.Element) -> str:
    return "".join((t.text or "") for t in p.findall(".//w:t", NS)).strip()


def create_simple_paragraph(value: str) -> ET.Element:
    p = ET.Element(f"{{{NS['w']}}}p")
    r = ET.SubElement(p, f"{{{NS['w']}}}r")
    t = ET.SubElement(r, f"{{{NS['w']}}}t")
    if value.startswith(" ") or value.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = value
    return p


def _next_relationship_id(rels_root: ET.Element) -> str:
    max_idx = 0
    for rel in rels_root.findall(f"{{{REL_NS}}}Relationship"):
        rel_id = rel.get("Id", "")
        if rel_id.startswith("rId"):
            suffix = rel_id[3:]
            if suffix.isdigit():
                max_idx = max(max_idx, int(suffix))
    return f"rId{max_idx + 1}"


def create_hyperlink_paragraph(text: str, target: str, rels_root: ET.Element) -> ET.Element:
    rel_id = _next_relationship_id(rels_root)
    ET.SubElement(
        rels_root,
        f"{{{REL_NS}}}Relationship",
        {
            "Id": rel_id,
            "Type": HYPERLINK_REL_TYPE,
            "Target": target,
            "TargetMode": "External",
        },
    )

    p = ET.Element(f"{{{NS['w']}}}p")
    hyperlink = ET.SubElement(p, f"{{{NS['w']}}}hyperlink", {f"{{{NS['r']}}}id": rel_id})
    run = ET.SubElement(hyperlink, f"{{{NS['w']}}}r")
    run_pr = ET.SubElement(run, f"{{{NS['w']}}}rPr")
    ET.SubElement(run_pr, f"{{{NS['w']}}}rStyle", {f"{{{NS['w']}}}val": "Hyperlink"})
    text_el = ET.SubElement(run, f"{{{NS['w']}}}t")
    text_el.text = text
    return p


def create_paragraph_from_entry(entry: dict[str, Any], rels_root: ET.Element) -> ET.Element:
    if entry.get("kind") == "link":
        return create_hyperlink_paragraph(str(entry.get("text", "")), str(entry.get("target", "")), rels_root)
    return create_simple_paragraph(str(entry.get("text", "")))


def insert_paragraphs_after(body: ET.Element, anchor: ET.Element, entries: list[dict[str, Any]], rels_root: ET.Element) -> ET.Element:
    current = anchor
    for entry in entries:
        new_paragraph = create_paragraph_from_entry(entry, rels_root)
        idx = list(body).index(current)
        body.insert(idx + 1, new_paragraph)
        current = new_paragraph
    return current


def append_paragraphs_before_sectpr(body: ET.Element, entries: list[dict[str, Any]], rels_root: ET.Element) -> ET.Element | None:
    current: ET.Element | None = None
    insert_idx = len(body)
    for idx, child in enumerate(list(body)):
        if child.tag == f"{{{NS['w']}}}sectPr":
            insert_idx = idx
            break
    for entry in entries:
        new_paragraph = create_paragraph_from_entry(entry, rels_root)
        body.insert(insert_idx, new_paragraph)
        insert_idx += 1
        current = new_paragraph
    return current


def fill_appendix_sections(document_root: ET.Element, rels_root: ET.Element, context: dict[str, Any]) -> None:
    body = document_root.find("w:body", NS)
    if body is None:
        return

    sections = context.get("appendix_sections", []) or []
    if not sections:
        return

    direct_paragraphs = [child for child in list(body) if child.tag == f"{{{NS['w']}}}p"]
    paragraph_map = {paragraph_text(p): p for p in direct_paragraphs if paragraph_text(p)}

    last_inserted: ET.Element | None = None
    for section in sections:
        heading = str(section.get("heading", "")).strip()
        entries = [x for x in section.get("entries", []) if str(x.get("text", "")).strip()]
        if not heading or not entries:
            continue
        anchor = paragraph_map.get(heading)
        if anchor is None:
            created = append_paragraphs_before_sectpr(body, [_text_entry(heading), *entries], rels_root)
            if created is not None:
                last_inserted = created
            continue
        last_inserted = insert_paragraphs_after(body, anchor, entries, rels_root)


def render_pdf_to_jpeg_pages(pdf_path: Path, output_dir: Path, dpi: int = APPENDIX_RENDER_DPI) -> list[Path]:
    import fitz
    from PIL import Image

    out_paths: list[Path] = []
    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    with fitz.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            png_bytes = pix.tobytes("png")
            src = Image.open(io.BytesIO(png_bytes))
            img = src.convert("RGB")
            src.close()
            out_path = output_dir / f".appendix_render_{uuid.uuid4().hex}_{page_idx}.jpg"
            img.save(out_path, format="JPEG", quality=APPENDIX_JPEG_QUALITY, optimize=True)
            img.close()
            out_paths.append(out_path)
    return out_paths


def insert_appendix_pdf_images(docx_path: Path, context: dict[str, Any]) -> None:
    from docx import Document
    from docx.shared import Inches

    sections = context.get("appendix_pdf_plan", []) or []
    if not sections:
        return

    def find_heading_paragraph(document: Any, heading: str) -> Any | None:
        for paragraph in document.paragraphs:
            if paragraph.text.strip() == heading:
                return paragraph
        return None

    def paragraph_is_blank(paragraph: Any) -> bool:
        if paragraph.text.strip():
            return False
        if paragraph._p.xpath(".//w:drawing"):
            return False
        return True

    def remove_paragraph(paragraph: Any) -> None:
        element = paragraph._element
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    document = Document(docx_path)
    width = Inches(APPENDIX_IMAGE_WIDTH_INCHES)
    heading_set = {str(section.get("heading", "")).strip() for section in sections if str(section.get("heading", "")).strip()}

    def insert_paragraph_after(paragraph: Any, text: str = "") -> Any:
        new_para = document.add_paragraph()
        if text:
            new_para.add_run(text)
        paragraph._p.addnext(new_para._p)
        return new_para

    def clear_placeholder_paragraphs_after(anchor: Any) -> None:
        # The template leaves several blank paragraphs and page-break placeholders
        # after each appendix heading. Remove those placeholders first so the
        # appendix content starts from the first available blank spot on the
        # same page as the matched heading.
        paragraphs_snapshot = list(document.paragraphs)
        try:
            start_idx = paragraphs_snapshot.index(anchor) + 1
        except ValueError:
            return

        to_remove: list[Any] = []
        for paragraph in paragraphs_snapshot[start_idx:]:
            text = paragraph.text.strip()
            if text in heading_set:
                break
            if not paragraph_is_blank(paragraph):
                break
            to_remove.append(paragraph)

        for paragraph in to_remove:
            remove_paragraph(paragraph)

    temp_images: list[Path] = []
    try:
        for section in sections:
            heading = str(section.get("heading", "")).strip()
            files = [Path(p) for p in section.get("files", [])]
            anchor = find_heading_paragraph(document, heading)
            if anchor is None or not files:
                continue

            clear_placeholder_paragraphs_after(anchor)
            current = anchor
            for file_path in files:
                if file_path.suffix.lower() != ".pdf":
                    continue

                try:
                    image_paths = render_pdf_to_jpeg_pages(file_path, docx_path.parent)
                    temp_images.extend(image_paths)
                except Exception as exc:
                    current = insert_paragraph_after(current, f"PDF渲染失败：{file_path.name} ({type(exc).__name__}: {exc})")
                    continue

                for image_path in image_paths:
                    img_para = document.add_paragraph()
                    img_para.add_run().add_picture(str(image_path), width=width)
                    current._p.addnext(img_para._p)
                    current = img_para
        document.save(docx_path)
    finally:
        for image_path in temp_images:
            try:
                image_path.unlink(missing_ok=True)
            except Exception:
                pass


def replace_dynamic_table_rows(table: ET.Element, rows_data: list[dict[str, Any]], header_rows: int, col_templates: list[str], env: Environment) -> None:
    rows = table.findall("w:tr", NS)
    if len(rows) <= header_rows:
        return
    prototype = rows[header_rows]
    for row_el in rows[header_rows:]:
        table.remove(row_el)

    if not rows_data:
        return

    compiled_templates = [env.from_string(tpl) for tpl in col_templates]
    for row_data in rows_data:
        new_row = copy.deepcopy(prototype)
        cells = new_row.findall("w:tc", NS)
        for idx, tpl in enumerate(compiled_templates):
            if idx >= len(cells):
                break
            val = tpl.render(row=row_data)
            set_cell_text(cells[idx], val)
        # Clear any remaining cells in the prototype row to avoid stale
        # template literals leaking into rendered data rows.
        for idx in range(len(compiled_templates), len(cells)):
            set_cell_text(cells[idx], "")
        table.append(new_row)


def set_table_cell(table: ET.Element, row_idx: int, col_idx: int, value: str) -> None:
    rows = table.findall("w:tr", NS)
    if row_idx >= len(rows):
        return
    cells = rows[row_idx].findall("w:tc", NS)
    if col_idx >= len(cells):
        return
    set_cell_text(cells[col_idx], value)


def fill_summary_tables(document_root: ET.Element, context: dict[str, Any]) -> None:
    tables = get_table_list(document_root)
    if len(tables) < 16:
        return

    # Table 9: member risk distribution
    table9 = tables[9]
    for idx, risk in enumerate(RISK_LEVEL_ORDER, start=1):
        set_table_cell(table9, 2, idx, str(context["member_risk_counts"].get(risk, 0)))
        set_table_cell(table9, 3, idx, context["member_risk_ratios"].get(risk, "0.00%"))

    # Table 10: node weld risk distribution by time (current + 5/10/15/20/25)
    table10 = tables[10]
    block_starts = [0, 4, 8, 12, 16, 20]
    for block_idx, block in enumerate(context["node_summary_blocks"][: len(block_starts)]):
        base = block_starts[block_idx]
        set_table_cell(table10, base, 0, block["title"])
        for ci, risk in enumerate(RISK_LEVEL_ORDER, start=1):
            set_table_cell(table10, base + 2, ci, str(block["counts"].get(risk, 0)))
            set_table_cell(table10, base + 3, ci, block["ratios"].get(risk, "0.00%"))

    # Table 14: member inspection summary
    table14 = tables[14]
    for row_idx, risk in enumerate(RISK_LEVEL_ORDER, start=2):
        entry = next((x for x in context["member_inspection_summary"] if x["risk_level"] == risk), None)
        if entry is None:
            entry = {"count": 0, "II": 0, "III": 0, "IV": 0}
        set_table_cell(table14, row_idx, 0, risk)
        set_table_cell(table14, row_idx, 1, str(entry["count"]))
        set_table_cell(table14, row_idx, 2, "-" if entry["II"] == 0 else str(entry["II"]))
        set_table_cell(table14, row_idx, 3, "-" if entry["III"] == 0 else str(entry["III"]))
        set_table_cell(table14, row_idx, 4, "-" if entry["IV"] == 0 else str(entry["IV"]))
    set_table_cell(table14, 7, 1, str(context["member_inspection_total"]))
    set_table_cell(table14, 7, 2, str(context["member_inspection_total_II"]))
    set_table_cell(table14, 7, 3, str(context["member_inspection_total_III"]))
    set_table_cell(table14, 7, 4, str(context["member_inspection_total_IV"]))

    # Table 15: node inspection summary by future 5-year checkpoints
    table15 = tables[15]
    block_starts_15 = [0, 8, 16, 24, 32]
    for block_idx, block in enumerate(context["node_inspection_blocks"][: len(block_starts_15)]):
        base = block_starts_15[block_idx]
        set_table_cell(table15, base, 0, block["time_node"])
        for ridx, risk in enumerate(RISK_LEVEL_ORDER, start=2):
            entry = next((x for x in block["summary_rows"] if x["risk_level"] == risk), None)
            if entry is None:
                entry = {"count": 0, "II": 0, "III": 0, "IV": 0}
            set_table_cell(table15, ridx + base, 0, risk)
            set_table_cell(table15, ridx + base, 1, str(entry["count"]))
            set_table_cell(table15, ridx + base, 2, "-" if entry["II"] == 0 else str(entry["II"]))
            set_table_cell(table15, ridx + base, 3, "-" if entry["III"] == 0 else str(entry["III"]))
            set_table_cell(table15, ridx + base, 4, "-" if entry["IV"] == 0 else str(entry["IV"]))
        set_table_cell(table15, base + 7, 1, str(block["total_count"]))
        set_table_cell(table15, base + 7, 2, str(block["total_II"]))
        set_table_cell(table15, base + 7, 3, str(block["total_III"]))
        set_table_cell(table15, base + 7, 4, str(block["total_IV"]))


def should_render_detail_table(context: dict[str, Any], context_key: str) -> bool:
    if context_key not in OPTIONAL_WORD_DETAIL_CONTEXT_KEYS:
        return True
    return bool(context.get("include_word_plan_detail_tables", False))


def fill_cover_paragraphs(document_root: ET.Element, context: dict[str, Any], env: Environment) -> None:
    body = document_root.find("w:body", NS)
    if body is None:
        return

    cover_title_suffix = "\u5e73\u53f0\u98ce\u9669\u8bc4\u4f30\u53ca\u68c0\u6d4b\u7b56\u7565\u62a5\u544a"
    title_tpl = env.from_string("{{ platform_name }}" + cover_title_suffix)
    date_tpl = env.from_string("{{ report_date }}")

    for p in body.findall("w:p", NS):
        text = "".join((t.text or "") for t in p.findall(".//w:t", NS))
        if cover_title_suffix in text:
            set_paragraph_text(p, title_tpl.render(platform_name=context["platform_name"]))
            continue
        if "xx\u6708xx\u65e5" in text or "xxxx\u5e74xx\u6708xx\u65e5" in text:
            set_paragraph_text(p, date_tpl.render(report_date=context["report_date"]))


def build_missing_requirements(context: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if to_text(context.get("platform_name")) == "":
        missing.append("封面平台名称(platform_name)缺失")
    if to_text(context.get("report_date")) == "":
        missing.append("封面报告日期(report_date)缺失")
    if len(context.get("fatigue_failure_rows", [])) == 0:
        missing.append("节点焊缝疲劳失效概率表无数据")
    if len(context.get("collapse_member_rows", [])) == 0:
        missing.append("构件倒塌失效概率表无数据")
    if len(context.get("collapse_joint_rows", [])) == 0:
        missing.append("节点倒塌失效概率表无数据")
    if len(context.get("node_risk_rows_current", [])) == 0:
        missing.append("当前节点风险等级表无数据")
    if len(context.get("member_risk_rows", [])) == 0:
        missing.append("构件风险等级表无数据")
    if context.get("include_word_plan_detail_tables", False) and len(context.get("member_inspection_rows", [])) == 0:
        missing.append("构件检验计划表无数据")
    if context.get("include_word_plan_detail_tables", False) and len(context.get("node_inspection_rows_future", [])) == 0:
        missing.append("节点检验计划(未来时间节点)表无数据")
    return missing


def build_row_cap_notes(context: dict[str, Any]) -> list[str]:
    total_counts = context.get("row_counts", {}) or {}
    limits = context.get("row_limits", {}) or {}

    mapping = {
        "fatigue_failure_rows": "fatigue_failure_rows_total",
        "collapse_member_rows": "collapse_member_rows_total",
        "collapse_joint_rows": "collapse_joint_rows_total",
        "node_risk_rows_current": "node_risk_rows_current_total",
        "member_risk_rows": "member_risk_rows_total",
        "member_inspection_rows": "member_inspection_rows_total",
        "node_inspection_rows_future": "node_inspection_rows_future_total",
    }

    notes: list[str] = []
    for key, total_key in mapping.items():
        shown = len(context.get(key, []))
        total = int(total_counts.get(total_key, shown))
        limit = limits.get(key)
        if isinstance(limit, int) and limit > 0 and total > shown:
            notes.append(f"{key}: {shown}/{total} (limited by {limit})")
    return notes


def render_report(template_docx: Path, output_docx: Path, context: dict[str, Any]) -> None:
    env = Environment(undefined=StrictUndefined, autoescape=False, trim_blocks=True, lstrip_blocks=True)

    with zipfile.ZipFile(template_docx, "r") as zin:
        doc_xml = zin.read("word/document.xml")
        root = ET.fromstring(doc_xml)
        rels_xml = zin.read("word/_rels/document.xml.rels")
        rels_root = ET.fromstring(rels_xml)

        fill_cover_paragraphs(root, context, env)
        tables = get_table_list(root)
        for spec in DYNAMIC_TABLE_SPECS:
            if spec.table_index >= len(tables):
                continue
            if not should_render_detail_table(context, spec.context_key):
                replace_dynamic_table_rows(
                    table=tables[spec.table_index],
                    rows_data=[],
                    header_rows=spec.header_rows,
                    col_templates=spec.column_templates,
                    env=env,
                )
                continue
            rows_data = context.get(spec.context_key, [])
            replace_dynamic_table_rows(
                table=tables[spec.table_index],
                rows_data=rows_data,
                header_rows=spec.header_rows,
                col_templates=spec.column_templates,
                env=env,
            )
        fill_summary_tables(root, context)
        if not context.get("appendix_pdf_plan"):
            fill_appendix_sections(root, rels_root, context)

        out_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        out_rels_xml = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

        with zipfile.ZipFile(output_docx, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "word/document.xml":
                    zout.writestr(item, out_xml)
                elif item.filename == "word/_rels/document.xml.rels":
                    zout.writestr(item, out_rels_xml)
                else:
                    zout.writestr(item, zin.read(item.filename))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render risk report docx using jinja2 and workbook data.")
    parser.add_argument("--workbook", required=True, help="Input xlsm workbook path.")
    parser.add_argument("--template", required=True, help="Input docx template path.")
    parser.add_argument("--output", required=True, help="Output rendered docx path.")
    parser.add_argument("--platform-name", default="", help="Platform display name for cover page.")
    parser.add_argument("--report-date", default="", help="Report date for cover page, e.g. 2026年3月12日.")
    parser.add_argument(
        "--metadata-json",
        default="",
        help="Optional metadata json file. Keys: platform_name, report_date. CLI args override file.",
    )
    parser.add_argument(
        "--full-rows",
        action="store_true",
        help="Deprecated: row caps are disabled by default.",
    )
    parser.add_argument(
        "--limit-rows",
        action="store_true",
        help="Enable row caps for large reports (disabled by default).",
    )
    parser.add_argument("--detail-row-limit", type=int, default=250, help="Row limit for Table 7/8/16 detail lists.")
    parser.add_argument("--future-row-limit", type=int, default=500, help="Total row limit for Table 17 future-node list.")
    parser.add_argument("--fatigue-row-limit", type=int, default=800, help="Row limit for Table 3 fatigue-failure list.")
    parser.add_argument("--collapse-row-limit", type=int, default=80, help="Row limit for Table 4/5 collapse-failure lists.")
    parser.add_argument("--appendix-a-file", default="", help="Appendix A file path.")
    parser.add_argument("--appendix-b-file", default="", help="Appendix B file path.")
    parser.add_argument("--appendix-c-dir", action="append", default=[], help="Appendix C directory path, repeatable.")
    parser.add_argument(
        "--include-word-plan-detail-tables",
        action="store_true",
        help="Fill Table 43/44 detail rows in Word. Default keeps these large detail tables only in Excel.",
    )
    parser.add_argument(
        "--non-vba-post-filters",
        action="store_true",
        help="Enable legacy non-VBA post filters/rebuilds in report context (default: strict VBA behavior).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workbook = Path(args.workbook).resolve()
    template = Path(args.template).resolve()
    output = Path(args.output).resolve()

    if not workbook.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook}")
    if not template.exists():
        raise FileNotFoundError(f"Template not found: {template}")

    metadata: dict[str, Any] = {}
    if args.metadata_json:
        metadata_path = Path(args.metadata_json).resolve()
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    if args.platform_name:
        metadata["platform_name"] = args.platform_name
    if args.report_date:
        metadata["report_date"] = args.report_date

    row_limits: dict[str, int] | None = None
    if args.limit_rows and (not args.full_rows):
        row_limits = {
            "fatigue_failure_rows": args.fatigue_row_limit,
            "collapse_member_rows": args.collapse_row_limit,
            "collapse_joint_rows": args.collapse_row_limit,
            "node_risk_rows_current": args.detail_row_limit,
            "member_risk_rows": args.detail_row_limit,
            "member_inspection_rows": args.detail_row_limit,
            "node_inspection_rows_future": args.future_row_limit,
        }

    context = load_context_from_workbook(
        workbook,
        metadata,
        row_limits=row_limits,
        strict_vba_algorithms=not args.non_vba_post_filters,
    )
    context["appendix_sections"] = build_appendix_sections(
        appendix_a_file=args.appendix_a_file,
        appendix_b_file=args.appendix_b_file,
        appendix_c_dirs=list(args.appendix_c_dir),
    )
    context["appendix_pdf_plan"] = build_appendix_pdf_plan(
        appendix_a_file=args.appendix_a_file,
        appendix_b_file=args.appendix_b_file,
        appendix_c_dirs=list(args.appendix_c_dir),
    )
    context["include_word_plan_detail_tables"] = bool(args.include_word_plan_detail_tables)
    missing = build_missing_requirements(context)
    if missing:
        print("以下信息缺失或为空，可能影响模板完整输出：")
        for m in missing:
            print(f"- {m}")

    cap_notes = build_row_cap_notes(context)
    if cap_notes:
        print("已启用明细表限行（提升 Word 打开性能）：")
        for note in cap_notes:
            print(f"- {note}")

    render_report(template, output, context)
    if context.get("appendix_pdf_plan"):
        insert_appendix_pdf_images(output, context)
    print(f"Report generated: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
