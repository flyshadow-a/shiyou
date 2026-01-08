# -*- coding: utf-8 -*-
# pages/special_inspection_strategy.py


import os
import csv
from typing import List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QPushButton, QScrollArea, QSizePolicy, QLabel
)

from base_page import BasePage
from dropdown_bar import DropdownBar


class SimpleTowerDiagram(QWidget):
    """右侧黑底“塔架示意图”占位控件（不依赖图片）。"""
    def __init__(self, variant: int = 0, parent=None):
        super().__init__(parent)
        self.variant = variant
        self.setMinimumSize(260, 520)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _evt):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(0, 0, 0))

        w, h = self.width(), self.height()
        margin = 30
        x1, x2 = margin, w - margin
        y_top, y_bot = margin, h - margin

        pen_line = QPen(QColor(0, 255, 0), 2)
        p.setPen(pen_line)

        p.drawLine(x1, y_top, x1, y_bot)
        p.drawLine(x2, y_top, x2, y_bot)

        for t in [0.18, 0.35, 0.52, 0.70, 0.86]:
            y = int(y_top + (y_bot - y_top) * t)
            p.drawLine(x1, y, x2, y)

        for t in [0.18, 0.35, 0.52, 0.70]:
            yA = int(y_top + (y_bot - y_top) * t)
            yB = int(y_top + (y_bot - y_top) * (t + 0.17))
            p.drawLine(x1, yA, x2, yB)
            p.drawLine(x2, yA, x1, yB)

        if self.variant == 0:
            pts = [
                (0.30, 0.22, QColor(0, 140, 255)),
                (0.70, 0.36, QColor(0, 200, 120)),
                (0.62, 0.66, QColor(255, 210, 0)),
            ]
        else:
            pts = [
                (0.72, 0.26, QColor(0, 140, 255)),
                (0.30, 0.52, QColor(0, 200, 120)),
                (0.78, 0.58, QColor(255, 210, 0)),
            ]

        for fx, fy, c in pts:
            cx = int(x1 + (x2 - x1) * fx)
            cy = int(y_top + (y_bot - y_top) * fy)
            r = 14
            p.setPen(QPen(Qt.NoPen))
            p.setBrush(QBrush(c))
            p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)

        p.end()


