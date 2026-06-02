# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy

from core.dropdown_bar import DropdownBar


FILE_FILTER_SEARCH_QSS = """
QFrame#FileFilterSearchRow {
    background-color: transparent;
    border: none;
}
QFrame#FileSearchFrame {
    background-color: #ffffff;
    border: 1px solid #e3e8ef;
    border-radius: 0px;
}
QFrame#FileSearchFrame QLabel {
    color: #4b5563;
    font-size: 11pt;
}
QLineEdit#FileSearchEdit {
    min-height: 28px;
    border: 1px solid #d7dee8;
    border-radius: 0px;
    padding: 0 8px;
    color: #1f2937;
    background-color: #ffffff;
    font-size: 11pt;
}
QLineEdit#FileSearchEdit:focus {
    border-color: #1677c5;
}
QPushButton#FileSearchButton {
    min-width: 72px;
    min-height: 30px;
    border: none;
    border-radius: 0px;
    background-color: #1f67c8;
    color: #ffffff;
    font-size: 11pt;
    font-weight: 600;
}
QPushButton#FileSearchButton:hover {
    background-color: #2b7be0;
}
"""


class FileManagementFilterSearchBar(QFrame):
    valueChanged = pyqtSignal(str, str)
    searchRequested = pyqtSignal(str, str)

    def __init__(self, fields: list[dict], parent=None):
        super().__init__(parent)
        self.setObjectName("FileFilterSearchRow")
        self.setStyleSheet(FILE_FILTER_SEARCH_QSS)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.dropdown_bar = DropdownBar(fields, self)
        self.dropdown_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dropdown_bar.valueChanged.connect(self.valueChanged.emit)
        layout.addWidget(self.dropdown_bar, 2)

        search_frame = QFrame(self)
        search_frame.setObjectName("FileSearchFrame")
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(14, 6, 10, 6)
        search_layout.setSpacing(10)

        search_layout.addWidget(QLabel("文件编码：", search_frame))
        self.code_edit = QLineEdit(search_frame)
        self.code_edit.setObjectName("FileSearchEdit")
        self.code_edit.setPlaceholderText("输入编码关键字")
        search_layout.addWidget(self.code_edit, 1)

        search_layout.addSpacing(16)
        search_layout.addWidget(QLabel("文件名称：", search_frame))
        self.name_edit = QLineEdit(search_frame)
        self.name_edit.setObjectName("FileSearchEdit")
        self.name_edit.setPlaceholderText("输入文件名关键字")
        search_layout.addWidget(self.name_edit, 1)

        self.search_button = QPushButton("搜索", search_frame)
        self.search_button.setObjectName("FileSearchButton")
        self.search_button.clicked.connect(self._emit_search)
        self.code_edit.returnPressed.connect(self._emit_search)
        self.name_edit.returnPressed.connect(self._emit_search)
        search_layout.addWidget(self.search_button)

        layout.addWidget(search_frame, 3)

    def _emit_search(self) -> None:
        self.searchRequested.emit(self.code_edit.text().strip(), self.name_edit.text().strip())

    def clear_search(self) -> None:
        self.code_edit.clear()
        self.name_edit.clear()

    def set_filter_visible(self, visible: bool) -> None:
        self.dropdown_bar.setVisible(visible)
        self.dropdown_bar.setFixedHeight(self.dropdown_bar.sizeHint().height() if visible else 0)
