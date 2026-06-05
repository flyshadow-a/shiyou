# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

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


def _cleanup_previous_analysis_outputs(work_dir: str) -> None:
    work_dir = _norm(work_dir)
    if not work_dir or not os.path.isdir(work_dir):
        return

    delete_names = {
        "analysis_exitcode.txt",
        "analysis_summary.log",
        "analysis_stdout.log",
        "analysis_stderr.log",
    }

    for fn in list(os.listdir(work_dir)):
        low = fn.lower()
        full = os.path.join(work_dir, fn)
        should_delete = (
            low in delete_names
            or low.startswith("psilst")
            or low.endswith(".listing")
        )
        if not should_delete:
            continue
        try:
            if os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
            else:
                os.remove(full)
        except Exception as exc:
            print("[FeasibilityRuntime] cleanup old analysis output failed:", full, exc, flush=True)


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


def _rewrite_runx_for_analysis(
    runx_path: str,
    *,
    analysis_mode: str,
    runtime_bundle: dict[str, Any],
) -> str:
    runx_path = _norm(runx_path)
    if not runx_path:
        return ""

    if analysis_mode == "original":
        model_file = str(runtime_bundle.get("new_model_file") or runtime_bundle.get("runtime_model_file") or "")
        sea_file = str(runtime_bundle.get("new_sea_file") or runtime_bundle.get("runtime_sea_file") or "")
        model_filename = os.path.basename(model_file)
        sea_filename = os.path.basename(sea_file) if sea_file else ""

        return rewrite_runx_input_file_names(
            runx_path,
            model_filename=model_filename,
            sea_filename=sea_filename,
            model_candidates=[
                os.path.basename(str(runtime_bundle.get("model_file") or "")),
                "sacinp.M1",
                "sacinp.JKnew",
            ],
            sea_candidates=[
                os.path.basename(str(runtime_bundle.get("sea_file") or "")),
                "seainp.M1",
                "seainp.JKnew FACTOR",
            ],
        )

    return rewrite_runx_input_file_names(
        runx_path,
        model_filename="sacinp.M1",
        sea_filename="seainp.M1",
        model_candidates=[
            os.path.basename(str(runtime_bundle.get("model_file") or "")),
            os.path.basename(str(runtime_bundle.get("new_model_file") or "")),
            "sacinp.JKnew",
            "sacinp.M1",
        ],
        sea_candidates=[
            os.path.basename(str(runtime_bundle.get("sea_file") or "")),
            os.path.basename(str(runtime_bundle.get("new_sea_file") or "")),
            "seainp.JKnew FACTOR",
            "seainp.M1",
        ],
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

    metadata = metadata or {}
    requested_mode = str(analysis_mode or "auto").strip().lower()

    if requested_mode not in {"auto", "original", "rebuild"}:
        requested_mode = "auto"

    # 客户端会根据页面状态传 original/rebuild。
    # 如果没传，就默认 rebuild；如果没有 M1，服务函数会自动回退原模型。
    actual_mode = requested_mode if requested_mode != "auto" else "rebuild"

    mysql_url = get_mysql_url()

    if actual_mode == "original":
        runtime_bundle = prepare_original_runtime_for_analysis(
            mysql_url=mysql_url,
            job_name=code,
        )
    else:
        runtime_bundle = prepare_latest_rebuild_runtime_for_analysis(
            mysql_url=mysql_url,
            job_name=code,
        )

    work_dir = str(runtime_bundle.get("model_dir") or "").strip() or get_job_runtime_dir(code)
    work_dir = _norm(work_dir)

    if not work_dir or not os.path.isdir(work_dir):
        raise FileNotFoundError(f"未找到模型运行目录：{work_dir}")

    support_files = stage_support_files_for_job(code, require_all=True)

    runx_path = support_files.get("runx", "") or ""
    if runx_path:
        runx_path = _rewrite_runx_for_analysis(
            runx_path,
            analysis_mode=actual_mode,
            runtime_bundle=runtime_bundle,
        )

    bat_path = ensure_analysis_bat(
        work_dir=work_dir,
        runx_path=runx_path,
        psiinp_path=support_files.get("psiinp", "") or os.path.join(work_dir, "psiinp.19-1d"),
        jcninp_path=support_files.get("jcninp", "") or os.path.join(work_dir, "Jcninp.19-1d"),
    )

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

    error_token = _analysis_output_has_error(work_dir, result_file)
    if error_token:
        raise RuntimeError(
            f"结果/日志中检测到错误标记：{error_token}\n"
            f"结果文件：{result_file}"
        )

    archived_path = ""
    if actual_mode == "original":
        archived_path = _archive_original_analysis_result(
            facility_code=code,
            result_file=result_file,
            runtime_bundle=runtime_bundle,
        )

    run_id = int(time.time())

    state = {
        "facility_code": code,
        "run_id": run_id,
        "analysis_mode": actual_mode,
        "work_dir": work_dir,
        "bat_path": bat_path,
        "runx_path": runx_path,
        "result_file": result_file,
        "archived_path": archived_path,
        "runtime_bundle": runtime_bundle,
        "metadata": metadata,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    state_path = Path(work_dir) / "feasibility_analysis_state.json"
    try:
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return state


def load_feasibility_result_bundle(
    *,
    facility_code: str,
    run_id: int | None = None,
) -> dict[str, Any]:
    code = str(facility_code or "").strip()
    work_dir = _norm(get_job_runtime_dir(code))
    result_file = find_result_file(work_dir)

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
        runtime_dir = _norm(get_job_runtime_dir(code))
        factor_path = find_result_file(runtime_dir)

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

    mode = str(analysis_mode or "auto").lower().strip()
    if mode == "auto":
        mode = str(state.get("analysis_mode") or "original").lower().strip() or "original"

    should_include_model = include_model_files and mode != "original"
    if should_include_model:
        candidates.append(_norm(get_job_new_model_file(code)))
        candidates.append(_norm(get_job_new_sea_file(code)))
        candidates.append(os.path.join(work_dir, "sacinp.M1"))
        candidates.append(os.path.join(work_dir, "seainp.M1"))

    if include_result_file:
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
