# server/routers/files.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from services.server_file_service import (
    get_current_sacinp_record,
    get_latest_seainp_record,
    record_display_name,
    record_to_server_path,
)


router = APIRouter()


def _safe_name(path: str) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    return os.path.basename(text.replace("/", os.sep).replace("\\", os.sep)) or Path(text).name


def _format_label(path: str) -> str:
    name = _safe_name(path).lower()
    for token in ("sacinp", "seainp", "clplog", "clplst", "clprst", "ftglst", "ftginp", "wvrinp"):
        if name.startswith(token) or token in name:
            return token.upper()
    suffix = Path(name).suffix.lstrip(".")
    return suffix.upper() if suffix else ""


def _row(
    *,
    facility_code: str,
    path: str,
    category_name: str,
    logical_path: str,
    source_label: str,
    branch_label: str = "",
) -> dict[str, Any]:
    text = str(path or "").strip()
    p = Path(text) if text else Path()
    exists = bool(text and p.exists() and p.is_file())
    size = p.stat().st_size if exists else 0
    return {
        "facility_code": facility_code,
        "storage_path": text,
        "server_path": text,
        "display_path": text,
        "original_name": _safe_name(text),
        "logical_path": logical_path,
        "category_name": category_name,
        "work_condition": "",
        "format_label": _format_label(text),
        "branch_label": branch_label,
        "source_label": source_label,
        "remark": "服务端当前默认输入文件",
        "file_size": size,
        "exists": exists,
    }


def _rows_from_paths(
    *,
    facility_code: str,
    paths: list[str],
    category_name: str,
    logical_path: str,
    source_label: str,
    branch_label: str = "",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in paths or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(
            _row(
                facility_code=facility_code,
                path=text,
                category_name=category_name,
                logical_path=logical_path,
                source_label=source_label,
                branch_label=branch_label,
            )
        )
    return out


@router.get("/latest-model")
def get_latest_model_file(facility_code: str = Query(...)):
    try:
        record = get_current_sacinp_record(facility_code)
        path = record_to_server_path(record)
        return {
            "facility_code": facility_code,
            "file_name": record_display_name(record),
            "server_path": str(path),
            "size": path.stat().st_size,
            "record": record,
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/download/latest-model")
def download_latest_model_file(facility_code: str = Query(...)):
    try:
        record = get_current_sacinp_record(facility_code)
        path = record_to_server_path(record)
        return FileResponse(
            path=str(path),
            media_type="application/octet-stream",
            filename=record_display_name(record) or path.name,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/latest-sea")
def get_latest_sea_file(facility_code: str = Query(...)):
    try:
        record = get_latest_seainp_record(facility_code)
        if not record:
            raise HTTPException(status_code=404, detail="SEA file record not found")
        path = record_to_server_path(record)
        return {
            "facility_code": facility_code,
            "file_name": record_display_name(record),
            "server_path": str(path),
            "size": path.stat().st_size,
            "record": record,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/download/latest-sea")
def download_latest_sea_file(facility_code: str = Query(...)):
    try:
        record = get_latest_seainp_record(facility_code)
        if not record:
            raise HTTPException(status_code=404, detail="SEA file record not found")
        path = record_to_server_path(record)
        return FileResponse(
            path=str(path),
            media_type="application/octet-stream",
            filename=record_display_name(record) or path.name,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/strategy-inputs")
def get_strategy_input_files(facility_code: str = Query(...)):
    """返回服务端当前用于特检策略计算的默认输入文件清单。

    客户端不要直接访问这些 server_path 做预览；预览仍通过 /download/latest-model 下载。
    这些 server_path 主要用于表格展示，以及提交给服务端计算时作为 input_overrides。
    """
    try:
        from services.special_strategy_runtime import load_base_config, resolve_current_model_inputs

        code = str(facility_code or "").strip()
        cfg = load_base_config(code)
        inputs = resolve_current_model_inputs(code, cfg)

        model = str(inputs.get("model") or "").strip()
        clplog = [str(x) for x in (inputs.get("clplog") or []) if str(x or "").strip()]
        ftglst = [str(x) for x in (inputs.get("ftglst") or []) if str(x or "").strip()]
        ftginp = [str(x) for x in (inputs.get("ftginp") or []) if str(x or "").strip()]

        files = {
            "model": _rows_from_paths(
                facility_code=code,
                paths=[model] if model else [],
                category_name="结构模型文件",
                logical_path=f"{code}/当前模型/结构模型",
                source_label="服务端当前模型",
            ),
            "collapse": _rows_from_paths(
                facility_code=code,
                paths=clplog,
                category_name="倒塌分析日志文件",
                logical_path=f"{code}/当前模型/倒塌分析/结果",
                source_label="服务端倒塌分析结果",
            ),
            "fatigue_result": _rows_from_paths(
                facility_code=code,
                paths=ftglst,
                category_name="疲劳分析结果文件",
                logical_path=f"{code}/当前模型/疲劳分析/结果",
                source_label="服务端疲劳结果",
                branch_label="疲劳结果文件",
            ),
            "fatigue_input": _rows_from_paths(
                facility_code=code,
                paths=ftginp,
                category_name="疲劳分析模型文件",
                logical_path=f"{code}/当前模型/疲劳分析/输入",
                source_label="服务端疲劳输入",
                branch_label="疲劳输入文件",
            ),
        }

        return {
            "facility_code": code,
            "inputs": inputs,
            "files": files,
            "counts": {key: len(value) for key, value in files.items()},
        }
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
