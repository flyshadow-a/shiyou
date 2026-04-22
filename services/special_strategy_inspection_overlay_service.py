from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from services.special_strategy_state_db import (
    load_latest_strategy_result_snapshot,
    load_strategy_result_snapshot_by_run,
)

DISPLAY_TO_CONTEXT_TIME = {
    "": "当前",
    "当前": "当前",
    "第0年": "当前",
    "0年": "当前",
    "+0年": "当前",
    "+5年": "第5年",
    "5年": "第5年",
    "第5年": "第5年",
    "+10年": "第10年",
    "10年": "第10年",
    "第10年": "第10年",
    "+15年": "第15年",
    "15年": "第15年",
    "第15年": "第15年",
    "+20年": "第20年",
    "20年": "第20年",
    "第20年": "第20年",
    "+25年": "第25年",
    "25年": "第25年",
    "第25年": "第25年",
}

INSPECTION_LEVEL_ORDER = {
    "": 0,
    "-": 0,
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
}

def _txt(value: Any) -> str:
    return "" if value is None else str(value).strip()

def _norm_time_value(value: Any) -> str:
    return DISPLAY_TO_CONTEXT_TIME.get(_txt(value).replace(" ", ""), _txt(value).replace(" ", ""))

def _norm_time_label(display_year: str | None) -> str:
    return _norm_time_value(display_year) or "当前"

def _norm_level(level: Any) -> str:
    text = _txt(level).upper()
    return text if text in ("II", "III", "IV") else ""

def _pick_worse_level(a: str, b: str) -> str:
    aa = _norm_level(a)
    bb = _norm_level(b)
    return bb if INSPECTION_LEVEL_ORDER.get(bb, 0) > INSPECTION_LEVEL_ORDER.get(aa, 0) else aa

def _member_key(joint_a: str, joint_b: str) -> str:
    a = _txt(joint_a)
    b = _txt(joint_b)
    if not a and not b:
        return ""
    pair = sorted([a, b])
    return f"{pair[0]}|{pair[1]}"

def _load_snapshot_payload(facility_code: str, run_id: int | None = None) -> dict[str, Any] | None:
    snapshot = load_strategy_result_snapshot_by_run(int(run_id)) if run_id else load_latest_strategy_result_snapshot(facility_code)
    if not snapshot:
        return None
    payload = snapshot.get("result_json")
    return payload if isinstance(payload, dict) else None

