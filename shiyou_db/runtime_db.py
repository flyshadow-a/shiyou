# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_db_config_path() -> Path:
    return _project_root() / "shiyou_db" / "db_config.json"


def load_db_config() -> dict:
    cfg_path = get_db_config_path()
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"未找到数据库配置文件: {cfg_path}\n"
            f"请先按接入文档创建 shiyou_db/db_config.json"
        )

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if "database" not in cfg:
        raise ValueError("db_config.json 缺少 database 节点")

    return cfg


def get_mysql_url() -> str:
    cfg = load_db_config()
    db = cfg["database"]

    host = db["host"]
    port = int(db["port"])
    user = db["user"]
    password = db["password"]
    database = db["database"]
    charset = db.get("charset", "utf8mb4")

    return (
        f"mysql+pymysql://{user}:{password}"
        f"@{host}:{port}/{database}?charset={charset}"
    )


def get_storage_root() -> str:
    cfg = load_db_config()
    root = cfg.get("storage_root", "").strip()
    if not root:
        raise ValueError("db_config.json 中 storage_root 为空")
    return root


def get_echo_sql() -> bool:
    cfg = load_db_config()
    return bool(cfg.get("echo_sql", False))