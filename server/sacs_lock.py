# server/sacs_lock.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    from shiyou_db.config import load_settings
except Exception:  # pragma: no cover
    load_settings = None


_PROCESS_LOCK = threading.Lock()


class SacsTaskBusyError(RuntimeError):
    """SACS 全局锁已被其他计算任务占用。"""

    def __init__(self, owner: dict[str, Any] | None = None):
        self.owner = dict(owner or {})
        facility_code = str(self.owner.get("facility_code") or "未知平台")
        analysis_mode = str(self.owner.get("analysis_mode") or "未知模式")
        started_at = str(self.owner.get("started_at") or "未知时间")
        pid = str(self.owner.get("pid") or "未知进程")

        message = (
            "当前已有 SACS 计算任务正在运行，请等待当前任务完成后再试。\n"
            f"正在计算平台：{facility_code}\n"
            f"计算模式：{analysis_mode}\n"
            f"开始时间：{started_at}\n"
            f"服务端进程：{pid}"
        )
        super().__init__(message)


def _server_base_dir() -> Path:
    if load_settings is not None:
        try:
            settings = load_settings()
            storage_root = str(settings.storage_root or "").strip()
            if storage_root:
                return Path(storage_root)
        except Exception:
            pass

    return Path.cwd()


def _lock_dir() -> Path:
    return _server_base_dir() / "_runtime_locks"


def sacs_lock_path() -> Path:
    return _lock_dir() / "sacs_global.lock"


def _now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_lock_owner(path: Path | None = None) -> dict[str, Any] | None:
    lock_file = path or sacs_lock_path()
    if not lock_file.exists():
        return None

    try:
        data = json.loads(lock_file.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {"raw": data}
    except Exception:
        try:
            return {"raw": lock_file.read_text(encoding="utf-8", errors="ignore")}
        except Exception:
            return {"raw": "", "path": str(lock_file)}


def get_sacs_lock_status() -> dict[str, Any]:
    owner = _read_lock_owner()
    return {
        "locked": owner is not None,
        "owner": owner,
        "lock_path": str(sacs_lock_path()),
        "message": (
            "当前已有 SACS 计算任务正在运行。"
            if owner is not None
            else "当前没有 SACS 计算任务运行。"
        ),
    }


def acquire_sacs_lock(
    *,
    facility_code: str,
    analysis_mode: str = "",
    task_type: str = "feasibility_run",
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    占用全局 SACS 锁。

    为什么用锁文件而不是只用内存锁：
    - 客户端关闭后，服务端任务仍会继续运行；
    - 服务端重启后，旧 SACS 子进程/文件占用可能仍存在；
    - 锁文件可以让新服务端进程也知道上一轮任务还没有正常释放。

    注意：
    - 只要锁文件存在，新的 SACS 计算请求就会被拒绝；
    - 正常任务结束后会自动 release；
    - 如果服务端异常退出导致锁残留，需要管理员确认没有 SACS 进程后手动删除锁文件。
    """
    lock_file = sacs_lock_path()
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    with _PROCESS_LOCK:
        token = uuid4().hex
        owner = {
            "token": token,
            "facility_code": str(facility_code or "").strip() or "未知平台",
            "analysis_mode": str(analysis_mode or "").strip() or "未知模式",
            "task_type": str(task_type or "").strip() or "sacs_task",
            "started_at": _now_text(),
            "pid": os.getpid(),
            "metadata": dict(metadata or {}),
            "lock_path": str(lock_file),
        }

        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(lock_file), flags)
        except FileExistsError as exc:
            raise SacsTaskBusyError(_read_lock_owner(lock_file)) from exc

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(owner, f, ensure_ascii=False, indent=2)
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            try:
                lock_file.unlink(missing_ok=True)
            except Exception:
                pass
            raise

        return token


def release_sacs_lock(token: str | None = None) -> None:
    """
    释放全局 SACS 锁。

    token 不匹配时不释放，避免某个旧任务误删新任务的锁。
    """
    lock_file = sacs_lock_path()

    with _PROCESS_LOCK:
        owner = _read_lock_owner(lock_file)
        if owner is None:
            return

        if token and str(owner.get("token") or "") != str(token):
            return

        try:
            lock_file.unlink(missing_ok=True)
        except Exception:
            pass
