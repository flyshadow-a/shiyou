# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import csv
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from shiyou_db.config import get_sacs_analysis_engine_exe
from shiyou_db.runtime_db import get_mysql_url

from pages.sacs_runtime_service import (
    ensure_analysis_bat,
    find_result_file,
    rewrite_runx_input_file_names,
)
from pages.sacs_storage_service import (
    get_job_new_model_file,
    get_job_new_sea_file,
    get_job_runtime_dir,
    stage_support_files_for_job,
)
from services.history_rebuild_auto_service import (
    prepare_latest_rebuild_runtime_for_analysis,
    prepare_original_runtime_for_analysis,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_OUTPUT_DIR = PROJECT_ROOT / "server_outputs"
FEASIBILITY_REPORT_DIR = SERVER_OUTPUT_DIR / "feasibility_reports"
FEASIBILITY_EXPORT_DIR = SERVER_OUTPUT_DIR / "feasibility_exports"


def _norm(path: object) -> str:
    text = str(path or "").strip()
    return os.path.normpath(text) if text else ""


def _make_analysis_work_dir(base_work_dir: str, facility_code: str) -> str:
    """
    当前需求：不再为每次 SACS 计算创建 analysis_runs/run_xxx 独立目录，
    直接复用 feasibility_assessment_runtime/<平台> 作为计算目录。

    并发判断仍然依赖 _assert_sacs_not_running_before_analysis()：
    只要服务端检测到 AnalysisEngine.exe / SACW*.exe 正在运行，就拒绝新任务。
    """
    work_dir = Path(_norm(base_work_dir))
    work_dir.mkdir(parents=True, exist_ok=True)
    return os.path.normpath(str(work_dir))

def _copy_input_to_analysis_dir(src_path: str, work_dir: str, target_name: str, *, required: bool = True) -> str:
    """复制输入文件到本次独立计算目录，并按目标文件名统一命名。"""
    src = _norm(src_path)
    dst = os.path.join(_norm(work_dir), target_name)
    if not src or not os.path.isfile(src):
        if required:
            raise FileNotFoundError(f"缺少计算输入文件：{target_name}，源文件：{src}")
        return ""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.normcase(src) != os.path.normcase(dst):
        shutil.copy2(src, dst)
    return dst




SACS_BUSY_PROCESS_NAMES = {
    "analysisengine.exe",
    "sacwsea.exe",
    "sacwpre.exe",
    "sacwslv.exe",
    "sacwpsi.exe",
    "sacwpst.exe",
    "sacwjcn.exe",
    "sacwpvi.exe",
    "sacwdb.exe",
}

SACS_COMMAND_LINE_TOKENS = (
    "analysisengine.exe",
    "autorun.bat",
    "analysis.bat",
    "psim1.runx",
    "sacinp.m1",
    "seainp.m1",
)

NON_BLOCKING_ANALYSIS_OUTPUT_PREFIXES = ("psvdb",)


def _decode_command_output(raw: bytes) -> str:
    for encoding in ("utf-8", "gbk", "mbcs", "cp936", "latin-1"):
        try:
            return raw.decode(encoding, errors="ignore")
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _configured_sacs_process_names() -> set[str]:
    names = set(SACS_BUSY_PROCESS_NAMES)
    try:
        exe_path = str(get_sacs_analysis_engine_exe() or "").strip()
    except Exception:
        exe_path = ""
    exe_name = os.path.basename(exe_path).strip().lower()
    if exe_name:
        names.add(exe_name)
    return names


def _is_sacs_process_name(name: str) -> bool:
    low = str(name or "").strip().lower()
    if not low:
        return False
    if low in _configured_sacs_process_names():
        return True
    if not low.endswith(".exe"):
        return False
    return low.startswith("sacw") or low.startswith("sacs") or "sacs" in low


def _is_sacs_command_line(name: str, command_line: str, work_dir: str | None = None) -> bool:
    proc_name = str(name or "").strip().lower()
    cmd = str(command_line or "").strip().lower()
    if not cmd:
        return False
    if proc_name not in {"cmd.exe", "powershell.exe", "pwsh.exe"}:
        return False

    normalized_cmd = cmd.replace("\\", "/")
    if work_dir:
        normalized_work_dir = _norm(work_dir).lower().replace("\\", "/")
        if normalized_work_dir and normalized_work_dir not in normalized_cmd:
            return False

    return any(token in normalized_cmd for token in SACS_COMMAND_LINE_TOKENS)


def _run_process_listing_command(command: list[str]) -> str:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
        timeout=10,
    )
    return _decode_command_output(proc.stdout)


