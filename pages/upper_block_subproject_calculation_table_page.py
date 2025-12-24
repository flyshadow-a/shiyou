# -*- coding: utf-8 -*-
# pages/upper_block_subproject_calculation_table_page.py

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)

from base_page import BasePage


@dataclass
class PhaseDef:
    key: str
    label: str


class UpperBlockSubprojectCalculationTablePage(BasePage):
    """
    平台载荷信息表 -> xxx平台上部组块分项目计算表

    说明：
    - 兼容 main.py 的 page_cls(self) 调用方式（self 是 MainWindow）:contentReference[oaicite:1]{index=1}

    """

    HEADER_ROWS = 3

    COL_PHASE = 0
    COL_ITEM = 1

    COL_OP_COEF = 2
    COL_OP_W = 3
    COL_OP_X = 4
    COL_OP_Y = 5
    COL_OP_Z = 6

    COL_EX_COEF = 7
    COL_EX_W = 8
    COL_EX_X = 9
    COL_EX_Y = 10
    COL_EX_Z = 11

    def __init__(self, main_window, parent=None):
        # 关键：兼容 page_cls(self) 的调用方式 seen in SpecialInspectionStrategy :contentReference[oaicite:2]{index=2}
        if parent is None:
            parent = main_window

        super().__init__("", parent)
        self.main_window = main_window

        self._updating = False
        self._auto_filled: Set[Tuple[int, int]] = set()

        self.phases: List[PhaseDef] = [
            PhaseDef("build", "建设阶段\n重量（计算项）"),
            PhaseDef("rebuild1", "改造1"),
            PhaseDef("rebuild2", "改造2"),
        ]

        # (名称, 操作系数, 极端系数)
        self.items: List[Tuple[str, str, str]] = [
            ("结构重量", "", ""),
            ("设备管线干重", "", ""),
            ("设备管线操作重", "×1.0", "×0.75"),
            ("活荷载", "×1.0", "×0.75"),
        ]

        self._phase_total_row: Dict[str, int] = {}
        self._grand_total_row: Optional[int] = None

        self._build_ui()
        self._fill_skeleton()
        self._recalc_all()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.setStyleSheet("""
            QWidget { background: #e6eef7; }

            QPushButton#TopSaveBtn {
                background: #f6a24a;
                border: 1px solid #2f3a4a;
                border-radius: 3px;
                padding: 6px 18px;
                font-weight: bold;
            }
            QPushButton#TopSaveBtn:hover { background: #ffb86b; }

            QTableWidget {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
                border: 1px solid #2f3a4a;
            }
            QTableWidget::item {
                border-bottom: 1px solid #d0d0d0;
                border-right:  1px solid #d0d0d0;
            }
            QTableWidget::item:selected { background-color: #dbe9ff; color: #000000; }
            QTableWidget::item:focus { outline: none; }
        """)

        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)

        # 顶部操作条：右侧保存按钮
        top_bar = QWidget()
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(8)

        top_lay.addStretch(1)
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("TopSaveBtn")
        self.btn_save.clicked.connect(self._on_save)
        top_lay.addWidget(self.btn_save)

        self.main_layout.addWidget(top_bar, 0)

        # 主体滚动区
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.main_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.table = QTableWidget(0, 12)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(False)  # 表内做合并表头

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)

        root.addWidget(self.table, 1)

    # ---------------- 表格骨架 ----------------
    def _mk_item(self, text: str, editable: bool = False, bold: bool = False,
                 bg: Optional[QColor] = None,
                 align: Qt.Alignment = Qt.AlignCenter) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setTextAlignment(align)

        flags = it.flags()
        if editable:
            flags |= Qt.ItemIsEditable
        else:
            flags &= ~Qt.ItemIsEditable
        it.setFlags(flags)

        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)

        if bg is not None:
            it.setBackground(bg)
        return it

    def _set_span_item(self, row: int, col: int, rowspan: int, colspan: int,
                       text: str, bold: bool = True, bg: Optional[QColor] = None):
        self.table.setSpan(row, col, rowspan, colspan)
        self.table.setItem(row, col, self._mk_item(text, editable=False, bold=bold, bg=bg))

    def _fill_skeleton(self):
        data_rows_per_phase = len(self.items) + 1
        total_data_rows = len(self.phases) * data_rows_per_phase + 1
        total_rows = self.HEADER_ROWS + total_data_rows
        self.table.setRowCount(total_rows)

        # 表头行高
        self.table.setRowHeight(0, 34)
        self.table.setRowHeight(1, 32)
        self.table.setRowHeight(2, 36)

        bg_header = QColor("#eef2ff")

        # 左侧两列：阶段/分项 纵向合并 3 行
        self._set_span_item(0, self.COL_PHASE, 3, 1, "阶段", bg=bg_header)
        self._set_span_item(0, self.COL_ITEM,  3, 1, "分项", bg=bg_header)

        # 组头：操作 / 极端
        self._set_span_item(0, self.COL_OP_COEF, 1, 5, "操作工况重量重心", bg=bg_header)
        self._set_span_item(0, self.COL_EX_COEF, 1, 5, "极端工况重量重心", bg=bg_header)

        # 二级表头（操作）
        self._set_span_item(1, self.COL_OP_COEF, 2, 1, "日常作业", bg=bg_header)
        self._set_span_item(1, self.COL_OP_W,    2, 1, "重量(t)", bg=bg_header)
        self._set_span_item(1, self.COL_OP_X,    1, 3, "重心(m)", bg=bg_header)
        self.table.setItem(2, self.COL_OP_X, self._mk_item("X", bold=True, bg=bg_header))
        self.table.setItem(2, self.COL_OP_Y, self._mk_item("Y", bold=True, bg=bg_header))
        self.table.setItem(2, self.COL_OP_Z, self._mk_item("Z", bold=True, bg=bg_header))

        # 二级表头（极端）
        self._set_span_item(1, self.COL_EX_COEF, 2, 1, "", bg=bg_header)
        self._set_span_item(1, self.COL_EX_W,    2, 1, "重量(t)", bg=bg_header)
        self._set_span_item(1, self.COL_EX_X,    1, 3, "重心(m)", bg=bg_header)
        self.table.setItem(2, self.COL_EX_X, self._mk_item("X", bold=True, bg=bg_header))
        self.table.setItem(2, self.COL_EX_Y, self._mk_item("Y", bold=True, bg=bg_header))
        self.table.setItem(2, self.COL_EX_Z, self._mk_item("Z", bold=True, bg=bg_header))

        # 填充数据区
        r = self.HEADER_ROWS
        for ph in self.phases:
            block_rows = len(self.items) + 1
            self.table.setSpan(r, self.COL_PHASE, block_rows, 1)
            self.table.setItem(r, self.COL_PHASE, self._mk_item(ph.label, bold=True, align=Qt.AlignLeft | Qt.AlignVCenter))

            for i, (name, op_coef, ex_coef) in enumerate(self.items):
                rr = r + i
                self.table.setRowHeight(rr, 32)

                self.table.setItem(rr, self.COL_ITEM, self._mk_item(name, align=Qt.AlignLeft | Qt.AlignVCenter))
                self.table.setItem(rr, self.COL_OP_COEF, self._mk_item(op_coef))
                self.table.setItem(rr, self.COL_EX_COEF, self._mk_item(ex_coef))

                for c in (self.COL_OP_W, self.COL_OP_X, self.COL_OP_Y, self.COL_OP_Z,
                          self.COL_EX_W, self.COL_EX_X, self.COL_EX_Y, self.COL_EX_Z):
                    self.table.setItem(rr, c, self._mk_item("", editable=True))

            total_rr = r + len(self.items)
            self.table.setRowHeight(total_rr, 34)
            self.table.setItem(total_rr, self.COL_ITEM, self._mk_item("总重量", bold=True, align=Qt.AlignLeft | Qt.AlignVCenter))
            self.table.setItem(total_rr, self.COL_OP_COEF, self._mk_item("求和", bold=True))
            self.table.setItem(total_rr, self.COL_EX_COEF, self._mk_item("求和", bold=True))

            for c in (self.COL_OP_W, self.COL_OP_X, self.COL_OP_Y, self.COL_OP_Z,
                      self.COL_EX_W, self.COL_EX_X, self.COL_EX_Y, self.COL_EX_Z):
                self.table.setItem(total_rr, c, self._mk_item("", editable=False, bold=True))

            self._phase_total_row[ph.key] = total_rr
            r += block_rows

        self._grand_total_row = r
        self.table.setRowHeight(r, 36)
        self.table.setItem(r, self.COL_PHASE, self._mk_item("当前总重", bold=True, align=Qt.AlignLeft | Qt.AlignVCenter))
        self.table.setItem(r, self.COL_ITEM, self._mk_item("总重量", bold=True, align=Qt.AlignLeft | Qt.AlignVCenter))
        self.table.setItem(r, self.COL_OP_COEF, self._mk_item("求和", bold=True))
        self.table.setItem(r, self.COL_EX_COEF, self._mk_item("求和", bold=True))
        for c in (self.COL_OP_W, self.COL_OP_X, self.COL_OP_Y, self.COL_OP_Z,
                  self.COL_EX_W, self.COL_EX_X, self.COL_EX_Y, self.COL_EX_Z):
            self.table.setItem(r, c, self._mk_item("", editable=False, bold=True))

    # ---------------- 计算逻辑（先保留，不影响打开） ----------------
    def _on_item_changed(self, item: QTableWidgetItem):
        if self._updating:
            return
        row = item.row()
        if row < self.HEADER_ROWS:
            return
        self._recalc_all()

    def _recalc_all(self):
        # 先留空也行：不影响打开。
        return

    # ---------------- actions ----------------
    def _on_save(self):
        QMessageBox.information(self, "保存", "已保存（示例占位）。")
