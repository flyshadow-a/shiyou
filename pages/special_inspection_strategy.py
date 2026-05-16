# -*- coding: utf-8 -*-
# pages/special_inspection_strategy.py
"""
特检策略主页面入口。

按最新需求：
- 取消原“特检策略”汇总主页；
- 左侧导航“特检策略”直接打开原“新增特检策略”页面；
- 保持原页面类名 SpecialInspectionStrategy 不变，避免其它导航/导入代码改动。
"""

from __future__ import annotations

from typing import Any

from pages.file_management_platforms import default_platform, find_platform
from pages.new_special_inspection_page import NewSpecialInspectionPage


class SpecialInspectionStrategy(NewSpecialInspectionPage):
    """导航入口包装类。

    仍然保留旧页面类名 ``SpecialInspectionStrategy``，
    但实际内容直接复用 ``NewSpecialInspectionPage``。
    """

    def __init__(self, main_window=None, parent=None):
        if parent is None:
            parent = main_window
        facility_code = self._resolve_initial_facility_code(main_window, parent)
        super().__init__(facility_code=facility_code, parent=parent)
        self.main_window = main_window

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return "" if value is None else str(value).strip()

    @classmethod
    def _resolve_initial_facility_code(cls, main_window=None, parent=None) -> str:
        """尽量从主窗口上下文中解析当前平台编码，解析不到时回退到默认平台。"""
        candidates: list[Any] = [main_window, parent]

        for obj in candidates:
            if obj is None:
                continue

            for attr in ("current_facility_code", "facility_code"):
                code = cls._normalize_text(getattr(obj, attr, ""))
                if code:
                    return find_platform(facility_code=code)["facility_code"]

            info = getattr(obj, "current_platform_info", None)
            if isinstance(info, dict):
                code = cls._normalize_text(info.get("facility_code"))
                if code:
                    return find_platform(facility_code=code)["facility_code"]

            name = cls._normalize_text(getattr(obj, "current_platform_name", ""))
            if name:
                return find_platform(facility_name=name)["facility_code"]

        return default_platform()["facility_code"]
