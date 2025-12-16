# -*- coding: utf-8 -*-
# pages/platform_basic_info_page.py

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)

from base_page import BasePage
from dropdown_bar import DropdownBar  # 你之前单独写好的下拉条类


class PlatformBasicInfoPage(BasePage):
    """
    平台基本信息页面：
    - 顶部：分公司 / 作业公司 / 油气田 / 设施编号 / 名称等下拉条；
    - 中部：左侧 3 个信息表格（飞溅区腐蚀余量 / 桩基信息 / 海生物信息），右侧黑色结构示意图；
    - 左右比例：7 : 3；
    - 表格列宽、行高根据文字自动适配 + padding。
    """

    def __init__(self, parent=None):
        super().__init__("平台基本信息", parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # 通用工具：表格初始化 / 居中单元格 / 列宽与行高自适应
    # ------------------------------------------------------------------
    def _init_table_common(self, table: QTableWidget, show_vertical_header: bool):
        """通用表格基础样式。"""
        table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)

        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                border-bottom: 1px solid #d0d0d0;
                border-right:  1px solid #d0d0d0;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                border: 0px;
                border-bottom: 1px solid #d0d0d0; /* 表头和内容之间也有一条线 */
                border-right:  1px solid #d0d0d0;
                padding: 4px 6px;
            }
        """)

        # 表头样式
        hh = table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setHighlightSections(False)

        table.verticalHeader().setVisible(show_vertical_header)

    def _set_center_item(self, table: QTableWidget, row: int, col: int, text):
        """在 (row, col) 放一个居中的单元格。"""
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)

    def _auto_fit_columns_with_padding(self, table: QTableWidget, padding: int = 16):
        """
        让表格列宽适配【表头文字】宽度，并在此基础上加上一点 padding 像素。
        适用于有表头文字的表（飞溅区 / 桩基）。
        """
        header = table.horizontalHeader()
        # 先让 Qt 根据内容算一个合适的宽度
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        table.resizeColumnsToContents()

        fm = QFontMetrics(table.font())
        for col in range(table.columnCount()):
            head_item = table.horizontalHeaderItem(col)
            if head_item is None:
                continue
            text = head_item.text()
            text_width = fm.horizontalAdvance(text)
            base_width = max(table.columnWidth(col), text_width + padding)
            table.setColumnWidth(col, base_width)

        header.setSectionResizeMode(QHeaderView.Fixed)

    def _auto_fit_columns_by_cells(self, table: QTableWidget, padding: int = 16):
        """
        根据单元格内容自动调整列宽（适用于海生物信息这种用单元格作为表头的表格）。
        """
        fm = QFontMetrics(table.font())
        for col in range(table.columnCount()):
            max_width = 0
            for row in range(table.rowCount()):
                item = table.item(row, col)
                if item is None:
                    continue
                w = fm.horizontalAdvance(item.text())
                if w > max_width:
                    max_width = w
            if max_width == 0:
                max_width = 20
            table.setColumnWidth(col, max_width + padding)

    def _auto_fit_row_height(self, table: QTableWidget, padding: int = 6):
        """根据字体高度调整默认行高，额外增加一点 padding。"""
        fm = QFontMetrics(table.font())
        h = fm.height() + padding
        table.verticalHeader().setDefaultSectionSize(h)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # ---------- 顶部下拉条 ----------
        fields = [
            {"key": "branch", "label": "分公司", "options": ["渤江分公司"], "default": "渤江分公司"},
            {"key": "op_company", "label": "作业公司", "options": ["文昌油田群作业公司"], "default": "文昌油田群作业公司"},
            {"key": "oilfield", "label": "油气田", "options": ["文昌19-1油田"], "default": "文昌19-1油田"},
            {"key": "facility_code", "label": "设施编号", "options": ["WC19-1WHPC"], "default": "WC19-1WHPC"},
            {"key": "facility_name", "label": "设施名称", "options": ["文昌19-1WHPC井口平台"], "default": "文昌19-1WHPC井口平台"},
            {"key": "facility_type", "label": "设施类型", "options": ["平台"], "default": "平台"},
            {"key": "category", "label": "分类", "options": ["井口平台"], "default": "井口平台"},
            {"key": "start_time", "label": "投产时间", "options": ["2013-07-15"], "default": "2013-07-15"},
            {"key": "design_life", "label": "设计年限", "options": ["15"], "default": "15"},
        ]
        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        # ---------- 中部左右区域 ----------
        center_frame = QFrame()
        center_layout = QHBoxLayout(center_frame)
        center_layout.setContentsMargins(8, 0, 8, 8)
        center_layout.setSpacing(8)

        # 左侧：表格区域（7）
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)

        self._build_left_tables(left_layout)

        # 右侧：黑色结构示意图（3）
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        preview_label = QLabel()
        preview_label.setObjectName("StructurePreview")
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setMinimumSize(260, 260)  # 大小可根据需要调整
        preview_label.setStyleSheet(
            """
            QLabel#StructurePreview {
                background-color: #000000;
                border-radius: 4px;
            }
            """
        )
        preview_text = QLabel("结构示意图\n(暂用黑色占位)")
        preview_text.setAlignment(Qt.AlignCenter)
        preview_text.setStyleSheet("color: #ffffff; font-size: 12px;")
        # 用布局叠一下文字
        overlay = QVBoxLayout(preview_label)
        overlay.addStretch()
        overlay.addWidget(preview_text, 0, Qt.AlignCenter)
        overlay.addStretch()

        right_layout.addWidget(preview_label, 1)
        right_layout.addStretch()

        center_layout.addWidget(left_frame, 7)
        center_layout.addWidget(right_frame, 3)

        self.main_layout.addWidget(center_frame, 1)

    # ------------------------------------------------------------------
    # 左侧三个表格区域
    # ------------------------------------------------------------------
    def _build_left_tables(self, left_layout: QVBoxLayout):
        # -------- 飞溅区腐蚀余量 --------
        splash_box = QGroupBox("飞溅区腐蚀余量")
        splash_layout = QVBoxLayout(splash_box)
        splash_layout.setContentsMargins(8, 6, 8, 8)
        splash_layout.setSpacing(4)

        self.tbl_splash = QTableWidget(1, 3, splash_box)
        self.tbl_splash.setHorizontalHeaderLabels(
            ["飞溅区上限 (m)", "飞溅区下限 (m)", "腐蚀余量 (mm/y)"]
        )
        self._init_table_common(self.tbl_splash, show_vertical_header=False)

        # 自动适配列宽 + 行高
        self._auto_fit_columns_with_padding(self.tbl_splash, padding=40)
        self._auto_fit_row_height(self.tbl_splash, padding=20)

        splash_layout.addWidget(self.tbl_splash)
        left_layout.addWidget(splash_box,1)

        # -------- 桩基信息 --------
        pile_box = QGroupBox("桩基信息")
        pile_layout = QVBoxLayout(pile_box)
        pile_layout.setContentsMargins(8, 6, 8, 8)
        pile_layout.setSpacing(4)

        self.tbl_pile = QTableWidget(1, 4, pile_box)
        self.tbl_pile.setHorizontalHeaderLabels(
            [
                "基础型式",
                "桩基最大承载能力 (t)",
                "桩基横向承载能力 (t)",
                "单根桩泥下自重 (t)",
            ]
        )
        self._init_table_common(self.tbl_pile, show_vertical_header=False)

        self._auto_fit_columns_with_padding(self.tbl_pile, padding=40)
        self._auto_fit_row_height(self.tbl_pile, padding=20)

        pile_layout.addWidget(self.tbl_pile)
        left_layout.addWidget(pile_box,1)

        # -------- 海生物信息（合并单元格布局） --------
        marine_box = QGroupBox("海生物信息")
        marine_layout = QVBoxLayout(marine_box)
        marine_layout.setContentsMargins(8, 6, 8, 8)
        marine_layout.setSpacing(4)

        # 5 行 × 12 列：
        #   左侧 3 列为“层数 / 高度区域 / 海生物 / 海生物密度”等标签区域
        #   右侧 9 列为层数 1~9
        self.tbl_marine = QTableWidget(5, 12, marine_box)
        self._init_table_common(self.tbl_marine, show_vertical_header=False)

        # 海生物信息表不用表头，全部用单元格自己画
        self.tbl_marine.horizontalHeader().setVisible(False)
        self.tbl_marine.verticalHeader().setVisible(False)

        # ==== 合并单元格 & 表头布局 ====
        # 行 0：层数 + 1~9
        self.tbl_marine.setSpan(0, 0, 1, 3)  # “层数”占 0 行 0~2 列
        self._set_center_item(self.tbl_marine, 0, 0, "层数")
        for i in range(9):
            self._set_center_item(self.tbl_marine, 0, 3 + i, str(i + 1))

        # 行 1~2：高度区域 + 上限/下限
        self.tbl_marine.setSpan(1, 0, 2, 2)  # “高度区域”占两行两列
        self._set_center_item(self.tbl_marine, 1, 0, "高度区域")

        self._set_center_item(self.tbl_marine, 1, 2, "上限 (m)")
        self._set_center_item(self.tbl_marine, 2, 2, "下限 (m)")

        # 行 3：海生物 + 厚度(cm)
        self.tbl_marine.setSpan(3, 0, 1, 2)
        self._set_center_item(self.tbl_marine, 3, 0, "海生物")
        self._set_center_item(self.tbl_marine, 3, 2, "厚度 (cm)")

        # 行 4：海生物密度(t/m³)，占宽三格
        self.tbl_marine.setSpan(4, 0, 1, 3)
        self._set_center_item(self.tbl_marine, 4, 0, "海生物密度(t/m³)")

        # ==== 示例数据（可随时删掉 / 替换真实数据） ====
        upper_vals = [0, -15, -30, -50, -60, -70, -80, -95, -110]
        lower_vals = [-15, -30, -50, -60, -70, -80, -95, -110, -122]
        thick_vals = [10, 10, 10, 4.5, 4.5, 4.5, 4, 4, 4]

        # 上限：行 1，从列 3 开始
        for c, v in enumerate(upper_vals, start=3):
            self._set_center_item(self.tbl_marine, 1, c, v)

        # 下限：行 2，从列 3 开始
        for c, v in enumerate(lower_vals, start=3):
            self._set_center_item(self.tbl_marine, 2, c, v)

        # 厚度：行 3，从列 3 开始
        for c, v in enumerate(thick_vals, start=3):
            self._set_center_item(self.tbl_marine, 3, c, v)

        # 海生物密度：行 4，列 3（其余留空）
        self.tbl_marine.setSpan(4, 3, 1, 9)
        self._set_center_item(self.tbl_marine, 4, 3, "1.4")

        # 根据单元格内容自动调列宽 + 行高
        self._auto_fit_columns_by_cells(self.tbl_marine, padding=20)
        self._auto_fit_row_height(self.tbl_marine, padding=20)

        marine_layout.addWidget(self.tbl_marine)
        left_layout.addWidget(marine_box,2)
        left_layout.addStretch()
