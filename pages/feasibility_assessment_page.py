# -*- coding: utf-8 -*-
# pages/feasibility_assessment_page.py
#
# 结构强度 -> WC19-1DPPA平台强度/改造可行性评估
#
# 本版改动：
# - 三张表格采用“表内多行表头 + 合并单元格（setSpan）”来匹配原型图样式
# - “高程及连接形式”列使用 QComboBox，并保证宽度可显示完整文本
# - 每张表格右上角保留“保存”按钮（在表格外的 header 区域）

import os
import shutil
import subprocess
from typing import Optional

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QFontMetrics, QColor, QBrush
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QWidget,
    QPushButton,
    QScrollArea,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QDialog,
    QTextEdit,
    QHeaderView,
)
from PyQt5.QtGui import QDesktopServices

from base_page import BasePage
from dropdown_bar import DropdownBar


class FeasibilityAssessmentPage(BasePage):
    """
    WC19-1DPPA平台强度/改造可行性评估（feasibility_assessment_page）
    """

    CONNECT_OPTIONS = ["焊接", "无连接", "导向连接"]
    ELEVATIONS = [27, 23, 18, 7, -12, -34, -58]

    # 表头颜色
    HEADER_BG = QColor("#cfe4b5")   # 浅绿
    SUBHDR_BG = QColor("#cfe4b5")   # 同色（原型里基本一致）
    DATA_BG   = QColor("#ffffff")   # 白

    def __init__(self, main_window, parent=None):
        if parent is None:
            parent = main_window
        super().__init__("", parent)
        self.main_window = main_window
        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # 顶部 DropdownBar（同平台基本信息）
        fields = [
            {"key": "branch", "label": "分公司", "options": ["湛江分公司"], "default": "湛江分公司"},
            {"key": "op_company", "label": "作业公司", "options": ["文昌油田群作业公司"], "default": "文昌油田群作业公司"},
            {"key": "oilfield", "label": "油气田", "options": ["文昌19-1油田"], "default": "文昌19-1油田"},
            {"key": "facility_code", "label": "设施编号", "options": ["WC19-1DPPA"], "default": "WC19-1DPPA"},
            {"key": "facility_name", "label": "设施名称", "options": ["WC19-1DPPA井口平台"], "default": "WC19-1DPPA井口平台"},
            {"key": "facility_type", "label": "设施类型", "options": ["平台"], "default": "平台"},
            {"key": "category", "label": "分类", "options": ["井口平台"], "default": "井口平台"},
            {"key": "start_time", "label": "投产时间", "options": ["2008-06-26"], "default": "2008-06-26"},
            {"key": "design_life", "label": "设计年限", "options": ["15"], "default": "15"},
        ]
        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        # 页面主体（滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        self.main_layout.addWidget(scroll, 1)

        body = QWidget()
        scroll.setWidget(body)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 0, 8, 8)
        body_layout.setSpacing(10)

        body_layout.addWidget(self._build_table_1(), 0)
        body_layout.addWidget(self._build_table_2(), 0)
        body_layout.addWidget(self._build_table_3(), 0)

        body_layout.addWidget(self._build_bottom_actions(), 0)
        body_layout.addStretch(1)

    # ---------------- 通用表格风格 ----------------
    def _init_table_common(self, table: QTableWidget):
        table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)

        table.setStyleSheet("""
                    QTableWidget { background-color: #ffffff; gridline-color: #d0d0d0; }
                    QTableWidget::item { border: 1px solid #e6e6e6; padding: 2px; }
                    QTableWidget::item:selected { background-color: #dbe9ff; color: #000000; }
                    QTableWidget::item:focus { outline: none; }
                    QHeaderView::section {
                        background-color: #f3f6fb;
                        border: 1px solid #e6e6e6;
                        padding: 4px;
                        font-weight: bold;
                    }
                """)

        # 隐藏默认 header，用“表内表头”实现合并单元格
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)

        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        table.verticalHeader().setDefaultSectionSize(26)

    def _set_cell(self, table: QTableWidget, r: int, c: int, text: str, *,
                  bg: Optional[QColor] = None, bold: bool = False, editable: bool = True, center: bool = True):
        it = QTableWidgetItem(str(text))
        if center:
            it.setTextAlignment(Qt.AlignCenter)
        if bg is not None:
            it.setBackground(QBrush(bg))
        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)
        if not editable:
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        table.setItem(r, c, it)
        return it

    def _set_combo_cell(self, table: QTableWidget, row: int, col: int, default: str = "无连接"):
        combo = QComboBox()
        combo.addItems(self.CONNECT_OPTIONS)
        if default in self.CONNECT_OPTIONS:
            combo.setCurrentText(default)
        combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        combo.setMinimumContentsLength(6)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.setStyleSheet("""
            QComboBox { background: #ffffff; border: 1px solid #c8d3e1; padding: 1px 6px; }
            QComboBox::drop-down { border-left: 1px solid #c8d3e1; width: 16px; }
        """)
        table.setCellWidget(row, col, combo)

    def _auto_fit_columns(self, table: QTableWidget, padding: int = 18):
        """考虑 item + combo 的内容宽度，避免下拉框只显示一个字。"""
        fm = QFontMetrics(table.font())
        for c in range(table.columnCount()):
            max_w = 38
            for r in range(table.rowCount()):
                it = table.item(r, c)
                if it is not None and it.text():
                    max_w = max(max_w, fm.horizontalAdvance(it.text().replace("\n", " ")) + padding)
                w = table.cellWidget(r, c)
                if isinstance(w, QComboBox):
                    txt = w.currentText() or ""
                    max_w = max(max_w, fm.horizontalAdvance(txt) + padding + 24)
            table.setColumnWidth(c, max_w)

    def _make_save_button(self) -> QPushButton:
        btn = QPushButton("保存")
        btn.setFixedSize(90, 28)
        btn.setStyleSheet("""
            QPushButton {
                background: #27a7d8;
                border: 1px solid #2f3a4a;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background: #45b8e2; }
        """)
        return btn

    def _make_group_header(self, title: str, on_save) -> QWidget:
        head = QWidget()
        lay = QHBoxLayout(head)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lab = QLabel(title)
        lab.setStyleSheet("font-weight: bold;")
        lay.addWidget(lab, 0)
        lay.addStretch(1)

        btn = self._make_save_button()
        btn.clicked.connect(on_save)
        lay.addWidget(btn, 0)
        return head

    # ---------------- 表1：新增井槽信息（合并表头） ----------------
    def _build_table_1(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(self._make_group_header("新增井槽信息", self._on_save_table1), 0)

        # 表内表头：2 行
        header_rows = 2
        data_rows = 3

        # 列布局（与原型一致）
        # 编号 | 水平面坐标(X,Y) | 井槽尺寸(OD,WT) | 支撑结构(OD,WT) | 垂向载荷Fz | 高程及连接形式(7列)
        base_cols = 1 + 2 + 2 + 2 + 1
        cols = base_cols + len(self.ELEVATIONS)

        self.tbl1 = QTableWidget(header_rows + data_rows, cols, box)
        self._init_table_common(self.tbl1)

        # --- 第0行：大表头（合并） ---
        c = 0
        self.tbl1.setSpan(0, c, 2, 1)
        self._set_cell(self.tbl1, 0, c, "编号", bg=self.HEADER_BG, bold=True, editable=False); c += 1

        self.tbl1.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl1, 0, c, "水平面坐标", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl1, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl1.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl1, 0, c, "井槽尺寸", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl1, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl1.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl1, 0, c, "支撑结构", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl1, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl1.setSpan(0, c, 1, 1)
        self._set_cell(self.tbl1, 0, c, "垂向载荷", bg=self.HEADER_BG, bold=True, editable=False)
        c += 1

        self.tbl1.setSpan(0, c, 1, len(self.ELEVATIONS))
        self._set_cell(self.tbl1, 0, c, "高程及连接形式", bg=self.HEADER_BG, bold=True, editable=False)
        for k in range(1, len(self.ELEVATIONS)):
            self._set_cell(self.tbl1, 0, c+k, "", bg=self.HEADER_BG, editable=False)

        # --- 第1行：子表头 ---
        c = 1
        self._set_cell(self.tbl1, 1, c, "X(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl1, 1, c, "Y(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl1, 1, c, "OD(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl1, 1, c, "WT(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl1, 1, c, "OD(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl1, 1, c, "WT(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl1, 1, c, "Fz(kN)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        for e in self.ELEVATIONS:
            self._set_cell(self.tbl1, 1, c, str(e), bg=self.SUBHDR_BG, bold=True, editable=False)
            c += 1

        # --- 数据区 ---
        demo = [
            ["1", "1.314", "1.714", "914", "25", "406", "19", "1000"],
            ["2", "1.314", "-0.572", "610", "25", "406", "19", "1000"],
            ["3", "1.314", "-2.858", "610", "25", "406", "19", "1000"],
        ]
        for r in range(data_rows):
            rr = header_rows + r
            # 编号
            self._set_cell(self.tbl1, rr, 0, demo[r][0], bg=QColor("#e9eef5"), editable=True)
            # 基础字段
            for c in range(1, base_cols):
                self._set_cell(self.tbl1, rr, c, demo[r][c], bg=self.DATA_BG, editable=True)

            # 连接形式下拉
            start = base_cols
            for i, e in enumerate(self.ELEVATIONS):
                col = start + i
                default = "焊接" if e in (27, 23, 18) else "无连接"
                self._set_combo_cell(self.tbl1, rr, col, default=default)

        self._auto_fit_columns(self.tbl1, padding=18)
        lay.addWidget(self.tbl1, 1)
        return box

    # ---------------- 表2：立管/电缆信息（合并表头） ----------------
    def _build_table_2(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(self._make_group_header("立管/电缆信息", self._on_save_table2), 0)

        header_rows = 2
        data_rows = 3

        # 编号 | 工作平面坐标(2) | 立管/电缆尺寸(2) | 方向(2) | 倾斜度(1) | 高程及连接形式(7)
        base_cols = 1 + 2 + 2 + 2 + 1
        cols = base_cols + len(self.ELEVATIONS)

        self.tbl2 = QTableWidget(header_rows + data_rows, cols, box)
        self._init_table_common(self.tbl2)

        # 第0行大表头
        c = 0
        self.tbl2.setSpan(0, c, 2, 1)
        self._set_cell(self.tbl2, 0, c, "编号", bg=self.HEADER_BG, bold=True, editable=False); c += 1

        self.tbl2.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl2, 0, c, "工作平面坐标", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl2, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl2.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl2, 0, c, "立管/电缆尺寸", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl2, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl2.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl2, 0, c, "方向", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl2, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl2.setSpan(0, c, 2, 1)
        self._set_cell(self.tbl2, 0, c, "倾斜度", bg=self.HEADER_BG, bold=True, editable=False); c += 1

        self.tbl2.setSpan(0, c, 1, len(self.ELEVATIONS))
        self._set_cell(self.tbl2, 0, c, "高程及连接形式", bg=self.HEADER_BG, bold=True, editable=False)
        for k in range(1, len(self.ELEVATIONS)):
            self._set_cell(self.tbl2, 0, c+k, "", bg=self.HEADER_BG, editable=False)

        # 第1行子表头
        c = 1
        self._set_cell(self.tbl2, 1, c, "X(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl2, 1, c, "Y(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl2, 1, c, "OD(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl2, 1, c, "WT(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl2, 1, c, "X方向", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl2, 1, c, "Y方向", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        # 倾斜度（第1行该列不需要重复写，因为已 rowspan=2，但为了边框一致写空格）
        # 该列索引 = 1+2+2+2 = 7
        # 不设置 item 也行；这里设置一个不可编辑空 cell，背景同表头
        self._set_cell(self.tbl2, 1, 7, "", bg=self.SUBHDR_BG, editable=False)

        c = base_cols
        for e in self.ELEVATIONS:
            self._set_cell(self.tbl2, 1, c, str(e), bg=self.SUBHDR_BG, bold=True, editable=False)
            c += 1

        # 数据区
        demo = [
            ["1", "1.314", "1.714", "914", "25", "406", "19", ""],
            ["2", "1.314", "-0.572", "610", "25", "406", "19", ""],
            ["3", "1.314", "-2.858", "610", "25", "406", "19", ""],
        ]
        for r in range(data_rows):
            rr = header_rows + r
            self._set_cell(self.tbl2, rr, 0, demo[r][0], bg=QColor("#e9eef5"), editable=True)
            for c in range(1, base_cols):
                self._set_cell(self.tbl2, rr, c, demo[r][c], bg=self.DATA_BG, editable=True)
            start = base_cols
            for i, e in enumerate(self.ELEVATIONS):
                col = start + i
                default = "焊接" if e in (27, 23) else "无连接"
                self._set_combo_cell(self.tbl2, rr, col, default=default)

        self._auto_fit_columns(self.tbl2, padding=18)
        lay.addWidget(self.tbl2, 1)
        return box

    # ---------------- 表3：新增组块载荷信息（合并表头） ----------------
    def _build_table_3(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(self._make_group_header("新增组块载荷信息", self._on_save_table3), 0)

        header_rows = 2
        data_rows = 6

        # 编号 | 组块载荷坐标(3) | 重量(1)
        cols = 1 + 3 + 1
        self.tbl3 = QTableWidget(header_rows + data_rows, cols, box)
        self._init_table_common(self.tbl3)

        # 第0行大表头
        self.tbl3.setSpan(0, 0, 2, 1)
        self._set_cell(self.tbl3, 0, 0, "编号", bg=self.HEADER_BG, bold=True, editable=False)

        self.tbl3.setSpan(0, 1, 1, 3)
        self._set_cell(self.tbl3, 0, 1, "组块载荷坐标", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl3, 0, 2, "", bg=self.HEADER_BG, editable=False)
        self._set_cell(self.tbl3, 0, 3, "", bg=self.HEADER_BG, editable=False)

        self.tbl3.setSpan(0, 4, 2, 1)
        self._set_cell(self.tbl3, 0, 4, "重量", bg=self.HEADER_BG, bold=True, editable=False)

        # 第1行子表头
        self._set_cell(self.tbl3, 1, 1, "X(m)", bg=self.SUBHDR_BG, bold=True, editable=False)
        self._set_cell(self.tbl3, 1, 2, "Y(m)", bg=self.SUBHDR_BG, bold=True, editable=False)
        self._set_cell(self.tbl3, 1, 3, "Z(m)", bg=self.SUBHDR_BG, bold=True, editable=False)
        self._set_cell(self.tbl3, 1, 4, "t", bg=self.SUBHDR_BG, bold=True, editable=False)

        demo = [
            ["1", "1.314", "1.714", "10", "5"],
            ["2", "1.314", "-0.572", "10", "5"],
            ["3", "1.314", "-2.858", "10", "5"],
            ["4", "-24", "1.714", "10", "5"],
            ["5", "-24", "-0.572", "10", "5"],
            ["6", "-24", "-2.858", "10", "5"],
        ]
        for r in range(data_rows):
            rr = header_rows + r
            self._set_cell(self.tbl3, rr, 0, demo[r][0], bg=QColor("#e9eef5"), editable=True)
            self._set_cell(self.tbl3, rr, 1, demo[r][1], bg=self.DATA_BG, editable=True)
            self._set_cell(self.tbl3, rr, 2, demo[r][2], bg=self.DATA_BG, editable=True)
            self._set_cell(self.tbl3, rr, 3, demo[r][3], bg=self.DATA_BG, editable=True)
            self._set_cell(self.tbl3, rr, 4, demo[r][4], bg=self.DATA_BG, editable=True)

        self._auto_fit_columns(self.tbl3, padding=18)
        lay.addWidget(self.tbl3, 1)
        return box

    # ---------------- 底部按钮 ----------------
    def _build_bottom_actions(self) -> QWidget:
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(14)

        def mk(text: str):
            b = QPushButton(text)
            b.setFixedHeight(42)
            b.setMinimumWidth(160)
            b.setStyleSheet("""
                QPushButton {
                    background: #2aa9df;
                    border: 2px solid #1b2a3a;
                    border-radius: 6px;
                    font-size: 15px;
                    font-weight: bold;
                }
                QPushButton:hover { background: #4bbbe8; }
            """)
            return b

        self.btn_create = mk("创建新模型")
        self.btn_run = mk("计算分析")
        self.btn_view = mk("查看结果")

        self.btn_create.clicked.connect(self._on_create_model)
        self.btn_run.clicked.connect(self._on_run_analysis)
        self.btn_view.clicked.connect(self._on_view_result)

        lay.addStretch(1)
        lay.addWidget(self.btn_create, 0)
        lay.addWidget(self.btn_run, 0)
        lay.addWidget(self.btn_view, 0)
        lay.addStretch(1)
        return wrap

    # ---------------- 保存按钮：导出当前表格数据 ----------------
    def _on_save_table1(self):
        self._save_table_as_csv(self.tbl1, header_rows=2, default_name="新增井槽信息.csv",
                                with_combo_cols=True, combo_start_col=8)

    def _on_save_table2(self):
        self._save_table_as_csv(self.tbl2, header_rows=2, default_name="立管电缆信息.csv",
                                with_combo_cols=True, combo_start_col=8)

    def _on_save_table3(self):
        self._save_table_as_csv(self.tbl3, header_rows=2, default_name="新增组块载荷信息.csv",
                                with_combo_cols=False, combo_start_col=0)

    def _save_table_as_csv(self, table: QTableWidget, header_rows: int, default_name: str,
                           with_combo_cols: bool, combo_start_col: int):
        path, _ = QFileDialog.getSaveFileName(self, "保存表格", default_name, "CSV (*.csv);;All Files (*)")
        if not path:
            return
        try:
            # 直接用第1行子表头作为列名（更接近真实字段）
            headers = []
            for c in range(table.columnCount()):
                it = table.item(1, c)
                headers.append(it.text().replace("\n", " ") if it else "")
            lines = [",".join(headers)]

            for r in range(header_rows, table.rowCount()):
                row_vals = []
                for c in range(table.columnCount()):
                    if with_combo_cols and c >= combo_start_col:
                        w = table.cellWidget(r, c)
                        row_vals.append(w.currentText() if isinstance(w, QComboBox) else "")
                    else:
                        it = table.item(r, c)
                        row_vals.append((it.text() if it else "").replace(",", " "))
                if all(v.strip() == "" for v in row_vals):
                    continue
                lines.append(",".join(row_vals))

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            QMessageBox.information(self, "保存成功", f"已保存：\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存失败：\n{e}")

    # ---------------- 业务按钮：占位实现（后续你定格式后再替换） ----------------
    def _on_create_model(self):
        base_path, _ = QFileDialog.getOpenFileName(self, "选择基准结构计算文件（示例：.inp/.sacs/.dat）", "", "All Files (*)")
        if not base_path:
            return
        out_path, _ = QFileDialog.getSaveFileName(self, "保存新模型文件", "WC19-1DPPA_new_model.txt", "All Files (*)")
        if not out_path:
            return

        try:
            shutil.copyfile(base_path, out_path)
            with open(out_path, "a", encoding="utf-8", errors="ignore") as f:
                f.write("\n\n")
                f.write("** ----------------------------\n")
                f.write("** MODIFICATIONS (Generated by FeasibilityAssessmentPage)\n")
                f.write("** ----------------------------\n\n")
                f.write(self._dump_table_block("新增井槽信息", self.tbl1, header_rows=2, with_combo_cols=True, combo_start_col=8))
                f.write("\n")
                f.write(self._dump_table_block("立管/电缆信息", self.tbl2, header_rows=2, with_combo_cols=True, combo_start_col=8))
                f.write("\n")
                f.write(self._dump_table_block("新增组块载荷信息", self.tbl3, header_rows=2, with_combo_cols=False, combo_start_col=0))
                f.write("\n")

            QMessageBox.information(self, "创建完成", f"已生成新模型文件：\n{out_path}\n\n（当前为占位写入方式，后续可替换为真实 SACS/结构文件写入逻辑）")
        except Exception as e:
            QMessageBox.critical(self, "创建失败", f"创建新模型失败：\n{e}")

    def _dump_table_block(self, title: str, table: QTableWidget, header_rows: int,
                          with_combo_cols: bool, combo_start_col: int) -> str:
        lines = []
        lines.append(f"** [{title}]")
        for r in range(header_rows, table.rowCount()):
            row_vals = []
            for c in range(table.columnCount()):
                if with_combo_cols and c >= combo_start_col:
                    w = table.cellWidget(r, c)
                    row_vals.append(w.currentText() if isinstance(w, QComboBox) else "")
                else:
                    it = table.item(r, c)
                    row_vals.append(it.text() if it else "")
            if all(v.strip() == "" for v in row_vals):
                continue
            lines.append("** " + " | ".join(row_vals))
        return "\n".join(lines) + "\n"

    def _on_run_analysis(self):
        model_path, _ = QFileDialog.getOpenFileName(self, "选择需要分析的模型文件", "", "All Files (*)")
        if not model_path:
            return

        exe = os.environ.get("SACS_ENGINEANALYSIS", "").strip()
        if (not exe) or (not os.path.exists(exe)):
            exe, _ = QFileDialog.getOpenFileName(self, "选择 SACS engineanalysis 可执行文件", "", "All Files (*)")
            if not exe:
                return

        try:
            proc = subprocess.run([exe, model_path], capture_output=True, text=True, timeout=60 * 30)
            ok = (proc.returncode == 0)
            title = "分析完成" if ok else "分析失败"
            detail = (proc.stdout or "")[-3000:] + ("\n" + (proc.stderr or "")[-3000:] if proc.stderr else "")
            if not detail.strip():
                detail = "(无输出)"
            self._show_text_dialog(title, detail)
        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "超时", "engineanalysis 运行超时（30分钟）。")
        except Exception as e:
            QMessageBox.critical(self, "运行失败", f"调用 engineanalysis 失败：\n{e}")

    def _on_view_result(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择分析结果文件（psilst）", "", "All Files (*)")
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            head = content[:8000]
            tail = content[-8000:] if len(content) > 16000 else ""
            show = head + ("\n\n...（中间省略）...\n\n" + tail if tail else "")
            self._show_text_dialog("查看结果（预览）", show, extra_open_path=path)
        except Exception as e:
            QMessageBox.critical(self, "读取失败", f"读取结果文件失败：\n{e}")

    def _show_text_dialog(self, title: str, text: str, extra_open_path: Optional[str] = None):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(900, 600)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        edt = QTextEdit()
        edt.setReadOnly(True)
        edt.setPlainText(text)
        v.addWidget(edt, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        if extra_open_path:
            btn_open = QPushButton("用系统打开")
            btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(extra_open_path)))
            btn_row.addWidget(btn_open)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)

        v.addLayout(btn_row)
        dlg.exec_()
