# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text

from core.app_paths import first_existing_path
from pages.sacs_wellslot_service import (
    generate_wellslot_to_db,
    ensure_tables as ensure_wellslot_result_tables,
    delete_old_results as delete_old_wellslot_results,
)
from pages.sacs_riser_service import (
    generate_riser_to_db,
    ensure_tables as ensure_riser_result_tables,
    delete_old_results as delete_old_riser_results,
)
from pages.sacs_topside_service import (
    transform_topside_weights_to_db,
    ensure_tables as ensure_topside_result_tables,
    delete_old_results as delete_old_topside_results,
)
from pages.sacs_export_service import export_model_bundle
from pages.sacs_storage_service import get_job_runtime_dir
from services.history_rebuild_auto_service import (
    archive_model_files_as_history_rebuild,
    sync_current_model_baseline_for_next_rebuild,
)


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


def _normalize_export_info(export_info: Optional[Dict[str, Any]], job_name: str) -> Dict[str, Any]:
    """
    把 export_model_bundle 的返回结果整理成页面后续可直接使用的统一字段。
    """
    export_info = dict(export_info or {})

    model_dir = (
            export_info.get("model_dir")
            or get_job_runtime_dir(job_name)
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


def _count_table_rows(conn, table_name: str, job_name: str) -> int:
    """
    统计当前 job 的某类输入数据数量。

    表不存在时按 0 处理，避免用户没有填写某一类构件时创建新模型直接报错。
    """
    try:
        value = conn.execute(
            text(f"SELECT COUNT(*) FROM {table_name} WHERE job_name = :job_name"),
            {"job_name": job_name},
        ).scalar()
        return int(value or 0)
    except Exception:
        return 0


def _make_skipped_result(job_name: str, input_table: str, reason: str = "未填写该类输入数据") -> dict:
    return {
        "job_name": job_name,
        "input_table": input_table,
        "skipped": True,
        "reason": reason,
    }


def _ensure_all_result_tables(engine) -> None:
    """确保导出阶段需要读取的结果表都存在。"""
    ensure_wellslot_result_tables(engine)
    ensure_riser_result_tables(engine)
    ensure_topside_result_tables(engine)


def _delete_all_generated_results(conn, job_name: str) -> None:
    """
    清空当前 job 的所有新增构件/新增载荷中间结果。

    这样可以避免用户这次只填写井槽时，仍然把上一次保存过的立管/组块载荷结果导出到新模型里。
    """
    delete_old_wellslot_results(conn, job_name)
    delete_old_riser_results(conn, job_name)
    delete_old_topside_results(conn, job_name)


def create_new_model_files(
    mysql_url: str,
    job_name: str,
    overwrite_job: bool = True,
    generate_bat: bool = False
) -> dict:
    """
    基于当前已保存的输入数据创建新模型。

    三类输入数据均为可选：井槽、立管/电缆、组块载荷可以只填其中一种，
    也可以任意组合。创建前会先根据“仍然存在的历史改造项目”重新确定基础模型：

    - 若存在历史改造项目及可用 M1，则基于最新可用 M1 继续改造；
    - 若用户手动删除了所有历史改造项目，或删除了最新项目下的 M1，则自动回退原始上传模型；
    - 因此删除历史改造项目就等价于把后续改造基础初始化到原模型或上一个仍存在的改造版本。
    """
    job_name = (job_name or "").strip()
    if not job_name:
        raise ValueError("job_name 为空，无法创建新模型")

    engine = create_engine(mysql_url, future=True, pool_pre_ping=True)
    _ensure_all_result_tables(engine)

    with engine.begin() as conn:
        input_counts = {
            "well_slots": _count_table_rows(conn, "well_slots", job_name),
            "risers": _count_table_rows(conn, "risers", job_name),
            "topside_weights": _count_table_rows(conn, "topside_weights", job_name),
        }

        if sum(input_counts.values()) <= 0:
            raise ValueError(
                f"job={job_name} 没有任何已保存的新增数据。"
                "请先填写井槽、立管/电缆或组块载荷中的至少一种，并点击保存数据。"
            )

    # 关键修复：创建新模型前重新同步基础模型。
    # 这样用户删除历史改造项目后，下一次创建会自动回退到仍存在的最新历史版本；
    # 如果历史项目已全部删除，则回退原始上传模型。
    baseline = sync_current_model_baseline_for_next_rebuild(
        mysql_url=mysql_url,
        job_name=job_name,
    )

    with engine.begin() as conn:
        if overwrite_job:
            _delete_all_generated_results(conn, job_name)

    if input_counts["well_slots"] > 0:
        result_wellslot = generate_wellslot_to_db(
            mysql_url=mysql_url,
            job_name=job_name,
            overwrite_job=False,
        )
    else:
        result_wellslot = _make_skipped_result(job_name, "well_slots")

    if input_counts["risers"] > 0:
        result_riser = generate_riser_to_db(
            mysql_url=mysql_url,
            job_name=job_name,
            overwrite_job=False,
        )
    else:
        result_riser = _make_skipped_result(job_name, "risers")

    if input_counts["topside_weights"] > 0:
        result_topside = transform_topside_weights_to_db(
            mysql_url=mysql_url,
            job_name=job_name,
            overwrite_job=False,
        )
    else:
        result_topside = _make_skipped_result(job_name, "topside_weights")

    result_export = export_model_bundle(
        mysql_url=mysql_url,
        job_name=job_name,
        generate_bat_flag=generate_bat,
    )
    result_export = _normalize_export_info(result_export, job_name)

    history_project = archive_model_files_as_history_rebuild(
        mysql_url=mysql_url,
        job_name=job_name,
        export_info=result_export,
    )

    return {
        "job_name": job_name,
        "input_counts": input_counts,
        "baseline": baseline,
        "wellslot": result_wellslot,
        "riser": result_riser,
        "topside": result_topside,
        "export": result_export,
        "history_project": history_project,
    }
