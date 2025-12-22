# -*- coding: utf-8 -*-
# pages/history_rebuild_files_page.py

import os
from typing import Dict, List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QSizePolicy,
)

from base_page import BasePage
from dropdown_bar import DropdownBar
from .construction_docs_widget import ConstructionDocsWidget


# ============================================================
# 1) 复用 ConstructionDocsWidget，专门给“历史改造文件”用
#    只改：文件夹结构 & 初始文件记录
# ============================================================
class HistoryRebuildDocsWidget(ConstructionDocsWidget):
    """历史改造文件用的文件管理控件：只保留“改造1 / 改造2 / 改造N”三个文件夹。"""

    def _build_folder_tree(self) -> Dict:
        """
        首页
        ├─ 改造1
        ├─ 改造2
        └─ 改造N

        三个都是叶子目录（file_view），进去就显示上传表格。
        """
        return {
            "改造1": {"type": "file_view"},
            "改造2": {"type": "file_view"},
            "改造N": {"type": "file_view"},
        }

    def _build_demo_file_records(self) -> Dict[str, List[Dict]]:
        """
        历史改造文件默认不放示例数据，全是空目录。
        后续上传的文件会按 current_path 写到 self.file_records 里。
        """
        return {}

    # 如果你希望历史改造文件和建设阶段用不同的物理存储位置，
    # 可以把 _get_upload_root 也重写掉，例如：
    #
    def _get_upload_root(self) -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_root, "uploads", "history_rebuild")
    #
    # 不需要区分的话，就直接用父类的实现即可。


# ============================================================
# 2) 页面：顶部下拉条 + 中间整块文件控件
# ============================================================
class HistoryRebuildFilesPage(BasePage):
    """
    文件管理 -> 历史改造文件 页面

    - 顶部：复用 DropdownBar 下拉条（分公司 / 作业公司 / 油气田 / 设施编号 / 名称 ...）
    - 中部：一整块 HistoryRebuildDocsWidget
      根目录显示三个文件夹图标：
          改造1   改造2   改造N
      点进任意一个，可以上传文件、显示表格，行为和建设阶段完工文件一致。
    """

    def __init__(self, parent=None):
        super().__init__("历史改造文件", parent)
        self._build_ui()

    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # ---------- 顶部下拉条（和其他页面保持一致即可） ----------
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

        # ---------- 中部卡片区域，里面塞一个 HistoryRebuildDocsWidget ----------
        card = QFrame(self)
        card.setObjectName("HistoryRebuildCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # 直接复用刚才定义的 HistoryRebuildDocsWidget
        self.docs_widget = HistoryRebuildDocsWidget(card)
        card_layout.addWidget(self.docs_widget)

        self.main_layout.addWidget(card, 1)

        # 可选：简单的背景样式（和你之前卡片风格保持一致）
        self.setStyleSheet("""
            QFrame#HistoryRebuildCard {
                background-color: #f3f4f6;
                border: none;
            }
        """)
