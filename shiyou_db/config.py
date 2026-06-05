from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PACKAGE_DIR / "db_config.json"


def _external_db_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "shiyou_db"
    return PACKAGE_DIR


DEFAULT_STORAGE_ROOT = _external_db_dir() / "shiyou_file_storage"


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"

    @property
    def sqlalchemy_url(self) -> str:
        password = self.password.replace("@", "%40")
        return (
            f"mysql+pymysql://{self.user}:{password}@{self.host}:{self.port}/"
            f"{self.database}?charset={self.charset}"
        )


@dataclass(frozen=True)
class DatabasePoolSettings:
    pool_size: int = 2
    max_overflow: int = 3
    pool_recycle: int = 1800
    pool_timeout: int = 30
    connect_timeout: int = 10


@dataclass(frozen=True)
class StorageShareSettings:
    auto_connect: bool = False
    unc_path: str = ""
    username: str = ""
    password: str = ""
    force_reconnect: bool = False


@dataclass(frozen=True)
class AppSettings:
    database: DatabaseSettings
    storage_root: str
    pool: DatabasePoolSettings = field(default_factory=DatabasePoolSettings)
    storage_share: StorageShareSettings = field(default_factory=StorageShareSettings)
    echo_sql: bool = False
    enable_3d_preview: bool = True

    # SACS 配置
    sacs_analysis_engine_exe: str = ""
    sacs_default_runx_path: str = ""
    sacs_default_psiinp_path: str = ""
    sacs_default_jcninp_path: str = ""


def resolve_config_path(config_path: str | None = None) -> Path:
    explicit = config_path or os.environ.get("SHIYOU_DB_CONFIG")
    if explicit:
        return Path(explicit).expanduser().resolve()

    candidates = [
        (_external_db_dir() / "db_config.json").resolve(),
        DEFAULT_CONFIG_PATH.resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_settings(config_path: str | None = None) -> AppSettings:
    path = resolve_config_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Database config not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    db = raw["database"]
    pool_raw = raw.get("database_pool") or db.get("pool") or {}

    storage_root_raw = str(raw.get("storage_root") or DEFAULT_STORAGE_ROOT).strip()
    share_raw = raw.get("storage_share") or {}
    share_username = str(share_raw.get("username") or share_raw.get("user") or "").strip()
    share_domain = str(share_raw.get("domain") or "").strip()
    if share_domain and share_username and "\\" not in share_username and "@" not in share_username:
        share_username = f"{share_domain}\\{share_username}"

    return AppSettings(
        database=DatabaseSettings(
            host=db["host"],
            port=int(db.get("port", 3306)),
            user=db["user"],
            password=db.get("password", ""),
            database=db["database"],
            charset=db.get("charset", "utf8mb4"),
        ),
        storage_root=os.path.normpath(storage_root_raw),
        pool=DatabasePoolSettings(
            pool_size=max(1, int(pool_raw.get("pool_size", 2))),
            max_overflow=max(0, int(pool_raw.get("max_overflow", 3))),
            pool_recycle=max(60, int(pool_raw.get("pool_recycle", 1800))),
            pool_timeout=max(1, int(pool_raw.get("pool_timeout", 30))),
            connect_timeout=max(1, int(pool_raw.get("connect_timeout", 10))),
        ),
        storage_share=StorageShareSettings(
            auto_connect=bool(share_raw.get("auto_connect", False)),
            unc_path=os.path.normpath(str(share_raw.get("unc_path") or storage_root_raw or "").strip()),
            username=share_username,
            password=str(share_raw.get("password") or "").strip(),
            force_reconnect=bool(share_raw.get("force_reconnect", False)),
        ),
        echo_sql=bool(raw.get("echo_sql", False)),
        enable_3d_preview=bool(raw.get("enable_3d_preview", True)),
        sacs_analysis_engine_exe=str(raw.get("sacs_analysis_engine_exe", "") or "").strip(),
        sacs_default_runx_path=str(raw.get("sacs_default_runx_path", "") or "").strip(),
        sacs_default_psiinp_path=str(raw.get("sacs_default_psiinp_path", "") or "").strip(),
        sacs_default_jcninp_path=str(raw.get("sacs_default_jcninp_path", "") or "").strip(),
    )


def get_sacs_analysis_engine_exe(config_path: str | None = None) -> str:
    settings = load_settings(config_path)
    return str(settings.sacs_analysis_engine_exe or "").strip()


def get_sacs_default_runx_path(config_path: str | None = None) -> str:
    settings = load_settings(config_path)
    return str(settings.sacs_default_runx_path or "").strip()


def get_storage_root(config_path: str | None = None) -> str:
    settings = load_settings(config_path)
    return str(settings.storage_root or "").strip()


def get_enable_3d_preview(config_path: str | None = None) -> bool:
    settings = load_settings(config_path)
    return bool(settings.enable_3d_preview)


def get_sacs_default_psiinp_path(config_path: str | None = None) -> str:
    settings = load_settings(config_path)
    return str(settings.sacs_default_psiinp_path or "").strip()


def get_sacs_default_jcninp_path(config_path: str | None = None) -> str:
    settings = load_settings(config_path)
    return str(settings.sacs_default_jcninp_path or "").strip()
