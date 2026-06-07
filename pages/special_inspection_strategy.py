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

from core.dropdown_bar import DropdownBar
from pages.file_management_platforms import (
    default_platform,
    find_platform,
    platform_codes,
    platform_names,
    sync_platform_dropdowns,
)
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
        self.dropdown_bar = DropdownBar(self._build_top_dropdown_fields(), parent=self)
        self.dropdown_bar.valueChanged.connect(self._on_top_filter_changed)
        self.main_layout.insertWidget(0, self.dropdown_bar, 0)
        self._sync_platform_ui()

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

    def _build_top_dropdown_fields(self) -> list[dict[str, Any]]:
        platform = find_platform(facility_code=self.facility_code)
        return [
            {"key": "branch", "label": "分公司", "options": [platform["branch"]], "default": platform["branch"]},
            {"key": "op_company", "label": "作业公司", "options": [platform["op_company"]], "default": platform["op_company"]},
            {"key": "oilfield", "label": "油气田", "options": [platform["oilfield"]], "default": platform["oilfield"]},
            {
                "key": "facility_code",
                "label": "设施编码",
                "options": platform_codes(),
                "default": platform["facility_code"],
            },
            {
                "key": "facility_name",
                "label": "设施名称",
                "options": platform_names(),
                "default": platform["facility_name"],
            },
            {
                "key": "facility_type",
                "label": "设施类型",
                "options": [platform["facility_type"]],
                "default": platform["facility_type"],
            },
            {"key": "category", "label": "分类", "options": [platform["category"]], "default": platform["category"]},
            {
                "key": "start_time",
                "label": "投产时间",
                "options": [platform["start_time"]],
                "default": platform["start_time"],
            },
            {
                "key": "design_life",
                "label": "设计年限",
                "options": [platform["design_life"]],
                "default": platform["design_life"],
            },
        ]

    def _on_top_filter_changed(self, key: str, value: str) -> None:
        if key in {"branch", "op_company", "oilfield", "facility_code", "facility_name"}:
            self._sync_platform_ui(changed_key=key)

    def _sync_platform_ui(self, changed_key: str | None = None) -> None:
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        if platform["facility_code"] != self.facility_code:
            self.reload_for_facility(platform["facility_code"])
        window = self.window()
        if hasattr(window, "set_current_platform_name"):
            window.set_current_platform_name(platform["facility_name"])

    def get_current_platform_name(self) -> str:
        return self.dropdown_bar.get_value("facility_name")
