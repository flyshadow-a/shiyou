# server/task_manager.py
from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4


# 测试阶段先用 4 个线程，避免某个长任务阻塞后续任务。
# 正式部署时，如果 SACS / Word / 导图不能并发，可以再按任务类型拆队列。
_executor = ThreadPoolExecutor(max_workers=4)

_TASKS: dict[str, dict[str, Any]] = {}


def create_task(name: str, payload: dict[str, Any] | None = None) -> str:
    task_id = uuid4().hex
    now = datetime.now().isoformat(timespec="seconds")

    _TASKS[task_id] = {
        "task_id": task_id,
        "name": name,
        "status": "pending",
        "progress": 0,
        "message": "Task created",
        "payload": payload or {},
        "result": None,
        "error": "",
        "created_at": now,
        "updated_at": now,
    }
    return task_id


def update_task(task_id: str, **kwargs) -> None:
    task = _TASKS.get(task_id)
    if not task:
        return

    task.update(kwargs)
    task["updated_at"] = datetime.now().isoformat(timespec="seconds")


def get_task(task_id: str) -> dict[str, Any] | None:
    task = _TASKS.get(task_id)
    return dict(task) if task else None


def submit_task(
    *,
    name: str,
    payload: dict[str, Any] | None,
    func: Callable[..., Any],
    kwargs: dict[str, Any],
) -> str:
    task_id = create_task(name, payload)

    def runner():
        try:
            update_task(
                task_id,
                status="running",
                progress=5,
                message="Task running",
            )

            result = func(**kwargs)

            update_task(
                task_id,
                status="success",
                progress=100,
                message="Task completed",
                result=result,
            )

        except Exception as exc:
            update_task(
                task_id,
                status="failed",
                progress=100,
                message="Task failed",
                error=f"{exc}\n{traceback.format_exc()}",
            )

    _executor.submit(runner)
    return task_id