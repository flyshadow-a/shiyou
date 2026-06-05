# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote_plus

from .config import resolve_config_path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_db_config_path() -> Path:
    """
    数据库/服务端配置文件路径。

    优先级：
    1. 环境变量 SHIYOU_DB_CONFIG
    2. 原有 resolve_config_path()
    """
    env_path = os.environ.get("SHIYOU_DB_CONFIG", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()

    return resolve_config_path()


def load_db_config() -> dict:
    cfg_path = get_db_config_path()
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"未找到数据库配置文件: {cfg_path}\n"
            f"请先按接入文档创建 shiyou_db/db_config.json"
        )

    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)

    if not isinstance(cfg, dict):
        raise ValueError(f"数据库配置文件格式错误: {cfg_path}")

    if "database" not in cfg:
        raise ValueError("db_config.json 缺少 database 节点")

    return cfg


def get_mysql_url() -> str:
    """
    返回 SQLAlchemy 使用的 MySQL URL。

    注意：
    用户名和密码要做 URL 编码，否则密码里有 @ : / # 等特殊字符时会连接失败。
    """
    cfg = load_db_config()
    db = cfg["database"]

    host = str(db.get("host") or "127.0.0.1").strip()
    port = int(db.get("port") or 3306)
    user = str(db.get("user") or "").strip()
    password = str(db.get("password") or "")
    database = str(db.get("database") or "").strip()
    charset = str(db.get("charset") or "utf8mb4").strip()

    if not user:
        raise ValueError("db_config.json 中 database.user 为空")
    if not database:
        raise ValueError("db_config.json 中 database.database 为空")

    return (
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}?charset={charset}"
    )


def get_storage_root() -> str:
    """
    服务端文件存储根目录。

    数据库里建议只存相对路径，例如：
        model_files/WC19-1D/当前模型/结构模型/用户上传/结构模型文件/sacinp.JKnew

    程序读取时再拼接：
        D:/shiyou_file_storage + 相对路径
    """
    cfg = load_db_config()
    root = str(cfg.get("storage_root", "")).strip()
    if not root:
        raise ValueError("db_config.json 中 storage_root 为空")

    path = Path(root).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_storage_root_path() -> Path:
    return Path(get_storage_root()).resolve()


def get_echo_sql() -> bool:
    cfg = load_db_config()
    return bool(cfg.get("echo_sql", False))


def get_sacs_analysis_engine_exe() -> str:
    """
    SACS 分析引擎路径，只应该在服务端使用。

    例如：
        D:/SACS/AnalysisEngine.exe
    """
    cfg = load_db_config()
    exe = str(cfg.get("sacs_analysis_engine_exe", "")).strip()
    if not exe:
        raise ValueError("db_config.json 中 sacs_analysis_engine_exe 为空")

    path = Path(exe).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"SACS AnalysisEngine.exe 不存在: {path}")

    return str(path)


def get_sacs_analysis_engine_path() -> Path:
    return Path(get_sacs_analysis_engine_exe()).resolve()