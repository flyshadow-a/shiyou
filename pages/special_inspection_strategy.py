# -*- coding: utf-8 -*-
# pages/special_inspection_strategy.py

import os
import csv
from PyQt5.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QPushButton, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush

from base_page import BasePage


class SimpleTowerDiagram(QWidget):
    """
    右侧黑底“塔架示意图”占位控件（不依赖图片）：
    - 画两根立柱 + 斜撑
    - 画几个彩色节点
    """
    def __init__(self, variant: int = 0, parent=None):
        super().__init__(parent)
        self.variant = variant
        self.setMinimumSize(260, 520)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _evt):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # 背景
        p.fillRect(self.rect(), QColor(0, 0, 0))

        w, h = self.width(), self.height()
        margin = 30
        x1, x2 = margin, w - margin
        y_top, y_bot = margin, h - margin

        # 绿线框架
        pen_line = QPen(QColor(0, 255, 0), 2)
        p.setPen(pen_line)

        # 立柱
        p.drawLine(x1, y_top, x1, y_bot)
        p.drawLine(x2, y_top, x2, y_bot)

        # 横撑
        for t in [0.18, 0.35, 0.52, 0.70, 0.86]:
            y = int(y_top + (y_bot - y_top) * t)
            p.drawLine(x1, y, x2, y)

        # 斜撑
        for t in [0.18, 0.35, 0.52, 0.70]:
            yA = int(y_top + (y_bot - y_top) * t)
            yB = int(y_top + (y_bot - y_top) * (t + 0.17))
            p.drawLine(x1, yA, x2, yB)
            p.drawLine(x2, yA, x1, yB)

        # 节点（彩色圆）
        # variant=0 / 1 画不同“阶段”
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
    重做后的“特检策略”页面（对应你第二张图）：
    - 顶部：1行表格（设施编码/设施名称/检测序号/检测时间/检测策略查看/节点检测历史查看/新增检测策略）
    - 下部：左侧两张汇总表（构件、节点）+ 年限切换；右侧两幅示意图
    """

    def __init__(self, main_window, parent=None):
        # 兼容 MainWindow: page_cls(self) 的调用方式
        if parent is None:
            parent = main_window

        # BasePage 默认会加标题，这里传空字符串避免页面内部再出现“特检策略”标题
        super().__init__("", parent)
        self.main_window = main_window

        # 你原来用 CSV 的方式，我这里继续沿用：
        self.data_dir = os.path.join(os.getcwd(), "data")

        # 记录当前年限
        self.current_year = "5年"

        # 让页面更贴近截图：减小边距
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)

        self._build_ui()
        self._load_year_data(self.current_year)

    # ---------------- UI ----------------
    def _build_ui(self):
        # 使用滚动区，防止小分辨率下挤压
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.main_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # 顶部表格（1行7列）
        root.addWidget(self._build_top_table(), 0)

        # 下部：左（表格） + 右（示意图）
        bottom = QFrame()
        bottom_lay = QHBoxLayout(bottom)
        bottom_lay.setContentsMargins(0, 0, 0, 0)
        bottom_lay.setSpacing(10)

        bottom_lay.addWidget(self._build_left_tables(), 3)
        bottom_lay.addWidget(self._build_right_diagrams(), 2)

        root.addWidget(bottom, 1)

    def _build_top_table(self) -> QTableWidget:
        table = QTableWidget(1, 7)
        table.setHorizontalHeaderLabels([
            "设施编码", "设施名称", "检测序号", "检测时间", "检测策略", "节点检测历史", "操作"
        ])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setFixedHeight(78)

        # 表头风格（接近截图）
        table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #00BFFF;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #4a4a4a;
            }
        """)
        table.setStyleSheet("""
            QTableWidget {
                background: #dfe9f6;
                gridline-color: #4a4a4a;
            }
            QTableWidget::item {
                background: #dfe9f6;
            }
        """)

        # 设施编码/名称/序号/时间（用下拉框模拟）
        cb_code = QComboBox()
        cb_code.addItems(["WC19-1WHPC", "WC19-2WHPC", "WC19-3WHPC"])
        table.setCellWidget(0, 0, cb_code)

        cb_name = QComboBox()
        cb_name.addItems(["文昌19-1WHPC井口平台", "文昌19-2井口平台", "文昌19-3井口平台"])
        table.setCellWidget(0, 1, cb_name)

        cb_seq = QComboBox()
        cb_seq.addItems(["0", "1", "2", "3"])
        table.setCellWidget(0, 2, cb_seq)

        cb_time = QComboBox()
        cb_time.addItems(["2008-06-26", "2008-07-12", "2008-08-21"])
        table.setCellWidget(0, 3, cb_time)

        # 查看按钮
        btn_view_strategy = QPushButton("查看")
        btn_view_strategy.clicked.connect(self._on_view_strategy)
        table.setCellWidget(0, 4, btn_view_strategy)

        btn_view_history = QPushButton("查看")
        btn_view_history.clicked.connect(self._on_view_history)
        table.setCellWidget(0, 5, btn_view_history)

        # 新增检测策略
        btn_add = QPushButton("新增检测策略")
        btn_add.setStyleSheet("background:#cfe6b8;font-weight:bold;")
        btn_add.clicked.connect(lambda: self._on_add_strategy(cb_code))
        table.setCellWidget(0, 6, btn_add)

        return table

    def _build_left_tables(self) -> QWidget:
        left = QWidget()
        v = QVBoxLayout(left)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # 构件检验汇总
        self.component_table = QTableWidget(6, 5)
        self.component_table.setHorizontalHeaderLabels(["构件风险等级", "构件数量", "检验等级II", "检验等级III", "检验等级IV"])
        self._style_summary_table(self.component_table, title="构件检验汇总")
        v.addWidget(self._wrap_with_title("构件检验汇总", self.component_table), 0)

        # 年限切换条
        v.addWidget(self._build_year_bar(), 0)

        # 节点风险等级汇总
        self.node_table = QTableWidget(6, 5)
        self.node_table.setHorizontalHeaderLabels(["节点风险等级", "节点焊缝数量", "检验等级II", "检验等级III", "检验等级IV"])
        self._style_summary_table(self.node_table, title="节点风险等级汇总")
        v.addWidget(self._wrap_with_title("节点风险等级汇总", self.node_table), 1)

        return left

    def _build_right_diagrams(self) -> QWidget:
        right = QWidget()
        h = QHBoxLayout(right)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        # 两幅示意图（对应截图右侧两个黑框）
        d1 = SimpleTowerDiagram(variant=0)
        d2 = SimpleTowerDiagram(variant=1)

        h.addWidget(d1, 1)
        h.addWidget(d2, 1)
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
                QPushButton {
                    background: #efefef;
                    border: 1px solid #333;
                    padding: 2px 14px;
                }
                QPushButton:checked {
                    background: #d6f0d0;
                    font-weight: bold;
                }
            """)
            btn.clicked.connect(lambda _, yy=y: self._on_year_changed(yy))
            lay.addWidget(btn)
            self.year_buttons.append(btn)

        lay.addStretch(1)

        # 默认选中 5年
        self._sync_year_buttons("5年")
        return bar

    # ---------------- helpers ----------------
    def _wrap_with_title(self, title: str, table: QTableWidget) -> QWidget:
        frame = QFrame()
        v = QVBoxLayout(frame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        # 蓝色标题条（接近截图）
        title_bar = QFrame()
        title_bar.setStyleSheet("background:#4f79bd;")
        tl = QHBoxLayout(title_bar)
        tl.setContentsMargins(10, 4, 10, 4)
        lab = QPushButton(title)
        lab.setEnabled(False)
        lab.setStyleSheet("color:white;font-weight:bold;border:none;background:transparent;")
        tl.addWidget(lab)
        tl.addStretch(1)

        v.addWidget(title_bar)
        v.addWidget(table)
        return frame

    def _style_summary_table(self, table: QTableWidget, title: str = ""):
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setFixedHeight(220)
        table.setStyleSheet("""
            QTableWidget { background: #dfe9f6; gridline-color: #ffffff; }
            QHeaderView::section { background-color: #4f79bd; color: white; font-weight: bold; }
        """)

        # 预填充风险等级行头（1~5+总计），和截图一致
        row_heads = ["一", "二", "三", "四", "五", "总计"]
        for r, head in enumerate(row_heads):
            it = QTableWidgetItem(head)
            it.setTextAlignment(Qt.AlignCenter)
            it.setBackground(QColor("#4f79bd"))
            it.setForeground(QColor("white"))
            table.setItem(r, 0, it)

    # ---------------- data loading ----------------
    def _load_year_data(self, year: str):
        # 构件汇总
        comp_csv = os.path.join(self.data_dir, f"component_summary_{year}_years.csv")
        self._fill_table_from_csv(self.component_table, comp_csv, start_col=1)

        # 节点汇总
        node_csv = os.path.join(self.data_dir, f"node_risk_summary_{year}_years.csv")
        self._fill_table_from_csv(self.node_table, node_csv, start_col=1)

    def _fill_table_from_csv(self, table: QTableWidget, filepath: str, start_col: int = 0):
        """
        从 CSV 填充表格。
        - CSV第一行默认是表头，会跳过
        - 如果文件不存在，用 '-' 填充
        """
        # 先清空除“风险等级列(0列)”之外的内容
        for r in range(table.rowCount()):
            for c in range(start_col, table.columnCount()):
                table.setItem(r, c, QTableWidgetItem("-"))

        if not os.path.exists(filepath):
            # 没有数据文件就保持占位
            return

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                next(reader)  # 跳过标题行
            except StopIteration:
                return

            for r, row in enumerate(reader):
                if r >= table.rowCount():
                    break
                for c, val in enumerate(row):
                    col = start_col + c
                    if col >= table.columnCount():
                        break
                    value = "" if val == "-" else str(val)
                    it = QTableWidgetItem(value)
                    it.setTextAlignment(Qt.AlignCenter)
                    table.setItem(r, col, it)

    # ---------------- actions ----------------
    def _on_year_changed(self, year: str):
        self.current_year = year
        self._sync_year_buttons(year)
        self._load_year_data(year)

    def _sync_year_buttons(self, year: str):
        for btn in getattr(self, "year_buttons", []):
            btn.setChecked(btn.text() == year)

    def _on_add_strategy(self, cb_code: QComboBox):
        facility_code = cb_code.currentText()
        if self.main_window is not None and hasattr(self.main_window, "open_new_special_strategy_tab"):
            self.main_window.open_new_special_strategy_tab(facility_code)

    def _on_view_strategy(self):
        # 这里先留空：你后面可以打开“历史检测策略汇总结论”的页面/对话框/新Tab
        pass

    def _on_view_history(self):
        # 这里先留空：你后面可以打开“节点检测历史”的页面/对话框/新Tab
        pass
