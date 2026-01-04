# -*- coding: utf-8 -*-
# pages/personal_center_page.py

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout, QTableWidget, QTableWidgetItem,
    QSizePolicy, QAbstractScrollArea, QHeaderView
)

from base_page import BasePage


class PersonalCenterPage(BasePage):
    """
    个人中心页面：
    - 顶部标题：个人中心
    - 主体：无表头两列表格（左字段名不可编辑，右内容可编辑）
    - 不出现滚动条：一次性完整显示
    """

    def __init__(self, parent=None):
        super().__init__("个人中心", parent)
        self._build_ui()

    def _build_ui(self):
        self.main_layout.setContentsMargins(40, 30, 40, 30)
        self.main_layout.setSpacing(20)

        field_names = ["用户名", "姓名", "工号", "部门", "作业公司", "电话", "邮箱"]

        self.table = QTableWidget(len(field_names), 2, self)
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.AllEditTriggers)

        # 关闭滚动条
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 列宽：左列固定，右列拉伸
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        # ✅ 控制整张表的宽度（避免右侧内容列太长）
        self.table.setMaximumWidth(520)  # 你想更宽就 600/700
        self.table.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # ✅ 左对齐放在页面左侧（否则可能居中/拉伸）
        self.main_layout.setAlignment(self.table, Qt.AlignLeft | Qt.AlignTop)

        self.table.setWordWrap(False)
        self.table.setShowGrid(True)

        for row, name in enumerate(field_names):
            left = QTableWidgetItem(name)
            left.setFlags(left.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, left)
            self.table.setItem(row, 1, QTableWidgetItem(""))

        # 行高
        for r in range(self.table.rowCount()):
            self.table.setRowHeight(r, 34)

        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)

        # 总高度 = 所有行高 + 边框（表头已隐藏，不加表头高度）
        total_h = self.table.frameWidth() * 2 + 2
        for r in range(self.table.rowCount()):
            total_h += self.table.rowHeight(r)

        self.table.setFixedHeight(total_h)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # ✅ 直接加到主布局（不再用 group/group_layout）
        self.main_layout.addWidget(self.table)
        self.main_layout.addStretch(1)
