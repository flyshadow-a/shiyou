# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
from shiyou_db.config import get_storage_root


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def get_runtime_root() -> str:
    root = str(get_storage_root() or "").strip()
    if not root:
        raise ValueError("db_config.json 未配置 storage_root")
    return os.path.normpath(root)


def get_job_root(job_name: str) -> str:
    return os.path.join(get_runtime_root(), "sacs_jobs", str(job_name).strip())


def get_job_source_dir(job_name: str) -> str:
    return os.path.join(get_job_root(job_name), "source")


def get_job_runtime_dir(job_name: str) -> str:
    return os.path.join(get_job_root(job_name), "runtime")


def ensure_job_root(job_name: str) -> str:
    return ensure_dir(get_job_root(job_name))


def ensure_job_source_dir(job_name: str) -> str:
    return ensure_dir(get_job_source_dir(job_name))


def ensure_job_runtime_dir(job_name: str) -> str:
    return ensure_dir(get_job_runtime_dir(job_name))


def get_job_model_file(job_name: str) -> str:
    return os.path.join(get_job_source_dir(job_name), "sacinp.JKnew")


def get_job_sea_file(job_name: str) -> str:
    return os.path.join(get_job_source_dir(job_name), "seainp.JKnew FACTOR")


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