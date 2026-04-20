# -*- coding: utf-8 -*-
# pages/history_rebuild_files_page.py

import os
from typing import Dict, List

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
)

from core.base_page import BasePage
from core.dropdown_bar import DropdownBar
from .file_management_platforms import default_platform, sync_platform_dropdowns
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
        field_map = {item["key"]: item for item in fields}
        field_map["oilfield"]["options"] = [platform_defaults["oilfield"]]
        field_map["oilfield"]["default"] = platform_defaults["oilfield"]
        field_map["facility_code"]["options"] = ["WC19-1D", "WC9-7"]
        field_map["facility_code"]["default"] = platform_defaults["facility_code"]
        field_map["facility_name"]["options"] = ["WC19-1D平台", "WC9-7平台"]
        field_map["facility_name"]["default"] = platform_defaults["facility_name"]
        field_map["facility_type"]["options"] = [platform_defaults["facility_type"]]
        field_map["facility_type"]["default"] = platform_defaults["facility_type"]
        field_map["category"]["options"] = [platform_defaults["category"]]
        field_map["category"]["default"] = platform_defaults["category"]
        field_map["start_time"]["options"] = [platform_defaults["start_time"]]
        field_map["start_time"]["default"] = platform_defaults["start_time"]
        field_map["design_life"]["options"] = [platform_defaults["design_life"]]
        field_map["design_life"]["default"] = platform_defaults["design_life"]
        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        card = QFrame(self)
        card.setObjectName("HistoryRebuildCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.stack = QStackedWidget(card)
        self.docs_widget = HistoryRebuildDocsWidget(card)
        self.detail_widget = ImportantHistoryDetailWidget(card)
        self.detail_widget.lbl_home.clicked.connect(self._go_home_from_detail)

        self.stack.addWidget(self.docs_widget)
        self.stack.addWidget(self.detail_widget)
        self.stack.setCurrentWidget(self.docs_widget)
        card_layout.addWidget(self.stack)

        self.main_layout.addWidget(card, 1)

        self.setStyleSheet(
            """
            QFrame#HistoryRebuildCard {
                background-color: #f3f4f6;
                border: none;
            }
            """
        )
        self.dropdown_bar.valueChanged.connect(self.on_filter_changed)
        self.docs_widget.navigationStateChanged.connect(self._set_dropdown_visible)
        self.docs_widget.historyInfoRequested.connect(self._open_history_info)
        self._sync_platform_ui()

    def _open_history_info(self, folder_name: str):
        self._set_dropdown_visible(False)
        self.detail_widget.set_facility_code(self.dropdown_bar.get_value("facility_code"))
        self.detail_widget.load_history_event(folder_name)
        self.stack.setCurrentWidget(self.detail_widget)

    def _go_home_from_detail(self):
        self._set_dropdown_visible(True)
        self.stack.setCurrentWidget(self.docs_widget)

    def on_filter_changed(self, key: str, value: str):
        self._sync_platform_ui()

    def _sync_platform_ui(self):
        platform_name = self.dropdown_bar.get_value("facility_name")
        window = self.window()
        if hasattr(window, "set_current_platform_name"):
            window.set_current_platform_name(platform_name)

    def on_filter_changed(self, key: str, value: str):
        self._sync_platform_ui(changed_key=key)

    def _sync_platform_ui(self, changed_key: str | None = None):
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        platform_name = platform["facility_name"]
        self.docs_widget.set_facility_code(platform["facility_code"])
        self.detail_widget.set_facility_code(platform["facility_code"])
        window = self.window()
        if hasattr(window, "set_current_platform_name"):
            window.set_current_platform_name(platform_name)

    def get_current_platform_name(self):
        return self.dropdown_bar.get_value("facility_name")

    def _set_dropdown_visible(self, visible: bool):
        self.dropdown_bar.setVisible(visible)
        self.dropdown_bar.setFixedHeight(self.dropdown_bar.sizeHint().height() if visible else 0)
