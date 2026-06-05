# server/routers/reports.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from server.schemas import ReportGenerateRequest
from server.task_manager import get_task, submit_task
from services.special_strategy_runtime import generate_special_strategy_report


router = APIRouter()


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = PROJECT_ROOT / "server_outputs" / "reports"


def _normalize_output_path(
    *,
    facility_code: str,
    run_id: int | None,
    output_path: str | None,
) -> str:
    text = str(output_path or "").strip()

    if text and text.lower() not in {"null", "none", "pull", "undefined"}:
        path = Path(text)
        if path.suffix.lower() != ".docx":
            path = path.with_suffix(".docx")
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_facility = str(facility_code or "facility").replace("/", "_").replace("\\", "_")
    run_part = f"run{run_id}" if run_id else "latest"

    return str(
        DEFAULT_REPORT_DIR
        / f"{safe_facility}_{run_part}_{timestamp}_special_strategy_report.docx"
    )


def _generate_report_task(
    *,
    facility_code: str,
    run_id: int | None,
    metadata: dict,
    output_path: str | None,
    generate_pdf: bool,
    pdf_timeout_seconds: int,
) -> dict:
    final_output_path = _normalize_output_path(
        facility_code=facility_code,
        run_id=run_id,
        output_path=output_path,
    )

    print(
        f"[ReportAPI] generate report start: facility_code={facility_code}, run_id={run_id}, "
        f"generate_pdf={generate_pdf}",
        flush=True,
    )
    print(f"[ReportAPI] output_path = {final_output_path}", flush=True)

    report_path = Path(
        generate_special_strategy_report(
            facility_code,
            run_id=run_id,
            metadata=metadata or {},
            output_path=final_output_path,
            generate_pdf=bool(generate_pdf),
            pdf_timeout_seconds=int(pdf_timeout_seconds or 300),
        )
    )

    pdf_path = report_path.with_suffix(".pdf")

    result = {
        "facility_code": facility_code,
        "run_id": run_id,
        "report_path": str(report_path),
        "report_exists": report_path.exists(),
        "pdf_path": str(pdf_path) if pdf_path.exists() else "",
        "pdf_exists": pdf_path.exists(),
    }

    if not pdf_path.exists():
        result["warning"] = (
            "Word report was generated successfully, but PDF was not generated. "
            "Please check Word COM or increase pdf_timeout_seconds."
        )

    print(f"[ReportAPI] generate report done: {result}", flush=True)
    return result


@router.post("/generate")
def generate_report(req: ReportGenerateRequest):
    task_id = submit_task(
        name="generate_strategy_report",
        payload=req.model_dump(),
        func=_generate_report_task,
        kwargs={
            "facility_code": req.facility_code,
            "run_id": req.run_id,
            "metadata": req.metadata,
            "output_path": req.output_path,
            "generate_pdf": req.generate_pdf,
            "pdf_timeout_seconds": req.pdf_timeout_seconds,
        },
    )
    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
def get_report_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/tasks/{task_id}/download")
def download_report(
    task_id: str,
    file_type: str = Query("docx", description="docx or pdf"),
):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    status = str(task.get("status") or "").lower()
    if status != "success":
        raise HTTPException(
            status_code=409,
            detail=f"Report task is not successful yet: status={status}",
        )

    result = task.get("result") or {}
    if not isinstance(result, dict):
        raise HTTPException(status_code=404, detail="Report task has no result")

    file_type_norm = str(file_type or "docx").strip().lower()

    if file_type_norm == "pdf":
        path_text = str(result.get("pdf_path") or "").strip()
        media_type = "application/pdf"
    else:
        path_text = str(result.get("report_path") or "").strip()
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    if not path_text:
        raise HTTPException(status_code=404, detail=f"{file_type_norm} path is empty")

    file_path = Path(path_text)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"{file_type_norm} file not found: {file_path}",
        )

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )