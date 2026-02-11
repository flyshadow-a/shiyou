# -*- coding: utf-8 -*-
# pages/feasibility_assessment_results_page.py
#
# 结构强度 -> WC19-1DPPA平台强度/改造可行性评估评估结果
#
# - 左侧：上方“快速评估汇总信息”表（含合并标题单元格）
#         下方：标签页（构件/节点冲剪/桩应力/桩承载力操作抗压） + “快速评估信息”表（含合并标题单元格）
#         左下：生成评估报告按钮
# - 右侧：自动加载 INP，显示线框投影（无额外操作）
#
# 说明：本页面只负责 UI 与基础占位逻辑；真实的结果解析/着色显示可后续接入。

import os
from typing import Dict, List, Tuple

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QPen, QBrush, QFontMetrics
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget, QHeaderView,
)

from base_page import BasePage
from dropdown_bar import DropdownBar


class InpWireframeView(QGraphicsView):
    """
    简化版 INP 可视化：解析 *NODE 和 *ELEMENT（取前两节点连线），做 2D 投影显示线框。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setStyleSheet("background:#0b0f14; border: 1px solid #2f3a4a;")
        self.setFrameShape(QFrame.NoFrame)
        self.setAlignment(Qt.AlignCenter)

        self._nodes: Dict[int, Tuple[float, float, float]] = {}
        self._edges: List[Tuple[int, int]] = []
        self._proj_pts: Dict[int, Tuple[float, float]] = {}

    def clear_view(self, message: str = ""):
        self.scene().clear()
        self._nodes, self._edges, self._proj_pts = {}, [], {}
        if message:
            t = self.scene().addText(message)
            t.setDefaultTextColor(QColor("#d7e3f0"))
            self._center_text_item(t)

    def load_inp(self, file_path: str):
        nodes, edges = self._parse_inp_nodes_elements(file_path)
        self._nodes = nodes
        self._edges = edges
        if not nodes or not edges:
            self.clear_view("未解析到 NODE/ELEMENT 数据")
            return
        self._render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._nodes and self._edges:
            self._render()
        else:
            for it in self.scene().items():
                if hasattr(it, "toPlainText"):
                    self._center_text_item(it)

    def _center_text_item(self, item):
        br = item.boundingRect()
        w = max(10, self.viewport().width())
        h = max(10, self.viewport().height())
        item.setPos((w - br.width()) / 2, (h - br.height()) / 2)

    def _render(self):
        self.scene().clear()

        # 等轴测投影
        z_scale = 0.9
        xs, ys = [], []
        proj = {}
        for nid, (x, y, z) in self._nodes.items():
            px = (x - y)
            py = (x + y) * 0.5 - z * z_scale
            proj[nid] = (px, py)
            xs.append(px)
            ys.append(py)

        if not xs or not ys:
            self.clear_view("无可显示数据")
            return

        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        spanx = max(1e-6, maxx - minx)
        spany = max(1e-6, maxy - miny)

        vw = max(10, self.viewport().width())
        vh = max(10, self.viewport().height())
        margin = 20
        s = min((vw - 2 * margin) / spanx, (vh - 2 * margin) / spany)
        s = max(0.1, s)

        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0
        vx = vw / 2.0
        vy = vh / 2.0

        def map_pt(p):
            x, y = p
            return (vx + (x - cx) * s, vy + (y - cy) * s)

        self._proj_pts = {nid: map_pt(p) for nid, p in proj.items()}

        pen = QPen(QColor("#62ff62"))
        pen.setWidth(1)

        for n1, n2 in self._edges:
            p1 = self._proj_pts.get(n1)
            p2 = self._proj_pts.get(n2)
            if p1 and p2:
                self.scene().addLine(p1[0], p1[1], p2[0], p2[1], pen)

        self.scene().setSceneRect(QRectF(0, 0, vw, vh))

    def _parse_inp_nodes_elements(self, file_path: str):
        nodes: Dict[int, Tuple[float, float, float]] = {}
        edges: List[Tuple[int, int]] = []
        in_node = False
        in_elem = False

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("**"):
                    continue

                if line.startswith("*"):
                    u = line.upper()
                    in_node = u.startswith("*NODE")
                    in_elem = u.startswith("*ELEMENT")
                    continue

                if in_node:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 4:
                        continue
                    try:
                        nid = int(float(parts[0]))
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    except Exception:
                        continue
                    nodes[nid] = (x, y, z)
                    continue

                if in_elem:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 3:
                        continue
                    try:
                        n1 = int(float(parts[1]))
                        n2 = int(float(parts[2]))
                    except Exception:
                        continue
                    edges.append((n1, n2))
                    continue

        return nodes, edges


class FeasibilityAssessmentResultsPage(BasePage):
    """
    feasibility_assessment_results_page
    """

    # 表头底色（接近原型的浅灰）
    HDR_BG = QColor("#e9edf5")
    TITLE_BG = QColor("#e9edf5")
    INDEX_BG = QColor("#e9eef5")

    def __init__(self, main_window,facility_code, parent=None):
        if parent is None:
            parent = main_window
        super().__init__("", parent)
        self.main_window = main_window
        self.facility_code = facility_code
        self.current_tab = "构件"

        self._build_ui()
        self._autoload_inp_to_view()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)



        # 中部：左右布局
        center = QWidget()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(8, 0, 8, 8)
        center_layout.setSpacing(10)
        self.main_layout.addWidget(center, 1)

        # 左侧滚动区域（表格较多）
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        center_layout.addWidget(left_scroll, 6)

        left = QWidget()
        left_scroll.setWidget(left)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        left_layout.addWidget(self._build_summary_table(), 0)
        left_layout.addWidget(self._build_detail_section(), 0)
        left_layout.addWidget(self._build_report_button(), 0)
        left_layout.addStretch(1)

        # 右侧模型视图
        right = self._build_inp_view_panel()
        center_layout.addWidget(right, 4)

    # ---------------- 右侧 INP 图层 ----------------
    def _build_inp_view_panel(self) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #b9c6d6; }")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        title = QLabel("三维模型（INP线框预览）")
        title.setStyleSheet("font-weight: bold; color: #1d2b3a;")
        lay.addWidget(title, 0)

        self.inp_view = InpWireframeView()
        self.inp_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.inp_view, 1)
        return frame

    def _autoload_inp_to_view(self):
        here = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(os.getcwd(), "upload", "demo_platform_jacket.inp"),
            os.path.join(os.getcwd(), "pict", "demo_platform_jacket.inp"),
            os.path.normpath(os.path.join(here, "..", "upload", "demo_platform_jacket.inp")),
            os.path.normpath(os.path.join(here, "..", "pict", "demo_platform_jacket.inp")),
            os.path.join(os.getcwd(), "demo_platform_jacket.inp"),
        ]
        path = next((p for p in candidates if os.path.exists(p)), "")
        if not path:
            self.inp_view.clear_view("未找到 INP：demo_platform_jacket.inp\n请放到 upload/ 或 pict/ 目录")
            return
        try:
            self.inp_view.load_inp(path)
        except Exception as e:
            self.inp_view.clear_view(f"INP 加载失败：\n{e}")

    # ---------------- 表格通用样式 ----------------
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

    def _set_cell(self, table: QTableWidget, r: int, c: int, text: str, bg: QColor = None, bold: bool = False, align_center: bool = True):
        it = QTableWidgetItem(str(text))
        if align_center:
            it.setTextAlignment(Qt.AlignCenter)
        if bg is not None:
            it.setBackground(QBrush(bg))
        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)
        table.setItem(r, c, it)
        return it

    def _auto_fit_columns(self, table: QTableWidget, padding: int = 20, min_w: int = 50):
        fm = QFontMetrics(table.font())
        for c in range(table.columnCount()):
            max_w = min_w
            for r in range(table.rowCount()):
                it = table.item(r, c)
                if it is None:
                    continue
                txt = it.text().replace("\n", " ")
                max_w = max(max_w, fm.horizontalAdvance(txt) + padding)
            table.setColumnWidth(c, max_w)

    # ---------------- 上方 快速评估汇总信息表 ----------------
    def _build_summary_table(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        # 1 行标题 + 1 行表头 + 5 行数据
        rows = 1 + 1 + 7
        cols = 5
        self.tbl_summary = QTableWidget(rows, cols)
        self._init_table_common(self.tbl_summary)

        # 标题行
        self.tbl_summary.setSpan(0, 0, 1, cols)
        self._set_cell(self.tbl_summary, 0, 0, "快速评估汇总信息", bg=self.TITLE_BG, bold=True)

        headers = ["核校内容", "构件名称", "最大（最小） UC值", "对应工况", "是否满足"]
        for c, h in enumerate(headers):
            self._set_cell(self.tbl_summary, 1, c, h, bg=self.HDR_BG, bold=True)

        # 数据行（与原型图可见内容一致）
        items = [
            "构件",
            "节点冲剪",
            "桩应力",
            "桩承载力操作抗压",
            "桩承载力操作抗拔",
            "桩承载能力极端抗压",
            "桩承载能力极端抗拔"
        ]
        for i, name in enumerate(items):
            r = 2 + i
            self._set_cell(self.tbl_summary, r, 0, name, bg=self.HDR_BG, bold=False, align_center=False)
            self._set_cell(self.tbl_summary, r, 1, "", bg=None)
            self._set_cell(self.tbl_summary, r, 2, "", bg=None)
            self._set_cell(self.tbl_summary, r, 3, "", bg=None)
            self._set_cell(self.tbl_summary, r, 4, "", bg=None)

        # 列宽粗调
        self.tbl_summary.setColumnWidth(0, 140)
        self.tbl_summary.setColumnWidth(1, 120)
        self.tbl_summary.setColumnWidth(2, 120)
        self.tbl_summary.setColumnWidth(3, 90)
        self.tbl_summary.setColumnWidth(4, 90)
        self.tbl_summary.setRowHeight(0, 26)
        for r in range(1, rows):
            self.tbl_summary.setRowHeight(r, 26)

        lay.addWidget(self.tbl_summary, 0)
        return box

    # ---------------- 下方详情区（标签 + 详情表） ----------------
    def _build_detail_section(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        # 标签条
        tab_bar = QWidget()
        tab_lay = QHBoxLayout(tab_bar)
        tab_lay.setContentsMargins(0, 0, 0, 0)
        tab_lay.setSpacing(0)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)

        tabs = ["构件", "节点冲剪", "桩应力", "桩承载力操作抗压"]
        for t in tabs:
            btn = QPushButton(t)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setStyleSheet("""
                QPushButton {
                    background: #dfead2;
                    border: 1px solid #3b3b3b;
                    border-right: none;
                    padding: 0 14px;
                    font-weight: bold;
                }
                QPushButton:checked {
                    background: #cfe4b5;
                }
            """)
            self.tab_group.addButton(btn)
            tab_lay.addWidget(btn)
            if t == self.current_tab:
                btn.setChecked(True)

        # 末尾补上右边框
        spacer = QWidget()
        spacer.setStyleSheet("border: 1px solid #3b3b3b; border-left:none; background:#dfead2;")
        spacer.setFixedHeight(26)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tab_lay.addWidget(spacer, 1)

        self.tab_group.buttonClicked.connect(self._on_tab_clicked)
        lay.addWidget(tab_bar, 0)

        # 详情表：1 行标题 + 1 行表头 + 4 行数据（与原型显示一致）
        rows = 1 + 1 + 4
        cols = 5
        self.tbl_detail = QTableWidget(rows, cols)
        self._init_table_common(self.tbl_detail)

        # 标题行
        self.tbl_detail.setSpan(0, 0, 1, cols)
        self._set_cell(self.tbl_detail, 0, 0, "快速评估信息", bg=self.TITLE_BG, bold=True)

        headers = ["序号", "构件名称", "最大（最小） UC值", "对应工况", "是否满足"]
        for c, h in enumerate(headers):
            self._set_cell(self.tbl_detail, 1, c, h, bg=self.HDR_BG, bold=True)

        for i in range(4):
            r = 2 + i
            self._set_cell(self.tbl_detail, r, 0, str(i + 1), bg=self.INDEX_BG, bold=False)
            self._set_cell(self.tbl_detail, r, 1, "", bg=None, align_center=False)
            self._set_cell(self.tbl_detail, r, 2, "", bg=None)
            self._set_cell(self.tbl_detail, r, 3, "", bg=None)
            self._set_cell(self.tbl_detail, r, 4, "", bg=None)

        # 列宽与行高
        self.tbl_detail.setColumnWidth(0, 60)
        self.tbl_detail.setColumnWidth(1, 160)
        self.tbl_detail.setColumnWidth(2, 140)
        self.tbl_detail.setColumnWidth(3, 100)
        self.tbl_detail.setColumnWidth(4, 100)
        for r in range(rows):
            self.tbl_detail.setRowHeight(r, 26)

        lay.addWidget(self.tbl_detail, 0)

        return box

    # -------------------按钮事件--------------------
    def _on_tab_clicked(self, btn: QPushButton):
        self.current_tab = btn.text().strip()
        # 当前仅做占位：清空数据区，后续接入解析结果后按 tab 填充
        for r in range(2, self.tbl_detail.rowCount()):
            for c in range(1, self.tbl_detail.columnCount()):
                it = self.tbl_detail.item(r, c)
                if it is not None:
                    it.setText("")
        # 也可在这里更新标题/其它内容（原型标题不变，所以不改）

    # ---------------- 生成报告按钮 ----------------
    def _build_report_button(self) -> QWidget:
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        btn = QPushButton("生成评估报告")
        btn.setFixedHeight(44)
        btn.setMinimumWidth(220)
        btn.setStyleSheet("""
            QPushButton {
                background: #2aa9df;
                border: 2px solid #1b2a3a;
                border-radius: 6px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover { background: #4bbbe8; }
        """)
        btn.clicked.connect(self._on_generate_report)

        lay.addWidget(btn, 0, Qt.AlignLeft)
        lay.addStretch(1)
        return wrap

    def _on_generate_report(self):
        QMessageBox.information(self, "生成评估报告", "已点击“生成评估报告”。\n\n后续可在此处按你定义的格式生成报告文件（Word/PDF/Excel）。")
