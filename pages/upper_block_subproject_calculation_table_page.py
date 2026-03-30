# -*- coding: utf-8 -*-
# upper_block_subproject_calculation_table_page.py (11列版本)

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)

# 兼容你项目里可能存在的 base（如果不存在也不影响运行）
try:
    from base_page import BasePage  # type: ignore
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

    计算逻辑：
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

    @staticmethod
    def _songti_small_four_font(bold: bool = False) -> QFont:
        font = QFont("SimSun")
        font.setPointSize(12)
        font.setBold(bold)
        return font

    def __init__(self, main_window=None, parent=None):
        super().__init__("", parent) # BasePage 定义了 self.main_layout
        self.main_window = main_window

        # 回填上下文
        self.source_row: Optional[int] = None
        self.source_col: Optional[int] = None
        self.source_row_data: Dict[int, str] = {}

        # 阶段 & 明细配置（保持你原来的中文项）
        self.phases: List[Phase] = [
            Phase("build", "建设阶段\n(详细设计或称重)"),
            Phase("rebuild_1", "改造1"),
            Phase("rebuild_2", "改造2"),
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
        self._recalc_all()

    def get_table_data(self) -> dict:
        """获取用户填写的明细数据，用于页面关闭后保留状态。"""
        data = {}
        for r in range(self.HEADER_ROWS, self.table.rowCount()):
            if r == self._grand_total_row or r in self._phase_total_row.values():
                continue
            row_data = {}
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                if it and (it.flags() & Qt.ItemIsEditable):
                    row_data[str(c)] = it.text()
            if row_data:
                data[str(r)] = row_data
        return data

    def load_table_data(self, data: dict):
        """恢复此前填写的状态并重算。"""
        if not data: return
        self._updating = True
        try:
            for r_idx, row_dict in data.items():
                r = int(r_idx)
                if r >= self.table.rowCount(): continue
                for c_idx, txt in row_dict.items():
                    c = int(c_idx)
                    if c >= self.table.columnCount(): continue
                    it = self.table.item(r, c)
                    if it: it.setText(str(txt))
        finally:
            self._updating = False
            self._recalc_all()

    # ---------- ui ----------

    def _build_ui(self):
        # 使用 BasePage 提供的布局
        # 顶部按钮区
        btn_bar = QHBoxLayout()
        btn_bar.addStretch(1)
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("TopActionBtn") # 使用与主页相同的 ObjectName 以便将来可能的样式扩展
        self.btn_save.setFont(self._songti_small_four_font(bold=True))
        self.btn_save.setMinimumSize(120, 32)
        
        # 应用与主页一致的样式
        self.btn_save.setStyleSheet("""
            QPushButton#TopActionBtn {
                background: #f6a24a;
                border: 1px solid #2f3a4a;
                border-radius: 3px;
                padding: 6px 16px;
                color: black;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton#TopActionBtn:hover { background: #ffb86b; }
        """)

        self.btn_save.clicked.connect(self._on_save)
        btn_bar.addWidget(self.btn_save)
        self.main_layout.addLayout(btn_bar)

        # 表格
        self.table = QTableWidget(0, 11)
        self.table.setFont(self._songti_small_four_font())
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setVisible(False)
        self.table.setWordWrap(True)

        self.main_layout.addWidget(self.table, 1)

        self._fill_skeleton()

        # ====== 优化：全列等宽拉伸填满窗口 ======
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        # ============================================

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
        it.setFont(self._songti_small_four_font(bold=bold))

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
        self._set_span_item(0, self.COL_COEF,  3, 1, "系数\n(操作/极端)", bg=bg_header)

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

                # 系数列
                op_t = op_coef if op_coef else "×1.0"
                ex_t = ex_coef if ex_coef else "×1.0"
                coef_text = f"{op_t}/{ex_t}" if (op_coef or ex_coef) else ""
                self.table.setItem(rr, self.COL_COEF, self._mk_item(coef_text, editable=True))

                # 输入区
                for c in range(3, 11):
                    self.table.setItem(rr, c, self._mk_item("", editable=True))

            # 阶段总计行
            total_rr = r + len(detail)
            self._phase_total_row[ph.key] = total_rr
            self.table.setItem(total_rr, self.COL_ITEM, self._mk_item("总重量", bold=True, bg=QColor("#fff2cc")))
            self.table.setItem(total_rr, self.COL_COEF, self._mk_item("求和", bg=QColor("#fff2cc")))
            for c in range(3, 11):
                self.table.setItem(total_rr, c, self._mk_item("", editable=False, bg=QColor("#fff2cc")))

            r += block_rows

        # 当前总重行
        self._grand_total_row = r
        self._set_span_item(r, 0, 1, 2, "当前总重", bg=QColor("#d9ead3"))
        self.table.setItem(r, self.COL_COEF, self._mk_item("求和", bg=QColor("#d9ead3")))
        for c in range(3, 11):
            self.table.setItem(r, c, self._mk_item("", editable=False, bg=QColor("#d9ead3")))

    # ---------- calc ----------
    def _parse_coef_pair(self, text: str):
        t = (text or "").strip().replace("×", "").replace("X", "x")
        if not t: return 1.0, 1.0
        import re as _re
        parts = _re.split(r"[\/\|\s,]+", t)
        nums = []
        for p in parts:
            try: nums.append(float(p.replace("x", "")))
            except: continue
        if not nums: return 1.0, 1.0
        return (nums[0], nums[1]) if len(nums) > 1 else (nums[0], nums[0])

    def _to_float(self, txt: str) -> float:
        try: return float((txt or "").strip().replace("，", ","))
        except: return 0.0

    def _fmt(self, v: float) -> str:
        return f"{v:.3f}"

    def _set_total_row(self, row: int, op_w, op_xw, op_yw, op_zw, ex_w, ex_xw, ex_yw, ex_zw):
        def _put(c, val):
            it = self.table.item(row, c)
            if it: it.setText(val)
        _put(self.COL_OP_W, self._fmt(op_w))
        if op_w > 1e-12:
            _put(self.COL_OP_X, self._fmt(op_xw/op_w)); _put(self.COL_OP_Y, self._fmt(op_yw/op_w)); _put(self.COL_OP_Z, self._fmt(op_zw/op_w))
        _put(self.COL_EX_W, self._fmt(ex_w))
        if ex_w > 1e-12:
            _put(self.COL_EX_X, self._fmt(ex_xw/ex_w)); _put(self.COL_EX_Y, self._fmt(ex_yw/ex_w)); _put(self.COL_EX_Z, self._fmt(ex_zw/ex_w))

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._updating or item.row() < self.HEADER_ROWS: return
        self._recalc_all()

    def _recalc_all(self):
        self._updating = True
        try:
            grand_vals = [0.0]*8 # op_w, op_xw...
            r = self.HEADER_ROWS
            for ph in self.phases:
                detail = self.build_items if ph.key.startswith("build") else self.rebuild_items
                total_rr = self._phase_total_row.get(ph.key)
                p_v = [0.0]*8
                for i in range(len(detail)):
                    rr = r + i
                    it_c = self.table.item(rr, self.COL_COEF)
                    op_c, ex_c = self._parse_coef_pair(it_c.text() if it_c else "")
                    
                    ow = self._to_float(self.table.item(rr, self.COL_OP_W).text() if self.table.item(rr, self.COL_OP_W) else "")
                    ox = self._to_float(self.table.item(rr, self.COL_OP_X).text() if self.table.item(rr, self.COL_OP_X) else "")
                    oy = self._to_float(self.table.item(rr, self.COL_OP_Y).text() if self.table.item(rr, self.COL_OP_Y) else "")
                    oz = self._to_float(self.table.item(rr, self.COL_OP_Z).text() if self.table.item(rr, self.COL_OP_Z) else "")
                    
                    ew = self._to_float(self.table.item(rr, self.COL_EX_W).text() if self.table.item(rr, self.COL_EX_W) else "")
                    ex = self._to_float(self.table.item(rr, self.COL_EX_X).text() if self.table.item(rr, self.COL_EX_X) else "")
                    ey = self._to_float(self.table.item(rr, self.COL_EX_Y).text() if self.table.item(rr, self.COL_EX_Y) else "")
                    ez = self._to_float(self.table.item(rr, self.COL_EX_Z).text() if self.table.item(rr, self.COL_EX_Z) else "")

                    p_v[0]+=ow*op_c; p_v[1]+=ow*op_c*ox; p_v[2]+=ow*op_c*oy; p_v[3]+=ow*op_c*oz
                    p_v[4]+=ew*ex_c; p_v[5]+=ew*ex_c*ex; p_v[6]+=ew*ex_c*ey; p_v[7]+=ew*ex_c*ez

                if total_rr is not None: self._set_total_row(total_rr, *p_v)
                for j in range(8): grand_vals[j] += p_v[j]
                r += (len(detail) + 1)

            if self._grand_total_row is not None: self._set_total_row(self._grand_total_row, *grand_vals)
        finally: self._updating = False

    # ---------- actions ----------
    def _on_save(self):
        if self.source_row is None: return
        r = self._grand_total_row
        if r is None: return

        op_w = self.table.item(r, self.COL_OP_W).text() if self.table.item(r, self.COL_OP_W) else "0"
        op_x = self.table.item(r, self.COL_OP_X).text() if self.table.item(r, self.COL_OP_X) else "0"
        op_y = self.table.item(r, self.COL_OP_Y).text() if self.table.item(r, self.COL_OP_Y) else "0"
        op_z = self.table.item(r, self.COL_OP_Z).text() if self.table.item(r, self.COL_OP_Z) else "0"

        payload = {
            "source_row": self.source_row,
            "source_col": self.source_col,
            "table_data": self.get_table_data(), # 必须导出明细数据
            "write_back": {
                4: op_w,
                7: f"{op_x},{op_y},{op_z}",
            }
        }
        self.saved.emit(payload)
        QMessageBox.information(self, "保存", "计算结果已回填。")

        # 自动跳回主表页面
        mw = self.window()
        if hasattr(mw, "tab_widget"):
            for i in range(mw.tab_widget.count()):
                if "平台载荷信息" in mw.tab_widget.tabText(i):
                    mw.tab_widget.setCurrentIndex(i)
                    break
