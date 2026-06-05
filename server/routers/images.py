# server/routers/images.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from server.schemas import ImageExportRequest
from server.task_manager import get_task, submit_task
from services.report_image_batch_export_process import export_report_images


router = APIRouter()


def _export_images_task(
    *,
    facility_code: str,
    run_id: int | None,
    mode: str,
    show_level_ii: bool = False,
) -> dict:
    export_report_images(
        facility_code=facility_code,
        run_id=run_id,
        mode=mode,
        show_level_ii=bool(show_level_ii),
    )

    return {
        "facility_code": facility_code,
        "run_id": run_id,
        "mode": mode,
        "show_level_ii": bool(show_level_ii),
    }


@router.post("/export")
def export_images(req: ImageExportRequest):
    task_id = submit_task(
        name="export_strategy_images",
        payload=req.model_dump(),
        func=_export_images_task,
        kwargs={
            "facility_code": req.facility_code,
            "run_id": req.run_id,
            "mode": req.mode,
            "show_level_ii": req.show_level_ii,
        },
    )
    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
def get_image_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task