# server/routers/feasibility.py
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from server.schemas import (
    FeasibilityExportFilesRequest,
    FeasibilityReportGenerateRequest,
    FeasibilityRunRequest,
)
from server.task_manager import get_active_task, get_task, submit_task, submit_task_if_no_active
from services.feasibility_runtime import (
    assert_sacs_not_running_before_analysis,
    export_feasibility_generated_files,
    generate_feasibility_report,
    load_feasibility_result_bundle,
    run_feasibility_analysis,
)
from server.schemas import FeasibilityCreateModelRequest
from pages.sacs_create_model_service import create_new_model_files
from shiyou_db.runtime_db import get_mysql_url


router = APIRouter()


def _run_feasibility_task(
    *,
    facility_code: str,
    analysis_mode: str,
    metadata: dict,
) -> dict:
    return run_feasibility_analysis(
        facility_code=facility_code,
        analysis_mode=analysis_mode,
        metadata=metadata or {},
    )


@router.post("/run")
def run_feasibility(req: FeasibilityRunRequest):
    """
    启动结构强度/改造可行性评估计算。

    不使用持久锁文件，只根据服务端当前任务状态判断：
    - 如果已有 feasibility_run 任务处于 pending/running，直接返回 409；
    - 如果没有正在运行的计算任务，才提交新的后台计算。
    """
    try:
        assert_sacs_not_running_before_analysis()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    task_id, active_task = submit_task_if_no_active(
        name="feasibility_run",
        payload=req.model_dump(),
        func=_run_feasibility_task,
        kwargs={
            "facility_code": req.facility_code,
            "analysis_mode": req.analysis_mode,
            "metadata": req.metadata,
        },
        active_names=("feasibility_run",),
    )

    if active_task is not None:
        payload = active_task.get("payload") or {}
        facility_code = str(payload.get("facility_code") or "未知平台")
        analysis_mode = str(payload.get("analysis_mode") or "未知模式")
        started_at = str(active_task.get("created_at") or active_task.get("updated_at") or "未知时间")
        active_task_id = str(active_task.get("task_id") or "")
        raise HTTPException(
            status_code=409,
            detail=(
                "当前已有 SACS 计算任务正在运行，请等待当前任务完成后再试。\n"
                f"正在计算平台：{facility_code}\n"
                f"计算模式：{analysis_mode}\n"
                f"开始时间：{started_at}\n"
                f"任务编号：{active_task_id}"
            ),
        )

    return {"task_id": task_id}



@router.get("/running/status")
def get_feasibility_running_status():
    active_task = get_active_task("feasibility_run")
    return {
        "running": active_task is not None,
        "task": active_task,
        "message": "当前已有 SACS 计算任务正在运行。" if active_task else "当前没有 SACS 计算任务运行。",
    }

@router.get("/tasks/{task_id}")
def get_feasibility_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/result/{facility_code}")
def get_feasibility_result(
    facility_code: str,
    run_id: int | None = None,
):
    bundle = load_feasibility_result_bundle(
        facility_code=facility_code,
        run_id=run_id,
    )
    if not bundle:
        raise HTTPException(status_code=404, detail="Feasibility result not found")
    return bundle


def _generate_feasibility_report_task(
    *,
    facility_code: str,
    run_id: int | None,
    report_payload: dict,
    metadata: dict,
    output_path: str | None,
) -> dict:
    return generate_feasibility_report(
        facility_code=facility_code,
        run_id=run_id,
        report_payload=report_payload or {},
        metadata=metadata or {},
        output_path=output_path,
    )


@router.post("/report/generate")
def generate_report(req: FeasibilityReportGenerateRequest):
    task_id = submit_task(
        name="feasibility_report_generate",
        payload=req.model_dump(),
        func=_generate_feasibility_report_task,
        kwargs={
            "facility_code": req.facility_code,
            "run_id": req.run_id,
            "report_payload": req.report_payload,
            "metadata": req.metadata,
            "output_path": req.output_path,
        },
    )
    return {"task_id": task_id}


@router.get("/report/tasks/{task_id}")
def get_report_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/report/tasks/{task_id}/download")
def download_report(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if str(task.get("status") or "").lower() != "success":
        raise HTTPException(status_code=409, detail="Report task is not successful yet")

    result = task.get("result") or {}
    output_path = str(result.get("output_path") or "").strip()
    if not output_path:
        raise HTTPException(status_code=404, detail="Report output path is empty")

    file_path = Path(output_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Report file not found: {file_path}")

    media_type = "application/pdf"
    if file_path.suffix.lower() == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )


def _export_files_task(
    *,
    facility_code: str,
    analysis_mode: str,
    include_model_files: bool,
    include_result_file: bool,
) -> dict:
    return export_feasibility_generated_files(
        facility_code=facility_code,
        analysis_mode=analysis_mode,
        include_model_files=include_model_files,
        include_result_file=include_result_file,
    )


@router.post("/files/export")
def export_files(req: FeasibilityExportFilesRequest):
    task_id = submit_task(
        name="feasibility_export_files",
        payload=req.model_dump(),
        func=_export_files_task,
        kwargs={
            "facility_code": req.facility_code,
            "analysis_mode": req.analysis_mode,
            "include_model_files": req.include_model_files,
            "include_result_file": req.include_result_file,
        },
    )
    return {"task_id": task_id}


@router.get("/files/tasks/{task_id}")
def get_export_files_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/files/tasks/{task_id}/download")
def download_export_files(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if str(task.get("status") or "").lower() != "success":
        raise HTTPException(status_code=409, detail="Export task is not successful yet")

    result = task.get("result") or {}
    zip_path = str(result.get("zip_path") or "").strip()
    if not zip_path:
        raise HTTPException(status_code=404, detail="Zip path is empty")

    file_path = Path(zip_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Zip file not found: {file_path}")

    return FileResponse(
        path=str(file_path),
        media_type="application/zip",
        filename=file_path.name,
    )

def _create_feasibility_model_task(
    *,
    facility_code: str,
    metadata: dict,
) -> dict:
    code = str(facility_code or "").strip()
    if not code:
        raise ValueError("facility_code 不能为空，无法创建新模型")

    result = create_new_model_files(
        mysql_url=get_mysql_url(),
        job_name=code,
        overwrite_job=True,
        generate_bat=True,
        user_export_dir="",
    )

    if not isinstance(result, dict):
        result = {}

    result["facility_code"] = code
    result["metadata"] = metadata or {}
    return result


@router.post("/model/create")
def create_feasibility_model(req: FeasibilityCreateModelRequest):
    task_id = submit_task(
        name="feasibility_create_model",
        payload=req.model_dump(),
        func=_create_feasibility_model_task,
        kwargs={
            "facility_code": req.facility_code,
            "metadata": req.metadata,
        },
    )
    return {"task_id": task_id}


@router.get("/model/tasks/{task_id}")
def get_feasibility_model_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task