def _iter_member_rows_from_context(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for key in (
        "member_inspection_strategy_rows",
        "member_inspection_rows_current",
        "member_inspection_rows",
    ):
        for row in context.get(key, []) or []:
            if isinstance(row, dict):
                rows.append(row)

    # 兜底：某些版本把 inspect_level 混在 member_risk_rows 里
    for row in context.get("member_risk_rows", []) or []:
        if isinstance(row, dict) and _txt(row.get("inspect_level")):
            rows.append(row)

    return rows

def _iter_node_rows_from_context(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for key in (
        "node_inspection_strategy_rows",
        "node_inspection_rows_current",
        "node_inspection_rows_future",
        "node_inspection_rows",
    ):
        for row in context.get(key, []) or []:
            if isinstance(row, dict):
                rows.append(row)

    # 兜底：当前风险表里如果带 inspect_level，也可拿来画“当前”
    for row in context.get("node_risk_rows_current", []) or []:
        if isinstance(row, dict) and _txt(row.get("inspect_level")):
            rows.append(row)

    return rows

def _time_matches(row_time: str, target_time: str) -> bool:
    row_time = _txt(row_time)
    target_time = _txt(target_time)

    row_norm = _norm_time_value(row_time)
    target_norm = _norm_time_value(target_time)

    # “当前”允许三种情况：
    # 1) time_node 为空
    # 2) time_node 明确写了“当前”
    # 3) time_node 被规范化后等于“当前”
    if target_norm == "当前":
        return row_time in ("", "当前") or row_norm == "当前"

    return row_norm == target_norm

TIME_PRIORITY = {
    "当前": 0,
    "第5年": 5,
    "第10年": 10,
    "第15年": 15,
    "第20年": 20,
    "第25年": 25,
}

def _collect_available_inspection_times(context: dict[str, Any]) -> list[str]:
    values = set()

    for row in _iter_member_rows_from_context(context):
        t = _norm_time_value(row.get("time_node"))
        if t:
            values.add(t)

    for row in _iter_node_rows_from_context(context):
        t = _norm_time_value(row.get("time_node"))
        if t:
            values.add(t)

    return sorted(values, key=lambda x: TIME_PRIORITY.get(x, 999))


def _resolve_overlay_context_year(context: dict[str, Any], display_year: str) -> str:
    target = _norm_time_label(display_year)

    # 非“当前”直接按用户选项走
    if target != "当前":
        return target

    # 当前只要有一条当前数据，就仍然用“当前”
    has_current_member = any(
        _time_matches(_txt(row.get("time_node")), "当前") and _norm_level(row.get("inspect_level"))
        for row in _iter_member_rows_from_context(context)
    )
    has_current_node = any(
        _time_matches(_txt(row.get("time_node")), "当前") and _norm_level(row.get("inspect_level"))
        for row in _iter_node_rows_from_context(context)
    )

    if has_current_member or has_current_node:
        return "当前"

    # 当前确实没有，则回退到最早存在的检验时间节点
    available = [t for t in _collect_available_inspection_times(context) if t != "当前"]
    if available:
        return available[0]

    return "当前"

def load_strategy_inspection_overlay(facility_code: str, *, run_id: int | None = None, display_year: str = "当前") -> dict[str, Any]:
    payload = _load_snapshot_payload(facility_code, run_id=run_id)
    if not payload:
        return {
            "facility_code": facility_code,
            "run_id": run_id,
            "display_year": display_year,
            "context_year": _norm_time_label(display_year),
            "member_level_by_key": {},
            "node_level_by_joint": {},
            "node_level_by_joint_brace": {},
            "member_items_by_key": {},
            "node_items_by_joint": {},
        }

    context = payload.get("context") or {}
    context_year = _resolve_overlay_context_year(context, display_year)

    member_level_by_key = {}
    node_level_by_joint = {}
    node_level_by_joint_brace = {}
    member_items_by_key = defaultdict(list)
    node_items_by_joint = defaultdict(list)

    for row in _iter_member_rows_from_context(context):
        if not _time_matches(_txt(row.get("time_node")), context_year):
            continue
        inspect_level = _norm_level(row.get("inspect_level"))
        if not inspect_level:
            continue

        joint_a = _txt(row.get("joint_a"))
        joint_b = _txt(row.get("joint_b"))
        key = _member_key(joint_a, joint_b)
        if not key:
            continue

        member_level_by_key[key] = _pick_worse_level(member_level_by_key.get(key, ""), inspect_level)
        member_items_by_key[key].append({
            "joint_a": joint_a,
            "joint_b": joint_b,
            "member_type": _txt(row.get("member_type")),
            "inspect_level": inspect_level,
            "time_node": _txt(row.get("time_node")),
        })

    seen_node_items = set()
    for row in _iter_node_rows_from_context(context):
        if not _time_matches(_txt(row.get("time_node")), context_year):
            continue
        inspect_level = _norm_level(row.get("inspect_level"))
        if not inspect_level:
            continue

        joint_id = _txt(row.get("joint_id"))
        brace = _txt(row.get("brace"))
        if joint_id:
            node_level_by_joint[joint_id] = _pick_worse_level(node_level_by_joint.get(joint_id, ""), inspect_level)

        if joint_id or brace:
            jb_key = f"{joint_id}|{brace}"
            node_level_by_joint_brace[jb_key] = _pick_worse_level(node_level_by_joint_brace.get(jb_key, ""), inspect_level)

        dedup_key = (joint_id, brace, inspect_level)
        if dedup_key in seen_node_items:
            continue
        seen_node_items.add(dedup_key)

        if joint_id:
            node_items_by_joint[joint_id].append({
                "joint_id": joint_id,
                "brace": brace,
                "joint_type": _txt(row.get("joint_type")),
                "inspect_level": inspect_level,
                "time_node": _txt(row.get("time_node")),
            })

    return {
        "facility_code": facility_code,
        "run_id": run_id,
        "display_year": display_year,
        "context_year": context_year,
        "member_level_by_key": dict(member_level_by_key),
        "node_level_by_joint": dict(node_level_by_joint),
        "node_level_by_joint_brace": dict(node_level_by_joint_brace),
        "member_items_by_key": dict(member_items_by_key),
        "node_items_by_joint": dict(node_items_by_joint),
    }

def get_member_inspect_level(
    overlay: dict[str, Any],
    joint_a: str,
    joint_b: str,
) -> str:
    key = _member_key(joint_a, joint_b)
    return _txt((overlay.get("member_level_by_key") or {}).get(key))


def get_node_inspect_level(
    overlay: dict[str, Any],
    joint_id: str,
) -> str:
    return _txt((overlay.get("node_level_by_joint") or {}).get(_txt(joint_id)))


def get_node_brace_inspect_level(
    overlay: dict[str, Any],
    joint_id: str,
    brace: str,
) -> str:
    key = f"{_txt(joint_id)}|{_txt(brace)}"
    return _txt((overlay.get("node_level_by_joint_brace") or {}).get(key))