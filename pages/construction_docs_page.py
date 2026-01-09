# -*- coding: utf-8 -*-
# pages/construction_docs_page.py

from PyQt5.QtWidgets import QWidget, QLabel
from base_page import BasePage
from dropdown_bar import DropdownBar
from pages.construction_docs_widget import ConstructionDocsWidget


class ConstructionDocsPage(BasePage):
    """
    建设阶段完工文件 页面：
    - 上方：可复用的条件筛选下拉条（DropdownBar）
    - 下方：建设阶段完工文件内容区域（ConstructionDocsWidget）
    """

    def __init__(self, parent=None):
        # ✅ 1) 传空标题：避免 BasePage 顶部显示“建设阶段完工文件”
        super().__init__("", parent)
        self._build_ui()

        # ✅ 2) 兜底：如果 BasePage 仍然有标题 QLabel，就把它隐藏
        self._hide_base_title_if_any()

    def _hide_base_title_if_any(self):
        """
        兼容不同 BasePage 写法：尽量把顶部标题控件隐藏掉
        （不会影响其它控件）
        """
        # 常见写法：BasePage 里有某个 label 成员
        for attr in ("title_label", "lbl_title", "label_title", "page_title_label"):
            w = getattr(self, attr, None)
            if isinstance(w, QLabel):
                w.hide()

        # 兜底：如果 BasePage 给标题设置了 objectName，也可能通过 findChild 找到
        for obj_name in ("PageTitle", "pageTitle", "titleLabel", "lblTitle"):
            w = self.findChild(QLabel, obj_name)
            if w:
                w.hide()

    def _build_ui(self):
        # 0) 页面整体间距（保持你原来的逻辑即可）
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # 1) 顶部筛选下拉条（可复用组件）
        fields = [
            {"key": "division",      "label": "分公司",   "options": ["渤江分公司"]},
            {"key": "company",       "label": "作业公司", "options": ["文昌油田群作业公司"]},
            {"key": "field",         "label": "油气田",   "options": ["文昌19-1油田"]},
            {"key": "facility_code", "label": "设施编号", "options": ["WC19-1WHPC"]},
            {"key": "facility_name", "label": "设施名称", "options": ["文昌19-1WHPC井口平台"]},
            {"key": "facility_type", "label": "设施类型", "options": ["平台"]},
            {"key": "category",      "label": "分类",     "options": ["井口平台"]},
            {"key": "start_time",    "label": "投产时间", "options": ["2013-07-15"]},
            {"key": "design_years",  "label": "设计年限", "options": ["15"]},
        ]

        self.dropdown_bar = DropdownBar(fields, self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        # ✅ 2) 关键：不要再额外包一层 HomeCard/HomeHeaderBar
        #    直接使用 ConstructionDocsWidget 自己那套“首页 + 文件夹UI”
        self.docs_widget = ConstructionDocsWidget(self)
        self.main_layout.addWidget(self.docs_widget, 1)

        # 3) 监听筛选条件变化（保留）
        self.dropdown_bar.valueChanged.connect(self.on_filter_changed)

    def on_filter_changed(self, key: str, value: str):
        print(f"[ConstructionDocsPage] 条件变化：{key} -> {value}")
        # 后续联动过滤：例如
        # self.docs_widget.reload_by_filters(self.dropdown_bar.get_all_values())
