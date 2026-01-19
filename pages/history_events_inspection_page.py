# -*- coding: utf-8 -*-
# pages/history_events_inspection_page.py

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QStackedWidget,
    QSizePolicy,
)

from base_page import BasePage
from pages.construction_docs_widget import ConstructionDocsWidget
from dropdown_bar import DropdownBar
from pages.important_history_rebuild_info_page import ImportantHistoryEventsPage
from pages.history_inspection_summary_page import HistoryInspectionSummaryPage


class _CombinedHistoryHomeWidget(ConstructionDocsWidget):
    folderSelected = pyqtSignal(str, str)

    def _build_folder_tree(self):
        return {
            "\u5386\u53f2\u6539\u9020\u4fe1\u606f": {"type": "folder", "children": {}},
            "\u7279\u68c0\u5ef6\u5bff": {"type": "folder", "children": {}},
            "\u53f0\u98ce&\u635f\u4f24": {"type": "folder", "children": {}},
            "\u5b8c\u5de5\u68c0\u6d4b": {"type": "folder", "children": {}},
            "\u7b2c\u4e00\u6b21\u68c0\u6d4b": {"type": "folder", "children": {}},
            "\u7b2cN\u6b21\u68c0\u6d4b": {"type": "folder", "children": {}},
            "\u5386\u53f2\u62bd\u68c0\u8bb0\u5f55": {"type": "folder", "children": {}},
        }

    def _build_demo_file_records(self):
        return {}

    def _on_folder_clicked(self, folder_name: str):
        events = {
            "\u5386\u53f2\u6539\u9020\u4fe1\u606f",
            "\u7279\u68c0\u5ef6\u5bff",
            "\u53f0\u98ce&\u635f\u4f24",
        }
        inspection = {
            "\u5b8c\u5de5\u68c0\u6d4b": "complete",
            "\u7b2c\u4e00\u6b21\u68c0\u6d4b": "first",
            "\u7b2cN\u6b21\u68c0\u6d4b": "nth",
            "\u5386\u53f2\u62bd\u68c0\u8bb0\u5f55": "history_sampling",
        }
        if folder_name in events:
            self.folderSelected.emit("events", folder_name)
        elif folder_name in inspection:
            self.folderSelected.emit("inspection", inspection[folder_name])


class _EventsPage(ImportantHistoryEventsPage):
    goHomeRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hide_dropdown_if_any()

    def _hide_dropdown_if_any(self):
        bar = getattr(self, "dropdown_bar", None)
        if bar is not None:
            bar.setVisible(False)
            bar.setFixedHeight(0)

    def _go_home(self):
        self.goHomeRequested.emit()

    def open_folder(self, folder_name: str):
        self._enter_detail(folder_name)


class _InspectionPage(HistoryInspectionSummaryPage):
    goHomeRequested = pyqtSignal()

    def __init__(self, parent=None):
        self._allow_internal_home = True
        super().__init__(parent)
        self._allow_internal_home = False
        self._hide_dropdown_if_any()

    def _hide_dropdown_if_any(self):
        bar = getattr(self, "dropdown_bar", None)
        if bar is not None:
            bar.setVisible(False)
            bar.setFixedHeight(0)

    def _switch_to(self, folder_key: str):
        if folder_key == "home":
            if self._allow_internal_home:
                super()._switch_to(folder_key)
                return
            self.goHomeRequested.emit()
            return
        super()._switch_to(folder_key)

    def open_folder(self, folder_key: str):
        super()._switch_to(folder_key)


class HistoryEventsInspectionPage(BasePage):
    """
    File Management -> History Events and Inspection

    Combines the folder entry points from ImportantHistoryEventsPage and
    HistoryInspectionSummaryPage on the same page. Functionality is unchanged.
    """

    def __init__(self, parent=None):
        # Use empty title to avoid extra header space above child pages.
        super().__init__("", parent)
        self._build_ui()
        self._hide_base_title_if_any()

    def _hide_base_title_if_any(self):
        for attr in ("title_label", "lbl_title", "label_title", "page_title_label"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.hide()
                except Exception:
                    pass

    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        fields = [
            {"key": "branch", "label": "\u5206\u516c\u53f8", "options": ["\u6e2d\u6c5f\u5206\u516c\u53f8"], "default": "\u6e2d\u6c5f\u5206\u516c\u53f8"},
            {"key": "op_company", "label": "\u4f5c\u4e1a\u516c\u53f8", "options": ["\u6587\u660c\u6cb9\u7530\u7fa4\u4f5c\u4e1a\u516c\u53f8"], "default": "\u6587\u660c\u6cb9\u7530\u7fa4\u4f5c\u4e1a\u516c\u53f8"},
            {"key": "oilfield", "label": "\u6cb9\u6c14\u7530", "options": ["\u6587\u660c19-1\u6cb9\u7530"], "default": "\u6587\u660c19-1\u6cb9\u7530"},
            {"key": "facility_code", "label": "\u8bbe\u65bd\u7f16\u53f7", "options": ["WC19-1WHPC"], "default": "WC19-1WHPC"},
            {"key": "facility_name", "label": "\u8bbe\u65bd\u540d\u79f0", "options": ["\u6587\u660c19-1WHPC\u4e95\u53e3\u5e73\u53f0"], "default": "\u6587\u660c19-1WHPC\u4e95\u53e3\u5e73\u53f0"},
            {"key": "facility_type", "label": "\u8bbe\u65bd\u7c7b\u578b", "options": ["\u5e73\u53f0"], "default": "\u5e73\u53f0"},
            {"key": "category", "label": "\u5206\u7c7b", "options": ["\u4e95\u53e3\u5e73\u53f0"], "default": "\u4e95\u53e3\u5e73\u53f0"},
            {"key": "start_time", "label": "\u6295\u4ea7\u65f6\u95f4", "options": ["2013-07-15"], "default": "2013-07-15"},
            {"key": "design_life", "label": "\u8bbe\u8ba1\u5e74\u9650", "options": ["15"], "default": "15"},
        ]
        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        # Content stack.
        self.stack = QStackedWidget(self)
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.home_widget = _CombinedHistoryHomeWidget(self)
        self.page_events = _EventsPage(self)
        self.page_inspection = _InspectionPage(self)

        self.stack.addWidget(self.home_widget)
        self.stack.addWidget(self.page_events)
        self.stack.addWidget(self.page_inspection)
        self.stack.setCurrentWidget(self.home_widget)

        self.main_layout.addWidget(self.stack, 1)

        self.home_widget.folderSelected.connect(self._open_folder)
        self.page_events.goHomeRequested.connect(self._go_home)
        self.page_inspection.goHomeRequested.connect(self._go_home)

    def _open_folder(self, group: str, key: str):
        self._set_dropdown_visible(False)
        if group == "events":
            self.page_events.open_folder(key)
            self.stack.setCurrentWidget(self.page_events)
        elif group == "inspection":
            self.page_inspection.open_folder(key)
            self.stack.setCurrentWidget(self.page_inspection)

    def _go_home(self):
        self._set_dropdown_visible(True)
        self.stack.setCurrentWidget(self.home_widget)

    def _set_dropdown_visible(self, visible: bool):
        if visible:
            self.dropdown_bar.setVisible(True)
            self.dropdown_bar.setFixedHeight(self.dropdown_bar.sizeHint().height())
        else:
            self.dropdown_bar.setVisible(False)
            self.dropdown_bar.setFixedHeight(0)
