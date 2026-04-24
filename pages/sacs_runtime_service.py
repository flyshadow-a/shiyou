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

    # 1. 优先用传入的 runx
    candidate = os.path.normpath(runx_path) if runx_path else ""
    if candidate and os.path.exists(candidate):
        if os.path.dirname(candidate) == work_dir:
            return candidate

        target = os.path.join(work_dir, "psiFACTOR.runx")
        if os.path.normcase(candidate) != os.path.normcase(target):
            shutil.copy2(candidate, target)
        return target

    # 2. 用 config 里的默认 runx 模板
    default_runx = os.path.normpath(get_sacs_default_runx_path())
    if not default_runx:
        raise ValueError("db_config.json 中未配置 sacs_default_runx_path")
    if not os.path.exists(default_runx):
        raise FileNotFoundError(f"默认 RUNX 文件不存在：{default_runx}")

    target = os.path.join(work_dir, "psiFACTOR.runx")
    if not os.path.exists(target):
        shutil.copy2(default_runx, target)
    return target


def build_bat_text(exe_path: str, runx_path: str, work_dir: str) -> str:
    exe_path = os.path.normpath(exe_path)
    runx_path = os.path.normpath(runx_path)
    work_dir = os.path.normpath(work_dir)
    sacs_home = os.path.dirname(exe_path)

    return rf"""@echo off
setlocal

set "MODEL_DIR={work_dir}"
set "SACS_EXE={exe_path}"
set "SACS_HOME={sacs_home}"
set "RUNX_FILE={runx_path}"

cd /d "%MODEL_DIR%"
"%SACS_EXE%" "%RUNX_FILE%" "%SACS_HOME%"

echo.
echo ExitCode=%errorlevel%
endlocal
exit /b %errorlevel%
"""


def ensure_analysis_bat(
    work_dir: str,
    runx_path: str = "",
    psiinp_path: str = "",
    jcninp_path: str = "",
) -> str:
    work_dir = os.path.normpath(work_dir)
    ensure_dir(work_dir)

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