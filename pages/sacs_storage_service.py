# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
from shiyou_db.config import get_storage_root


# 原来所有文件都放在：storage_root/sacs_jobs/<平台>/source|runtime
# 现在改为与 special_strategy_inputs / special_strategy_runtime 类似的共享盘一级目录：
#   <storage_root 的上一级>/feasibility_assessment_inputs/<平台>/...
#   <storage_root 的上一级>/feasibility_assessment_runtime/<平台>/...
# 原模型和海况文件不再复制到 source/input 目录；输入目录只保留兼容接口，不主动使用。
FEASIBILITY_INPUTS_DIR_NAME = "feasibility_assessment_inputs"
FEASIBILITY_RUNTIME_DIR_NAME = "feasibility_assessment_runtime"
LEGACY_SACS_JOBS_DIR_NAME = "sacs_jobs"


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def get_runtime_root() -> str:
    root = str(get_storage_root() or "").strip()
    if not root:
        raise ValueError("db_config.json 未配置 storage_root")
    return os.path.normpath(root)


def get_shared_parent_root() -> str:
    """返回共享盘一级目录。

    例如 storage_root=Y:/shiyou_file_storage，返回 Y:/。
    """
    return os.path.normpath(os.path.dirname(get_runtime_root()))


def get_feasibility_inputs_root() -> str:
    return os.path.join(get_shared_parent_root(), FEASIBILITY_INPUTS_DIR_NAME)


def get_feasibility_runtime_root() -> str:
    return os.path.join(get_shared_parent_root(), FEASIBILITY_RUNTIME_DIR_NAME)


def get_job_root(job_name: str) -> str:
    """兼容旧调用：现在 job 根目录指向运行结果目录。"""
    return os.path.join(get_feasibility_runtime_root(), str(job_name).strip())


def get_job_input_dir(job_name: str) -> str:
    return os.path.join(get_feasibility_inputs_root(), str(job_name).strip())


def get_job_source_dir(job_name: str) -> str:
    """兼容旧函数名。

    注意：新流程不再使用 source 文件夹，也不再把原模型/海况复制进来。
    旧调用如果仍然使用该函数，也只会得到 inputs 目录，不会生成 source 目录。
    """
    return get_job_input_dir(job_name)


def get_job_runtime_dir(job_name: str) -> str:
    return os.path.join(get_feasibility_runtime_root(), str(job_name).strip())


def get_legacy_job_root(job_name: str) -> str:
    return os.path.join(get_runtime_root(), LEGACY_SACS_JOBS_DIR_NAME, str(job_name).strip())


def get_legacy_job_source_dir(job_name: str) -> str:
    return os.path.join(get_legacy_job_root(job_name), "source")


def get_legacy_job_runtime_dir(job_name: str) -> str:
    return os.path.join(get_legacy_job_root(job_name), "runtime")


def remove_legacy_job_source_dir(job_name: str) -> None:
    """删除旧流程遗留的 sacs_jobs/<平台>/source 目录。"""
    source_dir = os.path.normpath(get_legacy_job_source_dir(job_name))
    if os.path.isdir(source_dir):
        shutil.rmtree(source_dir, ignore_errors=True)


def ensure_job_root(job_name: str) -> str:
    return ensure_dir(get_job_root(job_name))


def ensure_job_input_dir(job_name: str) -> str:
    return ensure_dir(get_job_input_dir(job_name))


def ensure_job_source_dir(job_name: str) -> str:
    # 兼容旧接口，实际创建 inputs 目录，不创建 source 目录。
    return ensure_job_input_dir(job_name)


def ensure_job_runtime_dir(job_name: str) -> str:
    return ensure_dir(get_job_runtime_dir(job_name))


def get_job_model_file(job_name: str) -> str:
    # 兼容旧接口；新流程不会主动调用它复制原模型。
    return os.path.join(get_job_input_dir(job_name), "sacinp.JKnew")


def get_job_sea_file(job_name: str) -> str:
    # 兼容旧接口；新流程不会主动调用它复制原海况文件。
    return os.path.join(get_job_input_dir(job_name), "seainp.JKnew FACTOR")


def get_job_new_model_file(job_name: str) -> str:
    return os.path.join(get_job_runtime_dir(job_name), "sacinp.M1")


def get_job_new_sea_file(job_name: str) -> str:
    return os.path.join(get_job_runtime_dir(job_name), "seainp.M1")


def get_job_runx_file(job_name: str) -> str:
    return os.path.join(get_job_runtime_dir(job_name), "psiFACTOR.runx")


