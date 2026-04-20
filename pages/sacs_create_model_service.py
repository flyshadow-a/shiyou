# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from core.app_paths import first_existing_path
from pages.sacs_wellslot_service import generate_wellslot_to_db
from pages.sacs_riser_service import generate_riser_to_db
from pages.sacs_topside_service import transform_topside_weights_to_db
from pages.sacs_export_service import export_model_bundle


def _pick_existing_file(folder: str, names: list[str]) -> str:
    if not folder or (not os.path.isdir(folder)):
        return ""
    for name in names:
        p = os.path.join(folder, name)
        if os.path.exists(p):
            return p
    return ""


def _pick_latest_result_file(folder: str) -> str:
    """
    在 model_files 目录里尽量找出最新的结果文件。
    """
    if not folder or (not os.path.isdir(folder)):
        return ""

    preferred = [
        "psilst.factor",
        "psilst.lst",
        "psilst.lis",
        "psilst",
    ]
    for name in preferred:
        p = os.path.join(folder, name)
        if os.path.exists(p):
            return p

    candidates = []
    for fn in os.listdir(folder):
        low = fn.lower()
        if (
            low.startswith("psilst")
            or low.endswith(".lst")
            or low.endswith(".lis")
            or low.endswith(".listing")
            or low.endswith(".factor")
        ):
            full = os.path.join(folder, fn)
            try:
                mtime = os.path.getmtime(full)
            except OSError:
                mtime = 0.0
            candidates.append((mtime, full))

    if not candidates:
        return ""

    candidates.sort(reverse=True)
    return candidates[0][1]


def _normalize_export_info(export_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    把 export_model_bundle 的返回结果整理成页面后续可直接使用的统一字段。
    """
    export_info = dict(export_info or {})

    model_dir = (
        export_info.get("model_dir")
        or first_existing_path("upload", "model_files")
    )
    model_dir = os.path.normpath(model_dir)

    new_model_file = (
        export_info.get("new_model_file")
        or _pick_existing_file(model_dir, ["sacinp.M1", "sacinp.m1"])
    )
    new_sea_file = (
        export_info.get("new_sea_file")
        or _pick_existing_file(model_dir, ["seainp.M1", "seainp.m1"])
    )
    runx_file = (
        export_info.get("runx_file")
        or _pick_existing_file(model_dir, ["psiFACTOR.runx", "psifactor.runx"])
    )
    psiinp_file = (
        export_info.get("psiinp_file")
        or _pick_existing_file(model_dir, ["psiinp.19-1d", "psiinp"])
    )
    jcninp_file = (
        export_info.get("jcninp_file")
        or _pick_existing_file(model_dir, ["Jcninp.19-1d", "jcninp.19-1d", "jcninp"])
    )
    bat_file = (
        export_info.get("bat_file")
        or _pick_existing_file(model_dir, ["Autorun.bat", "run_analysis.bat", "analysis.bat"])
    )
    result_file = (
        export_info.get("result_file")
        or export_info.get("listing_file")
        or _pick_latest_result_file(model_dir)
    )

    stdout_log = export_info.get("stdout_log") or os.path.join(model_dir, "analysis_stdout.log")
    exitcode_file = export_info.get("exitcode_file") or os.path.join(model_dir, "analysis_exitcode.txt")

    export_info.update({
        "model_dir": model_dir,
        "new_model_file": new_model_file,
        "new_sea_file": new_sea_file,
        "runx_file": runx_file,
        "psiinp_file": psiinp_file,
        "jcninp_file": jcninp_file,
        "bat_file": bat_file,
        "result_file": result_file,
        "stdout_log": stdout_log,
        "exitcode_file": exitcode_file,
    })
    return export_info


def create_new_model_files(
    mysql_url: str,
    job_name: str,
    overwrite_job: bool = True,
    generate_bat: bool = False
) -> dict:
    result_wellslot = generate_wellslot_to_db(
        mysql_url=mysql_url,
        job_name=job_name,
        overwrite_job=overwrite_job,
    )

    result_riser = generate_riser_to_db(
        mysql_url=mysql_url,
        job_name=job_name,
        overwrite_job=overwrite_job,
    )

    result_topside = transform_topside_weights_to_db(
        mysql_url=mysql_url,
        job_name=job_name,
        overwrite_job=overwrite_job,
    )

    result_export = export_model_bundle(
        mysql_url=mysql_url,
        job_name=job_name,
        generate_bat_flag=generate_bat,
    )
    result_export = _normalize_export_info(result_export)

    return {
        "job_name": job_name,
        "wellslot": result_wellslot,
        "riser": result_riser,
        "topside": result_topside,
        "export": result_export,
    }