class SpecialInspectionStrategy(BasePage):
    """
    “特检策略”页面（顶部继承 DropdownBar 设计）
    """

    def __init__(self, main_window, parent=None):
        if parent is None:
            parent = main_window
        super().__init__("", parent)
        self.main_window = main_window

        self.data_dir = os.path.join(os.getcwd(), "data")
        self.current_year = "5年"

        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)

        self._build_ui()

        # 初始：上表固定示例数据，下表按年份
        self._fill_component_demo_data()
        self._load_node_year_data(self.current_year)

    # ---------------- UI ----------------
    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.main_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        root.addWidget(self._build_top_bar_dropdown_style(), 0)

        bottom = QFrame()
        bottom_lay = QHBoxLayout(bottom)
        bottom_lay.setContentsMargins(0, 0, 0, 0)
        bottom_lay.setSpacing(10)

        bottom_lay.addWidget(self._build_left_tables(), 3)
        bottom_lay.addWidget(self._build_right_diagrams(), 2)

        root.addWidget(bottom, 1)  # 填满剩余空间（减少底部留白）

    # ---------------- 顶部：DropdownBar + 补充操作栏（同风格） ----------------
    def _build_top_bar_dropdown_style(self) -> QWidget:
        wrap = QFrame()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 左侧 4 列：DropdownBar 原样式
        fields = [
            {"key": "facility_code", "label": "设施编码",
             "options": ["WC19-1WHPC", "WC19-2WHPC", "WC19-3WHPC"], "default": "WC19-1WHPC"},
            {"key": "facility_name", "label": "设施名称",
             "options": ["文昌19-1WHPC井口平台", "文昌19-2井口平台", "文昌19-3井口平台"], "default": "文昌19-1WHPC井口平台"},
            {"key": "inspect_seq", "label": "检测序号",
             "options": ["0", "1", "2", "3"], "default": "0"},
            {"key": "inspect_time", "label": "检测时间",
             "options": ["2008-06-26", "2008-07-12", "2008-08-21"], "default": "2008-06-26"},
        ]
        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.dropdown_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # DropdownBar 在不同 DPI/字体下可能需要更高的高度，否则第二行控件会被遮挡
        # 这里给一个可靠的最小高度，并在后面用真实 sizeHint 取最大值。
        self.dropdown_bar.setMinimumHeight(72)

        lay.addWidget(self.dropdown_bar, 1)

        # 右侧 3 列：补充栏（模仿 DropdownBar：蓝底标题 + 白底按钮/按钮）
        right = QFrame()
        right.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # 使用与 dropdown_bar.py 一致的主色（你项目里为 #0090d0）
        right.setStyleSheet("""
            QFrame#RightActions { background-color: #0090d0; }
            QLabel { color: white; font-weight: bold; }
            QPushButton { background: #efefef; border: 1px solid #666; }
            QPushButton:hover { background: #f7f7f7; }
            QPushButton#AddBtn { background:#cfe6b8; font-weight:bold; }
        """)
        right.setObjectName("RightActions")

        g = QVBoxLayout(right)
        g.setContentsMargins(10, 10, 10, 10)
        g.setSpacing(6)

        # 标题行
        titles = QFrame()
        tl = QHBoxLayout(titles)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)

        for t in ["检测策略", "节点检测历史", "操作"]:
            lab = QLabel(t)
            lab.setAlignment(Qt.AlignCenter)
            lab.setMinimumWidth(90)
            lab.setMinimumHeight(22)
            tl.addWidget(lab)

        g.addWidget(titles, 0)

        # 控件行
        row = QFrame()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self.btn_view_strategy = QPushButton("查看")
        self.btn_view_history = QPushButton("查看")
        self.btn_add = QPushButton("新增检测策略")
        self.btn_add.setObjectName("AddBtn")

        for b in [self.btn_view_strategy, self.btn_view_history]:
            b.setFixedSize(90, 30)
        self.btn_add.setFixedSize(120, 30)

        self.btn_view_strategy.clicked.connect(self._on_view_strategy)
        self.btn_view_history.clicked.connect(self._on_view_history)
        self.btn_add.clicked.connect(self._on_add_strategy)

        rl.addWidget(self.btn_view_strategy)
        rl.addWidget(self.btn_view_history)
        rl.addWidget(self.btn_add)

        g.addWidget(row, 0)

        # 让顶部整条栏位“足够高”，避免内容被遮挡（取 sizeHint / minimumHeight 的最大值）
        h_candidates = [
            self.dropdown_bar.sizeHint().height(),
            self.dropdown_bar.minimumSizeHint().height(),
            self.dropdown_bar.minimumHeight(),
            72,
        ]
        bar_h = max([v for v in h_candidates if v and v > 0])
        wrap.setMinimumHeight(bar_h)
        right.setFixedHeight(bar_h)

        lay.addWidget(right, 0)
        return wrap

    # ---------------- 左侧表格区 ----------------
    def _build_left_tables(self) -> QWidget:
        left = QWidget()
        v = QVBoxLayout(left)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # 上表：构件检验汇总（固定示例数据）
        self.component_table = QTableWidget(6, 5)
        self.component_table.setHorizontalHeaderLabels(["构件风险等级", "构件数量", "检验等级II", "检验等级III", "检验等级IV"])
        self._style_summary_table(self.component_table)
        v.addWidget(self._wrap_with_title("构件检验汇总", self.component_table), 0)

        # 年份切换条
        v.addWidget(self._build_year_bar(), 0)

        # 下表：节点风险等级汇总（随年份变化，并吃掉剩余高度）
        self.node_table = QTableWidget(6, 5)
        self.node_table.setHorizontalHeaderLabels(["节点风险等级", "节点焊缝数量", "检验等级II", "检验等级III", "检验等级IV"])
        self._style_summary_table(self.node_table)
        v.addWidget(self._wrap_with_title("节点风险等级汇总", self.node_table), 1)

        return left

    def _build_right_diagrams(self) -> QWidget:
        right = QWidget()
        h = QHBoxLayout(right)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        h.addWidget(SimpleTowerDiagram(variant=0), 1)
        h.addWidget(SimpleTowerDiagram(variant=1), 1)
        return right

    def _build_year_bar(self) -> QWidget:
        bar = QFrame()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        years = ["5年", "10年", "15年", "20年", "25年"]
        self.year_buttons = []

        for y in years:
            btn = QPushButton(y)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton { background: #efefef; border: 1px solid #333; padding: 2px 14px; }
                QPushButton:checked { background: #d6f0d0; font-weight: bold; }
            """)
            btn.clicked.connect(lambda _, yy=y: self._on_year_changed(yy))
            lay.addWidget(btn)
            self.year_buttons.append(btn)

        lay.addStretch(1)
        self._sync_year_buttons("5年")
        return bar

    # ---------------- helpers ----------------
    def _wrap_with_title(self, title: str, table: QTableWidget) -> QWidget:
        frame = QFrame()
        v = QVBoxLayout(frame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        title_bar = QFrame()
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet("background:#4f79bd;")
        tl = QHBoxLayout(title_bar)
        tl.setContentsMargins(10, 4, 10, 4)

        title_label = QLabel(title)
        title_label.setStyleSheet("color:white;font-weight:bold;")
        tl.addWidget(title_label)
        tl.addStretch(1)

        v.addWidget(title_bar, 0)
        v.addWidget(table, 1)
        return frame

    def _style_summary_table(self, table: QTableWidget):
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setShowGrid(True)

        # 表格自身出现滚动条（原型有）
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        table.setStyleSheet("""
            QTableWidget { background: #dfe9f6; gridline-color: #ffffff; }
            QHeaderView::section { background-color: #4f79bd; color: white; font-weight: bold; border: 1px solid #2f3a4a; }
        """)

        row_heads = ["一", "二", "三", "四", "五", "总计"]
        for r, head in enumerate(row_heads):
            it = QTableWidgetItem(head)
            it.setTextAlignment(Qt.AlignCenter)
            it.setBackground(QColor("#4f79bd"))
            it.setForeground(QColor("white"))
            table.setItem(r, 0, it)

        for r in range(table.rowCount()):
            for c in range(1, table.columnCount()):
                it = QTableWidgetItem("-")
                it.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, it)

    # ---------------- data ----------------
    def _fill_component_demo_data(self):
        comp = [
            ("2",   "-",  "-",  "-"),
            ("6",   "-",  "-",  "5"),
            ("188", "151", "37", "-"),
            ("758", "758", "-",  "-"),
            ("0",   "0",   "-",  "-"),
            ("954", "909", "42", "3"),
        ]
        self._fill_rows(self.component_table, comp)

    def _load_node_year_data(self, year: str):
        if year == "5年":
            node = [
                ("30",  "-",  "-",  "30"),
                ("64",  "-",  "52", "12"),
                ("226", "181", "45", "-"),
                ("422", "422", "-",  "-"),
                ("0",   "0",   "-",  "-"),
                ("742", "603", "97", "42"),
            ]
            self._fill_rows(self.node_table, node)
            return

        node_csv = os.path.join(self.data_dir, f"node_risk_summary_{year}_years.csv")
        self._fill_table_from_csv(self.node_table, node_csv, start_col=1)

    def _fill_rows(self, table: QTableWidget, rows: List[Tuple[str, str, str, str]]):
        for r, row in enumerate(rows):
            if r >= table.rowCount():
                break
            for i, val in enumerate(row):
                c = 1 + i
                if c >= table.columnCount():
                    break
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, it)

    def _fill_table_from_csv(self, table: QTableWidget, filepath: str, start_col: int = 0):
        for r in range(table.rowCount()):
            for c in range(start_col, table.columnCount()):
                it = QTableWidgetItem("-")
                it.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, it)

        if not os.path.exists(filepath):
            return

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                next(reader)
            except StopIteration:
                return

            for r, row in enumerate(reader):
                if r >= table.rowCount():
                    break
                for c, val in enumerate(row):
                    col = start_col + c
                    if col >= table.columnCount():
                        break
                    it = QTableWidgetItem("-" if val == "-" else str(val))
                    it.setTextAlignment(Qt.AlignCenter)
                    table.setItem(r, col, it)

    # ---------------- actions ----------------
    def _on_year_changed(self, year: str):
        self.current_year = year
        self._sync_year_buttons(year)
        # 只刷新下表
        self._load_node_year_data(year)

    def _sync_year_buttons(self, year: str):
        for btn in getattr(self, "year_buttons", []):
            btn.setChecked(btn.text() == year)

    def _get_dropdown_value(self, key: str) -> str:
        """兼容不同 DropdownBar 实现的取值方式。"""
        if not hasattr(self, "dropdown_bar"):
            return ""
        bar = self.dropdown_bar
        if hasattr(bar, "get_value"):
            try:
                v = bar.get_value(key)
                return (v or "").strip()
            except Exception:
                pass
        if hasattr(bar, "values") and isinstance(bar.values, dict):
            return (bar.values.get(key, "") or "").strip()
        # 兜底：尝试在 bar 内部找同名 combobox
        for attr in ("combos", "combo_boxes", "widgets"):
            d = getattr(bar, attr, None)
            if isinstance(d, dict) and key in d and isinstance(d[key], QComboBox):
                return d[key].currentText().strip()
        return ""

    def _on_add_strategy(self):
        facility_code = self._get_dropdown_value("facility_code")
        if self.main_window is not None and hasattr(self.main_window, "open_new_special_strategy_tab"):
            self.main_window.open_new_special_strategy_tab(facility_code)

    def _on_view_strategy(self):
        pass

    def _on_view_history(self):
        pass
