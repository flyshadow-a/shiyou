# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil


from shiyou_db.config import (
    get_sacs_analysis_engine_exe,
    get_sacs_default_runx_path,
    get_sacs_default_psiinp_path,
    get_sacs_default_jcninp_path,
)

def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def resolve_analysis_engine_exe() -> str:
    exe_path = os.path.normpath(get_sacs_analysis_engine_exe())
    if not exe_path:
        raise ValueError("db_config.json 中未配置 sacs_analysis_engine_exe")
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"AnalysisEngine.exe 不存在：{exe_path}")
    return exe_path


def ensure_runx_in_workdir(work_dir: str, runx_path: str = "") -> str:
    work_dir = os.path.normpath(work_dir)
    ensure_dir(work_dir)

    target = os.path.join(work_dir, "psiFACTOR.runx")

    # 1. 优先用传入的 runx
    candidate = os.path.normpath(runx_path) if runx_path else ""
    if candidate and os.path.exists(candidate):
        if os.path.normcase(candidate) == os.path.normcase(target):
            return target
        if os.path.normcase(os.path.dirname(candidate)) == os.path.normcase(work_dir):
            return candidate
        shutil.copy2(candidate, target)
        return target

    # 2. 如果运行目录里已经有用户上传/前序步骤复制过来的 runx，直接使用。
    #    这样 db_config.json 里失效的默认模板路径不会覆盖运行目录文件。
    if os.path.exists(target):
        return target

    # 3. 最后才用 config 里的默认 runx 模板
    default_runx = os.path.normpath(get_sacs_default_runx_path())
    if default_runx and os.path.exists(default_runx):
        shutil.copy2(default_runx, target)
        return target

    if default_runx:
        raise FileNotFoundError(
            f"默认 RUNX 文件不存在：{default_runx}。请上传 psiFACTOR.runx 到当前模型/其他，或修正 db_config.json。"
        )
    raise ValueError("db_config.json 中未配置 sacs_default_runx_path，且运行目录中没有 psiFACTOR.runx")


def build_bat_text(exe_path: str, runx_path: str, work_dir: str) -> str:
    """
    生成 SACS 计算 BAT。

    关键优化：
    - 不再把 SACS 大量 stdout/stderr 输出交给 PyQt QProcess 管道；
    - 也不再把完整输出持续追加到 analysis_stdout.log；
    - 只保留 analysis_summary.log 和 analysis_exitcode.txt。

    原因：SACS 计算过程中可能持续输出大量日志。
    如果这些输出进入 QProcess 管道，或者持续写入大日志文件，都会明显拖慢计算。
    这里用 >nul 2>nul 丢弃大量运行输出，让软件启动方式尽量接近用户双击 bat。
    """
    exe_path = os.path.normpath(exe_path)
    runx_path = os.path.normpath(runx_path)
    work_dir = os.path.normpath(work_dir)
    sacs_home = os.path.dirname(exe_path)

    summary_log = os.path.join(work_dir, "analysis_summary.log")
    exitcode_file = os.path.join(work_dir, "analysis_exitcode.txt")

    return rf"""@echo off
setlocal

set "MODEL_DIR={work_dir}"
set "SACS_EXE={exe_path}"
set "SACS_HOME={sacs_home}"
set "RUNX_FILE={runx_path}"
set "SUMMARY_LOG={summary_log}"
set "EXITCODE_FILE={exitcode_file}"

cd /d "%MODEL_DIR%"

echo MODEL_DIR=%MODEL_DIR% > "%SUMMARY_LOG%"
echo SACS_EXE=%SACS_EXE% >> "%SUMMARY_LOG%"
echo SACS_HOME=%SACS_HOME% >> "%SUMMARY_LOG%"
echo RUNX_FILE=%RUNX_FILE% >> "%SUMMARY_LOG%"
echo START_TIME=%date% %time% >> "%SUMMARY_LOG%"

"%SACS_EXE%" "%RUNX_FILE%" "%SACS_HOME%" >nul 2>nul

set "SACS_EXIT=%errorlevel%"

echo END_TIME=%date% %time% >> "%SUMMARY_LOG%"
echo ExitCode=%SACS_EXIT% >> "%SUMMARY_LOG%"
echo %SACS_EXIT% > "%EXITCODE_FILE%"

endlocal
exit /b %SACS_EXIT%
"""