def get_job_psiinp_file(job_name: str) -> str:
    return os.path.join(get_job_runtime_dir(job_name), "psiinp.19-1d")


def get_job_jcninp_file(job_name: str) -> str:
    return os.path.join(get_job_runtime_dir(job_name), "Jcninp.19-1d")


def get_job_bat_file(job_name: str) -> str:
    return os.path.join(get_job_runtime_dir(job_name), "Autorun.bat")


def stage_file(src_path: str, dst_path: str) -> str:
    if not src_path:
        return ""
    src_path = os.path.normpath(src_path)
    dst_path = os.path.normpath(dst_path)
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"源文件不存在: {src_path}")
    ensure_dir(os.path.dirname(dst_path))
    if os.path.normcase(src_path) != os.path.normcase(dst_path):
        shutil.copy2(src_path, dst_path)
    return dst_path


def stage_optional_from_same_dir(base_file: str, candidate_names: list[str], dst_path: str) -> str:
    if not base_file:
        return ""
    folder = os.path.dirname(os.path.normpath(base_file))
    for name in candidate_names:
        p = os.path.join(folder, name)
        if os.path.exists(p):
            return stage_file(p, dst_path)
    return ""

# =========================
# SACS 计算辅助文件（RUNX / PSIINP / JCNINP）
# =========================
# 用户现在把这些文件上传到：
#   shiyou_file_storage/model_files/<平台>/当前模型/其他/用户上传/其他
# 所以创建模型 / 计算分析时，需要从文件库真实存储路径复制到
#   feasibility_assessment_runtime/<平台>

_SUPPORT_FILE_SPECS = {
    "runx": {
        "target": get_job_runx_file,
        "names": ["psiFACTOR.runx", "psifactor.runx", "psiSTATIC.runx"],
        "label": "RUNX 文件（psiFACTOR.runx）",
    },
    "psiinp": {
        "target": get_job_psiinp_file,
        "names": ["psiinp.19-1d", "psiinp"],
        "label": "PSIINP 文件（psiinp.19-1d）",
    },
    "jcninp": {
        "target": get_job_jcninp_file,
        "names": ["Jcninp.19-1d", "jcninp.19-1d", "jcninp"],
        "label": "JCNINP 文件（Jcninp.19-1d）",
    },
}


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _norm_file_name(name: str) -> str:
    return str(name or "").strip().lower()


def _file_name_matches(kind: str, path: str) -> bool:
    spec = _SUPPORT_FILE_SPECS.get(kind) or {}
    name = _norm_file_name(os.path.basename(path))
    expected = [_norm_file_name(x) for x in spec.get("names") or []]
    if name in expected:
        return True
    if kind == "runx":
        return name.startswith("psi") and name.endswith(".runx")
    if kind == "psiinp":
        return name.startswith("psiinp")
    if kind == "jcninp":
        return name.startswith("jcninp")
    return False


def _support_logical_prefixes(job_name: str) -> list[str]:
    code = str(job_name or "").strip()
    if not code:
        return []
    return [
        f"{code}/当前模型/其他/用户上传/其他",
        f"{code}/当前模型/其他/用户上传",
        f"{code}/当前模型/其他",
        f"{code}/当前模型/结构模型/其他/用户上传/其他",
        f"{code}/当前模型/结构模型/其他/用户上传",
        f"{code}/当前模型/结构模型/其他",
        f"{code}/其他/用户上传/其他",
        f"{code}/其他/用户上传",
        f"{code}/其他",
    ]


def _row_time(row: dict) -> float:
    for key in ("source_modified_at", "uploaded_at", "updated_at"):
        value = row.get(key)
        if hasattr(value, "timestamp"):
            try:
                return float(value.timestamp())
            except Exception:
                pass
    return 0.0


def _query_support_candidates_from_db(job_name: str) -> list[tuple[str, dict]]:
    """从文件库记录中寻找当前平台“其他”目录下的计算辅助文件。"""
    code = str(job_name or "").strip()
    if not code:
        return []

    try:
        from services.file_db_adapter import (
            FileBackendError,
            is_file_db_configured,
            list_files_by_prefix,
            resolve_storage_path,
        )
    except Exception:
        return []

    if not is_file_db_configured():
        return []

    candidates: list[tuple[str, dict]] = []
    seen: set[str] = set()
    modules = ("model_files", "special_strategy")
    prefixes = _support_logical_prefixes(code)

    for module_code in modules:
        for facility_code in (code, None):
            for prefix in prefixes:
                try:
                    rows = list_files_by_prefix(
                        file_type_code=None,
                        module_code=module_code,
                        logical_path_prefix=prefix,
                        facility_code=facility_code,
                    )
                except FileBackendError:
                    continue
                except Exception:
                    continue

                for row in rows or []:
                    try:
                        path = resolve_storage_path(row)
                    except Exception:
                        path = ""
                    path = os.path.normpath(str(path or "").strip())
                    if not path or not os.path.exists(path):
                        continue
                    key = os.path.normcase(path)
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append((path, dict(row)))

    return candidates


