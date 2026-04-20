# -*- coding: utf-8 -*-
# base_page.py

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel


class BasePage(QWidget):
    """
    所有业务页面的基类：
    - 统一边距、间距
    - 可选标题栏
    所有功能页面统一继承这个类，方便统一风格。
    """
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(10)

        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("font-size:16px; font-weight:bold;")
            self.main_layout.addWidget(title_label)
