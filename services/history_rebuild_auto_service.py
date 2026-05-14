# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text

from services.inspection_business_db_adapter import (
    create_inspection_project,
    list_inspection_projects,
    update_inspection_project,
)
from services.file_db_adapter import (
    append_docman_file,
    list_files_by_prefix,
    load_docman_record_list,
    resolve_storage_path,
)
from pages.sacs_import_service import import_model_bundle_to_db
from pages.sacs_storage_service import get_job_new_model_file, get_job_new_sea_file, get_job_runtime_dir


HISTORY_FOLDER_NAME = "历史改造信息"
HISTORY_PROJECT_TYPE = "history_rebuild"
PROJECT_NAME_PREFIX = "历史改造项目"


def _norm(path: str) -> str:
    return os.path.normpath(str(path or "").strip())


def _file_exists(path: str) -> bool:
    path = _norm(path)
    return bool(path) and os.path.isfile(path)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _extract_project_no(name: str) -> int:
    text = str(name or "")
    # 支持：历史改造项目1、改造项目1、改造1
    m = re.search(r"(?:历史)?改造(?:项目)?\s*(\d+)", text)
    if m:
        return _safe_int(m.group(1), 0)
    return 0


def _list_history_projects(facility_code: str) -> list[dict[str, Any]]:
    try:
        rows = list_inspection_projects(
            facility_code=facility_code,
            project_type=HISTORY_PROJECT_TYPE,
        )
    except Exception:
        rows = []
    return [dict(row) for row in (rows or [])]


def _project_order_no(row: dict[str, Any], fallback_index: int = 0) -> int:
    """返回历史改造项目的真实顺序号。

    新逻辑：
    1. 优先使用数据库中的 sort_order，避免用户修改项目名称后影响版本判断；
    2. 旧数据如果没有 sort_order，再兼容从“历史改造项目N”名称中提取 N；
    3. 最后用 fallback_index/id 兜底，避免排序键为空。
    """
    sort_order = _safe_int(row.get("sort_order"), 0)
    if sort_order > 0:
        return sort_order

    name = str(row.get("project_name") or row.get("name") or "")
    name_no = _extract_project_no(name)
    if name_no > 0:
        return name_no

    row_id = _safe_int(row.get("id"), 0)
    return _safe_int(fallback_index, 0) or row_id


def _project_sort_key(row: dict[str, Any], fallback_index: int = 0) -> tuple[int, int]:
    """历史改造项目排序键。

    只把项目名称作为旧数据兜底，不再把名称中的数字作为主排序依据。
    因此用户把“历史改造项目2”改成“历史改造项目test”后，只要 sort_order 仍为 2，
    它仍然会被当作第 2 次改造。
    """
    order_no = _project_order_no(row, fallback_index)
    row_id = _safe_int(row.get("id"), 0)
    return (order_no, row_id)


def _next_project_no(facility_code: str) -> int:
    """返回用于创建前临时命名的下一个编号。

    真正归档后的编号以后续 create_inspection_project 返回的 sort_order 为准。
    这里仅用于创建前给数据库一个非空项目名，兼容旧流程。
    """
    projects = _list_history_projects(facility_code)
    max_no = 0
    for idx, row in enumerate(projects, start=1):
        max_no = max(max_no, _project_order_no(row, idx))
    return max_no + 1


def _current_year_label() -> str:
    return f"{_dt.datetime.now().year}年"