def _query_support_candidates_from_disk(job_name: str) -> list[str]:
    """数据库记录异常时，直接扫描共享盘 model_files/<平台>/当前模型/其他。"""
    code = str(job_name or "").strip()
    if not code:
        return []

    roots = []
    storage_root = get_runtime_root()
    roots.extend([
        os.path.join(storage_root, "model_files", code, "当前模型", "其他"),
        os.path.join(storage_root, "model_files", code, "当前模型"),
        os.path.join(storage_root, "model_files", code),
    ])

    out: list[str] = []
    seen: set[str] = set()
    for root in roots:
        root = os.path.normpath(root)
        if not os.path.isdir(root):
            continue
        for current_root, _dirs, files in os.walk(root):
            for fn in files:
                full = os.path.normpath(os.path.join(current_root, fn))
                key = os.path.normcase(full)
                if key in seen:
                    continue
                seen.add(key)
                out.append(full)
    return out


def find_support_source_file(job_name: str, kind: str) -> str:
    """定位用户上传的某类 SACS 辅助文件。kind: runx / psiinp / jcninp。"""
    kind = str(kind or "").strip().lower()
    if kind not in _SUPPORT_FILE_SPECS:
        return ""

    scored: list[tuple[int, float, str]] = []

    for path, row in _query_support_candidates_from_db(job_name):
        if not _file_name_matches(kind, path):
            continue
        logical = str(row.get("logical_path") or "").replace("\\", "/")
        logical_low = logical.lower()
        score = 100
        name = _norm_file_name(os.path.basename(path))
        expected = [_norm_file_name(x) for x in _SUPPORT_FILE_SPECS[kind].get("names") or []]
        if name in expected:
            score += 700
        if "当前模型" in logical:
            score += 220
        if "其他" in logical:
            score += 180
        if "用户上传" in logical:
            score += 80
        if str(job_name or "").strip().lower() in path.lower():
            score += 60
        if kind == "runx" and name == "psifactor.runx":
            score += 120
        scored.append((score, _row_time(row) or _mtime(path), path))

    # 文件系统兜底：优先“其他/用户上传/其他”目录里的最新文件
    for path in _query_support_candidates_from_disk(job_name):
        if not _file_name_matches(kind, path):
            continue
        path_low = path.lower()
        name = _norm_file_name(os.path.basename(path))
        score = 50
        if "当前模型" in path:
            score += 180
        if "其他" in path:
            score += 160
        if "用户上传" in path:
            score += 80
        if kind == "runx" and name == "psifactor.runx":
            score += 120
        scored.append((score, _mtime(path), path))

    if not scored:
        return ""

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return os.path.normpath(scored[0][2])


def stage_support_file_for_job(job_name: str, kind: str, *, required: bool = False) -> str:
    """把单个辅助文件复制到 feasibility_assessment_runtime/<平台>。

    若文件库中存在同名辅助文件，则每次点击创建模型/计算分析都会复制到运行目录，
    避免运行目录残留旧版本。
    """
    kind = str(kind or "").strip().lower()
    spec = _SUPPORT_FILE_SPECS.get(kind)
    if not spec:
        return ""

    target = os.path.normpath(spec["target"](job_name))
    source = find_support_source_file(job_name, kind)
    if source:
        return stage_file(source, target)

    if os.path.exists(target):
        return target

    if required:
        raise FileNotFoundError(
            f"未找到{spec['label']}。请先在【模型文件】中上传到："
            f"{job_name}/当前模型/其他/用户上传/其他，或在 db_config.json 中配置默认路径。"
        )
    return ""


def stage_support_files_for_job(job_name: str, *, require_all: bool = False) -> dict[str, str]:
    """复制 RUNX / PSIINP / JCNINP 到运行目录，并返回复制后的路径。"""
    ensure_job_runtime_dir(job_name)
    result: dict[str, str] = {}
    for kind in ("runx", "psiinp", "jcninp"):
        path = stage_support_file_for_job(job_name, kind, required=require_all)
        if path:
            result[kind] = path
    return result

