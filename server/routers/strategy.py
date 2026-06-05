# server/routers/strategy.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from server.schemas import StrategyRunRequest
from server.task_manager import get_task, submit_task
from services.special_strategy_runtime import (
    check_special_strategy_manual_fill_rows,
    list_result_run_history,
    load_result_bundle,
    run_special_strategy_calculation,
)
from services.special_strategy_state_db import (
    load_latest_strategy_result_snapshot,
    load_strategy_result_snapshot_by_run,
)


router = APIRouter()


def _json_safe(value: Any) -> Any:
    """FastAPI 返回前统一清洗，避免 Decimal / Path / datetime 无法 JSON 序列化。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(_json_safe(k)): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def _normalize_facility_code(value: str) -> str:
    return str(value or "").strip().upper()


def _run_strategy_task(
    *,
    facility_code: str,
    param_overrides: dict[str, Any],
    input_overrides: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    # C/S 服务端永远不允许弹本机 GUI。客户端会把 ManualBrace 补全结果放到 metadata.manual_fill_entries。
    safe_metadata = dict(metadata or {})
    safe_metadata["disable_server_gui"] = True
    safe_metadata.setdefault("manual_fill_source", "client_or_disabled")

    result = run_special_strategy_calculation(
        facility_code,
        param_overrides=param_overrides,
        input_overrides=input_overrides,
        metadata=safe_metadata,
    )

    state = result.get("state") or {}
    return _json_safe({
        "facility_code": facility_code,
        "run_id": state.get("db_run_id"),
        "snapshot_id": state.get("db_snapshot_id"),
        "updated_at": state.get("updated_at"),
        "state": state,
    })


@router.post("/manual-fill/check")
def check_strategy_manual_fill(req: StrategyRunRequest):
    """
    只检查 ManualBrace 是否需要人工补充。

    这个接口不会弹服务端 GUI，也不会保存最终计算结果；客户端收到 manual_fill_rows 后，
    在客户端弹输入框，再把 manual_fill_entries 放到 /run 的 metadata 里。
    """
    try:
        rows = check_special_strategy_manual_fill_rows(
            req.facility_code,
            param_overrides=req.param_overrides or {},
            input_overrides=req.input_overrides or {},
            metadata={**(req.metadata or {}), "disable_server_gui": True, "manual_fill_check_only": True},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _json_safe({
        "facility_code": req.facility_code,
        "manual_fill_required": bool(rows),
        "manual_fill_rows": rows or [],
    })


@router.post("/run")
def run_strategy(req: StrategyRunRequest):
    task_id = submit_task(
        name="special_strategy_run",
        payload=_json_safe(req.model_dump()),
        func=_run_strategy_task,
        kwargs={
            "facility_code": req.facility_code,
            "param_overrides": _json_safe(req.param_overrides),
            "input_overrides": _json_safe(req.input_overrides),
            "metadata": _json_safe({**(req.metadata or {}), "disable_server_gui": True}),
        },
    )
    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
def get_strategy_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _json_safe(task)


@router.get("/history/{facility_code}")
def get_strategy_history(facility_code: str, limit: int = 20):
    rows = list_result_run_history(facility_code, limit=limit)
    return _json_safe({
        "facility_code": facility_code,
        "count": len(rows),
        "items": rows,
    })


def _snapshot_payload(facility_code: str, run_id: int | None) -> dict[str, Any]:
    snapshot = None
    if run_id not in (None, ""):
        try:
            snapshot = load_strategy_result_snapshot_by_run(int(run_id))
        except Exception:
            snapshot = None
    if snapshot is None:
        try:
            snapshot = load_latest_strategy_result_snapshot(_normalize_facility_code(facility_code))
        except Exception:
            snapshot = None
    payload = (snapshot or {}).get("result_json")
    return dict(payload) if isinstance(payload, dict) else {}


def _first_list(*values: Any) -> list:
    for value in values:
        if isinstance(value, list) and value:
            return value
    return []


def _merged_result_bundle(facility_code: str, run_id: int | None) -> dict[str, Any] | None:
    bundle = load_result_bundle(facility_code, run_id) or {}
    snap = _snapshot_payload(facility_code, run_id)

    if not bundle and not snap:
        return None

    state: dict[str, Any] = {}
    for source in (snap, bundle):
        candidate = source.get("state") if isinstance(source, dict) else None
        if isinstance(candidate, dict) and candidate:
            state.update(candidate)

    context: dict[str, Any] = {}
    for source in (bundle, snap):
        candidate = source.get("context") if isinstance(source, dict) else None
        if isinstance(candidate, dict) and candidate:
            context.update(candidate)

    member_strategy_rows = _first_list(
        bundle.get("member_inspection_strategy_rows"),
        snap.get("member_inspection_strategy_rows"),
        context.get("member_inspection_strategy_rows"),
        context.get("member_inspection_rows"),
    )
    node_strategy_rows = _first_list(
        bundle.get("node_inspection_strategy_rows"),
        snap.get("node_inspection_strategy_rows"),
        context.get("node_inspection_strategy_rows"),
        context.get("node_inspection_rows"),
    )

    if member_strategy_rows and not context.get("member_inspection_strategy_rows"):
        context["member_inspection_strategy_rows"] = member_strategy_rows
    if node_strategy_rows and not context.get("node_inspection_strategy_rows"):
        context["node_inspection_strategy_rows"] = node_strategy_rows
    if member_strategy_rows and not context.get("member_inspection_rows"):
        context["member_inspection_rows"] = member_strategy_rows
    if node_strategy_rows and not context.get("node_inspection_rows"):
        context["node_inspection_rows"] = node_strategy_rows

    member_rows = _first_list(
        bundle.get("member_risk_rows_full"),
        snap.get("member_risk_rows_full"),
        bundle.get("member_risk_rows"),
        snap.get("member_risk_rows"),
        context.get("member_risk_rows"),
        member_strategy_rows,
    )
    node_rows = _first_list(
        bundle.get("node_risk_rows_full"),
        snap.get("node_risk_rows_full"),
        bundle.get("node_risk_rows"),
        snap.get("node_risk_rows"),
        context.get("node_risk_rows_current"),
        context.get("node_risk_rows"),
        node_strategy_rows,
    )

    return {
        "facility_code": facility_code,
        "run_id": state.get("db_run_id") or (run_id if run_id not in (None, "") else None),
        "state": state,
        "context": context,
        "member_risk_rows_full": member_rows,
        "node_risk_rows_full": node_rows,
        "member_inspection_strategy_rows": member_strategy_rows,
        "node_inspection_strategy_rows": node_strategy_rows,
        "debug_counts": {
            "context_keys": len(context.keys()),
            "member_risk_rows_full": len(member_rows),
            "node_risk_rows_full": len(node_rows),
            "member_inspection_strategy_rows": len(member_strategy_rows),
            "node_inspection_strategy_rows": len(node_strategy_rows),
        },
    }


@router.get("/result/{facility_code}")
def get_strategy_result(facility_code: str, run_id: int | None = None, compact: bool | None = None):
    result = _merged_result_bundle(facility_code, run_id)
    if not result:
        raise HTTPException(status_code=404, detail="未找到计算结果")

    print(
        "[strategy.result]",
        "facility=", facility_code,
        "run_id=", run_id,
        "counts=", result.get("debug_counts"),
    )
    return _json_safe(result)