def _get_current_workpoint_and_threshold(mysql_url: str, job_name: str) -> tuple[float, int]:
    workpoint = 9.1
    level_threshold = 40
    try:
        engine = create_engine(mysql_url, future=True, pool_pre_ping=True)
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT workpoint
                    FROM wizard_model_info
                    WHERE job_name = :job_name
                    ORDER BY id DESC
                    LIMIT 1
                """),
                {"job_name": job_name},
            ).mappings().first()
            if row and row.get("workpoint") is not None:
                workpoint = float(row.get("workpoint"))
    except Exception:
        pass
    return workpoint, level_threshold


def _docman_path_segments(project_id: int) -> list[str]:
    # ImportantHistoryDetailWidget._project_storage_segments() 也是这个规则。
    return [HISTORY_FOLDER_NAME, f"project_{int(project_id)}"]


def _upload_history_file(
    *,
    local_path: str,
    facility_code: str,
    project_id: int,
    category: str,
    remark: str,
) -> Dict[str, Any]:
    return append_docman_file(
        local_path,
        path_segments=_docman_path_segments(project_id),
        category=category,
        work_condition="",
        remark=remark,
        facility_code=facility_code,
    )


def _pick_sacinp_and_seainp_from_docman(project_id: int, facility_code: str) -> tuple[str, str]:
    """
    从一个历史改造项目下的 doc_man 文件记录中，找出仍然存在的 sacinp.M1 / seainp.M1。
    如果用户手动删除了项目文件，这里会返回空，从而自动回退到更早项目或原始模型。
    """
    try:
        records = load_docman_record_list(
            _docman_path_segments(project_id),
            facility_code=facility_code,
        )
    except Exception:
        records = []

    model_file = ""
    sea_file = ""

    def _score(name: str, path: str) -> int:
        text = f"{name} {path}".lower()
        score = 0
        if "m1" in text:
            score += 100
        if "自动归档" in text:
            score += 10
        return score

    model_candidates: list[tuple[int, str]] = []
    sea_candidates: list[tuple[int, str]] = []

    for row in records or []:
        filename = str(row.get("filename") or row.get("name") or "").strip()
        path = _norm(str(row.get("path") or ""))
        if not _file_exists(path):
            continue
        low = filename.lower()
        if low.startswith("sacinp"):
            model_candidates.append((_score(filename, path), path))
        elif low.startswith("seainp"):
            sea_candidates.append((_score(filename, path), path))

    if model_candidates:
        model_candidates.sort(key=lambda item: item[0], reverse=True)
        model_file = model_candidates[0][1]
    if sea_candidates:
        sea_candidates.sort(key=lambda item: item[0], reverse=True)
        sea_file = sea_candidates[0][1]

    return model_file, sea_file


def find_latest_active_history_model_bundle(facility_code: str) -> dict[str, Any]:
    """
    返回当前仍然存在、且包含可用 M1 文件的最新历史改造项目。

    注意：这里只看“未删除的历史改造项目”和“项目下仍然存在的 M1 文件”。
    因此，如果用户手动删除了项目或删除了项目下的 M1 文件，下一次创建新模型不会再基于它。
    """
    code = (facility_code or "").strip()
    if not code:
        return {}

    projects = _list_history_projects(code)
    indexed = list(enumerate(projects, start=1))
    indexed.sort(key=lambda pair: _project_sort_key(pair[1], pair[0]), reverse=True)

    for _idx, project in indexed:
        project_id = _safe_int(project.get("id"), 0)
        if project_id <= 0:
            continue
        model_file, sea_file = _pick_sacinp_and_seainp_from_docman(project_id, code)
        if model_file:
            return {
                "source": "history",
                "project_id": project_id,
                "project_name": project.get("project_name") or project.get("name") or "",
                "project_order": _project_order_no(project, _idx),
                "model_file": model_file,
                "sea_file": sea_file,
            }

    return {}



def find_active_history_model_bundles(facility_code: str) -> list[dict[str, Any]]:
    """
    返回当前仍存在且包含可用 sacinp.M1 的历史改造版本，按改造编号从新到旧排序。
    用于“查看结果”和“计算分析”始终定位最新有效 M1。
    """
    code = (facility_code or "").strip()
    if not code:
        return []

    projects = _list_history_projects(code)
    indexed = list(enumerate(projects, start=1))
    indexed.sort(key=lambda pair: _project_sort_key(pair[1], pair[0]), reverse=True)

    bundles: list[dict[str, Any]] = []
    for _idx, project in indexed:
        project_id = _safe_int(project.get("id"), 0)
        if project_id <= 0:
            continue
        model_file, sea_file = _pick_sacinp_and_seainp_from_docman(project_id, code)
        if not model_file:
            continue
        bundles.append({
            "source": "history",
            "project_id": project_id,
            "project_name": project.get("project_name") or project.get("name") or "",
            "project_order": _project_order_no(project, _idx),
            "model_file": model_file,
            "sea_file": sea_file,
        })
    return bundles


def _copy_file_if_needed(src: str, dst: str) -> str:
    src = _norm(src)
    dst = _norm(dst)
    if not _file_exists(src):
        return ""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        if os.path.exists(dst) and os.path.samefile(src, dst):
            return dst
    except Exception:
        pass
    shutil.copy2(src, dst)
    return dst


def get_latest_rebuild_compare_model_paths(
    *,
    mysql_url: str | None = None,
    job_name: str,
) -> dict[str, Any]:
    """
    给“查看结果”使用的模型路径。

    当前规则按用户最新要求改为“上一版 M1 vs 最新 M1”：

    - 如果至少有 2 个仍存在的历史改造项目：
      old_model_file = 上一次历史改造项目的 sacinp.M1；
      new_model_file = 最新历史改造项目的 sacinp.M1。

    - 如果只有 1 个历史改造项目：
      old_model_file = 原始上传模型；
      new_model_file = 历史改造项目1的 sacinp.M1。

    - 如果没有任何历史改造项目，或历史项目的 M1 被删除：
      回退到原始上传模型。

    这样第二次改造后，图中只高亮“第二次相对第一次新增/变化”的构件；
    第一次改造已存在的构件会作为旧模型已有结构参与对比，不再被标为本次新增。
    """
    code = (job_name or "").strip()
    if not code:
        return {}

    original = find_original_uploaded_model_bundle(code)
    history_bundles = find_active_history_model_bundles(code)  # 新 -> 旧

    if history_bundles:
        latest = history_bundles[0]

        if len(history_bundles) >= 2:
            baseline = history_bundles[1]
            baseline_source = "history_previous"
            baseline_project_id = baseline.get("project_id")
            baseline_project_name = baseline.get("project_name")
        else:
            baseline = original
            baseline_source = "original"
            baseline_project_id = None
            baseline_project_name = "原始模型"

        old_model = _norm(baseline.get("model_file") or "")
        old_sea = _norm(baseline.get("sea_file") or "")
        new_model = _norm(latest.get("model_file") or "")
        new_sea = _norm(latest.get("sea_file") or "")

        # 如果上一版 M1 或原始模型被删除，退化为最新模型自身，避免页面崩溃。
        # 正常项目删除逻辑下，find_active_history_model_bundles 已经会跳过失效项目。
        if not _file_exists(old_model):
            old_model = new_model
            old_sea = new_sea
            baseline_source = "latest_self_fallback"
            baseline_project_id = latest.get("project_id")
            baseline_project_name = latest.get("project_name")

        return {
            "source": "history_previous_vs_latest",
            "baseline_source": baseline_source,
            "old_model_file": old_model,
            "new_model_file": new_model,
            "old_sea_file": old_sea,
            "new_sea_file": new_sea,
            "latest_project_id": latest.get("project_id"),
            "latest_project_name": latest.get("project_name"),
            "latest_project_order": latest.get("project_order"),
            "baseline_project_id": baseline_project_id,
            "baseline_project_name": baseline_project_name,
            "baseline_project_order": baseline.get("project_order") if isinstance(baseline, dict) else None,
        }

    # 没有历史改造项目时，回退到用户原始上传模型，相当于初始化状态。
    if original.get("model_file"):
        return {
            "source": "original",
            "old_model_file": _norm(original.get("model_file") or ""),
            "new_model_file": _norm(original.get("model_file") or ""),
            "old_sea_file": _norm(original.get("sea_file") or ""),
            "new_sea_file": _norm(original.get("sea_file") or ""),
        }
    return {}


def prepare_original_runtime_for_analysis(
    *,
    mysql_url: str | None = None,
    job_name: str,
) -> dict[str, Any]:
    """给“原模型计算”使用。

    当页面三张新增数据表为空、用户没有保存数据且没有创建新模型时，计算应当基于
    用户最初上传的原模型，而不是最新历史改造 M1。

    这里做的事情：
    1. 从文件库中找到原始 sacinp / seainp；
    2. 复制到 feasibility_assessment_runtime/<平台>/ 下，并保留原文件名；
    3. 返回运行目录和运行时文件名，供 RUNX 修正与 BAT 生成使用。
    """
    code = (job_name or "").strip()
    if not code:
        raise ValueError("job_name/facility_code 为空，无法准备原模型计算")

    bundle = find_original_uploaded_model_bundle(code)
    model_file = _norm(bundle.get("model_file") or "")
    sea_file = _norm(bundle.get("sea_file") or "")

    if not _file_exists(model_file):
        raise FileNotFoundError(
            f"未找到可用于计算的原始模型文件。平台：{code}\n"
            "请确认【模型文件】中已上传当前模型的 sacinp 原始结构模型。"
        )

    runtime_dir = get_job_runtime_dir(code)
    os.makedirs(runtime_dir, exist_ok=True)

    runtime_model_file = os.path.join(runtime_dir, os.path.basename(model_file))
    runtime_sea_file = os.path.join(runtime_dir, os.path.basename(sea_file)) if _file_exists(sea_file) else ""

    _copy_file_if_needed(model_file, runtime_model_file)
    if _file_exists(sea_file):
        _copy_file_if_needed(sea_file, runtime_sea_file)

    return {
        "source": "original",
        "project_id": None,
        "project_name": "原始模型",
        "model_dir": runtime_dir,
        "model_file": model_file,
        "sea_file": sea_file,
        "new_model_file": runtime_model_file,
        "new_sea_file": runtime_sea_file,
        "runtime_model_file": runtime_model_file,
        "runtime_sea_file": runtime_sea_file,
        "runtime_model_filename": os.path.basename(runtime_model_file),
        "runtime_sea_filename": os.path.basename(runtime_sea_file) if runtime_sea_file else "",
    }

def prepare_latest_rebuild_runtime_for_analysis(
    *,
    mysql_url: str | None = None,
    job_name: str,
) -> dict[str, Any]:
    """
    给“计算分析”使用。

    SACS 实际计算通常读取 feasibility_assessment_runtime/<平台>/sacinp.M1 和 seainp.M1。
    因此每次点击计算前，都把“当前仍存在的最新历史改造 M1”同步到 runtime 目录。

    若用户删除了所有历史改造项目，则同步原始上传模型到 runtime，避免继续计算已删除项目遗留的旧 M1。
    """
    code = (job_name or "").strip()
    if not code:
        raise ValueError("job_name/facility_code 为空，无法准备计算模型")

    bundle = find_latest_active_history_model_bundle(code)
    if not bundle:
        bundle = find_original_uploaded_model_bundle(code)

    model_file = _norm(bundle.get("model_file") or "")
    sea_file = _norm(bundle.get("sea_file") or "")
    if not _file_exists(model_file):
        raise FileNotFoundError(
            f"未找到可用于计算的模型文件。平台：{code}\n"
            "请先创建新模型，或确认原始模型/历史改造模型文件仍然存在。"
        )

    runtime_dir = get_job_runtime_dir(code)
    dst_model = get_job_new_model_file(code)
    dst_sea = get_job_new_sea_file(code)

    copied_model = _copy_file_if_needed(model_file, dst_model)
    copied_sea = ""
    if _file_exists(sea_file):
        copied_sea = _copy_file_if_needed(sea_file, dst_sea)

    return {
        "source": bundle.get("source") or "unknown",
        "project_id": bundle.get("project_id"),
        "project_name": bundle.get("project_name"),
        "project_order": bundle.get("project_order"),
        "model_dir": runtime_dir,
        "model_file": model_file,
        "sea_file": sea_file,
        "new_model_file": copied_model,
        "new_sea_file": copied_sea,
    }


def _score_original_model_row(row: dict[str, Any], path: str) -> int:
    logical = str(row.get("logical_path") or "").replace("\\", "/")
    name = str(row.get("original_name") or row.get("stored_name") or os.path.basename(path) or "")
    text = f"{logical} {name} {path}".lower()
    score = 0
    if "当前模型" in logical:
        score += 200
    if "结构模型" in logical:
        score += 100
    if "用户上传" in logical:
        score += 80
    if "结构模型文件" in logical:
        score += 60
    if "jknew" in text:
        score += 50
    if "m1" in text:
        score -= 500
    if "历史改造" in logical:
        score -= 1000
    return score


def _score_original_sea_row(row: dict[str, Any], path: str) -> int:
    logical = str(row.get("logical_path") or "").replace("\\", "/")
    name = str(row.get("original_name") or row.get("stored_name") or os.path.basename(path) or "")
    text = f"{logical} {name} {path}".lower()
    score = 0
    if "当前模型" in logical:
        score += 200
    if "结构模型" in logical:
        score += 100
    if "海况" in logical:
        score += 120
    if "用户上传" in logical:
        score += 80
    if "factor" in text:
        score += 50
    if "m1" in text:
        score -= 500
    if "历史改造" in logical:
        score -= 1000
    return score


def find_original_uploaded_model_bundle(facility_code: str) -> dict[str, Any]:
    """
    查找用户最初上传的当前模型文件和海况文件。

    用途：当所有历史改造项目都被删除后，下一次创建新模型需要回退到原始上传模型，
    相当于初始化，而不是继续使用已经被删除的第 N 次改造 M1。
    """
    code = (facility_code or "").strip()
    if not code:
        return {}

    prefixes = [
        f"{code}/当前模型/结构模型",
        f"{code}/当前模型",
        code,
    ]

    rows: list[dict[str, Any]] = []
    seen = set()
    for prefix in prefixes:
        for fc in (code, None):
            try:
                current_rows = list_files_by_prefix(
                    file_type_code="model",
                    module_code="model_files",
                    logical_path_prefix=prefix,
                    facility_code=fc,
                )
            except Exception:
                current_rows = []
            for row in current_rows or []:
                sig = row.get("id") or (
                    row.get("storage_path"), row.get("storage_rel_path"), row.get("original_name")
                )
                if sig in seen:
                    continue
                seen.add(sig)
                rows.append(dict(row))

    model_candidates: list[tuple[int, str]] = []
    sea_candidates: list[tuple[int, str]] = []

    for row in rows:
        path = _norm(resolve_storage_path(row))
        if not _file_exists(path):
            continue
        name = str(row.get("original_name") or row.get("stored_name") or os.path.basename(path) or "").strip()
        low_name = name.lower()
        if low_name.startswith("sacinp"):
            model_candidates.append((_score_original_model_row(row, path), path))
        elif low_name.startswith("seainp"):
            sea_candidates.append((_score_original_sea_row(row, path), path))

    if not model_candidates:
        return {}

    model_candidates.sort(key=lambda item: item[0], reverse=True)
    sea_candidates.sort(key=lambda item: item[0], reverse=True)

    return {
        "source": "original",
        "model_file": model_candidates[0][1],
        "sea_file": sea_candidates[0][1] if sea_candidates else "",
    }


def sync_current_model_baseline_for_next_rebuild(
    *,
    mysql_url: str,
    job_name: str,
) -> dict[str, Any]:
    """
    创建新模型前调用，重新确定本次改造的基础模型：

    1. 若存在未删除的历史改造项目，且最新项目下仍有 sacinp.M1，则基于该 M1 继续改造；
    2. 若所有历史改造项目被删除，或历史项目下 M1 文件被删除，则回退到用户原始上传模型；
    3. 将选中的基础模型重新导入 wizard_model_info，保证 export_model_bundle 使用正确基线。
    """
    code = (job_name or "").strip()
    if not code:
        raise ValueError("job_name/facility_code 为空，无法确定改造基础模型")

    bundle = find_latest_active_history_model_bundle(code)
    if not bundle:
        bundle = find_original_uploaded_model_bundle(code)

    model_file = _norm(bundle.get("model_file") or "")
    sea_file = _norm(bundle.get("sea_file") or "")

    if not _file_exists(model_file):
        raise FileNotFoundError(
            f"未找到可用的基础模型文件。平台：{code}\n"
            "请确认当前模型中存在原始 sacinp 文件，或历史改造项目中存在 sacinp.M1。"
        )
    if sea_file and not _file_exists(sea_file):
        sea_file = ""

    workpoint, level_threshold = _get_current_workpoint_and_threshold(mysql_url, code)
    reimport_result = import_model_bundle_to_db(
        mysql_url=mysql_url,
        job_name=code,
        model_file=model_file,
        sea_file=sea_file or None,
        workpoint=workpoint,
        level_threshold=level_threshold,
        overwrite_job=True,
    )

    return {
        "source": bundle.get("source") or "unknown",
        "project_id": bundle.get("project_id"),
        "project_name": bundle.get("project_name"),
        "project_order": bundle.get("project_order"),
        "model_file": model_file,
        "sea_file": sea_file,
        "reimport": reimport_result,
    }


def archive_model_files_as_history_rebuild(
    *,
    mysql_url: str,
    job_name: str,
    export_info: Dict[str, Any],
    summary_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    每次创建新模型成功后调用：
    1. 自动创建“历史改造项目N”；
    2. 将 sacinp.M1 / seainp.M1 上传到历史改造文件页面对应项目下；
    3. 将本次归档后的 M1 文件重新导入为当前基础模型，保证下一次改造基于上一次 M1。

    注意：下一次真正创建模型前，create_new_model_files 还会再次调用
    sync_current_model_baseline_for_next_rebuild()。因此如果用户在两次创建之间手动删除了
    历史改造项目，系统会自动回退到原始上传模型。
    """
    facility_code = (job_name or "").strip()
    if not facility_code:
        raise ValueError("job_name/facility_code 为空，无法生成历史改造项目")

    export_info = dict(export_info or {})
    new_model_file = _norm(export_info.get("new_model_file") or get_job_new_model_file(facility_code))
    new_sea_file = _norm(export_info.get("new_sea_file") or get_job_new_sea_file(facility_code))

    if not _file_exists(new_model_file):
        raise FileNotFoundError(f"本次新模型文件不存在，无法归档：{new_model_file}")

    # 没有海况文件时允许只归档模型文件，兼容早期没有 sea_file 的模型。
    has_sea = _file_exists(new_sea_file)

    # 先用临时编号创建项目；真正编号以后端返回的 sort_order 为准。
    # 这样即使用户删除了“历史改造项目2”，新建项目的 sort_order 仍会继续递增为 3，
    # 不会复用“2”；同时用户后续修改项目名称也不会影响版本顺序。
    initial_project_no = _next_project_no(facility_code)
    initial_project_name = f"{PROJECT_NAME_PREFIX}{initial_project_no}"
    auto_summary = summary_text is None

    created = create_inspection_project(
        facility_code=facility_code,
        project_type=HISTORY_PROJECT_TYPE,
        project_name=initial_project_name,
        project_year=_current_year_label(),
        summary_text="" if auto_summary else summary_text,
    )
    project_id = int(created.get("id"))

    project_no = _safe_int(created.get("sort_order"), 0) or initial_project_no
    project_name = f"{PROJECT_NAME_PREFIX}{project_no}"

    if auto_summary:
        summary_text = (
            f"系统自动生成的第{project_no}次改造记录。"
            "本次创建新模型后，已自动归档新模型文件和新海况文件；"
            "后续再次创建新模型时，将在当前仍存在的最新改造项目模型基础上继续修改。"
        )

    if project_name != str(created.get("project_name") or "") or auto_summary:
        created = update_inspection_project(
            project_id,
            project_name=project_name,
            summary_text=summary_text,
        )
        project_no = _safe_int(created.get("sort_order"), project_no) or project_no
        project_name = str(created.get("project_name") or project_name)

    model_row = _upload_history_file(
        local_path=new_model_file,
        facility_code=facility_code,
        project_id=project_id,
        category="模型文件",
        remark=f"{project_name} 自动归档的新模型文件",
    )
    archived_model_file = _norm(resolve_storage_path(model_row))

    sea_row = None
    archived_sea_file = ""
    if has_sea:
        sea_row = _upload_history_file(
            local_path=new_sea_file,
            facility_code=facility_code,
            project_id=project_id,
            category="海况文件",
            remark=f"{project_name} 自动归档的新海况文件",
        )
        archived_sea_file = _norm(resolve_storage_path(sea_row))

    if not _file_exists(archived_model_file):
        raise FileNotFoundError(f"模型文件归档后无法定位：{archived_model_file}")
    if has_sea and not _file_exists(archived_sea_file):
        raise FileNotFoundError(f"海况文件归档后无法定位：{archived_sea_file}")

    # 注意：这里不再把本次归档的 M1 立即重新导入 wizard_model_info。
    # 原因：查看结果页面需要拿“本次创建前的基础模型”和“本次新模型”做对比；
    # 如果归档后立刻重导入，会导致 wizard_model_info.model_file 变成最新 M1，
    # 从而查看结果/计算分析容易继续使用旧状态或丢失对比基准。
    # 下一次创建新模型前，create_new_model_files 会调用
    # sync_current_model_baseline_for_next_rebuild()，届时会重新选择当前仍存在的最新历史 M1。

    return {
        "project_id": project_id,
        "project_no": project_no,
        "project_sort_order": _safe_int(created.get("sort_order"), project_no) or project_no,
        "project_name": project_name,
        "project_year": _current_year_label(),
        "model_record_id": model_row.get("id"),
        "sea_record_id": sea_row.get("id") if sea_row else None,
        "archived_model_file": archived_model_file,
        "archived_sea_file": archived_sea_file,
    }
