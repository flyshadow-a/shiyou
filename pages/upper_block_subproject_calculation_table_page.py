# -*- coding: utf-8 -*-
# upper_block_subproject_calculation_table_page.py (11列版本)

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)

# 兼容你项目里可能存在的 base（如果不存在也不影响运行）
try:
    from base import BasePage  # type: ignore
except Exception:
    BasePage = QWidget  # fallback


@dataclass
class Phase:
    key: str
    label: str


class UpperBlockSubprojectCalculationTablePage(BasePage):
    """
    11列结构（与你确认一致）：
    0 阶段 | 1 日常作业(分项) | 2 系数(操作/极端) | 3-6 操作(重量+XYZ) | 7-10 极端(重量+XYZ)

    系数列输入格式：
    - “×1.0/×0.75” 或 “1.0/0.75” 或 “x1.0/x0.75”
      左边是操作系数，右边是极端系数
    - 只有一个数字：两者同值
    - 空：默认(1.0, 1.0)

    计算逻辑（按示意图）：
    - 阶段总重量 = Σ(分项重量 × 系数)
    - 阶段重心 = Σ(分项重量 × 系数 × 分项重心) / 阶段总重量
    - 当前总重：对所有阶段的总重量/加权重心再汇总
    """

    saved = pyqtSignal(dict)

    HEADER_ROWS = 3

    COL_PHASE = 0
    COL_ITEM = 1
    COL_COEF = 2

    COL_OP_W = 3
    COL_OP_X = 4
    COL_OP_Y = 5
    COL_OP_Z = 6

    COL_EX_W = 7
    COL_EX_X = 8
    COL_EX_Y = 9
    COL_EX_Z = 10

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        # 回填上下文
        self.source_row: Optional[int] = None
        self.source_col: Optional[int] = None
        self.source_row_data: Dict[int, str] = {}

        # 阶段 & 明细配置（保持你原来的中文项）
        self.phases: List[Phase] = [
            Phase("build", "建设阶段\n(详细设计或称重)"),
            Phase("rebuild_1", "改造1"),
            Phase("rebuild_2", "改造1"),  # 你原文件也是两个“改造1”，如需改为“改造2”可直接改这里
        ]

        # (分项名称, 默认操作系数, 默认极端系数)
        self.build_items: List[Tuple[str, str, str]] = [
            ("结构重量", "", ""),
            ("设备管线操作重", "×1.0", "×0.75"),
            ("活荷载", "×1.0", "×0.75"),
        ]
        self.rebuild_items: List[Tuple[str, str, str]] = [
            ("结构", "", ""),
            ("设备管线干重", "×1.0", "×0.75"),
            ("设备管线操作重", "×1.0", "×0.75"),
            ("活荷载", "×1.0", "×0.75"),
        ]

        self._phase_total_row: Dict[str, int] = {}
        self._grand_total_row: Optional[int] = None
        self._updating = False

        self._build_ui()

    # ---------- public ----------

    def set_context(self,source_row: int,source_row_data: Dict[int, str],source_col: int = None
    ):
        self.source_row = source_row
        self.source_col = source_col
        self.source_row_data = source_row_data or {}

        # 主表传入的是“汇总值”。为避免把旧汇总值当作本页计算结果，这里不直接写入“当前总重”行。
        # 如需显示旧值，建议在页面上单独加只读标签展示（此版本先不做）。
        self._recalc_all()

    # ---------- ui ----------

    def _build_ui(self):
        root = QVBoxLayout(self)

        # 顶部按钮区
        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        self.btn_save = QPushButton("保存")

        self.btn_save.clicked.connect(self._on_save)
        btn_bar.addWidget(self.btn_save)
        root.addLayout(btn_bar)

        # 表格
        self.table = QTableWidget(0, 11)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setWordWrap(True)

        root.addWidget(self.table, 1)

        self._fill_skeleton()

        self.table.itemChanged.connect(self._on_item_changed)
        self._recalc_all()

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
        rebuild_phases = [p for p in self.phases if p.key.startswith("rebuild")]
        total_data_rows = (len(self.build_items) + 1) + (len(rebuild_phases) * (len(self.rebuild_items) + 1)) + 1
        total_rows = self.HEADER_ROWS + total_data_rows
        self.table.setRowCount(total_rows)

        bg_header = QColor("#eef2ff")

        # 表头
        self._set_span_item(0, self.COL_PHASE, 3, 1, "阶段", bg=bg_header)
        self._set_span_item(0, self.COL_ITEM,  3, 1, "日常作业", bg=bg_header)
        self._set_span_item(0, self.COL_COEF,  3, 1, "", bg=bg_header)

        self._set_span_item(0, self.COL_OP_W, 1, 4, "操作工况重量重心", bg=bg_header)
        self._set_span_item(0, self.COL_EX_W, 1, 4, "极端工况重量重心", bg=bg_header)

        self._set_span_item(1, self.COL_OP_W, 2, 1, "重量(t)", bg=bg_header)
        self._set_span_item(1, self.COL_OP_X, 1, 3, "重心(m)", bg=bg_header)
        self.table.setItem(2, self.COL_OP_X, self._mk_item("X", bold=True, bg=bg_header))
        self.table.setItem(2, self.COL_OP_Y, self._mk_item("Y", bold=True, bg=bg_header))
        self.table.setItem(2, self.COL_OP_Z, self._mk_item("Z", bold=True, bg=bg_header))

        self._set_span_item(1, self.COL_EX_W, 2, 1, "重量(t)", bg=bg_header)
        self._set_span_item(1, self.COL_EX_X, 1, 3, "重心(m)", bg=bg_header)
        self.table.setItem(2, self.COL_EX_X, self._mk_item("X", bold=True, bg=bg_header))
        self.table.setItem(2, self.COL_EX_Y, self._mk_item("Y", bold=True, bg=bg_header))
        self.table.setItem(2, self.COL_EX_Z, self._mk_item("Z", bold=True, bg=bg_header))

        # 数据区
        r = self.HEADER_ROWS
        for ph in self.phases:
            detail = self.build_items if ph.key.startswith("build") else self.rebuild_items
            block_rows = len(detail) + 1

            self.table.setSpan(r, self.COL_PHASE, block_rows, 1)
            self.table.setItem(r, self.COL_PHASE, self._mk_item(ph.label, bold=True, align=Qt.AlignLeft | Qt.AlignVCenter))

            # 明细行
            for i, (name, op_coef, ex_coef) in enumerate(detail):
                rr = r + i
                self.table.setRowHeight(rr, 32)

                self.table.setItem(rr, self.COL_ITEM, self._mk_item(name, align=Qt.AlignLeft | Qt.AlignVCenter))

                # 系数列（合并显示）
                if op_coef or ex_coef:
                    op_t = op_coef if op_coef else "×1.0"
                    ex_t = ex_coef if ex_coef else "×1.0"
                    coef_text = f"{op_t}/{ex_t}"
                else:
                    coef_text = ""
                self.table.setItem(rr, self.COL_COEF, self._mk_item(coef_text, editable=True))

                # 可编辑输入区
                for c in (self.COL_OP_W, self.COL_OP_X, self.COL_OP_Y, self.COL_OP_Z,
                          self.COL_EX_W, self.COL_EX_X, self.COL_EX_Y, self.COL_EX_Z):
                    self.table.setItem(rr, c, self._mk_item("", editable=True))

            # 阶段总计行
            total_rr = r + len(detail)
            self.table.setRowHeight(total_rr, 34)
            self.table.setItem(total_rr, self.COL_ITEM, self._mk_item("总重量", bold=True, align=Qt.AlignLeft | Qt.AlignVCenter))
            self.table.setItem(total_rr, self.COL_COEF, self._mk_item("求和", bold=True))
            for c in (self.COL_OP_W, self.COL_OP_X, self.COL_OP_Y, self.COL_OP_Z,
                      self.COL_EX_W, self.COL_EX_X, self.COL_EX_Y, self.COL_EX_Z):
                self.table.setItem(total_rr, c, self._mk_item("", editable=False, bold=True))

            self._phase_total_row[ph.key] = total_rr
            r += block_rows

        # 当前总重行
        self._grand_total_row = r
        self.table.setRowHeight(r, 36)
        self.table.setItem(r, self.COL_PHASE, self._mk_item("当前总重", bold=True, align=Qt.AlignLeft | Qt.AlignVCenter))
        self.table.setItem(r, self.COL_ITEM, self._mk_item("总重量", bold=True, align=Qt.AlignLeft | Qt.AlignVCenter))
        self.table.setItem(r, self.COL_COEF, self._mk_item("求和", bold=True))
        for c in (self.COL_OP_W, self.COL_OP_X, self.COL_OP_Y, self.COL_OP_Z,
                  self.COL_EX_W, self.COL_EX_X, self.COL_EX_Y, self.COL_EX_Z):
            self.table.setItem(r, c, self._mk_item("", editable=False, bold=True))

    # ---------- calc ----------
    def _parse_coef_pair(self, text: str):
        t = (text or "").strip()
        if not t:
            return 1.0, 1.0
        t = t.replace("×", "").replace("X", "x")
        # separators: / | 空格 ,
        import re as _re
        parts = _re.split(r"[\/\|\s,]+", t)
        nums = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            p = p.replace("x", "")
            try:
                nums.append(float(p))
            except Exception:
                continue
        if not nums:
            return 1.0, 1.0
        if len(nums) == 1:
            return nums[0], nums[0]
        return nums[0], nums[1]

    def _to_float(self, txt: str) -> float:
        try:
            t = (txt or "").strip().replace("，", ",")
            if not t:
                return 0.0
            return float(t)
        except Exception:
            return 0.0

    def _fmt(self, v: float) -> str:
        if abs(v) < 1e-12:
            return "0"
        return (f"{v:.6f}").rstrip("0").rstrip(".")

    def _set_text(self, row: int, col: int, text: str):
        it = self.table.item(row, col)
        if it is None:
            it = self._mk_item("", editable=False, bold=True)
            self.table.setItem(row, col, it)
        it.setText(text)

    def _set_total_row(self, row: int,
                       op_w_sum: float, op_xw: float, op_yw: float, op_zw: float,
                       ex_w_sum: float, ex_xw: float, ex_yw: float, ex_zw: float):
        # 操作
        self._set_text(row, self.COL_OP_W, self._fmt(op_w_sum))
        if op_w_sum > 1e-12:
            self._set_text(row, self.COL_OP_X, self._fmt(op_xw / op_w_sum))
            self._set_text(row, self.COL_OP_Y, self._fmt(op_yw / op_w_sum))
            self._set_text(row, self.COL_OP_Z, self._fmt(op_zw / op_w_sum))
        else:
            self._set_text(row, self.COL_OP_X, "0")
            self._set_text(row, self.COL_OP_Y, "0")
            self._set_text(row, self.COL_OP_Z, "0")

        # 极端
        self._set_text(row, self.COL_EX_W, self._fmt(ex_w_sum))
        if ex_w_sum > 1e-12:
            self._set_text(row, self.COL_EX_X, self._fmt(ex_xw / ex_w_sum))
            self._set_text(row, self.COL_EX_Y, self._fmt(ex_yw / ex_w_sum))
            self._set_text(row, self.COL_EX_Z, self._fmt(ex_zw / ex_w_sum))
        else:
            self._set_text(row, self.COL_EX_X, "0")
            self._set_text(row, self.COL_EX_Y, "0")
            self._set_text(row, self.COL_EX_Z, "0")

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._updating:
            return
        if item.row() < self.HEADER_ROWS:
            return
        self._recalc_all()

    def _recalc_all(self):
        self._updating = True
        try:
            phase_totals = []
            r = self.HEADER_ROWS
            for ph in self.phases:
                detail = self.build_items if ph.key.startswith("build") else self.rebuild_items
                block_rows = len(detail) + 1
                total_rr = self._phase_total_row.get(ph.key)

                op_w_sum = 0.0
                op_xw = op_yw = op_zw = 0.0
                ex_w_sum = 0.0
                ex_xw = ex_yw = ex_zw = 0.0

                for i in range(len(detail)):
                    rr = r + i
                    coef_it = self.table.item(rr, self.COL_COEF)
                    op_c, ex_c = self._parse_coef_pair(coef_it.text() if coef_it else "")

                    op_w = self._to_float(self.table.item(rr, self.COL_OP_W).text() if self.table.item(rr, self.COL_OP_W) else "")
                    op_x = self._to_float(self.table.item(rr, self.COL_OP_X).text() if self.table.item(rr, self.COL_OP_X) else "")
                    op_y = self._to_float(self.table.item(rr, self.COL_OP_Y).text() if self.table.item(rr, self.COL_OP_Y) else "")
                    op_z = self._to_float(self.table.item(rr, self.COL_OP_Z).text() if self.table.item(rr, self.COL_OP_Z) else "")

                    ex_w = self._to_float(self.table.item(rr, self.COL_EX_W).text() if self.table.item(rr, self.COL_EX_W) else "")
                    ex_x = self._to_float(self.table.item(rr, self.COL_EX_X).text() if self.table.item(rr, self.COL_EX_X) else "")
                    ex_y = self._to_float(self.table.item(rr, self.COL_EX_Y).text() if self.table.item(rr, self.COL_EX_Y) else "")
                    ex_z = self._to_float(self.table.item(rr, self.COL_EX_Z).text() if self.table.item(rr, self.COL_EX_Z) else "")

                    op_eff = op_w * op_c
                    op_w_sum += op_eff
                    op_xw += op_eff * op_x
                    op_yw += op_eff * op_y
                    op_zw += op_eff * op_z

                    ex_eff = ex_w * ex_c
                    ex_w_sum += ex_eff
                    ex_xw += ex_eff * ex_x
                    ex_yw += ex_eff * ex_y
                    ex_zw += ex_eff * ex_z

                if total_rr is not None:
                    self._set_total_row(total_rr, op_w_sum, op_xw, op_yw, op_zw, ex_w_sum, ex_xw, ex_yw, ex_zw)

                phase_totals.append((op_w_sum, op_xw, op_yw, op_zw, ex_w_sum, ex_xw, ex_yw, ex_zw))
                r += block_rows

            # 当前总重（汇总所有阶段）
            if self._grand_total_row is not None and phase_totals:
                op_w_sum = sum(p[0] for p in phase_totals)
                op_xw = sum(p[1] for p in phase_totals)
                op_yw = sum(p[2] for p in phase_totals)
                op_zw = sum(p[3] for p in phase_totals)

                ex_w_sum = sum(p[4] for p in phase_totals)
                ex_xw = sum(p[5] for p in phase_totals)
                ex_yw = sum(p[6] for p in phase_totals)
                ex_zw = sum(p[7] for p in phase_totals)

                self._set_total_row(self._grand_total_row, op_w_sum, op_xw, op_yw, op_zw, ex_w_sum, ex_xw, ex_yw, ex_zw)
        finally:
            self._updating = False

    # ---------- actions ----------
    def _on_save(self):
        if self.source_row is None:
            QMessageBox.information(self, "保存", "未绑定来源单元格，无法回填。")
            return

        r = self._grand_total_row
        if r is None:
            QMessageBox.information(self, "保存", "未找到“当前总重”行，无法回填。")
            return

        op_w = self.table.item(r, self.COL_OP_W).text() if self.table.item(r, self.COL_OP_W) else "0"
        op_x = self.table.item(r, self.COL_OP_X).text() if self.table.item(r, self.COL_OP_X) else "0"
        op_y = self.table.item(r, self.COL_OP_Y).text() if self.table.item(r, self.COL_OP_Y) else "0"
        op_z = self.table.item(r, self.COL_OP_Z).text() if self.table.item(r, self.COL_OP_Z) else "0"

        # 回填到主表：col4=重量, col7=重心
        payload = {
            "source_row": self.source_row,
            "source_col": self.source_col,
            "write_back": {
                4: op_w,
                7: f"{op_x},{op_y},{op_z}",
            }
        }
        self.saved.emit(payload)
        QMessageBox.information(self, "保存", "已保存并回填到平台载荷信息表。")
