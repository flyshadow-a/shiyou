from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from core.app_paths import external_path
from services.file_db_adapter import shared_storage_dir
from services.special_strategy_state_db import save_strategy_risk_image


_EXACT_ENGLISH_NAME_MAP: dict[str, str] = {
    # 常用固定立面
    "XZ 前": "XZ_Front",
    "XZ前": "XZ_Front",
    "XZ 后": "XZ_Back",
    "XZ后": "XZ_Back",
    "YZ 左": "YZ_Left",
    "YZ左": "YZ_Left",
    "YZ 右": "YZ_Right",
    "YZ右": "YZ_Right",

    # 兼容旧代码或动态立面可能出现的写法
    "XY 上": "XY_Top",
    "XY上": "XY_Top",
    "XY 下": "XY_Bottom",
    "XY下": "XY_Bottom",
    "前": "Front",
    "后": "Back",
    "左": "Left",
    "右": "Right",

    # 年份目录
    "当前": "Current",
    "+5年": "Year_5",
    "+10年": "Year_10",
    "+15年": "Year_15",
    "+20年": "Year_20",
    "+25年": "Year_25",
    "第5年": "Year_5",
    "第10年": "Year_10",
    "第15年": "Year_15",
    "第20年": "Year_20",
    "第25年": "Year_25",
}

_REPLACE_TOKEN_MAP: dict[str, str] = {
    "当前": "Current",
    "第": "Year_",
    "年": "",
    "前": "Front",
    "后": "Back",
    "左": "Left",
    "右": "Right",
    "上": "Top",
    "下": "Bottom",
    "立面": "Elevation",
    "轮廓": "Outline",
    "风险": "Risk",
    "模型": "Model",
    "构件": "Member",
    "节点": "Node",
}


def _to_ascii_fallback(value: str) -> str:
    """把未知非 ASCII 字符转成 uXXXX，保证文件名完全不含中文。"""
    parts: list[str] = []
    for ch in value:
        code = ord(ch)
        if code < 128:
            parts.append(ch)
        elif ch.isalnum():
            parts.append(f"u{code:04X}")
        else:
            parts.append("_")
    return "".join(parts)


def _safe_name(text: object) -> str:
    """生成英文安全文件夹/文件名。

    之前这里保留中文，导致导出的立面图路径中包含“当前 / XZ_前”等中文，
    后续在报告导出、服务器同步或非 UTF-8 环境读取时可能出现乱码。

    现在统一规则：
    - 已知立面名：XZ 前 -> XZ_Front，YZ 右 -> YZ_Right；
    - 已知年份：当前 -> Current，+5年 / 第5年 -> Year_5；
    - 其他中文会被替换为英文 token 或 uXXXX，保证最终路径只包含 ASCII。
    """
    raw = str(text or "").strip()
    if not raw:
        return "default"

    if raw in _EXACT_ENGLISH_NAME_MAP:
        return _EXACT_ENGLISH_NAME_MAP[raw]

    value = raw
    # 常见动态写法：XY A / XY 1 / ROW A 等，直接把空白变下划线即可。
    # 但先处理中文 token，避免混入中文。
    for zh, en in sorted(_REPLACE_TOKEN_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        value = value.replace(zh, en)

    value = value.replace("+", "Year_")
    value = value.replace("％", "Percent")
    value = value.replace("%", "Percent")
    value = _to_ascii_fallback(value)

    chars: list[str] = []
    last_is_sep = False
    for ch in value:
        if ch.isalnum() or ch in ("-", "."):
            chars.append(ch)
            last_is_sep = False
        elif ch == "_":
            if not last_is_sep:
                chars.append("_")
                last_is_sep = True
        else:
            if not last_is_sep:
                chars.append("_")
                last_is_sep = True

    safe = "".join(chars).strip("._-")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe or "default"


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
    if create_dirs:
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
