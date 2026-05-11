from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from core.app_paths import external_path
from services.file_db_adapter import shared_storage_dir
from services.special_strategy_state_db import save_strategy_risk_image


def _safe_name(text: object, *, kind: str = "generic") -> str:
    """生成英文/ASCII安全的路径片段。

    页面和数据库里的 row_name/year_label 仍可保留中文；这里只影响实际文件夹名
    和文件名，避免报告导出、网络共享、非 UTF-8 环境下出现乱码。
    """
    raw = str(text or "").strip()
    if not raw:
        return "default"

    row_map = {
        "XZ 前": "XZ_Front",
        "XZ前": "XZ_Front",
        "XZ 后": "XZ_Back",
        "XZ后": "XZ_Back",
        "YZ 左": "YZ_Left",
        "YZ左": "YZ_Left",
        "YZ 右": "YZ_Right",
        "YZ右": "YZ_Right",
    }
    if raw in row_map:
        return row_map[raw]

    if raw in {"当前", "current", "Current"}:
        return "Current"

    import re as _re

    # 第5年 / +5年 / 5年 -> Year_5；第-5年 -> Year_M5
    m = _re.search(r"([+-]?\d+(?:\.\d+)?)\s*年", raw)
    if m:
        number = m.group(1).replace("+", "")
        number = number.replace("-", "M").replace(".", "p")
        return f"Year_{number}"

    # XY 9 / XY -14 / XY -118.95
    m = _re.match(r"^(XY)\s*([+-]?\d+(?:\.\d+)?)$", raw, flags=_re.IGNORECASE)
    if m:
        return f"{m.group(1).upper()}_{m.group(2)}"

    chars: list[str] = []
    for ch in raw:
        if ch.isascii() and (ch.isalnum() or ch in ("-", "_", ".")):
            chars.append(ch)
        elif ch.isspace() or ch in ("/", "\\", ":", "：", "（", "）", "(", ")", "[", "]"):
            chars.append("_")
        # 其它非 ASCII 字符不进入路径
    value = "".join(chars)
    value = _re.sub(r"_+", "_", value).strip("._")
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
    create_dirs: bool = True,
) -> Path:
    """生成图片保存路径。

    同一 run_id / 页面 / 年份 / 立面会覆盖保存为最新图片，数据库也只保留最新记录。
    create_dirs 参数用于兼容旧代码；新版默认自动创建目录。
    """
    run_folder = f"run_{int(run_id)}" if run_id else "latest"
    root = (
        get_strategy_image_root()
        / _safe_name(facility_code, kind="facility")
        / run_folder
        / _safe_name(page_code, kind="page")
        / _safe_name(image_type, kind="image_type")
    )
    if year_label:
        root = root / _safe_name(year_label, kind="year")
    if create_dirs:
        root.mkdir(parents=True, exist_ok=True)
    return root / f"{_safe_name(row_name, kind='row')}.png"


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
