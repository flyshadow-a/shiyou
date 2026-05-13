# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from typing import List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel


class PathLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PathBreadcrumbBar(QFrame):
    pathClicked = pyqtSignal(list)

    def __init__(self, icon_path: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("PathBar")
        self.setFixedHeight(40)
        self._icon_path = icon_path
        self._font_ratio = 0.015
        self._path: List[str] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignVCenter)
        self._layout = layout

        self._icon_label = QLabel(self)
        self._icon_label.setObjectName("PathIcon")
        self._icon_label.setFixedSize(22, 22)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._set_icon(icon_path)
        layout.addWidget(self._icon_label)

        self._crumb_container = QFrame(self)
        self._crumb_layout = QHBoxLayout(self._crumb_container)
        self._crumb_layout.setContentsMargins(0, 0, 0, 0)
        self._crumb_layout.setSpacing(4)
        layout.addWidget(self._crumb_container)
        layout.addStretch()

        self.setStyleSheet(
            """
            QFrame#PathBar {
                background-color: #006bb3;
                color: #ffffff;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QLabel#PathIcon {
                background-color: #004a87;
                border-radius: 3px;
            }
            QLabel#Breadcrumb {
                color: #ffffff;
                background-color: transparent;
            }
            QLabel#Breadcrumb:hover {
                text-decoration: underline;
            }
            QLabel#BreadcrumbCurrent {
                font-weight: bold;
                color: #ffffff;
                background-color: transparent;
            }
            QLabel#BreadcrumbArrow {
                color: #ffffff;
                background-color: transparent;
            }
            """
        )
        self.set_path([])

    def _set_icon(self, icon_path: str) -> None:
        if not icon_path or not os.path.exists(icon_path):
            return
        pix = QPixmap(icon_path)
        if pix.isNull():
            return
        self._icon_label.setPixmap(pix.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_path(self, path: List[str], *, show_home: bool = True) -> None:
        self._path = list(path or [])
        while self._crumb_layout.count():
            item = self._crumb_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        segments = [("首页", [])] if show_home else []
        for index, name in enumerate(self._path):
            segments.append((name, self._path[: index + 1]))

        if not segments:
            segments = [("首页", [])]

        for index, (name, prefix) in enumerate(segments):
            is_last = index == len(segments) - 1
            label = QLabel(name, self) if is_last else PathLabel(name, self)
            label.setObjectName("BreadcrumbCurrent" if is_last else "Breadcrumb")
            if not is_last:
                label.clicked.connect(lambda p=list(prefix): self.pathClicked.emit(p))
            self._crumb_layout.addWidget(label)

            if not is_last:
                arrow = QLabel(">", self)
                arrow.setObjectName("BreadcrumbArrow")
                self._crumb_layout.addWidget(arrow)

        self.update_font_scale()

    def update_font_scale(self) -> None:
        font_size = max(11.0, min(20.0, self.width() * self._font_ratio - 2.0))
        for index in range(self._crumb_layout.count()):
            item = self._crumb_layout.itemAt(index)
            widget = item.widget()
            if widget is None or not isinstance(widget, QLabel):
                continue
            font = widget.font()
            font.setPointSizeF(font_size)
            widget.setFont(font)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_font_scale()
