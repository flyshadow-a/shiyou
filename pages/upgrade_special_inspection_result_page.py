# -*- coding: utf-8 -*-
# pages/upgrade_special_inspection_result_page.py


from PyQt5.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QComboBox, QTabWidget, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush

from base_page import BasePage


class PlanDiagram(QWidget):
    """右侧黑底平面示意图占位：绿线框架 + 红点/绿点节点（示例）。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 640)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _evt):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(0, 0, 0))

        w, h = self.width(), self.height()
        m = 28
        x1, x2 = m, w - m
        y1, y2 = m, h - m

        # 绿线框架
        p.setPen(QPen(QColor(0, 255, 0), 2))
        p.drawLine(x1, y1, x1, y2)
        p.drawLine(x2, y1, x2, y2)

        for t in [0.18, 0.35, 0.52, 0.70, 0.86]:
            y = int(y1 + (y2 - y1) * t)
            p.drawLine(x1, y, x2, y)

        for t in [0.18, 0.35, 0.52, 0.70]:
            ya = int(y1 + (y2 - y1) * t)
            yb = int(y1 + (y2 - y1) * (t + 0.17))
            p.drawLine(x1, ya, x2, yb)
            p.drawLine(x2, ya, x1, yb)

        # 示例节点：红=需检测；绿=已检测
        nodes = [
            (0.50, 0.26, QColor(255, 0, 0)),
            (0.72, 0.40, QColor(255, 0, 0)),
            (0.32, 0.68, QColor(0, 200, 120)),
        ]
        for fx, fy, c in nodes:
            cx = int(x1 + (x2 - x1) * fx)
            cy = int(y1 + (y2 - y1) * fy)
            r = 14
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(c))
            p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)

        p.end()


class UpgradeSpecialInspectionResultPage(BasePage):
    """
    更新风险等级结果页（严格表头/汇总样式版）
    """
    HEADER_ROWS = 2
    SUMMARY_YEARS = ["构件","当前", "第5年", "第10年", "第15年", "第20年", "第25年"]

    # 汇总颜色条（红、橙、黄、蓝、棕）
    RISK_COLORS = [
        QColor("#ff3b30"),
        QColor("#ffcc00"),
        QColor("#ffee58"),
        QColor("#1e88e5"),
        QColor("#6d4c41"),
    ]
    RISK_LABELS = ["一", "二", "三", "四", "五"]

    def __init__(self, facility_code: str, parent=None):
        self.facility_code = facility_code
        super().__init__(f"{facility_code}更新风险结果", parent)
        self._build_ui()
        self._fill_demo()

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget { background: #e6eef7; }
            QFrame#Card { background: #e6eef7; border: 1px solid #c7d2e3; }

            QTabWidget::pane { border: 1px solid #4a4a4a; background: #e6eef7; }
            QTabBar::tab {
                background: #eaf2ff;
                border: 1px solid #4a4a4a;
                border-bottom: none;
                padding: 6px 16px;
                min-width: 110px;
                font-weight: bold;
            }
            QTabBar::tab:selected { background: #d6f0d0; }

            /* 表格（网格线明显） */
            QTableWidget {
                background: #f7fbff;
                gridline-color: #7b8798;
                border: 1px solid #7b8798;
            }
            QHeaderView::section {
                background: #d9e6f5;
                border: 1px solid #7b8798;
                padding: 4px 6px;
                font-weight: bold;
            }

            QPushButton#ReportBtn {
                background: #00a0d6;
                color: black;
                border: 1px solid #0a5f7a;
                border-radius: 8px;
                min-height: 46px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton#ReportBtn:hover { background: #00b6f2; }
        """)

        # 整页滚动（内容多时滚轮可滚）
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.main_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("Card")
        root.addWidget(card)

        lay = QHBoxLayout(card)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        lay.addWidget(self._build_left(), 3)
        lay.addWidget(self._build_right(), 2)

    # ---------------- Left ----------------
    def _build_left(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # 顶部：条数选择（10/20/50/100/全部）
        row_bar = QHBoxLayout()
        row_bar.addWidget(QLabel("明细显示行数："))
        self.cb_rows = QComboBox()
        self.cb_rows.addItems(["10", "20", "50", "100", "全部"])
        self.cb_rows.currentIndexChanged.connect(self._apply_row_limit)
        row_bar.addWidget(self.cb_rows)
        row_bar.addStretch(1)
        v.addLayout(row_bar)

        # 构件/节点 二级tab
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)

        comp_wrap = QWidget()
        comp_l = QVBoxLayout(comp_wrap)
        comp_l.setContentsMargins(0, 0, 0, 0)
        comp_l.setSpacing(10)
        self.table_comp = self._make_detail_table(is_node=False)
        self.summary_comp = self._make_summary_table()

        comp_l.addWidget(self.table_comp, 0)
        comp_l.addWidget(self.summary_comp, 1)


        node_wrap = QWidget()
        node_l = QVBoxLayout(node_wrap)
        node_l.setContentsMargins(0, 0, 0, 0)
        node_l.setSpacing(10)
        self.table_node = self._make_detail_table(is_node=True)
        self.summary_node = self._make_summary_table()
        node_l.addWidget(self.table_node, 0)
        node_l.addWidget(self.summary_node, 1)

        self.tabs.addTab(comp_wrap, "构件风险等级")
        self.tabs.addTab(node_wrap, "节点风险等级")
        v.addWidget(self.tabs, 1)

        return panel

    # ---------------- Detail table with merged headers ----------------
    def _make_detail_table(self, is_node: bool) -> QTableWidget:
        """
        明细表：两行表头（row 0 分组，row 1 字段），数据从 row=2 开始。
        """
        if not is_node:
            # 4 + 6 + 1 = 11 列
            sub_headers = [
                "A", "B", "MemberType", "失效后果等级",
                "A", "B", "倒塌分析载荷系数Rn", "Vr", "Pf", "失效概率等级",
                "构件风险等级",
            ]
        else:
            sub_headers = [
                "JointA", "JointB", "WeldType", "失效后果等级",
                "A", "B", "倒塌分析载荷系数Rn", "Vr", "Pf", "失效概率等级",
                "节点风险等级",
            ]

        cols = len(sub_headers)
        data_rows = 120

        t = QTableWidget(self.HEADER_ROWS + data_rows, cols)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setVisible(False)
        t.setShowGrid(True)
        t.setGridStyle(Qt.SolidLine)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setSelectionMode(QTableWidget.SingleSelection)

        # 列宽：用 Stretch（和你现有实现一致）
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # ---- row 0: group headers ----
        hdr_bg = QColor("#d9e6f5")
        bold = True
        # 基本信息：0..3
        t.setSpan(0, 0, 1, 4)
        self._set_cell(t, 0, 0, "基本信息", hdr_bg, bold)
        for c in range(1, 4):
            self._set_cell(t, 0, c, "", hdr_bg, bold)

        # 失效概率等级：4..9
        t.setSpan(0, 4, 1, 6)
        self._set_cell(t, 0, 4, "失效概率等级", hdr_bg, bold)
        for c in range(5, 10):
            self._set_cell(t, 0, c, "", hdr_bg, bold)

        # 风险等级（最后一列）
        self._set_cell(t, 0, 10, "风险等级", hdr_bg, bold)

        # ---- row 1: sub headers ----
        for c, name in enumerate(sub_headers):
            self._set_cell(t, 1, c, name, hdr_bg, True)

        # row heights
        t.setRowHeight(0, 26)
        t.setRowHeight(1, 26)
        for r in range(2, t.rowCount()):
            t.setRowHeight(r, 24)

        # minimum height so it looks like the sample (scroll inside table)
        t.setMinimumHeight(260)

        return t

    def _set_cell(self, table: QTableWidget, r: int, c: int, text: str, bg: QColor = None, bold: bool = False):
        it = QTableWidgetItem(str(text))
        it.setTextAlignment(Qt.AlignCenter)
        if bg is not None:
            it.setBackground(bg)
        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)
        table.setItem(r, c, it)

    # ---------------- Summary big table (tagged) ----------------
    def _make_summary_table(self) -> QTableWidget:
        """
        汇总表：顶部 1 行标签（合并单元格），下面每个年份 3 行：
        - 年份标签 + 风险等级颜色条
        - 数量
        - 占比
        """
        cols = 6  # 0: 标签列，1..5: 风险等级一~五
        rows =  len(self.SUMMARY_YEARS) * 4

        t = QTableWidget(rows, cols)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setVisible(False)
        t.setShowGrid(True)
        t.setGridStyle(Qt.SolidLine)
        t.setSelectionMode(QTableWidget.NoSelection)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.setStyleSheet("QTableWidget{background:#dfe9f6;}")

        # Tag row
        # t.setSpan(0, 0, 1, cols)
        tag_bg = QColor("#e3e7ef")
        green = QColor("#cfe6b8")
        for r in range(len(self.SUMMARY_YEARS)):
            t.setSpan(r * 4, 0, 1, 6)
            self._set_cell(t, r * 4, 0, self.SUMMARY_YEARS[r], green, True)







        # Year blocks
        green = QColor("#cfe6b8")
        for i, year in enumerate(self.SUMMARY_YEARS):
            base_r = 1 + i * 4


            # row base_r: year label + risk headers
            # self._set_cell(t, base_r, 0, year, green, True)

            for k in range(5):
                it = QTableWidgetItem(self.RISK_LABELS[k])
                it.setTextAlignment(Qt.AlignCenter)
                it.setBackground(self.RISK_COLORS[k])
                f = it.font()
                f.setBold(True)
                it.setFont(f)
                t.setItem(base_r, 1 + k, it)

            # row base_r+1: 风险等级
            self._set_cell(t, base_r, 0, "风险等级", QColor("#e3e7ef"), True)
            # for k in range(1,5):
            #     self._set_cell(t, base_r + 1, 1 + k, "", None, False)

            # row base_r+2: 数量
            self._set_cell(t, base_r + 1, 0, "数量", QColor("#e3e7ef"), True)
            for k in range(5):
                self._set_cell(t, base_r + 1, 1 + k, "", None, False)

            # row base_r+3: 占比
            self._set_cell(t, base_r +2 , 0, "占比", QColor("#e3e7ef"), True)
            for k in range(5):
                self._set_cell(t, base_r + 2, 1 + k, "", None, False)

            # row heights
            t.setRowHeight(base_r, 26)
            t.setRowHeight(base_r + 1, 24)
            t.setRowHeight(base_r + 2, 24)

        t.setRowHeight(0, 26)
        t.setMinimumHeight(430)
        return t

    # ---------------- Right ----------------
    def _build_right(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        frame = QFrame()
        frame.setStyleSheet("background:black;border:1px solid #c7d2e3;")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(6, 6, 6, 6)
        fl.addWidget(PlanDiagram(), 1)
        v.addWidget(frame, 1)

        btn = QPushButton("生成特检策略报告")
        btn.setObjectName("ReportBtn")
        btn.clicked.connect(self._on_report)
        v.addWidget(btn, 0)

        return panel

    # ---------------- demo data fill ----------------
    def _fill_demo(self):
        # 明细表填充（从第2行开始）
        self._fill_detail_demo(self.table_comp, is_node=False)
        self._fill_detail_demo(self.table_node, is_node=True)

        # 汇总填充（构件/节点分别一套）
        self._fill_summary_demo(self.summary_comp, seed=13)
        self._fill_summary_demo(self.summary_node, seed=29)

        self._apply_row_limit()

    def _fill_detail_demo(self, table: QTableWidget, is_node: bool):
        start = self.HEADER_ROWS
        for r in range(start, table.rowCount()):
            idx = r - start
            if not is_node:
                vals = [
                    "501L", "511L", "LEG", "2",
                    "0.272", "0.158", "1.9", "10%", "6.9E-05", "4",
                    "三" if idx % 3 == 0 else "四"
                ]
            else:
                vals = [
                    f"J{idx+1:03d}", f"J{idx+2:03d}", "WELD", "2",
                    "0.272", "0.158", "1.9", "10%", "6.9E-05", "4",
                    "二" if idx % 4 == 0 else "三"
                ]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, it)

    def _fill_summary_demo(self, summary_table: QTableWidget, seed: int = 7):
        """
        给汇总表填一组稳定的演示数据（数量 + 占比）。
        每个年份块：数量行在 base_r+1，比例行 base_r+2。
        """
        import random
        rnd = random.Random(seed)

        for i, _year in enumerate(self.SUMMARY_YEARS):
            base_r = 1 + i * 4
            nums = [rnd.randint(0, 500) for _ in range(5)]
            total = sum(nums) or 1
            pcts = [n * 100.0 / total for n in nums]

            for k in range(5):
                # 数量
                itn = QTableWidgetItem(str(nums[k]))
                itn.setTextAlignment(Qt.AlignCenter)
                summary_table.setItem(base_r + 1, 1 + k, itn)

                # 占比
                itp = QTableWidgetItem(f"{pcts[k]:.2f}%")
                itp.setTextAlignment(Qt.AlignCenter)
                summary_table.setItem(base_r + 2, 1 + k, itp)

    def _apply_row_limit(self):
        choice = self.cb_rows.currentText()
        limit = None if choice == "全部" else int(choice)

        def apply(table: QTableWidget):
            start = self.HEADER_ROWS
            for r in range(start, table.rowCount()):
                table.setRowHidden(r, (limit is not None and (r - start) >= limit))

        apply(self.table_comp)
        apply(self.table_node)

    def _on_report(self):
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "生成报告", "示例：按预定义格式生成特检策略报告（后续接导出PDF/Word）。")