def ensure_analysis_bat(
    work_dir: str,
    runx_path: str = "",
    psiinp_path: str = "",
    jcninp_path: str = "",
) -> str:
    work_dir = os.path.normpath(work_dir)
    ensure_dir(work_dir)

    # 计算分析可能被用户直接点击；此时再次尝试从“当前模型/其他”复制辅助文件。
    try:
        from pages.sacs_storage_service import stage_support_files_for_job
        job_name = os.path.basename(work_dir)
        staged = stage_support_files_for_job(job_name, require_all=False)
        runx_path = runx_path or staged.get("runx", "")
        psiinp_path = psiinp_path or staged.get("psiinp", "")
        jcninp_path = jcninp_path or staged.get("jcninp", "")
    except Exception:
        pass

    exe_path = resolve_analysis_engine_exe()
    local_runx = ensure_runx_in_workdir(work_dir, runx_path)

    # 新增：保证 psiinp / jcninp 也在工作目录
    ensure_support_inputs_in_workdir(
        work_dir=work_dir,
        psiinp_path=psiinp_path,
        jcninp_path=jcninp_path,
    )

    bat_path = os.path.join(work_dir, "Autorun.bat")
    content = build_bat_text(exe_path, local_runx, work_dir)

    with open(bat_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content)

    return bat_path


def find_result_file(work_dir: str) -> str:
    if not work_dir or not os.path.isdir(work_dir):
        return ""

    preferred = [
        "psilst.factor",
        "psilst.lst",
        "psilst.lis",
        "psilst",
    ]
    for name in preferred:
        p = os.path.join(work_dir, name)
        if os.path.exists(p):
            return p

    candidates = []
    for fn in os.listdir(work_dir):
        low = fn.lower()
        if (
            low.startswith("psilst")
            or low.endswith(".factor")
            or low.endswith(".lst")
            or low.endswith(".lis")
            or low.endswith(".listing")
        ):
            full = os.path.join(work_dir, fn)
            try:
                mtime = os.path.getmtime(full)
            except OSError:
                mtime = 0
            candidates.append((mtime, full))

    if not candidates:
        return ""

    candidates.sort(reverse=True)
    return candidates[0][1]

def ensure_named_input_in_workdir(
    work_dir: str,
    target_name: str,
    source_path: str = "",
    default_path: str = "",
) -> str:
    work_dir = os.path.normpath(work_dir)
    ensure_dir(work_dir)

    target = os.path.join(work_dir, target_name)

    candidate = os.path.normpath(source_path) if source_path else ""
    if candidate and os.path.exists(candidate):
        if os.path.normcase(candidate) != os.path.normcase(target):
            shutil.copy2(candidate, target)
        return target

    default_candidate = os.path.normpath(default_path) if default_path else ""
    if default_candidate and os.path.exists(default_candidate):
        if os.path.normcase(default_candidate) != os.path.normcase(target):
            shutil.copy2(default_candidate, target)
        return target

    if os.path.exists(target):
        return target

    raise FileNotFoundError(f"缺少输入文件：{target_name}")


def ensure_support_inputs_in_workdir(
    work_dir: str,
    psiinp_path: str = "",
    jcninp_path: str = "",
) -> tuple[str, str]:
    psiinp_file = ensure_named_input_in_workdir(
        work_dir=work_dir,
        target_name="psiinp.19-1d",
        source_path=psiinp_path,
        default_path=get_sacs_default_psiinp_path(),
    )
    jcninp_file = ensure_named_input_in_workdir(
        work_dir=work_dir,
        target_name="Jcninp.19-1d",
        source_path=jcninp_path,
        default_path=get_sacs_default_jcninp_path(),
    )
    return psiinp_file, jcninp_file