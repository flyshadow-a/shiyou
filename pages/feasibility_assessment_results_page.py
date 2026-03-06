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
    QStackedWidget,
    QComboBox,
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

        # left_layout.addWidget(self._build_summary_table(), 0)
        # left_layout.addWidget(self._build_detail_section(), 0)
        # left_layout.addWidget(self._build_report_button(), 0)
        # left_layout.addStretch(1)

        # ========== 替换为新代码 ==========
        left_layout.addWidget(self._build_summary_table(), 0)

        # 将权重改为 1，让详情区（第二个表格及标签）像海绵一样吸满剩余的所有纵向空间
        left_layout.addWidget(self._build_detail_section(), 1)

        left_layout.addWidget(self._build_report_button(), 0)


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
            os.path.join(os.getcwd(), "data", "demo_platform_jacket.inp"),
            os.path.join(os.getcwd(), "upload", "demo_platform_jacket.inp"),
            os.path.normpath(os.path.join(here, "..", "data", "demo_platform_jacket.inp")),
            os.path.normpath(os.path.join(here, "..", "upload", "demo_platform_jacket.inp")),
            os.path.join(os.getcwd(), "demo_platform_jacket.inp"),
        ]
        path = next((p for p in candidates if os.path.exists(p)), "")
        if not path:
            self.inp_view.clear_view("未找到 INP：demo_platform_jacket.inp\n请放到 data/ 或 upload/ 目录")
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
        # table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        table.verticalHeader().setDefaultSectionSize(26)

    # 设置单元格内容
    def _set_cell(self, table: QTableWidget, r: int, c: int, text: str, bg: QColor = None, bold: bool = False, align_center: bool = True, editable: bool = True):
        it = QTableWidgetItem(str(text))
        if align_center:
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
        self._set_cell(self.tbl_summary, 0, 0, "快速评估汇总信息", bg=self.TITLE_BG, bold=True, editable=False)

        headers = ["核校内容", "构件名称", "最大（最小） UC值", "对应工况", "是否满足"]
        for c, h in enumerate(headers):
            self._set_cell(self.tbl_summary, 1, c, h, bg=self.HDR_BG, bold=True, editable=False)

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
            self._set_cell(self.tbl_summary, r, 0, name, bg=self.HDR_BG, bold=False, align_center=False, editable=False)
            self._set_cell(self.tbl_summary, r, 1, "", bg=None)
            self._set_cell(self.tbl_summary, r, 2, "", bg=None)
            self._set_cell(self.tbl_summary, r, 3, "", bg=None)
            self._set_cell(self.tbl_summary, r, 4, "", bg=None)

            # ====== 列宽自适应与滚动条终极策略 ======
            # 1. 明确开启：内容超出时显示横向滚动条
            self.tbl_summary.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            # 2. 核心：让 Qt 引擎根据实际文字内容，精准计算每一列所需的最小像素
            self.tbl_summary.resizeColumnsToContents()

            header = self.tbl_summary.horizontalHeader()
            for c in range(cols):
                # 3. 设为 Interactive 模式，允许滚动条生效，也允许用户鼠标拖拽调整列宽
                header.setSectionResizeMode(c, QHeaderView.Interactive)

                # 4. 获取系统刚算出的完美宽度，并加上 30 像素的安全留白，彻底告别省略号
                ideal_width = self.tbl_summary.columnWidth(c)
                # 设置列宽，并给一个 100 的下限保底
                self.tbl_summary.setColumnWidth(c, max(100, ideal_width + 30))

            # 5. 让最后一列自动拉伸，填补窗口放大时右侧的灰色空白区域
            header.setStretchLastSection(True)
            # =======================================

        # self.tbl_summary.setRowHeight(0, 26)
        # for r in range(1, rows):
        #     self.tbl_summary.setRowHeight(r, 26)
        #
        # lay.addWidget(self.tbl_summary, 0)
            # ========== 替换为新代码 ==========
        self.tbl_summary.setRowHeight(0, 26)
        for r in range(1, rows):
            self.tbl_summary.setRowHeight(r, 26)

        # 核心：精准计算包含所有行的总像素高度，彻底锁死并关闭其专属的纵向滚动条
        total_h = sum(self.tbl_summary.rowHeight(r) for r in range(rows))
        self.tbl_summary.setFixedHeight(total_h + 4)  # +4 像素留给上下边框
        self.tbl_summary.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

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
        tab_lay.setSpacing(0)  # 【关键点1】强制设置布局内元素间距为 0

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)

        tabs = ["构件", "节点冲剪", "桩应力", "桩承载力操作抗压"]

        # 准备堆叠容器存放不同的表格 (保留你之前的 QStackedWidget 逻辑)
        self.table_stack = QStackedWidget()
        self.detail_tables = {}

        for i, t in enumerate(tabs):
            btn = QPushButton(t)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            # 【修改点】：根据文字的实际绘制长度动态分配宽度，外加 30 像素的留白
            text_width = btn.fontMetrics().horizontalAdvance(t)
            btn.setMinimumWidth(text_width + 30)
            # 【关键点2】样式中必须有 border-right: none; 这样按钮才能无缝拼接，且中间边框不会变粗
            btn.setStyleSheet("""
                        QPushButton {
                            background: #dfead2;
                            border: 1px solid #3b3b3b;
                            border-right: none;  /* 隐藏右边框 */
                            padding: 0 14px;
                            font-weight: bold;
                        }
                        QPushButton:checked {
                            background: #cfe4b5;
                        }
                    """)
            self.tab_group.addButton(btn, i)
            tab_lay.addWidget(btn)

            # (保留你之前的表格创建逻辑)
            tbl = self._create_single_detail_table(t)
            self.table_stack.addWidget(tbl)
            self.detail_tables[t] = tbl

            if t == self.current_tab:
                btn.setChecked(True)
                self.table_stack.setCurrentIndex(i)

        # 【关键点3】因为所有按钮都没了右边框，末尾必须加一个固定大小的块来“封口”
        spacer = QWidget()
        spacer.setStyleSheet("border: 1px solid #3b3b3b; border-left:none; background:#dfead2;")
        spacer.setFixedSize(30, 26)  # 宽度30（可调），高度和按钮保持一致
        tab_lay.addWidget(spacer)

        # 【关键点4】在最右侧增加弹簧。它会吸收所有剩余的空白空间，将左侧的所有按钮紧紧地向左挤压
        tab_lay.addStretch(1)

        # ====== 新增：右侧“显示行数”控件 ======
        lbl_rows = QLabel("显示行数：")
        lbl_rows.setStyleSheet("font-size: 13px; color: #333; font-weight: bold;")
        tab_lay.addWidget(lbl_rows, 0)

        self.cb_row_limit = QComboBox()
        self.cb_row_limit.addItems(["10", "20", "50", "100", "全部"])
        self.cb_row_limit.setFixedHeight(24)
        self.cb_row_limit.setStyleSheet("""
                    QComboBox {
                        border: 1px solid #b9c6d6;
                        border-radius: 3px;
                        padding: 1px 10px 1px 5px;
                        background: #ffffff;
                        min-width: 60px;
                    }
                """)
        # 绑定下拉框值改变的信号
        self.cb_row_limit.currentTextChanged.connect(self._on_row_limit_changed)
        tab_lay.addWidget(self.cb_row_limit, 0)
        # ====================================

        self.tab_group.buttonClicked.connect(self._on_tab_clicked)
        lay.addWidget(tab_bar, 0)

        lay.addWidget(self.table_stack, 1)

        # 初始化完毕后，触发一次表格行数渲染
        self._update_current_table_rows()

        return box

    def _create_single_detail_table(self, tab_name: str) -> QTableWidget:
        """为每一个标签页生成一个独立的、自适应列宽的表格基础框架"""
        cols = 5
        # 初始只创建 2 行（标题行 + 表头行），数据行留给动态方法生成
        tbl = QTableWidget(2, cols)
        self._init_table_common(tbl)

        tbl.setSpan(0, 0, 1, cols)
        self._set_cell(tbl, 0, 0, f"{tab_name} - 快速评估信息", bg=self.TITLE_BG, bold=True, editable=False)

        headers = ["序号", "构件名称", "最大（最小） UC值", "对应工况", "是否满足"]
        for c, h in enumerate(headers):
            self._set_cell(tbl, 1, c, h, bg=self.HDR_BG, bold=True, editable=False)

            # ====== 列宽自适应与滚动条终极策略 ======
            tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            tbl.resizeColumnsToContents()

            header = tbl.horizontalHeader()
            for c in range(cols):
                header.setSectionResizeMode(c, QHeaderView.Interactive)
                ideal_width = tbl.columnWidth(c)
                tbl.setColumnWidth(c, max(100, ideal_width + 30))

            header.setStretchLastSection(True)
            # =======================================

        tbl.setRowHeight(0, 26)
        tbl.setRowHeight(1, 26)

        return tbl

    # ------------------- 表格行数控制与事件 --------------------
    def _update_current_table_rows(self):
        """根据下拉框的值，动态调整当前显示表格的行数并填充空单元格"""
        limit_text = self.cb_row_limit.currentText()
        if limit_text == "全部":
            limit = 200  # UI占位：假设"全部"对应200行测试数据
        else:
            limit = int(limit_text)

        # 获取当前正在显示的表格
        idx = self.table_stack.currentIndex()
        if idx == -1: return
        current_tbl = self.table_stack.widget(idx)

        # 目标总行数 = 2行表头 + 数据行
        target_rows = 2 + limit
        current_tbl.setRowCount(target_rows)

        # 补充新增出来的行数据（如果是减少行数，setRowCount 会自动截断）
        for i in range(limit):
            r = 2 + i
            current_tbl.setRowHeight(r, 26)

            # 判断第0列（序号）是否为空，为空说明是新生成的行，需要初始化格式
            if current_tbl.item(r, 0) is None:
                self._set_cell(current_tbl, r, 0, str(i + 1), bg=self.INDEX_BG, bold=False, editable=False)
                self._set_cell(current_tbl, r, 1, "", bg=None, align_center=False)
                self._set_cell(current_tbl, r, 2, "", bg=None)
                self._set_cell(current_tbl, r, 3, "", bg=None)
                self._set_cell(current_tbl, r, 4, "", bg=None)

    def _on_row_limit_changed(self, text):
        """下拉框数值改变时触发"""
        self._update_current_table_rows()

    def _on_tab_clicked(self, btn: QPushButton):
        """点击标签页切换时触发"""
        self.current_tab = btn.text().strip()
        idx = self.tab_group.id(btn)
        if idx != -1:
            self.table_stack.setCurrentIndex(idx)
            # 切换表格后，确保新表格的行数也和右上角的下拉框保持一致
            self._update_current_table_rows()

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
