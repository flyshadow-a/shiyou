from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from core.app_paths import external_path
from services.file_db_adapter import shared_storage_dir
from services.special_strategy_state_db import save_strategy_risk_image


def _safe_name(text: object) -> str:
    """生成适合做文件夹/文件名的字符串，保留中文、数字、字母。"""
    raw = str(text or "").strip()
    chars: list[str] = []
    for ch in raw:
        if ch.isalnum() or ch in ("-", "_", "."):
            chars.append(ch)
        else:
            chars.append("_")
    value = "".join(chars).strip("._")
    return value or "default"


def get_strategy_image_root() -> Path:
    """图片保存根目录。

    优先保存到服务器共享盘：<storage_root 的上一级>/special_strategy_images。
    如果共享盘配置不可用，则回退到项目外部目录。
    """
    root = shared_storage_dir("special_strategy_images")
    if root:
        path = Path(root)
    else:
        path = Path(external_path("special_strategy_images"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_strategy_image_path(
    *,
    facility_code: str,
    run_id: Optional[int],
    page_code: str,
    year_label: Optional[str],
    row_name: str,
    image_type: str = "elevation_risk",
) -> Path:
    """生成当前图片保存路径。

    同一 run_id / 页面 / 年份 / 立面会覆盖保存为最新图片，数据库也只保留最新记录。
    """
    run_folder = f"run_{int(run_id)}" if run_id else "latest"
    root = (
        get_strategy_image_root()
        / _safe_name(facility_code)
        / run_folder
        / _safe_name(page_code)
        / _safe_name(image_type)
    )
    if year_label:
        root = root / _safe_name(year_label)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{_safe_name(row_name)}.png"


def save_strategy_image_record(
    *,
    facility_code: str,
    run_id: Optional[int],
    page_code: str,
    image_type: str,
    year_label: Optional[str],
    row_name: str,
    image_path: str,
    remark: str = "",
) -> int:
    """保存图片数据库记录。"""
    image_path = os.path.normpath(str(image_path or ""))
    return save_strategy_risk_image(
        facility_code=facility_code,
        run_id=run_id,
        page_code=page_code,
        image_type=image_type,
        year_label=year_label,
        row_name=row_name,
        image_path=image_path,
        image_name=os.path.basename(image_path),
        remark=remark,
    )
