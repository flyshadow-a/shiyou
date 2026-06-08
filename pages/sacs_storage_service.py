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
    return os.path.join(get_job_runtime_dir(job_name), "psiM1.runx")


def get_job_psiinp_file(job_name: str) -> str:
    return os.path.join(get_job_runtime_dir(job_name), "psiinp.M1")


def get_job_jcninp_file(job_name: str) -> str:
    return os.path.join(get_job_runtime_dir(job_name), "Jcninp.M1")


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
# 新流程：
# - PSIINP / JCNINP 由用户在【模型文件 / 当前模型 / 静力】体系上传；
# - 复制到 feasibility_assessment_runtime/<平台>/ 后统一改名为 psiinp.M1 / Jcninp.M1；
# - RUNX 不再由用户上传，统一使用服务端固定模板 server/psiM1.runx。

_SUPPORT_FILE_SPECS = {
    "runx": {
        "target": get_job_runx_file,
        "names": ["psiM1.runx", "psim1.runx"],
        "label": "服务端固定 RUNX 模板（psiM1.runx）",
    },
    "psiinp": {
        "target": get_job_psiinp_file,
        "names": ["psiinp.M1", "psiinp.m1", "psiinp.19-1d", "psiinp"],
        "label": "PSIINP 文件（复制后命名为 psiinp.M1）",
    },
    "jcninp": {
        "target": get_job_jcninp_file,
        "names": ["Jcninp.M1", "jcninp.M1", "jcninp.m1", "Jcninp.19-1d", "jcninp.19-1d", "jcninp"],
        "label": "JCNINP 文件（复制后命名为 Jcninp.M1）",
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
        # 新流程：PSI / JCN 与模型、海况一起放在“当前模型 / 静力”体系下。
        f"{code}/当前模型/静力",
        f"{code}/当前模型/静力/用户上传",
        f"{code}/当前模型/静力/桩基",
        f"{code}/当前模型/静力/桩基/用户上传",
        f"{code}/当前模型/静力/建模",
        f"{code}/当前模型/静力/建模/用户上传",
        f"{code}/当前模型/静力/其他",
        f"{code}/当前模型/静力/其他/用户上传",

        # 兼容部分页面把静力输入归入结构模型目录。
        f"{code}/当前模型/结构模型",
        f"{code}/当前模型/结构模型/用户上传",
        f"{code}/当前模型/结构模型/桩基",
        f"{code}/当前模型/结构模型/桩基/用户上传",
        f"{code}/当前模型/结构模型/建模",
        f"{code}/当前模型/结构模型/建模/用户上传",

        # 兼容旧流程。
        f"{code}/当前模型/其他/用户上传/其他",
        f"{code}/当前模型/其他/用户上传",
        f"{code}/当前模型/其他",
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
    """数据库记录异常时，直接扫描共享盘 model_files/<平台>/当前模型。"""
    code = str(job_name or "").strip()
    if not code:
        return []

    roots = []
    storage_root = get_runtime_root()
    roots.extend([
        os.path.join(storage_root, "model_files", code, "当前模型", "静力"),
        os.path.join(storage_root, "model_files", code, "当前模型", "结构模型"),
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
        if "静力" in logical:
            score += 260
        if "桩基" in logical or "建模" in logical:
            score += 120
        if "其他" in logical:
            score += 40
        if "用户上传" in logical:
            score += 80
        if str(job_name or "").strip().lower() in path.lower():
            score += 60
        if kind == "runx" and name == "psim1.runx":
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
        if "静力" in path:
            score += 240
        if "桩基" in path or "建模" in path:
            score += 100
        if "其他" in path:
            score += 40
        if "用户上传" in path:
            score += 80
        if kind == "runx" and name == "psim1.runx":
            score += 120
        scored.append((score, _mtime(path), path))

    if not scored:
        return ""

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return os.path.normpath(scored[0][2])


def get_server_runx_template_candidates() -> list[str]:
    """返回服务端固定 RUNX 模板候选路径。

    新流程不再使用 data/sacs_templates/psiFACTOR.runx。
    请把平台通用模板命名为 psiM1.runx，优先放在服务端目录 server/psiM1.runx。
    为兼容不同部署结构，这里保留几个兜底候选路径。
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pages_dir = os.path.dirname(os.path.abspath(__file__))
    return [
        # 推荐放置位置：服务端目录。
        # 例如：D:/shiyou/server/psiM1.runx
        os.path.join(project_root, "server", "psiM1.runx"),

        # 兼容上一版以及其它部署习惯。
        os.path.join(project_root, "psiM1.runx"),
        os.path.join(project_root, "data", "psiM1.runx"),
        os.path.join(project_root, "data", "sacs_templates", "psiM1.runx"),
        os.path.join(pages_dir, "psiM1.runx"),
    ]


def get_server_runx_template_path() -> str:
    """服务端固定 RUNX 模板路径。

    模板文件应统一引用以下运行目录文件名：
        sacinp.M1
        seainp.M1
        psiinp.M1
        Jcninp.M1
        psilst.M1
    """
    candidates = get_server_runx_template_candidates()
    for path in candidates:
        if os.path.isfile(path):
            return os.path.normpath(path)
    return os.path.normpath(candidates[0])


def stage_server_runx_for_job(job_name: str, *, required: bool = True) -> str:
    """把服务端固定 RUNX 模板复制到当前平台运行目录。"""
    target = os.path.normpath(get_job_runx_file(job_name))
    template = os.path.normpath(get_server_runx_template_path())

    if not os.path.isfile(template):
        if os.path.isfile(target):
            return target
        if required:
            candidates_text = "\n".join(get_server_runx_template_candidates())
            raise FileNotFoundError(
                f"服务端固定 RUNX 模板不存在。请将平台通用 RUNX 命名为 psiM1.runx。\n"
                f"推荐放置路径：{get_server_runx_template_candidates()[0]}\n"
                f"已尝试候选路径：\n{candidates_text}\n"
                "模板内容应引用 sacinp.M1、seainp.M1、psiinp.M1、Jcninp.M1，最终计算结果统一为 psilst.M1。"
            )
        return ""

    return stage_file(template, target)


def stage_support_file_for_job(job_name: str, kind: str, *, required: bool = False) -> str:
    """把单个辅助文件复制到 feasibility_assessment_runtime/<平台>。

    若文件库中存在同名辅助文件，则每次点击创建模型/计算分析都会复制到运行目录，
    避免运行目录残留旧版本。
    """
    kind = str(kind or "").strip().lower()
    spec = _SUPPORT_FILE_SPECS.get(kind)
    if not spec:
        return ""

    if kind == "runx":
        return stage_server_runx_for_job(job_name, required=required)

    target = os.path.normpath(spec["target"](job_name))
    source = find_support_source_file(job_name, kind)
    if source:
        return stage_file(source, target)

    if os.path.exists(target):
        return target

    if required:
        raise FileNotFoundError(
            f"未找到{spec['label']}。请先在【模型文件 / 当前模型 / 静力】中上传。"
            f"平台：{job_name}"
        )
    return ""


def stage_support_files_for_job(job_name: str, *, require_all: bool = False) -> dict[str, str]:
    """复制 RUNX / PSIINP / JCNINP 到运行目录，并返回复制后的路径。

    RUNX 来自服务端固定模板；PSIINP / JCNINP 来自用户在当前模型静力目录上传的文件，
    复制后统一命名为 psiinp.M1 / Jcninp.M1。
    """
    ensure_job_runtime_dir(job_name)
    result: dict[str, str] = {}
    for kind in ("runx", "psiinp", "jcninp"):
        path = stage_support_file_for_job(job_name, kind, required=require_all)
        if path:
            result[kind] = path
    return result

