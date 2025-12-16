# -*- coding: utf-8 -*-
# pages/construction_docs_page.py

from PyQt5.QtWidgets import QWidget
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
        super().__init__("建设阶段完工文件", parent)
        self._build_ui()

    def _build_ui(self):
        # 1. 顶部筛选下拉条（可复用组件）
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
        self.main_layout.addWidget(self.dropdown_bar)

        # 2. 下方文件夹 + 上传 + 返回等界面（ConstructionDocsWidget）
        self.docs_widget = ConstructionDocsWidget(self)
        self.main_layout.addWidget(self.docs_widget)

        # 3. 可选：监听筛选条件变化，后面如果要联动 docs_widget 可以在这里写
        self.dropdown_bar.valueChanged.connect(self.on_filter_changed)

    def on_filter_changed(self, key: str, value: str):
        """
        任意下拉条件改变时的回调。
        目前先简单打印，后续你可以在这里调用 self.docs_widget 的方法做过滤。
        """
        print(f"[ConstructionDocsPage] 条件变化：{key} -> {value}")
        # 例如后续可以设计：
        # self.docs_widget.reload_by_filters(self.dropdown_bar.get_all_values())
