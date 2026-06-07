# server/sacs_lock.py
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any
from uuid import uuid4


_LOCK_GUARD = threading.Lock()
_SACS_OWNER: dict[str, Any] | None = None


class SacsTaskBusyError(RuntimeError):
    """当前已有 SACS 任务占用全局计算锁。"""

    def __init__(self, owner: dict[str, Any] | None = None):
        self.owner = dict(owner or {})
        facility_code = str(self.owner.get("facility_code") or "未知平台")
        analysis_mode = str(self.owner.get("analysis_mode") or "未知模式")
        started_at = str(self.owner.get("started_at") or "未知时间")
        message = (
            "当前已有 SACS 计算任务正在运行，请等待当前任务完成后再试。\n"
            f"正在计算平台：{facility_code}\n"
            f"计算模式：{analysis_mode}\n"
            f"开始时间：{started_at}"
        )
        super().__init__(message)


def get_sacs_lock_status() -> dict[str, Any]:
    """返回当前 SACS 全局锁状态。"""
    with _LOCK_GUARD:
        if _SACS_OWNER is None:
            return {
                "locked": False,
                "owner": None,
                "message": "当前没有 SACS 计算任务运行。",
            }

        return {
            "locked": True,
            "owner": dict(_SACS_OWNER),
            "message": "当前已有 SACS 计算任务正在运行。",
        }


def acquire_sacs_lock(
    *,
    facility_code: str,
    analysis_mode: str = "",
    task_type: str = "feasibility_run",
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    尝试占用全局 SACS 计算锁。

    说明：
    - 服务端只有一个 SACS / 一个许可证时，同一时刻只能允许一个计算任务；
    - 客户端关闭不会释放锁，锁由服务端任务 finally 释放；
    - 如果已有任务运行，直接抛 SacsTaskBusyError，调用方返回 409 给客户端。
    """
    global _SACS_OWNER

    code = str(facility_code or "").strip()
    mode = str(analysis_mode or "").strip()
    task_type = str(task_type or "sacs_task").strip() or "sacs_task"

    if not code:
        code = "未知平台"

    with _LOCK_GUARD:
        if _SACS_OWNER is not None:
            raise SacsTaskBusyError(_SACS_OWNER)

        token = uuid4().hex
        _SACS_OWNER = {
            "token": token,
            "facility_code": code,
            "analysis_mode": mode,
            "task_type": task_type,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "metadata": dict(metadata or {}),
        }
        return token


def release_sacs_lock(token: str | None = None) -> None:
    """
    释放 SACS 全局计算锁。

    token 不匹配时不释放，避免误释放别的任务的锁。
    """
    global _SACS_OWNER

    with _LOCK_GUARD:
        if _SACS_OWNER is None:
            return

        if token and str(_SACS_OWNER.get("token") or "") != str(token):
            return

        _SACS_OWNER = None
