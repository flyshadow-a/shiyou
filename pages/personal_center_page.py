# -*- coding: utf-8 -*-
# pages/personal_center_page.py

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
)

from core.base_page import BasePage


class PersonalCenterPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("用户基本信息", parent)
        self._build_ui()

    def _build_ui(self):
        self.main_layout.setContentsMargins(40, 30, 40, 30)
        self.main_layout.setSpacing(20)

        session = getattr(self.parent(), "session", None)
        rows = [
            ("用户名", getattr(session, "username", "")),
            ("姓名", getattr(session, "display_name", "")),
            ("角色", getattr(session, "role_name", "")),
            ("工号", getattr(session, "employee_no", "")),
            ("分公司", getattr(session, "branch_company", "")),
            ("作业公司", getattr(session, "operation_company", "")),
            ("电话", getattr(session, "phone", "")),
            ("邮箱", getattr(session, "email", "")),
        ]

        self.table = QTableWidget(len(rows), 2, self)
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 120)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        self.table.setMaximumWidth(560)
        self.table.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.main_layout.setAlignment(self.table, Qt.AlignLeft | Qt.AlignTop)
        self.table.setWordWrap(False)
        self.table.setShowGrid(True)

        for row, (name, value) in enumerate(rows):
            left = QTableWidgetItem(name)
            left.setFlags(left.flags() & ~Qt.ItemIsEditable)
            right = QTableWidgetItem(str(value or ""))
            right.setFlags(right.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, left)
            self.table.setItem(row, 1, right)

        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 34)

        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        total_h = self.table.frameWidth() * 2 + 2
        for row in range(self.table.rowCount()):
            total_h += self.table.rowHeight(row)
        self.table.setFixedHeight(total_h)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.main_layout.addWidget(self.table)
        self.main_layout.addStretch(1)