def _read_tasklist_process_names() -> list[str]:
    try:
        output = _run_process_listing_command(["tasklist", "/FO", "CSV", "/NH"])
    except Exception as exc:
        print("[FeasibilityRuntime] tasklist check failed:", exc, flush=True)
        return []

    names: list[str] = []
    if not output.strip():
        return names

    try:
        for row in csv.reader(output.splitlines()):
            if row:
                names.append(str(row[0] or "").strip())
    except Exception:
        low = output.lower()
        for candidate in _configured_sacs_process_names():
            if candidate in low:
                names.append(candidate)
    return names


def _read_windows_process_details() -> list[tuple[str, str]]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_Process | Select-Object Name,CommandLine | ConvertTo-Csv -NoTypeInformation",
    ]
    try:
        output = _run_process_listing_command(command)
    except Exception as exc:
        print("[FeasibilityRuntime] process command line check failed:", exc, flush=True)
        return []

    details: list[tuple[str, str]] = []
    if not output.strip():
        return details

    try:
        for row in csv.DictReader(output.splitlines()):
            details.append((str(row.get("Name") or "").strip(), str(row.get("CommandLine") or "").strip()))
    except Exception:
        return []
    return details


def _is_sacs_process_running(work_dir: str | None = None) -> tuple[bool, str]:
    """判断服务端是否已有 SACS 计算进程在运行。

    按当前需求：不做平台锁/数据库锁，只在启动计算前检查服务端 Windows
    进程列表。只要发现 AnalysisEngine 或 SACW* 计算模块正在运行，就拒绝
    新任务，从而避免多个用户同时占用 SACS。

    注意：这是运行前进程检测，不是严格原子锁；但对普通客户端点击场景
    已能避免重复启动。实际清理阶段仍会保护旧结果文件不被追加。
    """
    if os.name != "nt":
        return False, ""

    running: list[str] = []

    for name in _read_tasklist_process_names():
        if _is_sacs_process_name(name):
            running.append(str(name).strip().lower())

    if work_dir:
        for name, command_line in _read_windows_process_details():
            if _is_sacs_command_line(name, command_line, work_dir=work_dir):
                running.append(f"{str(name).strip().lower()} ({command_line})")

    if running:
        names = ", ".join(sorted(set(running)))
        return True, names
    return False, ""


def assert_sacs_not_running_before_analysis(work_dir: str | None = None) -> None:
    busy, process_names = _is_sacs_process_running(work_dir=work_dir)
    if not busy:
        return
    raise RuntimeError(
        "当前服务端已有 SACS 计算任务正在运行，请等待当前计算完成后再试。\n"
        f"检测到运行中的 SACS 进程：{process_names}"
    )


def _assert_sacs_not_running_before_analysis(work_dir: str | None = None) -> None:
    assert_sacs_not_running_before_analysis(work_dir=work_dir)

