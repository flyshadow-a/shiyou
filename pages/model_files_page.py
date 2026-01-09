# -*- coding: utf-8 -*-
# pages/model_files_page.py

import os
from typing import Dict, List

from PyQt5.QtWidgets import QFrame, QVBoxLayout, QSizePolicy, QLabel

from base_page import BasePage
from dropdown_bar import DropdownBar
from .construction_docs_widget import ConstructionDocsWidget


# ============================================================
# 1) 直接复用 ConstructionDocsWidget（布局/交互/上传/返回全部沿用）
#    只改：文件夹结构 & 初始文件记录 & 上传路径
# ============================================================
class ModelFilesDocsWidget(ConstructionDocsWidget):
    """模型文件专用：直接使用 ConstructionDocsWidget 的布局与行为，只改目录树与存储路径。"""

    def _build_folder_tree(self) -> Dict:
        """
        首页
        ├─ 模型1
        ├─ 模型2
        └─ 模型N

        三个都是叶子目录（file_view），点进去直接显示上传表格。
        """
        return {
            "模型1": {"type": "file_view"},
            "模型2": {"type": "file_view"},
            "模型N": {"type": "file_view"},
        }

    def _build_demo_file_records(self) -> Dict[str, List[Dict]]:
        """默认不放示例数据，空目录。"""
        return {}

    def _get_upload_root(self) -> str:
        """模型文件上传的物理路径（你可按需要改）"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_root, "uploads", "model_files")


# ============================================================
# 2) 页面：DropdownBar + 一个 ModelFilesDocsWidget（不自写 folder 布局）
# ============================================================
class ModelFilesPage(BasePage):
    """文件管理 -> 模型文件 页面（直接使用 ConstructionDocsWidget 的布局）"""

    def __init__(self, parent=None):
        # ✅ 删除“模型文件”标题：不给 BasePage 传标题
        super().__init__("", parent)
        self._build_ui()
        self._hide_base_title_if_any()

    def _hide_base_title_if_any(self):
        """兜底：兼容不同 BasePage 实现，隐藏顶部标题控件"""
        for attr in ("title_label", "lbl_title", "label_title", "page_title_label"):
            w = getattr(self, attr, None)
            if isinstance(w, QLabel):
                w.hide()

        for obj_name in ("PageTitle", "pageTitle", "titleLabel", "lblTitle"):
            w = self.findChild(QLabel, obj_name)
            if w:
                w.hide()

    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # ---------- 顶部下拉条（你按项目实际字段来） ----------
        fields = [
            {"key": "branch",         "label": "分公司",   "options": ["渤江分公司"],             "default": "渤江分公司"},
            {"key": "op_company",     "label": "作业公司", "options": ["文昌油田群作业公司"],     "default": "文昌油田群作业公司"},
            {"key": "oilfield",       "label": "油气田",   "options": ["文昌19-1油田"],          "default": "文昌19-1油田"},
            {"key": "facility_code",  "label": "设施编号", "options": ["WC19-1WHPC"],           "default": "WC19-1WHPC"},
            {"key": "facility_name",  "label": "设施名称", "options": ["文昌19-1WHPC井口平台"],   "default": "文昌19-1WHPC井口平台"},
            {"key": "facility_type",  "label": "设施类型", "options": ["平台"],                  "default": "平台"},
            {"key": "category",       "label": "分类",     "options": ["井口平台"],              "default": "井口平台"},
            {"key": "start_time",     "label": "投产时间", "options": ["2013-07-15"],           "default": "2013-07-15"},
            {"key": "design_life",    "label": "设计年限", "options": ["15"],                   "default": "15"},
        ]
        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        # ---------- 中间容器（可选） ----------
        # 不写任何“文件夹首页布局”，直接塞一个 ConstructionDocsWidget 子类
        card = QFrame(self)
        card.setObjectName("ModelFilesCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.docs_widget = ModelFilesDocsWidget(card)
        card_layout.addWidget(self.docs_widget)

        self.main_layout.addWidget(card, 1)

        # 可选：背景风格（不影响 ConstructionDocsWidget 内部布局）
        self.setStyleSheet("""
            QFrame#ModelFilesCard {
                background-color: #f3f4f6;
                border: none;
            }
        """)

        # 你原来如果要联动过滤，照旧挂这里即可
        self.dropdown_bar.valueChanged.connect(self.on_filter_changed)

    def on_filter_changed(self, key: str, value: str):
        print(f"[ModelFilesPage] 条件变化：{key} -> {value}")
        # 如果 ConstructionDocsWidget 未来支持过滤接口，可在这里调用
        # self.docs_widget.reload_by_filters(self.dropdown_bar.get_all_values())
