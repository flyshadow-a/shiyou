# -*- coding: utf-8 -*-
# pages/platform_strength_page.py

import os
from typing import Dict, List, Tuple

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QFontMetrics, QColor, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QWidget,
    QLineEdit,
    QScrollArea,
    QGraphicsView,
    QGraphicsScene,
)

from base_page import BasePage
from dropdown_bar import DropdownBar


class InpWireframeView(QGraphicsView):
    """
    用 QGraphicsScene 渲染 Abaqus .inp（*NODE + *ELEMENT）线框的 2D 投影。
    说明：这是“先能看见”的简化显示，不是完整三维交互渲染。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(self.renderHints())
        self.setStyleSheet("background:#0b0f14; border: 1px solid #2f3a4a;")
        self.setFrameShape(QFrame.NoFrame)
        self.setAlignment(Qt.AlignCenter)

        self._nodes: Dict[int, Tuple[float, float, float]] = {}
        self._edges: List[Tuple[int, int]] = []
        self._proj_pts: Dict[int, Tuple[float, float]] = {}
        self._loaded_path: str = ""

    def clear_view(self, message: str = ""):
        self.scene().clear()
        self._nodes = {}
        self._edges = []
        self._proj_pts = {}
        self._loaded_path = ""

        if message:
            t = self.scene().addText(message)
            t.setDefaultTextColor(QColor("#d7e3f0"))
            # center later in resizeEvent
            self._center_text_item(t)

    def load_inp(self, file_path: str):
        self._loaded_path = file_path
        nodes, edges = self._parse_inp_nodes_elements(file_path)
        self._nodes = nodes
        self._edges = edges

        if not self._nodes or not self._edges:
            self.clear_view("未解析到 NODE/ELEMENT 数据")
            return

        self._render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 窗口变化时重新拟合
        if self._nodes and self._edges:
            self._render()
        else:
            # 让提示文字居中
            for it in self.scene().items():
                if hasattr(it, "toPlainText"):
                    self._center_text_item(it)

    def _center_text_item(self, item):
        br = item.boundingRect()
        w = max(10, self.viewport().width())
        h = max(10, self.viewport().height())
        item.setPos((w - br.width()) / 2, (h - br.height()) / 2)

    # --------- 渲染（2D 投影） ----------
    def _render(self):
        self.scene().clear()

        # 1) 投影：等轴测（可按需调参）
        # x2d = (x - y)
        # y2d = (x + y) * 0.5 - z * z_scale
        z_scale = 0.9
        proj = {}
        xs, ys = [], []
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

        # 2) 拟合到视口
        vw = max(10, self.viewport().width())
        vh = max(10, self.viewport().height())
        margin = 20
        sx = (vw - 2 * margin) / spanx
        sy = (vh - 2 * margin) / spany
        s = max(0.1, min(sx, sy))

        # 将模型中心移到视口中心
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0
        vx = vw / 2.0
        vy = vh / 2.0

        def map_pt(p):
            x, y = p
            return (vx + (x - cx) * s, vy + (y - cy) * s)

        self._proj_pts = {nid: map_pt(p) for nid, p in proj.items()}

        # 3) 画线
        pen = QPen(QColor("#62ff62"))
        pen.setWidth(1)

        for n1, n2 in self._edges:
            p1 = self._proj_pts.get(n1)
            p2 = self._proj_pts.get(n2)
            if p1 is None or p2 is None:
                continue
            self.scene().addLine(p1[0], p1[1], p2[0], p2[1], pen)

        # 4) 设置 sceneRect 以便 view 正常工作
        self.scene().setSceneRect(QRectF(0, 0, vw, vh))

    # --------- INP 解析 ----------
    def _parse_inp_nodes_elements(self, file_path: str):
        """
        解析：
        - *NODE: id, x, y, z
        - *ELEMENT: 取前两个节点作为线段（适配 B31/beam/2节点单元的可视化）
        """
        nodes: Dict[int, Tuple[float, float, float]] = {}
        edges: List[Tuple[int, int]] = []

        in_node = False
        in_elem = False

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("**"):
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
                        x = float(parts[1])
                        y = float(parts[2])
                        z = float(parts[3])
                    except Exception:
                        continue
                    nodes[nid] = (x, y, z)
                    continue

                if in_elem:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 3:
                        continue
                    try:
                        # eid = int(float(parts[0]))  # 不需要
                        n1 = int(float(parts[1]))
                        n2 = int(float(parts[2]))
                    except Exception:
                        continue
                    edges.append((n1, n2))
                    continue

        return nodes, edges


class PlatformStrengthPage(BasePage):
    """
    菜单：结构强度 -> 平台强度

    需求实现：
    1) 右侧图层：直接显示 INP 文件线框（无需任何按钮/点击）
    2) “是否水平”行：点击单元格在 ✓/× 之间切换（避免用户输入）
    """

    def __init__(self, main_window, parent=None):
        if parent is None:
            parent = main_window
        super().__init__("", parent)
        self.main_window = main_window

        self._build_ui()
        self._autoload_inp_to_view()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # ---------- 顶部下拉条（同平台基本信息） ----------
        fields = [
            {"key": "branch", "label": "分公司", "options": ["湛江分公司"], "default": "湛江分公司"},
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

        # ---------- 中部：左右分栏 ----------
        center = QWidget()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(8, 0, 8, 8)
        center_layout.setSpacing(10)
        self.main_layout.addWidget(center, 1)

        # 左侧（滚动）：结构模型信息 + 三个标签表格
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        center_layout.addWidget(left_scroll, 6)

        left_container = QWidget()
        left_scroll.setWidget(left_container)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self._build_structure_model_box(left_layout)
        self._build_left_tables(left_layout)
        left_layout.addStretch(1)

        # 右侧：INP 线框视图（自动加载）
        right = self._build_inp_view_panel()
        center_layout.addWidget(right, 4)

    # ---------------- 右侧 INP 视图 ----------------
    def _build_inp_view_panel(self) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame { background: #ffffff; border: 1px solid #b9c6d6; }
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        title = QLabel("INP 模型线框预览（自动加载）")
        title.setStyleSheet("font-weight: bold; color: #1d2b3a;")
        lay.addWidget(title, 0)

        self.inp_view = InpWireframeView()
        self.inp_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.inp_view, 1)

        return frame

    def _autoload_inp_to_view(self):
        """
        自动加载示例/默认 INP。
        你只需要把文件放到项目目录的以下任一位置（优先级从高到低）：
        1) upload/demo_platform_jacket.inp
        2) pict/demo_platform_jacket.inp
        3) pages/../upload/demo_platform_jacket.inp
        4) pages/../pict/demo_platform_jacket.inp
        5) 当前运行目录下的 demo_platform_jacket.inp
        """
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

    # ---------------- 结构模型信息（含表格✓/×点击切换） ----------------
    def _build_structure_model_box(self, left_layout: QVBoxLayout):
        box = QGroupBox("结构模型信息")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(10, 8, 10, 10)
        box_layout.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        lab_mud = QLabel("泥面高度")
        lab_mud.setFixedWidth(90)
        self.edt_mud_level = QLineEdit()
        self.edt_mud_level.setText("-122.4")
        self.edt_mud_level.setMaximumWidth(140)
        row1.addWidget(lab_mud)
        row1.addWidget(self.edt_mud_level)
        row1.addStretch(1)
        box_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        lab_limit = QLabel("水平台层节点数量限制")
        lab_limit.setFixedWidth(140)
        self.edt_node_limit = QLineEdit()
        self.edt_node_limit.setText("40")
        self.edt_node_limit.setMaximumWidth(140)
        row2.addWidget(lab_limit)
        row2.addWidget(self.edt_node_limit)
        row2.addStretch(1)
        box_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        lab_layers = QLabel("水平台层高程")
        lab_layers.setFixedWidth(90)
        row3.addWidget(lab_layers)
        row3.addStretch(1)
        box_layout.addLayout(row3)

        self.tbl_layers = QTableWidget(3, 10, box)
        self.tbl_layers.setFocusPolicy(Qt.NoFocus)
        self.tbl_layers.setHorizontalHeaderLabels(["编号"] + [str(i) for i in range(1, 10)])
        self._init_table_common(self.tbl_layers, show_vertical_header=False)
        self.tbl_layers.setRowCount(3)
        self.tbl_layers.setVerticalHeaderLabels(["Z(m)", "节点数量", "是否水平"])

        self._set_center_item(self.tbl_layers, 0, 0, "Z(m)")
        self._set_center_item(self.tbl_layers, 1, 0, "节点数量")
        self._set_center_item(self.tbl_layers, 2, 0, "是否水平")

        demo_z = ["36", "31", "27", "23", "18", "7", "", "", ""]
        demo_n = ["1", "412", "191", "456", "289", "85", "74", "62", ""]
        demo_h = ["✓", "✓", "✓", "✓", "✓", "✓", "✓", "✓", ""]
        for i in range(9):
            self._set_center_item(self.tbl_layers, 0, i + 1, demo_z[i])
            self._set_center_item(self.tbl_layers, 1, i + 1, demo_n[i])
            self._set_center_item(self.tbl_layers, 2, i + 1, demo_h[i])

        # “是否水平”行：点击切换 ✓/×，不允许直接编辑
        for col in range(1, 10):
            it = self.tbl_layers.item(2, col)
            if it is None:
                it = QTableWidgetItem("")
                it.setTextAlignment(Qt.AlignCenter)
                self.tbl_layers.setItem(2, col, it)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        self.tbl_layers.cellClicked.connect(self._on_layers_cell_clicked)

        self._auto_fit_columns_with_padding(self.tbl_layers, padding=28)
        box_layout.addWidget(self.tbl_layers, 0)

        left_layout.addWidget(box)

    def _on_layers_cell_clicked(self, row: int, col: int):
        if row != 2 or col < 1:
            return
        it = self.tbl_layers.item(row, col)
        if it is None:
            it = QTableWidgetItem("")
            it.setTextAlignment(Qt.AlignCenter)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.tbl_layers.setItem(row, col, it)

        cur = (it.text() or "").strip()
        it.setText("×" if cur == "✓" else "✓")
        self.tbl_layers.clearSelection()

    # ---------------- 表格风格（同平台基本信息） ----------------
    def _init_table_common(self, table: QTableWidget, show_vertical_header: bool):
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

        table.verticalHeader().setVisible(bool(show_vertical_header))
        table.horizontalHeader().setVisible(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setDefaultSectionSize(28)

    def _set_center_item(self, table: QTableWidget, row: int, col: int, text: str):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)

    def _auto_fit_columns_with_padding(self, table: QTableWidget, padding: int = 30):
        fm = QFontMetrics(table.font())
        cols = table.columnCount()
        for c in range(cols):
            max_w = 40
            header = table.horizontalHeaderItem(c)
            if header is not None:
                max_w = max(max_w, fm.horizontalAdvance(header.text()) + padding)

            for r in range(table.rowCount()):
                it = table.item(r, c)
                if it is None:
                    continue
                max_w = max(max_w, fm.horizontalAdvance(it.text()) + padding)

            table.setColumnWidth(c, max_w)

    # ---------------- 其余三个表（保持与之前一致） ----------------
    def _build_left_tables(self, left_layout: QVBoxLayout):
        # 飞溅区腐蚀余量
        splash_box = QGroupBox("飞溅区腐蚀余量")
        splash_layout = QVBoxLayout(splash_box)
        splash_layout.setContentsMargins(8, 6, 8, 8)

        tbl_splash = QTableWidget(1, 3, splash_box)
        tbl_splash.setHorizontalHeaderLabels(["飞溅区上限 (m)", "飞溅区下限 (m)", "腐蚀余量 (mm/y)"])
        self._init_table_common(tbl_splash, show_vertical_header=False)
        self._set_center_item(tbl_splash, 0, 0, "8.54")
        self._set_center_item(tbl_splash, 0, 1, "3.75")
        self._set_center_item(tbl_splash, 0, 2, "7.5")
        splash_layout.addWidget(tbl_splash)
        left_layout.addWidget(splash_box)

        # 桩基信息
        pile_box = QGroupBox("桩基信息")
        pile_layout = QVBoxLayout(pile_box)
        pile_layout.setContentsMargins(8, 6, 8, 8)

        tbl_pile = QTableWidget(1, 4, pile_box)
        tbl_pile.setHorizontalHeaderLabels(["基础冲刷(m)", "桩基础抗压承载能力(t)", "桩基础抗拔承载能力(t)", "单根桩泥下自重(t)"])
        self._init_table_common(tbl_pile, show_vertical_header=False)
        for c in range(4):
            self._set_center_item(tbl_pile, 0, c, "")
        pile_layout.addWidget(tbl_pile)
        left_layout.addWidget(pile_box)

        # 海生物信息（示意）
        marine_box = QGroupBox("海生物信息")
        marine_layout = QVBoxLayout(marine_box)
        marine_layout.setContentsMargins(8, 6, 8, 8)

        tbl_marine = QTableWidget(5, 12, marine_box)
        self._init_table_common(tbl_marine, show_vertical_header=False)
        tbl_marine.horizontalHeader().setVisible(False)
        tbl_marine.verticalHeader().setVisible(False)

        # 第一行
        tbl_marine.setSpan(0, 0, 1, 3)
        self._set_center_item(tbl_marine, 0, 0, "层数")
        for i in range(9):
            self._set_center_item(tbl_marine, 0, 3 + i, str(i + 1))

        # 第二行
        tbl_marine.setSpan(1, 0, 2, 2)
        self._set_center_item(tbl_marine, 1, 0, "高度区域")
        self._set_center_item(tbl_marine, 1, 2, "上限(m)")
        self._set_center_item(tbl_marine, 2, 2, "下限(m)")

        upper = ["0", "-15", "-30", "-50", "-60", "-70", "-80", "-95", "-110"]
        lower = ["-15", "-30", "-50", "-60", "-70", "-80", "-95", "-110", "-122"]
        for i in range(9):
            self._set_center_item(tbl_marine, 1, 3 + i, upper[i])
            self._set_center_item(tbl_marine, 2, 3 + i, lower[i])

        # 第三行（合并了三、四行）
        tbl_marine.setSpan(3, 0, 1, 2)
        self._set_center_item(tbl_marine, 3, 0, "海生物")
        self._set_center_item(tbl_marine, 3, 2, "厚度(mm)")
        thickness = ["10", "10", "10", "4.5", "4.5", "4.5", "4", "4", "4"]
        for i in range(9):
            self._set_center_item(tbl_marine, 3, 3 + i, thickness[i])
        self._set_center_item(tbl_marine, 3, 11, "1.4")

        # 第5行
        tbl_marine.setSpan(4, 0, 1, 3)
        tbl_marine.setSpan(4, 3, 1, 9)
        self._set_center_item(tbl_marine, 4, 0, "海生物密度（t/m^2）")
        self._set_center_item(tbl_marine, 4, 3, "1.4")

        marine_layout.addWidget(tbl_marine)
        left_layout.addWidget(marine_box)