def _latest_state_result_file(code: str) -> tuple[str, str, dict[str, Any]]:
    """返回最新计算状态中的结果文件、工作目录和状态。

    优先读取平台运行根目录下的 feasibility_analysis_state.json。
    这是导出文件/查看结果的唯一主依据，避免多个独立计算目录并存时混乱。
    如果旧版本没有写根目录 state，则兜底扫描 analysis_runs 下最新的
    feasibility_analysis_state.json。
    """
    state = _load_latest_analysis_state(code)
    work_dir = _norm(state.get("work_dir") or get_job_runtime_dir(code))
    result_file = _norm(state.get("result_file"))

    if result_file and os.path.isfile(result_file):
        return result_file, work_dir, state

    if work_dir:
        found = find_result_file(work_dir)
        if found and os.path.isfile(found):
            return _norm(found), work_dir, state

    base_dir = _norm(get_job_runtime_dir(code))
    runs_root = os.path.join(base_dir, "analysis_runs")
    state_candidates: list[tuple[float, str]] = []
    if os.path.isdir(runs_root):
        for root, _dirs, files in os.walk(runs_root):
            if "feasibility_analysis_state.json" not in files:
                continue
            p = os.path.join(root, "feasibility_analysis_state.json")
            try:
                state_candidates.append((os.path.getmtime(p), p))
            except Exception:
                pass

    for _mtime, state_file in sorted(state_candidates, reverse=True):
        try:
            payload = json.loads(Path(state_file).read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        candidate_work_dir = _norm(payload.get("work_dir") or os.path.dirname(state_file))
        candidate_result = _norm(payload.get("result_file"))
        if candidate_result and os.path.isfile(candidate_result):
            return candidate_result, candidate_work_dir, payload
        found = find_result_file(candidate_work_dir)
        if found and os.path.isfile(found):
            return _norm(found), candidate_work_dir, payload

    found = find_result_file(base_dir)
    return _norm(found), base_dir, state


def _analysis_state_path(facility_code: str) -> Path:
    return Path(get_job_runtime_dir(facility_code)) / "feasibility_analysis_state.json"


def _load_latest_analysis_state(facility_code: str) -> dict[str, Any]:
    state_path = _analysis_state_path(facility_code)
    if not state_path.exists() or not state_path.is_file():
        return {}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_tail_text(path: str, max_bytes: int = 256 * 1024) -> str:
    path = _norm(path)
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as fp:
            fp.seek(0, os.SEEK_END)
            size = fp.tell()
            fp.seek(max(0, size - int(max_bytes)), os.SEEK_SET)
            data = fp.read()
        for enc in ("utf-8", "gbk", "cp1252", "latin-1"):
            try:
                return data.decode(enc, errors="ignore")
            except Exception:
                continue
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _read_analysis_exit_code(work_dir: str) -> int | None:
    work_dir = _norm(work_dir)
    if not work_dir:
        return None

    exitcode_path = os.path.join(work_dir, "analysis_exitcode.txt")
    text = _read_tail_text(exitcode_path, max_bytes=8 * 1024).strip()
    if text:
        for token in text.replace("=", " ").replace(";", " ").replace(",", " ").split():
            token = token.strip()
            if token.lstrip("+-").isdigit():
                try:
                    return int(token)
                except Exception:
                    pass

    summary_path = os.path.join(work_dir, "analysis_summary.log")
    summary_text = _read_tail_text(summary_path, max_bytes=64 * 1024)
    for raw_line in reversed(summary_text.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower().replace(" ", "")
        if not low.startswith("exitcode="):
            continue
        value = line.split("=", 1)[-1].strip()
        if value.lstrip("+-").isdigit():
            try:
                return int(value)
            except Exception:
                return None

    return None


def _analysis_runx_has_done_marker(work_dir: str) -> bool:
    exit_code = _read_analysis_exit_code(work_dir)
    if exit_code is not None:
        return True

    stdout_text = _read_tail_text(os.path.join(work_dir, "analysis_stdout.log"), max_bytes=512 * 1024)
    stderr_text = _read_tail_text(os.path.join(work_dir, "analysis_stderr.log"), max_bytes=512 * 1024)
    text = (stdout_text + "\n" + stderr_text).lower()
    return (
        "sacs linear static analysis finished" in text
        or "*** error in sacs execution ***" in text
        or "please check output listing files" in text
    )


def _analysis_output_has_error(work_dir: str, result_file: str) -> str:
    exit_code = _read_analysis_exit_code(work_dir)
    if exit_code is not None and exit_code != 0:
        return f"ExitCode={exit_code}"

    paths = [
        os.path.join(work_dir, "analysis_stdout.log"),
        os.path.join(work_dir, "analysis_stderr.log"),
        os.path.join(work_dir, "analysis_summary.log"),
        result_file,
    ]
    joined = "\n".join(_read_tail_text(path) for path in paths if path)
    low = joined.lower()

    strong_error_tokens = [
        "*** error in sacs execution ***",
        "please check output listing files",
        "fatal error",
        "severe error",
        "cannot open",
        "can not open",
        "could not open",
        "file not found",
        "no such file",
        "系统找不到指定的文件",
        "找不到指定的文件",
    ]
    for token in strong_error_tokens:
        if token in low:
            return token
    return ""


def _is_previous_analysis_output_name(file_name: str) -> bool:
    low = str(file_name or "").strip().lower()
    if not low:
        return False

    exact_names = {
        "analysis_exitcode.txt",
        "analysis_summary.log",
        "analysis_stdout.log",
        "analysis_stderr.log",
        "psicsf",
        "psinpf",
        "psincf",
        "psvtmp",
        "psvtemp",
    }

    return (
        low in exact_names
        or low.startswith("psilst")
        or low.startswith("seaoci")
        or low.startswith("psvdb")
        or low.endswith(".listing")
    )


def _is_non_blocking_analysis_output_name(file_name: str) -> bool:
    low = str(file_name or "").strip().lower()
    return any(low.startswith(prefix) for prefix in NON_BLOCKING_ANALYSIS_OUTPUT_PREFIXES)


def _is_blocking_analysis_output_name(file_name: str) -> bool:
    return _is_previous_analysis_output_name(file_name) and not _is_non_blocking_analysis_output_name(file_name)

def _remove_analysis_output_with_retry(path: str, *, retries: int = 12, interval: float = 0.5) -> None:
    """
    删除旧 SACS 输出文件。

    关键点：
    - 旧代码删除失败只打印日志然后继续计算，容易导致第二次计算继续向旧 psilst.factor 追加；
    - 这里删除失败必须抛错，阻止新计算启动，避免新旧结果混在同一个文件里。
    """
    full = _norm(path)
    if not full or not os.path.exists(full):
        return

    last_exc: Exception | None = None
    for attempt in range(1, int(retries) + 1):
        try:
            if not os.path.exists(full):
                return

            try:
                os.chmod(full, 0o666)
            except Exception:
                pass

            if os.path.isdir(full):
                shutil.rmtree(full)
            else:
                os.remove(full)

            if not os.path.exists(full):
                return
        except Exception as exc:
            last_exc = exc
            time.sleep(max(0.1, float(interval)))

    raise RuntimeError(f"旧计算结果文件无法删除，可能仍被 SACS 或其他进程占用：{full}\n{last_exc}")



def _analysis_output_paths(work_dir: str) -> list[str]:
    work_dir = _norm(work_dir)
    if not work_dir or not os.path.isdir(work_dir):
        return []

    paths: list[str] = []
    for fn in list(os.listdir(work_dir)):
        if _is_previous_analysis_output_name(fn):
            paths.append(os.path.join(work_dir, fn))
    return paths


def _blocking_analysis_output_paths(work_dir: str) -> list[str]:
    work_dir = _norm(work_dir)
    if not work_dir or not os.path.isdir(work_dir):
        return []

    paths: list[str] = []
    for fn in list(os.listdir(work_dir)):
        if _is_blocking_analysis_output_name(fn):
            paths.append(os.path.join(work_dir, fn))
    return paths


def _can_rename_for_lock_check(path: str) -> bool:
    """
    Windows/共享盘上判断文件是否还被 SACS 占用。

    仅 open/read 不能可靠判断是否被占用，因为 Windows 文件共享模式允许“可读但不可删除/重命名”。
    这里用 rename 到临时名再 rename 回来的方式测试是否已经释放。
    """
    full = _norm(path)
    if not full or not os.path.exists(full):
        return True

    if os.path.isdir(full):
        return True

    parent = os.path.dirname(full)
    name = os.path.basename(full)
    tmp = os.path.join(parent, f".{name}.lockcheck.tmp")

    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except Exception:
            return False

    try:
        os.rename(full, tmp)
        os.rename(tmp, full)
        return True
    except Exception:
        # 尽量恢复
        try:
            if os.path.exists(tmp) and not os.path.exists(full):
                os.rename(tmp, full)
        except Exception:
            pass
        return False


def _wait_for_analysis_outputs_released(
    work_dir: str,
    *,
    timeout_seconds: float = 180.0,
    interval_seconds: float = 1.0,
) -> None:
    """
    等待 SACS 输出文件完全释放后再把后台任务标记为完成。

    原因：
    - SACS/共享盘有时在 bat 返回后仍短暂占用 psilst.factor / analysis_*.log；
    - 如果此时 task_manager 已把任务标记 success，用户马上开始第二次计算，
      第二次清理旧结果会失败，或者 SACS 继续追加旧结果。
    """
    start = time.time()
    last_locked: list[str] = []

    while time.time() - start <= float(timeout_seconds):
        locked: list[str] = []
        for path in _blocking_analysis_output_paths(work_dir):
            if not _can_rename_for_lock_check(path):
                locked.append(path)

        if not locked:
            if last_locked:
                print(
                    f"[FeasibilityRuntime] analysis outputs released: work_dir={work_dir}",
                    flush=True,
                )
            return

        last_locked = locked
        time.sleep(max(0.2, float(interval_seconds)))

    raise RuntimeError(
        "SACS 计算已结束，但输出文件仍被占用，暂不能开始下一次计算。\n"
        "请稍后重试；如果长时间不释放，请检查服务端任务管理器中是否仍有 AnalysisEngine.exe / SACS / cmd.exe 进程。\n"
        "被占用文件：\n" + "\n".join(last_locked)
    )


def _locked_blocking_analysis_output_paths(work_dir: str) -> list[str]:
    locked: list[str] = []
    for path in _blocking_analysis_output_paths(work_dir):
        if not _can_rename_for_lock_check(path):
            locked.append(path)
    return locked


def assert_analysis_outputs_ready_before_analysis(work_dir: str) -> None:
    locked = _locked_blocking_analysis_output_paths(work_dir)
    if not locked:
        return

    raise RuntimeError(
        "上一轮 SACS 关键计算结果文件仍被占用，请等待文件释放后再试。\n"
        "为避免新结果追加到旧结果文件，本次计算未启动。\n"
        "被占用的关键文件：\n" + "\n".join(locked)
    )



def _cleanup_previous_analysis_outputs(work_dir: str) -> None:
    """
    每次 SACS 计算前强制清理上一轮输出。

    如果 psilst.factor 等旧输出没有被删除，SACS 可能会在旧文件后面继续追加写入，
    导致第二次计算结果和第一次结果混在一起。因此这里不能只打印错误后继续，
    必须在清理失败时中止本次计算。
    """
    work_dir = _norm(work_dir)
    if not work_dir or not os.path.isdir(work_dir):
        return

    targets: list[str] = _analysis_output_paths(work_dir)

    if not targets:
        return

    failed_messages: list[str] = []
    skipped_messages: list[str] = []
    for full in targets:
        try:
            _remove_analysis_output_with_retry(full)
        except Exception as exc:
            if _is_non_blocking_analysis_output_name(os.path.basename(full)):
                skipped_messages.append(str(exc))
            else:
                failed_messages.append(str(exc))

    if skipped_messages:
        print(
            "[FeasibilityRuntime] skipped non-blocking SACS outputs:\n" + "\n".join(skipped_messages),
            flush=True,
        )

    if failed_messages:
        raise RuntimeError(
            "无法清理上一轮 SACS 计算结果，已停止本次计算，避免新结果追加到旧结果文件。\n"
            + "\n".join(failed_messages)
        )

    print(
        f"[FeasibilityRuntime] cleaned previous analysis outputs: count={len(targets)}, work_dir={work_dir}",
        flush=True,
    )


def _wait_for_fresh_result_file(
    *,
    work_dir: str,
    start_time: float,
    max_wait_seconds: int = 30 * 60,
    interval_seconds: float = 2.0,
) -> tuple[str, str]:
    work_dir = _norm(work_dir)
    required_stable_count = 8
    min_result_size = 8 * 1024

    elapsed = 0.0
    last_path = ""
    last_size = -1
    stable_count = 0

    while elapsed <= max_wait_seconds:
        result_file = find_result_file(work_dir)
        runx_done = _analysis_runx_has_done_marker(work_dir)

        if result_file and os.path.isfile(result_file):
            try:
                mtime = os.path.getmtime(result_file)
                size = os.path.getsize(result_file)
            except OSError:
                mtime = 0
                size = 0

            is_fresh = mtime >= float(start_time) - 2.0
            if is_fresh and size >= min_result_size:
                if result_file == last_path and size == last_size:
                    stable_count += 1
                else:
                    stable_count = 0
                    last_path = result_file
                    last_size = size

                if runx_done and stable_count >= required_stable_count:
                    return result_file, ""

            else:
                stable_count = 0

        time.sleep(max(0.5, interval_seconds))
        elapsed += max(0.5, interval_seconds)

    exit_code = _read_analysis_exit_code(work_dir)
    result_file = find_result_file(work_dir)
    detail = (
        f"等待计算结果写入完成超时：{work_dir}\n"
        f"result_file={result_file or ''}\n"
        f"runx_done={_analysis_runx_has_done_marker(work_dir)}\n"
        f"exit_code={'' if exit_code is None else exit_code}\n"
        f"stable_count={stable_count}/{required_stable_count}"
    )
    return result_file or "", detail


def _canonical_result_m1_path(work_dir: str) -> str:
    return os.path.join(_norm(work_dir), "psilst.M1")


def _ensure_result_file_suffix_m1(work_dir: str, result_file: str) -> str:
    """确保最终对外使用的计算结果文件后缀为 .M1。

    如果 RUNX 已经生成 psilst.M1，则直接返回；如果 SACS 仍生成 psilst.factor /
    psilst.lst 等旧名称，则在确认文件稳定后复制一份为 psilst.M1，后续查看结果、
    生成报告和导出文件都使用 psilst.M1。
    """
    src = _norm(result_file)
    if not src or not os.path.isfile(src):
        return src

    target = _canonical_result_m1_path(work_dir)
    if os.path.normcase(src) == os.path.normcase(target):
        return target

    os.makedirs(os.path.dirname(target), exist_ok=True)
    try:
        shutil.copy2(src, target)
        return target
    except Exception as exc:
        print(
            "[FeasibilityRuntime] copy result to psilst.M1 failed:",
            src,
            "->",
            target,
            exc,
            flush=True,
        )
        return src


def _rewrite_runx_for_analysis(
    runx_path: str,
    *,
    analysis_mode: str,
    runtime_bundle: dict[str, Any],
) -> str:
    """新流程统一把 RUNX 输入文件名修正为 M1。

    即使三个新增数据表为空，也会先创建等价于原模型的 M1 文件，
    所以计算阶段不再恢复 sacinp.JKnew / seainp.JKnew FACTOR。
    """
    runx_path = _norm(runx_path)
    if not runx_path:
        return ""

    return rewrite_runx_input_file_names(
        runx_path,
        model_filename="sacinp.M1",
        sea_filename="seainp.M1",
        model_candidates=[
            os.path.basename(str(runtime_bundle.get("model_file") or "")),
            os.path.basename(str(runtime_bundle.get("new_model_file") or "")),
            os.path.basename(str(runtime_bundle.get("runtime_model_file") or "")),
            "sacinp.JKnew",
            "sacinp.M1",
        ],
        sea_candidates=[
            os.path.basename(str(runtime_bundle.get("sea_file") or "")),
            os.path.basename(str(runtime_bundle.get("new_sea_file") or "")),
            os.path.basename(str(runtime_bundle.get("runtime_sea_file") or "")),
            "seainp.JKnew FACTOR",
            "seainp.M1",
        ],
        psiinp_filename="psiinp.M1",
        jcninp_filename="Jcninp.M1",
        result_filename="psilst.M1",
    )


def _archive_original_analysis_result(
    *,
    facility_code: str,
    result_file: str,
    runtime_bundle: dict[str, Any],
) -> str:
    result_file = _norm(result_file)
    if not result_file or not os.path.isfile(result_file):
        return ""

    try:
        from services.file_db_adapter import resolve_storage_path, upload_file
    except Exception:
        return ""

    source_label = str(runtime_bundle.get("project_name") or runtime_bundle.get("source") or "").strip()
    logical_path = f"{facility_code}/当前模型/静力/结果/自动计算/原模型"
    remark = f"结构强度/改造可行性评估计算结果；计算对象：原模型；来源：{source_label}"

    try:
        record = upload_file(
            result_file,
            file_type_code="other",
            module_code="model_files",
            logical_path=logical_path,
            facility_code=facility_code,
            category_name="静力分析结果文件",
            work_condition="原模型",
            remark=remark,
        )
        return resolve_storage_path(record) or result_file
    except Exception as exc:
        print("[FeasibilityRuntime] archive original analysis result failed:", exc, flush=True)
        return ""


def run_feasibility_analysis(
    *,
    facility_code: str,
    analysis_mode: str = "auto",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    code = str(facility_code or "").strip()
    if not code:
        raise ValueError("facility_code 不能为空")

    # 全局单任务：只要服务端已有 SACS 相关 exe 正在运行，就拒绝本次计算。
    # 不使用平台锁/数据库锁，按用户要求直接基于 SACS 进程占用状态判断。
    _assert_sacs_not_running_before_analysis()

    metadata = metadata or {}
    requested_mode = str(analysis_mode or "auto").strip().lower()

    if requested_mode not in {"auto", "original", "rebuild"}:
        requested_mode = "auto"

    # 新流程不再单独计算原模型。
    # 页面必须先保存数据并创建 M1；当三张表为空时，创建出的 M1 等价于原模型。
    actual_mode = "rebuild"

    mysql_url = get_mysql_url()

    runtime_bundle = prepare_latest_rebuild_runtime_for_analysis(
        mysql_url=mysql_url,
        job_name=code,
    )

    base_work_dir = str(runtime_bundle.get("model_dir") or "").strip() or get_job_runtime_dir(code)
    base_work_dir = _norm(base_work_dir)

    if not base_work_dir or not os.path.isdir(base_work_dir):
        raise FileNotFoundError(f"未找到模型运行目录：{base_work_dir}")

    # 先把服务端固定 RUNX、PSI、JCN 复制/规范化到平台运行根目录。
    support_files = stage_support_files_for_job(code, require_all=True)

    # 当前需求：直接在平台运行目录内计算，不再创建 analysis_runs/run_xxx。
    # 并发控制依赖 SACS 进程检测；计算前会清理上一轮输出。
    work_dir = _make_analysis_work_dir(base_work_dir, code)

    # 确认计算目录后再查一次，可识别执行当前 RUNX/BAT 的 cmd/powershell 进程。
    _assert_sacs_not_running_before_analysis(work_dir=work_dir)
    assert_analysis_outputs_ready_before_analysis(work_dir)

    model_src = _norm(get_job_new_model_file(code))
    sea_src = _norm(get_job_new_sea_file(code))
    if not os.path.isfile(model_src):
        model_src = _norm(runtime_bundle.get("new_model_file") or runtime_bundle.get("model_file"))
    if not os.path.isfile(sea_src):
        sea_src = _norm(runtime_bundle.get("new_sea_file") or runtime_bundle.get("sea_file"))

    _copy_input_to_analysis_dir(model_src, work_dir, "sacinp.M1", required=True)
    _copy_input_to_analysis_dir(sea_src, work_dir, "seainp.M1", required=True)
    psiinp_path = _copy_input_to_analysis_dir(
        support_files.get("psiinp", "") or os.path.join(base_work_dir, "psiinp.M1"),
        work_dir,
        "psiinp.M1",
        required=True,
    )
    jcninp_path = _copy_input_to_analysis_dir(
        support_files.get("jcninp", "") or os.path.join(base_work_dir, "Jcninp.M1"),
        work_dir,
        "Jcninp.M1",
        required=True,
    )
    runx_path = _copy_input_to_analysis_dir(
        support_files.get("runx", "") or os.path.join(base_work_dir, "psiM1.runx"),
        work_dir,
        "psiM1.runx",
        required=True,
    )

    runx_path = _rewrite_runx_for_analysis(
        runx_path,
        analysis_mode=actual_mode,
        runtime_bundle=runtime_bundle,
    )

    bat_path = ensure_analysis_bat(
        work_dir=work_dir,
        runx_path=runx_path,
        psiinp_path=psiinp_path,
        jcninp_path=jcninp_path,
    )

    # 复用同一个计算目录，启动前必须清理上一轮 SACS 输出。
    _cleanup_previous_analysis_outputs(work_dir)
    start_time = time.time()

    print(
        f"[FeasibilityRuntime] start analysis: facility={code}, mode={actual_mode}, work_dir={work_dir}",
        flush=True,
    )

    proc = subprocess.run(
        [bat_path],
        cwd=work_dir,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60 * 60,
    )

    print(
        f"[FeasibilityRuntime] bat finished: returncode={proc.returncode}, work_dir={work_dir}",
        flush=True,
    )

    result_file, wait_detail = _wait_for_fresh_result_file(
        work_dir=work_dir,
        start_time=start_time,
    )

    if not result_file or not os.path.isfile(result_file):
        raise RuntimeError(
            f"SACS 进程已结束，但没有找到本次新生成的结果文件。\n"
            f"计算目录：{work_dir}\n{wait_detail}"
        )

    result_file = _ensure_result_file_suffix_m1(work_dir, result_file)

    error_token = _analysis_output_has_error(work_dir, result_file)
    if error_token:
        raise RuntimeError(
            f"结果/日志中检测到错误标记：{error_token}\n"
            f"结果文件：{result_file}"
        )

    # 新流程取消“原模型结果自动保存到模型文件页面”。
    # 计算结果只保留在运行目录，用户通过“导出文件”手动导出。
    archived_path = ""

    # 等待输出文件释放后再把后台任务标记为完成，避免用户立即开始第二次计算时旧文件仍被占用。
    _wait_for_analysis_outputs_released(work_dir)

    run_id = int(time.time())

    state = {
        "facility_code": code,
        "run_id": run_id,
        "analysis_mode": actual_mode,
        "work_dir": work_dir,
        "base_work_dir": base_work_dir,
        "bat_path": bat_path,
        "runx_path": runx_path,
        "model_file": os.path.join(work_dir, "sacinp.M1"),
        "sea_file": os.path.join(work_dir, "seainp.M1"),
        "psiinp_file": os.path.join(work_dir, "psiinp.M1"),
        "jcninp_file": os.path.join(work_dir, "Jcninp.M1"),
        "result_file": result_file,
        "archived_path": archived_path,
        "runtime_bundle": runtime_bundle,
        "metadata": metadata,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    # 同时写入：
    # 当前 work_dir 就是平台运行根目录；这里保留双路径写入兼容旧逻辑。
    # 两个路径相同时会覆盖写入同一个 state 文件。
    for state_path in (Path(work_dir) / "feasibility_analysis_state.json", _analysis_state_path(code)):
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            print("[FeasibilityRuntime] write analysis state failed:", state_path, exc, flush=True)

    return state


def load_feasibility_result_bundle(
    *,
    facility_code: str,
    run_id: int | None = None,
) -> dict[str, Any]:
    code = str(facility_code or "").strip()
    result_file, work_dir, _state = _latest_state_result_file(code)

    if not result_file or not os.path.isfile(result_file):
        raise FileNotFoundError(f"未找到可行性评估结果文件：{work_dir}")

    project_root = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
    src_root = project_root / "src"
    for path in (str(project_root), str(src_root)):
        if path not in sys.path:
            sys.path.insert(0, path)

    try:
        from report_service import build_analysis_results_for_ui
    except Exception:
        from src.report_service import build_analysis_results_for_ui

    results = build_analysis_results_for_ui(
        result_file,
        pile_capacity_input_rows=[],
    )

    return {
        "facility_code": code,
        "run_id": run_id,
        "work_dir": work_dir,
        "factor_path": result_file,
        "results": results,
        "state_path": str(Path(work_dir) / "feasibility_analysis_state.json"),
    }


def _default_report_output_path(facility_code: str) -> Path:
    FEASIBILITY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_code = str(facility_code or "facility").replace("/", "_").replace("\\", "_")
    return FEASIBILITY_REPORT_DIR / f"{safe_code}_{timestamp}_feasibility_report.pdf"


def generate_feasibility_report(
    *,
    facility_code: str,
    run_id: int | None = None,
    report_payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    code = str(facility_code or "").strip()
    payload = dict(report_payload or {})

    project_root = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
    src_root = project_root / "src"
    for path in (str(project_root), str(src_root)):
        if path not in sys.path:
            sys.path.insert(0, path)

    try:
        from report_service import generate_report_with_project_defaults
    except Exception:
        from src.report_service import generate_report_with_project_defaults

    factor_path = _norm(payload.get("factor_path"))
    if not factor_path or not os.path.exists(factor_path):
        factor_path, _work_dir, _state = _latest_state_result_file(code)

    if not factor_path or not os.path.exists(factor_path):
        raise FileNotFoundError(f"未找到可行性评估结果文件，无法生成报告：{code}")

    if output_path:
        final_output_path = Path(output_path).expanduser().resolve()
    else:
        final_output_path = _default_report_output_path(code)

    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"[FeasibilityReportAPI] generate report: facility={code}, factor={factor_path}, output={final_output_path}",
        flush=True,
    )

    result_path = generate_report_with_project_defaults(
        project_root=project_root,
        chapter_1_3_sources=payload.get("chapter_1_3", {}),
        factor_path=factor_path,
        template_path=payload.get("template_path"),
        output_path=str(final_output_path),
        pile_capacity_input_rows=payload.get("pile_capacity_input_rows", []),
    )

    result_path = str(result_path or final_output_path)

    return {
        "facility_code": code,
        "run_id": run_id,
        "output_path": result_path,
        "output_exists": os.path.exists(result_path),
        "factor_path": factor_path,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _collect_export_files(
    *,
    facility_code: str,
    analysis_mode: str,
    include_model_files: bool,
    include_result_file: bool,
) -> list[str]:
    code = str(facility_code or "").strip()
    state = _load_latest_analysis_state(code)
    work_dir = _norm(state.get("work_dir") or get_job_runtime_dir(code))

    candidates: list[str] = []

    if include_model_files:
        candidates.extend([
            _norm(state.get("model_file")),
            _norm(state.get("sea_file")),
            _norm(state.get("psiinp_file")),
            _norm(state.get("jcninp_file")),
            _norm(get_job_new_model_file(code)),
            _norm(get_job_new_sea_file(code)),
            os.path.join(work_dir, "sacinp.M1"),
            os.path.join(work_dir, "seainp.M1"),
            os.path.join(work_dir, "psiinp.M1"),
            os.path.join(work_dir, "Jcninp.M1"),
        ])

    if include_result_file:
        candidates.append(os.path.join(work_dir, "psilst.M1"))
        result_file = _norm(state.get("result_file")) if state else ""
        if not result_file or not os.path.isfile(result_file):
            result_file = find_result_file(work_dir)
        if result_file:
            candidates.append(result_file)

    existing: list[str] = []
    seen: set[str] = set()

    for path in candidates:
        path = _norm(path)
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.isfile(path):
            existing.append(path)

    return existing


def export_feasibility_generated_files(
    *,
    facility_code: str,
    analysis_mode: str = "auto",
    include_model_files: bool = True,
    include_result_file: bool = True,
) -> dict[str, Any]:
    code = str(facility_code or "").strip()
    files = _collect_export_files(
        facility_code=code,
        analysis_mode=analysis_mode,
        include_model_files=include_model_files,
        include_result_file=include_result_file,
    )

    if not files:
        raise FileNotFoundError("当前没有找到可导出的 M1 文件或计算结果文件。")

    FEASIBILITY_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    zip_path = FEASIBILITY_EXPORT_DIR / f"{code}_{timestamp}_feasibility_outputs.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, arcname=os.path.basename(file_path))

    return {
        "facility_code": code,
        "analysis_mode": analysis_mode,
        "zip_path": str(zip_path),
        "zip_exists": zip_path.exists(),
        "files": files,
        "file_count": len(files),
    }
