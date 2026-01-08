# -*- coding: utf-8 -*-
# pages/special_inspection_result_page.py

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
    更新风险等级结果页（示例）：
    - 左：构件/节点二级tab + 明细表 + 多段汇总
    - 右：黑底示意图 + 生成报告按钮 + 绿色占位块
    - 支持滚轮滚动（QScrollArea）
    """
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

            QTableWidget { background: #f7fbff; gridline-color: #7b8798; border: 1px solid #7b8798; }
            QHeaderView::section { background: #d9e6f5; border: 1px solid #7b8798; padding: 4px 6px; font-weight: bold; }

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

        # 构件/节点 二级tab（贴近截图）
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)

        self.table_comp = self._make_detail_table(is_node=False)
        self.table_node = self._make_detail_table(is_node=True)

        comp_wrap = QWidget()
        comp_l = QVBoxLayout(comp_wrap)
        comp_l.setContentsMargins(0, 0, 0, 0)
        comp_l.addWidget(self.table_comp)

        node_wrap = QWidget()
        node_l = QVBoxLayout(node_wrap)
        node_l.setContentsMargins(0, 0, 0, 0)
        node_l.addWidget(self.table_node)

        self.tabs.addTab(comp_wrap, "构件风险等级")
        self.tabs.addTab(node_wrap, "节点风险等级")
        v.addWidget(self.tabs, 0)

        # 汇总信息（当前、5、10、15、20、25年）
        v.addWidget(self._build_summary_block(), 1)

        return panel

    def _make_detail_table(self, is_node: bool) -> QTableWidget:
        cols = [
            "A", "B", "MemberType", "失效后果等级", "A", "B", "倒塌分析载荷系数Rn", "Vr", "Pf", "构件风险等级"
        ]
        if is_node:
            cols = [
                "JointA", "JointB", "WeldType", "失效后果等级", "A", "B", "倒塌分析载荷系数Rn", "Vr", "Pf", "节点风险等级"
            ]

        t = QTableWidget(120, len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.setMinimumHeight(240)
        return t

    def _build_summary_block(self) -> QWidget:
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        for title in ["当前", "第5年", "第10年", "第15年", "第20年", "第25年"]:
            v.addWidget(self._make_one_summary_table(title), 0)

        v.addStretch(1)
        return wrap

    def _make_one_summary_table(self, title: str) -> QTableWidget:
        # 3行 x 6列（0列标签 + 1~5列风险等级一~五），颜色条贴近截图
        t = QTableWidget(3, 6)
        t.setFixedHeight(100)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setVisible(False)
        t.setStyleSheet("QTableWidget{background:#dfe9f6;border:1px solid #7b8798;}")

        # 标签列
        labels = ["风险等级", "数量", "占比"]
        for r, lab in enumerate(labels):
            it = QTableWidgetItem(lab)
            it.setTextAlignment(Qt.AlignCenter)
            t.setItem(r, 0, it)

        # 左上角显示“当前/第5年...”
        corner = QTableWidgetItem(title)
        corner.setTextAlignment(Qt.AlignCenter)
        corner.setBackground(QColor("#cfe6b8"))
        t.setItem(0, 0, corner)

        # 颜色条（红、橙、黄、蓝、棕）
        colors = [QColor("#ff3b30"), QColor("#ffcc00"), QColor("#ffee58"), QColor("#1e88e5"), QColor("#6d4c41")]
        headers = ["一", "二", "三", "四", "五"]

        for i in range(5):
            h = QTableWidgetItem(headers[i])
            h.setTextAlignment(Qt.AlignCenter)
            h.setBackground(colors[i])
            t.setItem(0, i + 1, h)

            # 示例数字/占比（你后续接真实算法结果即可）
            num = QTableWidgetItem(str((i * 97 + len(title) * 13) % 900))
            pct = QTableWidgetItem(f"{((i + 1) * 7.41) % 80:.2f}%")
            num.setTextAlignment(Qt.AlignCenter)
            pct.setTextAlignment(Qt.AlignCenter)
            t.setItem(1, i + 1, num)
            t.setItem(2, i + 1, pct)

        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        return t

    def _build_right(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # 黑底示意图（一个）
        frame = QFrame()
        frame.setStyleSheet("background:black;border:1px solid #c7d2e3;")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(6, 6, 6, 6)
        fl.addWidget(PlanDiagram(), 1)
        v.addWidget(frame, 1)

        # 生成报告按钮（示例）
        btn = QPushButton("生成特检策略报告")
        btn.setObjectName("ReportBtn")
        btn.clicked.connect(self._on_report)
        v.addWidget(btn, 0)

        # 绿色占位块（贴近截图右下角）
        green = QFrame()
        green.setMinimumHeight(130)
        green.setStyleSheet("background:#b7e37a;border:1px solid #7b8798;")
        gl = QVBoxLayout(green)
        gl.addStretch(1)
        lab = QLabel("某个平台特检策略页面3")
        lab.setAlignment(Qt.AlignCenter)
        lab.setStyleSheet("font-size:20px;")
        gl.addWidget(lab)
        gl.addStretch(1)
        v.addWidget(green, 0)

        return panel

    # -------- demo data --------
    def _fill_demo(self):
        # 构件明细示例
        for r in range(self.table_comp.rowCount()):
            vals = ["501L", "511L", "LEG", "2", "0.272", "0.158", "1.9", "10%", "6.9E-05", "三" if r % 3 == 0 else "四"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignCenter)
                self.table_comp.setItem(r, c, it)

        # 节点明细示例
        for r in range(self.table_node.rowCount()):
            vals = [f"J{r+1:02d}", f"J{r+2:02d}", "WELD", "2", "0.272", "0.158", "1.9", "10%", "6.9E-05", "二" if r % 4 == 0 else "三"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignCenter)
                self.table_node.setItem(r, c, it)

        self._apply_row_limit()

    def _apply_row_limit(self):
        choice = self.cb_rows.currentText()
        limit = None if choice == "全部" else int(choice)

        def apply(table: QTableWidget):
            for r in range(table.rowCount()):
                table.setRowHidden(r, (limit is not None and r >= limit))

        apply(self.table_comp)
        apply(self.table_node)

    def _on_report(self):
        # 这里后续接你真实“导出报告（PDF/Word）”
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "生成报告", "示例：按预定义格式生成评估报告（后续接导出PDF/Word）。")
