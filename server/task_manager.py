# server/task_manager.py
from __future__ import annotations

import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Iterable
from uuid import uuid4


# 测试阶段先用 4 个线程，避免某个长任务阻塞后续任务。
# 注意：SACS 计算是否允许并发，由业务路由在提交任务前判断。
_executor = ThreadPoolExecutor(max_workers=4)

_TASKS: dict[str, dict[str, Any]] = {}
_TASKS_LOCK = threading.RLock()
ACTIVE_TASK_STATUSES = {"pending", "running"}


def _now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _copy_task(task: dict[str, Any] | None) -> dict[str, Any] | None:
    return dict(task) if task else None


def _normalize_names(names: str | Iterable[str] | None) -> set[str]:
    if names is None:
        return set()
    if isinstance(names, str):
        return {names}
    return {str(name) for name in names if str(name).strip()}


def create_task(name: str, payload: dict[str, Any] | None = None) -> str:
    task_id = uuid4().hex
    now = _now_text()

    with _TASKS_LOCK:
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
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return

        task.update(kwargs)
        task["updated_at"] = _now_text()


def get_task(task_id: str) -> dict[str, Any] | None:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        return _copy_task(task)


def list_tasks() -> list[dict[str, Any]]:
    with _TASKS_LOCK:
        return [dict(task) for task in _TASKS.values()]


def get_active_task(
    names: str | Iterable[str] | None = None,
    *,
    statuses: Iterable[str] | None = None,
) -> dict[str, Any] | None:
    """
    查询当前是否已有未结束任务。

    这里不是持久锁，只根据当前服务端进程内的任务状态判断：
    - pending / running 视为正在执行；
    - success / failed 视为已结束，可再次提交。
    """
    name_set = _normalize_names(names)
    status_set = {str(status).lower() for status in (statuses or ACTIVE_TASK_STATUSES)}

    with _TASKS_LOCK:
        active_tasks = []
        for task in _TASKS.values():
            task_name = str(task.get("name") or "")
            task_status = str(task.get("status") or "").lower()
            if name_set and task_name not in name_set:
                continue
            if task_status not in status_set:
                continue
            active_tasks.append(task)

        if not active_tasks:
            return None

        active_tasks.sort(key=lambda item: str(item.get("created_at") or ""))
        return dict(active_tasks[0])


def _start_task_runner(
    *,
    task_id: str,
    func: Callable[..., Any],
    kwargs: dict[str, Any],
) -> None:
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


def submit_task(
    *,
    name: str,
    payload: dict[str, Any] | None,
    func: Callable[..., Any],
    kwargs: dict[str, Any],
) -> str:
    task_id = create_task(name, payload)
    _start_task_runner(task_id=task_id, func=func, kwargs=kwargs)
    return task_id


def submit_task_if_no_active(
    *,
    name: str,
    payload: dict[str, Any] | None,
    func: Callable[..., Any],
    kwargs: dict[str, Any],
    active_names: str | Iterable[str] | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    """
    如果同类任务正在执行，则不提交新任务。

    返回：
    - (task_id, None)：成功提交新任务；
    - (None, active_task)：已有任务正在执行。

    这个判断和创建任务在同一把进程内互斥锁里完成，避免两个请求同时通过检查。
    它不会创建残留锁文件；任务状态变为 success/failed 后自然允许下一次计算。
    """
    names_to_check = active_names if active_names is not None else name

    with _TASKS_LOCK:
        active_task = get_active_task(names_to_check)
        if active_task is not None:
            return None, active_task

        task_id = create_task(name, payload)

    _start_task_runner(task_id=task_id, func=func, kwargs=kwargs)
    return task_id, None
