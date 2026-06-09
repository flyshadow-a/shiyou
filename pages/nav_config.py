# -*- coding: utf-8 -*-
# nav_config.py

"""
左侧导航配置。
- text: 树节点显示文字
- page: 叶子节点对应的页面类，启动时只保存导入路径，点击时再加载
- children: 子节点列表
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


class LazyPage:
    """Delay heavy page imports until the user actually opens the page."""

    def __init__(self, dotted_path: str) -> None:
        module_name, class_name = dotted_path.rsplit(".", 1)
        self.module_name = module_name
        self.class_name = class_name
        self._page_cls: type[Any] | None = None

    @property
    def __name__(self) -> str:
        return self.class_name

    def resolve(self) -> type[Any]:
        if self._page_cls is None:
            module = import_module(self.module_name)
            page_cls = getattr(module, self.class_name)
            self._page_cls = page_cls
        return self._page_cls

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.resolve()(*args, **kwargs)


def lazy_page(dotted_path: str) -> LazyPage:
    return LazyPage(dotted_path)


NAV_CONFIG = [
    {
        "text": "个人中心",
        "page": lazy_page("pages.personal_center_page.PersonalCenterPage"),
    },
    {
        "text": "文件管理",
        "children": [
            {"text": "汇总信息","page": lazy_page("pages.platform_summary_page.PlatformSummaryPage")},
            {"text": "设计文件", "page": lazy_page("pages.construction_docs_page.ConstructionDocsPage")},
            {"text": "历次改造文件", "page": lazy_page("pages.history_rebuild_files_page.HistoryRebuildFilesPage")},
            {"text": "检测记录文件", "page": lazy_page("pages.history_events_inspection_page.HistoryEventsInspectionPage")},
            {"text": "模型文件", "page": lazy_page("pages.model_files_page.ModelFilesPage")},
        ],
    },
    {
        "text": "平台载荷管理",
        "children": [
            {
                "text": "海洋环境",
                "page": lazy_page("pages.oilfield_water_level_page.OilfieldWaterLevelPage"),
            },
            {
                "text": "载荷信息",
                "children": [
                    {"text": "汇总信息", "page": lazy_page("pages.summary_information_table_page.SummaryInformationTablePage")},
                    {"text": "平台载荷信息", "page": lazy_page("pages.platform_load_information_page.PlatformLoadInformationPage")},
                ],
            },
            {"text": "状态监测（结构和腐蚀性检测）", "disabled": True},
            {
                "text": "结构强度/改造可行性评估",
                "page": lazy_page("pages.platform_strength_page.PlatformStrengthPage"),
            },
            {
                "text": "特检策略",
                "page": lazy_page("pages.special_inspection_strategy.SpecialInspectionStrategy"),
            },
        ],
    },
]
