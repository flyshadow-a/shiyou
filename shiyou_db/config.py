from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().with_name("db_config.json")
DEFAULT_STORAGE_ROOT = Path(__file__).resolve().parent / "shiyou_file_storage"


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
class AppSettings:
    database: DatabaseSettings
    storage_root: str
    echo_sql: bool = False

    # SACS 配置
    sacs_analysis_engine_exe: str = ""
    sacs_default_runx_path: str = ""
    sacs_default_psiinp_path: str = ""
    sacs_default_jcninp_path: str = ""


def resolve_config_path(config_path: str | None = None) -> Path:
    explicit = config_path or os.environ.get("SHIYOU_DB_CONFIG")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return DEFAULT_CONFIG_PATH.resolve()


def load_settings(config_path: str | None = None) -> AppSettings:
    path = resolve_config_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Database config not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    db = raw["database"]

    storage_root_raw = str(raw.get("storage_root") or DEFAULT_STORAGE_ROOT).strip()

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
        echo_sql=bool(raw.get("echo_sql", False)),
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


def get_sacs_default_psiinp_path(config_path: str | None = None) -> str:
    settings = load_settings(config_path)
    return str(settings.sacs_default_psiinp_path or "").strip()


def get_sacs_default_jcninp_path(config_path: str | None = None) -> str:
    settings = load_settings(config_path)
    return str(settings.sacs_default_jcninp_path or "").strip()