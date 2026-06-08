# -*- coding: utf-8 -*-
# pages/history_rebuild_files_page.py

import os
from typing import Dict, List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)

from core.base_page import BasePage
from .file_management_platforms import (
    apply_platform_defaults_to_fields,
    default_platform,
    sync_platform_dropdowns,
)
from .file_management_filter_search_bar import FileManagementFilterSearchBar
from .construction_docs_widget import ConstructionDocsWidget
from .important_history_rebuild_info_page import ImportantHistoryDetailWidget


class HistoryRebuildDocsWidget(ConstructionDocsWidget):
    historyInfoRequested = pyqtSignal(str)

    def _build_folder_tree(self) -> Dict:
        return {
            "历史改造信息": {"type": "folder", "children": {}},
            "改造1": {"type": "file_view"},
            "改造2": {"type": "file_view"},
            "改造n": {"type": "file_view"},
        }

    def _build_demo_file_records(self) -> Dict[str, List[Dict]]:
        return {}

    def _get_upload_root(self) -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_root, "upload", "history_rebuild")

    def _on_folder_clicked(self, folder_name: str):
        if folder_name == "历史改造信息":
            self.historyInfoRequested.emit(folder_name)
            return
        super()._on_folder_clicked(folder_name)


class HistoryRebuildFilesPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("", parent)
        self._build_ui()
        self._hide_base_title_if_any()

    def _hide_base_title_if_any(self):
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

        fields = [
            {"key": "branch", "label": "分公司", "options": ["湛江分公司"], "default": "湛江分公司"},
            {"key": "op_company", "label": "作业公司", "options": ["文昌油田群作业公司"], "default": "文昌油田群作业公司"},
            {"key": "oilfield", "label": "油气田", "options": ["文昌19-1油田"], "default": "文昌19-1油田"},
            {"key": "facility_code", "label": "设施编号", "options": ["WC19-1WHPC"], "default": "WC19-1WHPC"},
            {"key": "facility_name", "label": "设施名称", "options": ["文昌19-1WHPC井口平台"], "default": "文昌19-1WHPC井口平台"},
            {"key": "facility_type", "label": "设施类型", "options": ["平台"], "default": "平台"},
            {"key": "category", "label": "分类", "options": ["井口平台"], "default": "井口平台"},
            {"key": "start_time", "label": "投产时间", "options": ["2013-07-15"], "default": "2013-07-15"},
            {"key": "design_life", "label": "设计年限", "options": ["15"], "default": "15"},
        ]
        platform_defaults = default_platform()
        apply_platform_defaults_to_fields(fields, platform_defaults)
        self.filter_search_bar = FileManagementFilterSearchBar(fields, self)
        self.dropdown_bar = self.filter_search_bar.dropdown_bar
        self.filter_search_bar.searchRequested.connect(self._search_documents)
        self.main_layout.addWidget(self.filter_search_bar, 0)

        card = QFrame(self)
        card.setObjectName("HistoryRebuildCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.detail_widget = ImportantHistoryDetailWidget(card)
        self.detail_widget.set_path_bar_home_visible(False)
        card_layout.addWidget(self.detail_widget)

        self.content_scroll = QScrollArea(self)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_scroll.setWidget(card)
        self.main_layout.addWidget(self.content_scroll, 1)

        self.setStyleSheet(
            """
            QFrame#HistoryRebuildCard {
                background-color: #f3f4f6;
                border: none;
            }
            """
        )
        self.filter_search_bar.valueChanged.connect(self.on_filter_changed)
        self._sync_platform_ui()
        self._set_dropdown_visible(True)

    def on_filter_changed(self, key: str, value: str):
        self._sync_platform_ui(changed_key=key)

    def _search_documents(self, code: str = "", name: str = ""):
        self.detail_widget.search_all_documents(code, name)

    def _sync_platform_ui(self, changed_key: str | None = None):
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        platform_name = platform["facility_name"]
        self.detail_widget.set_facility_code(platform["facility_code"])
        window = self.window()
        if hasattr(window, "set_current_platform_name"):
            window.set_current_platform_name(platform_name)

    def get_current_platform_name(self):
        return self.dropdown_bar.get_value("facility_name")

    def _set_dropdown_visible(self, visible: bool):
        self.filter_search_bar.set_filter_visible(visible)
