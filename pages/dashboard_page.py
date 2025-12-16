# -*- coding: utf-8 -*-
# pages/dashboard_page.py

from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem
)
from base_page import BasePage


class DashboardPage(BasePage):
    """
    系统首页：
    - 左侧显示一些快捷入口
    - 右侧显示简单的状态信息
    可以根据需要继续扩展。
    """
    def __init__(self, parent=None):
        super().__init__("系统首页", parent)
        self.build_ui()

    def build_ui(self):
        container = QFrame()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 左侧：快捷入口
        shortcut_frame = QFrame()
        shortcut_layout = QVBoxLayout(shortcut_frame)
        shortcut_layout.setContentsMargins(10, 10, 10, 10)
        shortcut_layout.setSpacing(8)

        shortcut_title = QLabel("常用功能")
        shortcut_title.setStyleSheet("font-weight:bold;")

        shortcut_list = QListWidget()
        for text in ["油气田信息维护", "平台基本信息", "载荷信息录入", "文件管理"]:
            item = QListWidgetItem(text)
            shortcut_list.addItem(item)

        btn_refresh = QPushButton("刷新统计数据")

        shortcut_layout.addWidget(shortcut_title)
        shortcut_layout.addWidget(shortcut_list)
        shortcut_layout.addWidget(btn_refresh)

        # 右侧：状态信息
        status_frame = QFrame()
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 10, 10, 10)
        status_layout.setSpacing(8)

        title_status = QLabel("系统状态")
        title_status.setStyleSheet("font-weight:bold;")

        lbl_info1 = QLabel("当前登录用户：工程师1")
        lbl_info2 = QLabel("角色：平台结构工程师")
        lbl_info3 = QLabel("提示：左侧导航栏可进入各业务功能页面。")

        for lbl in (lbl_info1, lbl_info2, lbl_info3):
            lbl.setWordWrap(True)

        status_layout.addWidget(title_status)
        status_layout.addWidget(lbl_info1)
        status_layout.addWidget(lbl_info2)
        status_layout.addWidget(lbl_info3)
        status_layout.addStretch()

        layout.addWidget(shortcut_frame, 1)
        layout.addWidget(status_frame, 2)

        self.main_layout.addWidget(container)
