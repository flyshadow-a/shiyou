# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
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
    stdout_log = os.path.join(work_dir, "analysis_stdout.log")
    stderr_log = os.path.join(work_dir, "analysis_stderr.log")
    exitcode_file = os.path.join(work_dir, "analysis_exitcode.txt")

    return rf"""@echo off
setlocal

set "MODEL_DIR={work_dir}"
set "SACS_EXE={exe_path}"
set "SACS_HOME={sacs_home}"
set "RUNX_FILE={runx_path}"
set "SUMMARY_LOG={summary_log}"
set "STDOUT_LOG={stdout_log}"
set "STDERR_LOG={stderr_log}"
set "EXITCODE_FILE={exitcode_file}"

cd /d "%MODEL_DIR%"

echo MODEL_DIR=%MODEL_DIR% > "%SUMMARY_LOG%"
echo SACS_EXE=%SACS_EXE% >> "%SUMMARY_LOG%"
echo SACS_HOME=%SACS_HOME% >> "%SUMMARY_LOG%"
echo RUNX_FILE=%RUNX_FILE% >> "%SUMMARY_LOG%"
echo START_TIME=%date% %time% >> "%SUMMARY_LOG%"

rem 不把输出写入 PyQt 管道，避免阻塞；但保留到文件，便于判断是否执行完整/失败。
"%SACS_EXE%" "%RUNX_FILE%" "%SACS_HOME%" > "%STDOUT_LOG%" 2> "%STDERR_LOG%"

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

    # 注意：
    # _on_run_analysis 中会先把用户上传的 psiFACTOR.runx 复制到运行目录，
    # 然后根据“原模型 / 改造后模型”把 RUNX 中的 sacinp/seainp 文件名改好。
    #
    # 旧逻辑这里又调用了一次 stage_support_files_for_job()，会把用户上传的
    # 原始 RUNX 再复制到运行目录，从而覆盖已经修正过的 RUNX，导致计算时
    # 仍然引用 sacinp.JKnew / seainp.JKnew FACTOR。
    #
    # 因此这里必须遵循：如果调用方已经传入 runx_path，绝不重新复制 RUNX。
    # 只在 runx_path 为空时才兜底查找/复制 RUNX；psiinp/jcninp 也同理只补缺失项。
    if not runx_path or not psiinp_path or not jcninp_path:
        try:
            from pages.sacs_storage_service import stage_support_file_for_job
            job_name = os.path.basename(work_dir)

            if not runx_path:
                runx_path = stage_support_file_for_job(job_name, "runx", required=False) or ""
            if not psiinp_path:
                psiinp_path = stage_support_file_for_job(job_name, "psiinp", required=False) or ""
            if not jcninp_path:
                jcninp_path = stage_support_file_for_job(job_name, "jcninp", required=False) or ""
        except Exception:
            pass

    exe_path = resolve_analysis_engine_exe()
    local_runx = ensure_runx_in_workdir(work_dir, runx_path)

    # 保证 psiinp / jcninp 也在工作目录
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

# =========================
# RUNX 文件输入名修正
# =========================
def _unique_non_empty(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def rewrite_runx_input_file_names(
    runx_path: str,
    *,
    model_filename: str,
    sea_filename: str = "",
    model_candidates: list[str] | None = None,
    sea_candidates: list[str] | None = None,
) -> str:
    """把 RUNX 中引用的模型/海况文件名修正为当前运行目录中的文件名。

    背景：用户上传的 psiFACTOR.runx 通常引用原始模型名，例如：
        sacinp.JKnew
        seainp.JKnew FACTOR

    计算改造后模型时，运行目录中真正参与计算的文件是：
        sacinp.M1
        seainp.M1

    因此需要在运行前把 RUNX 中的输入文件名替换为当前应计算的文件名。
    反过来，当当前页面没有任何新增数据、需要计算原模型时，也可以把 RUNX
    从 M1 引用恢复为原始文件名，避免误算最新改造模型。
    """
    runx_path = os.path.normpath(str(runx_path or "").strip())
    if not runx_path or not os.path.isfile(runx_path):
        raise FileNotFoundError(f"RUNX 文件不存在：{runx_path}")

    target_model = str(model_filename or "").strip()
    target_sea = str(sea_filename or "").strip()
    if not target_model:
        raise ValueError("model_filename 不能为空，无法修正 RUNX 文件")

    with open(runx_path, "r", encoding="utf-8", errors="ignore") as fp:
        raw = fp.read()

    model_names = _unique_non_empty(
        list(model_candidates or [])
        + [
            "sacinp.JKnew",
            "sacinp.M1",
            target_model,
        ]
    )
    sea_names = _unique_non_empty(
        list(sea_candidates or [])
        + [
            "seainp.JKnew FACTOR",
            "seainp.M1",
            target_sea,
        ]
    )

    def replace_names(content: str, names: list[str], target: str) -> str:
        if not target:
            return content
        # 长文件名优先，例如先替换 "seainp.JKnew FACTOR"，再替换 "seainp.M1"。
        for old in sorted(names, key=len, reverse=True):
            if not old or old.lower() == target.lower():
                continue
            content = re.sub(re.escape(old), target, content, flags=re.IGNORECASE)
        return content

    new_text = replace_names(raw, model_names, target_model)
    new_text = replace_names(new_text, sea_names, target_sea)

    if new_text != raw:
        with open(runx_path, "w", encoding="utf-8", newline="\r\n") as fp:
            fp.write(new_text)

    return runx_path
