# -*- coding: utf-8 -*-
# pages/upgrade_special_inspection_result_page.py

from typing import Any
import re
import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QComboBox, QTabWidget, QSizePolicy, QMessageBox, QSlider, QApplication, QProgressDialog
)
from PyQt5.QtCore import Qt, QTimer, QProcess, QProcessEnvironment, QUrl
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QDesktopServices

from core.base_page import BasePage
from services.special_strategy_services import NodeYearLabelMapper, SpecialStrategyResultService
from pages.sacs_elevation_risk_view import SacsElevationRiskView
from services.special_strategy_inspection_overlay_service import load_strategy_inspection_overlay
from services.special_strategy_image_service import build_strategy_image_path, save_strategy_image_record

NODE_SUMMARY_DISPLAY_LABELS = ["当前", "+5年", "+10年", "+15年", "+20年", "+25年"]
NODE_SUMMARY_CONTEXT_MAP = {
    "当前": "当前",
    "+5年": "第5年",
    "+10年": "第10年",
    "+15年": "第15年",
    "+20年": "第20年",
    "+25年": "第25年",
}


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
    COMPONENT_SUMMARY_LABELS = ["构件"]
    NODE_SUMMARY_LABELS = ["当前", "第5年", "第10年", "第15年", "第20年", "第25年"]

    # 汇总颜色条（红、橙、黄、蓝、棕）
    RISK_COLORS = [
        QColor("#ff3b30"),
        QColor("#ffcc00"),
        QColor("#ffee58"),
        QColor("#1e88e5"),
        QColor("#6d4c41"),
    ]
    RISK_LABELS = ["一", "二", "三", "四", "五"]

    def _sync_dynamic_row_combo_from_view(self):
        if not hasattr(self, "row_combo") or not hasattr(self, "elevation_view"):
            return

        options = self.elevation_view.available_row_names()
        if not options:
            return

        current = self.row_combo.currentText().strip()
        old_options = [self.row_combo.itemText(i) for i in range(self.row_combo.count())]

        self.row_combo.blockSignals(True)
        try:
            if old_options != options:
                self.row_combo.clear()
                self.row_combo.addItems(options)

            if current in options:
                self.row_combo.setCurrentText(current)
            else:
                self.row_combo.setCurrentText(options[0])
        finally:
            self.row_combo.blockSignals(False)

    def _on_row_changed(self, _row_text: str):
        self._refresh_elevation_view()

    def _on_year_changed(self, year: str):
        self.current_year = (year or "").strip() or self._year_mapper.default_display_label()
        try:
            self._overlay_bundle = load_strategy_inspection_overlay(
                self.facility_code,
                run_id=self.run_id,
                display_year=self.current_year,
            )
        except Exception as exc:
            print("[UpgradeSpecialInspectionResultPage] load overlay failed:", exc)
            self._overlay_bundle = {}

        self._refresh_elevation_view()

    def __init__(self, facility_code: str, parent=None, run_id: int | None = None):
        self.facility_code = facility_code
        self.run_id = run_id
        self._result_service = SpecialStrategyResultService()
        self._year_mapper = NodeYearLabelMapper()

        # 这些状态必须先初始化
        self.current_year = self._year_mapper.default_display_label()
        self._overlay_bundle = {}
        self._result_bundle = {}
        self._batch_exported_keys = set()

        super().__init__("", parent)

        # 后台分步导出图片：每次只处理一张，避免一次性批量保存时卡死界面。
        self._export_timer = QTimer(self)
        self._export_timer.setInterval(10)
        self._export_timer.timeout.connect(self._process_next_export_task)
        self._export_tasks = []
        self._export_index = 0
        self._export_total = 0
        self._export_view = None
        self._export_context = None
        self._export_key = None

        # 生成报告时使用独立子进程：子进程负责“导出图片 + 生成报告”，主界面不直接执行重任务，避免闪退影响主程序。
        self._report_running = False
        self._report_export_process = None
        self._report_export_log: list[str] = []
        self._report_progress = None

        self._build_ui()
        self._load_result_data()

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget { 
                background: #e6eef7; 
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QFrame#Card { background: #e6eef7; border: 1px solid #c7d2e3; }

            QTabWidget::pane { border: 1px solid #4a4a4a; background: #e6eef7; }
            QTabBar::tab {
                background: #eaf2ff;
                border: 1px solid #4a4a4a;
                border-bottom: none;
                min-width: 150px;
                max-width: 150px;
                min-height: 34px;
                padding: 6px 18px;
                font-weight: bold;
                font-size: 12pt;
            }

            QTabBar::tab:selected { background: #d6f0d0; }

            /* 表格（网格线明显） */
            QTableWidget {
                background: #ffffff;
                gridline-color: #d0d0d0;
                border: 1px solid #d0d0d0;
                font-size: 12pt;
            }
            QHeaderView::section {
                background: #f3f6fb;
                color: #000000;
                border: 1px solid #e6e6e6;
                padding: 4px 6px;
                font-weight: normal;
                font-size: 12pt;
            }

            QPushButton#ReportBtn {
                background: #00a0d6;
                color: black;
                border: 1px solid #0a5f7a;
                border-radius: 8px;
                min-height: 46px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton#ReportBtn:hover { background: #00b6f2; }
        """)

        # 整页滚动（内容多时滚轮可滚）
        card = QFrame()
        card.setObjectName("Card")
        self.main_layout.addWidget(card, 1)

        lay = QHBoxLayout(card)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        left_scroll = QScrollArea(card)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        left_panel = self._build_left()
        left_scroll.setWidget(left_panel)

        right_panel = self._build_right()
        right_panel.setMinimumWidth(660)
        right_panel.setMaximumWidth(720)
        right_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        lay.addWidget(left_scroll, 5)
        lay.addWidget(right_panel, 3)

    # ---------------- Left ----------------
    def _build_left(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(0)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        # 顶部：条数选择（10/20/50/100/全部）
        row_bar = QHBoxLayout()
        row_bar.setContentsMargins(0, 0, 0, 0)
        row_bar.setSpacing(6)
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
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setElideMode(Qt.ElideNone)
        self.tabs.tabBar().setUsesScrollButtons(False)
        self.tabs.setMinimumWidth(0)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        comp_wrap = QWidget()
        comp_l = QVBoxLayout(comp_wrap)
        comp_l.setContentsMargins(0, 0, 0, 0)
        comp_l.setSpacing(8)

        self.table_comp = self._make_detail_table(is_node=False)
        self.summary_comp = self._make_summary_table(self.COMPONENT_SUMMARY_LABELS)

        comp_l.addWidget(self.table_comp, 3)
        comp_l.addWidget(self.summary_comp, 2)

        node_wrap = QWidget()
        node_l = QVBoxLayout(node_wrap)
        node_l.setContentsMargins(0, 0, 0, 0)
        node_l.setSpacing(8)

        self.table_node = self._make_detail_table(is_node=True)
        self.summary_node = self._make_summary_table(self._year_mapper.display_labels())

        node_l.addWidget(self.table_node, 3)
        node_l.addWidget(self.summary_node, 2)

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
                "A", "B", "倒塌分析载荷系数Rm", "VR", "Pf", "失效概率等级",
                "构件风险等级",
            ]
        else:
            sub_headers = [
                "JointA", "JointB", "WeldType", "失效后果等级",
                "A", "B", "倒塌分析载荷系数Rm", "VR", "Pf", "失效概率等级",
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
        t.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        t.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 列宽：用 Stretch（和你现有实现一致）
        # t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # ---- row 0: group headers ----
        hdr_bg = QColor("#f3f6fb")
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

        # ====== 核心修复：列宽自适应与横向滚动条 ======
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        header = t.horizontalHeader()
        for c in range(cols):
            # 将所有列均设为根据内容自适应，包括最后一列“风险等级”
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)

        # 确保列宽不仅贴合内容，还留有最小安全边距
        t.resizeColumnsToContents()
        for c in range(cols):
            w = t.columnWidth(c)
            # 在自适应宽度基础上，强行再增加 10 像素的安全边距
            t.setColumnWidth(c, max(80, w + 10))

        # 禁用自动拉伸最后一列，以防破坏已计算好的宽度
        header.setStretchLastSection(True)
        # ============================================

        # row heights
        t.setRowHeight(0, 26)
        t.setRowHeight(1, 26)
        for r in range(2, t.rowCount()):
            t.setRowHeight(r, 24)

        # minimum height so it looks like the sample (scroll inside table)
        # fixed_height = t.frameWidth() * 2 + 2
        # fixed_height += t.rowHeight(0) + t.rowHeight(1)
        # fixed_height += 20 * 24
        # t.setFixedHeight(fixed_height)
        t.setMinimumHeight(420)

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

    def _set_detail_table_height(self, table: QTableWidget, visible_rows: int) -> None:
        display_rows = min(max(int(visible_rows), 15), 20)
        fixed_height = table.frameWidth() * 2 + 2
        fixed_height += table.rowHeight(0) + table.rowHeight(1)
        fixed_height += display_rows * 24
        if table.horizontalScrollBar().isVisible():
            fixed_height += table.horizontalScrollBar().height()
        table.setFixedHeight(fixed_height)

    # ---------------- Summary big table (tagged) ----------------
    def _make_summary_table(self, labels: list[str]) -> QTableWidget:
        """
        汇总表：顶部 1 行标签（合并单元格），下面每个年份 3 行：
        - 年份标签 + 风险等级颜色条
        - 数量
        - 占比
        """
        cols = 6  # 0: 标签列，1..5: 风险等级一~五
        rows = len(labels) * 4

        t = QTableWidget(rows, cols)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setVisible(False)
        t.setShowGrid(True)
        t.setGridStyle(Qt.SolidLine)
        t.setSelectionMode(QTableWidget.NoSelection)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.setStyleSheet("QTableWidget{background:#ffffff;}")

        # 取消滚动条以完全显示
        t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Tag row
        # t.setSpan(0, 0, 1, cols)
        tag_bg = QColor("#e3e7ef")
        green = QColor("#cfe6b8")
        for r, text in enumerate(labels):
            t.setSpan(r * 4, 0, 1, 6)
            self._set_cell(t, r * 4, 0, text, green, True)

        # Year blocks
        green = QColor("#cfe6b8")
        for i, _year in enumerate(labels):
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
            self._set_cell(t, base_r + 2, 0, "占比", QColor("#e3e7ef"), True)
            for k in range(5):
                self._set_cell(t, base_r + 2, 1 + k, "", None, False)

            # row heights
            t.setRowHeight(base_r, 26)
            t.setRowHeight(base_r + 1, 24)
            t.setRowHeight(base_r + 2, 24)

        t.setRowHeight(0, 26)

        # 动态计算表格实际需要的高度并固定死
        total_h = t.frameWidth() * 2 + 2
        for r in range(t.rowCount()):
            total_h += t.rowHeight(r)
        t.setMinimumHeight(total_h)
        t.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        t.setProperty("summary_labels", labels)
        return t

    # ---------------- Right ----------------
    def _build_right(self) -> QWidget:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        frame = QFrame()
        frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #b9c6d6; }")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame.setMinimumWidth(660)
        frame.setMaximumWidth(720)

        outer = QVBoxLayout(frame)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        title = QLabel("模型立面风险图")
        title.setStyleSheet("""
            color: #1d2b3a;
            font-weight: bold;
            font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
            font-size: 12pt;
        """)
        outer.addWidget(title, 0)

        # ===== 顶部选择区域 =====
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        lbl_row = QLabel("立面：")
        lbl_row.setStyleSheet('color:#1d2b3a; font-size:12pt;')

        self.row_combo = QComboBox()
        self.row_combo.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                border: 1px solid #b9c6d6;
                min-height: 28px;
                padding: 2px 8px;
                font-size: 12pt;
            }
        """)
        self.row_combo.addItems(["XZ 前"])
        self.row_combo.currentTextChanged.connect(self._on_row_changed)

        lbl_year = QLabel("年份：")
        lbl_year.setStyleSheet('color:#1d2b3a; font-size:12pt;')

        self.year_combo = QComboBox()
        self.year_combo.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                border: 1px solid #b9c6d6;
                min-height: 28px;
                padding: 2px 8px;
                font-size: 12pt;
            }
        """)
        self.year_combo.addItems(self._year_mapper.display_labels())
        self.year_combo.setCurrentText(self.current_year)
        self.year_combo.currentTextChanged.connect(self._on_year_changed)

        top_row.addWidget(lbl_row, 0)
        top_row.addWidget(self.row_combo, 0)
        top_row.addSpacing(12)
        top_row.addWidget(lbl_year, 0)
        top_row.addWidget(self.year_combo, 0)
        top_row.addStretch(1)
        outer.addLayout(top_row, 0)

        self.elevation_hint_label = QLabel("当前显示：立面轮廓图 + 检验等级；滚轮缩放，双击恢复初始视图。")
        self.elevation_hint_label.setWordWrap(False)
        self.elevation_hint_label.setFixedHeight(24)
        self.elevation_hint_label.setStyleSheet("color:#5d6f85; font-size:12px;")
        outer.addWidget(self.elevation_hint_label, 0)

        # ===== 图像区域：和特检策略页保持同样的结构 =====
        VIEW_SIZE = 540

        self.elevation_view = SacsElevationRiskView(frame)
        self.elevation_view.set_info_label(self.elevation_hint_label)
        self.elevation_view.setFixedSize(VIEW_SIZE, VIEW_SIZE)
        self.elevation_view.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.slider_v = QSlider(Qt.Vertical)
        self.slider_v.setRange(-100, 100)
        self.slider_v.setValue(0)
        self.slider_v.setSingleStep(2)
        self.slider_v.setPageStep(10)
        self.slider_v.setFixedSize(20, VIEW_SIZE)
        self.slider_v.setStyleSheet("""
            QSlider::groove:vertical {
                background: #e7edf5;
                width: 10px;
                border: 1px solid #c8d6e8;
                border-radius: 4px;
            }
            QSlider::handle:vertical {
                background: #2d8cf0;
                height: 42px;
                margin: -2px -4px;
                border-radius: 5px;
            }
        """)

        # 用一个固定容器把“图 + 右滑条”包起来，防止竖滑条被挤没
        view_wrap = QWidget(frame)
        view_wrap.setFixedSize(VIEW_SIZE + 28, VIEW_SIZE)

        view_wrap_lay = QHBoxLayout(view_wrap)
        view_wrap_lay.setContentsMargins(0, 0, 0, 0)
        view_wrap_lay.setSpacing(8)
        view_wrap_lay.addWidget(self.elevation_view, 0, Qt.AlignVCenter)
        view_wrap_lay.addWidget(self.slider_v, 0, Qt.AlignVCenter)

        view_row = QHBoxLayout()
        view_row.setContentsMargins(0, 0, 0, 0)
        view_row.setSpacing(0)
        view_row.addStretch(1)
        view_row.addWidget(view_wrap, 0, Qt.AlignCenter)
        view_row.addStretch(1)
        outer.addLayout(view_row, 1)

        self.slider_h = QSlider(Qt.Horizontal)
        self.slider_h.setRange(-100, 100)
        self.slider_h.setValue(0)
        self.slider_h.setFixedWidth(VIEW_SIZE)
        self.slider_h.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #e7edf5;
                height: 10px;
                border: 1px solid #c8d6e8;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #2d8cf0;
                width: 42px;
                margin: -4px -2px;
                border-radius: 5px;
            }
        """)

        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(0, 0, 0, 0)
        slider_row.setSpacing(0)
        slider_row.addStretch(1)
        slider_row.addWidget(self.slider_h, 0)
        slider_row.addStretch(1)
        outer.addLayout(slider_row, 0)

        self.elevation_view.bind_sliders(self.slider_h, self.slider_v)

        self.slider_h.valueChanged.connect(
            lambda v: self.elevation_view.pan_view(v, self.slider_v.value())
        )
        self.slider_v.valueChanged.connect(
            lambda v: self.elevation_view.pan_view(self.slider_h.value(), v)
        )

        v.addWidget(frame, 1)

        btn = QPushButton("生成特检策略报告")
        btn.setObjectName("ReportBtn")
        btn.clicked.connect(self._on_report)
        v.addWidget(btn, 0)

        return panel

    # ---------------- real data fill ----------------
    @staticmethod
    def _display_cell(value: object) -> str:
        if value in ("", None):
            return ""
        return str(value)

    def _refresh_elevation_view(self):
        if not hasattr(self, "elevation_view"):
            return

        bundle = self._result_bundle or {}
        context = bundle.get("context") or {}
        if not context:
            self.elevation_view._draw_message("当前没有可用的特检结果")
            return

        try:
            self.elevation_view.load_for_facility(
                facility_code=self.facility_code,
                context=context,
                year_label=self.current_year,
                row_name=self.row_combo.currentText().strip() if hasattr(self, "row_combo") else "XZ 前",
            )

            # 先同步立面下拉
            self._sync_dynamic_row_combo_from_view()

            # 再叠加检验等级
            if hasattr(self.elevation_view, "set_inspection_overlay"):
                self.elevation_view.set_inspection_overlay(self._overlay_bundle)

            # 浏览页面时只绘制真实图，不在这里导出/保存图片。

        except Exception as exc:
            print("[UpgradeSpecialInspectionResultPage] refresh elevation failed:", exc)
            self.elevation_view._draw_message(f"立面图加载失败：{exc}")

    def _save_current_elevation_image(self):
        """页面浏览阶段不保存图片；点击生成报告时由子进程统一导出。"""
        return

    def _batch_export_key(self, context: dict | None) -> tuple:
        state = (self._result_bundle or {}).get("state") or (
            (context or {}).get("state") if isinstance(context, dict) else {})
        if not isinstance(state, dict):
            state = {}
        source_key = (
                str(state.get("intermediate_workbook") or "")
                or str((context or {}).get("intermediate_workbook") or "")
                or str((context or {}).get("source_workbook") or "")
        )
        return (
        "upgrade_special_inspection_result", str(self.facility_code or ""), int(self.run_id) if self.run_id else 0,
        source_key)

    def _schedule_export_all_elevation_images(self, context: dict | None):
        """结果页异步批量导出所有年份/所有面，不阻塞界面。"""
        if not context:
            return

        key = self._batch_export_key(context)
        if key in self._batch_exported_keys:
            return

        # 正在导出时不重复启动，避免多个离屏视图同时写文件。
        if self._export_timer.isActive():
            return

        self._batch_exported_keys.add(key)

        try:
            self._export_context = dict(context)
            self._export_key = key

            # 使用独立的离屏视图导出，不影响用户当前正在看的 self.elevation_view。
            self._export_view = SacsElevationRiskView()
            self._export_view.resize(900, 900)

            self._export_view.clear_inspection_overlay()
            self._export_view.load_for_facility(
                facility_code=self.facility_code,
                context=self._export_context,
                year_label=self.current_year,
                row_name="XZ 前",
            )
            QApplication.processEvents()

            row_names = self._export_view.available_row_names()
            if not row_names:
                row_names = ["XZ 前", "XZ 后", "YZ 左", "YZ 右"]

            year_labels = self._year_mapper.display_labels()

            tasks = []
            for year_label in year_labels:
                for row_name in row_names:
                    tasks.append({
                        "year_label": year_label,
                        "row_name": row_name,
                    })

            self._export_tasks = tasks
            self._export_index = 0
            self._export_total = len(self._export_tasks)

            if self._export_total <= 0:
                self._finish_async_export()
                return

            print(f"[UpgradeSpecialInspectionResultPage] start async risk image export, total={self._export_total}")
            self._export_timer.start()

        except Exception as exc:
            if key is not None:
                self._batch_exported_keys.discard(key)
            print("[UpgradeSpecialInspectionResultPage] schedule async risk image export failed:", exc)
            self._finish_async_export()

    def _process_next_export_task(self):
        """每次只导出一张带标注图，导完一张就让界面继续响应。"""
        if self._export_index >= self._export_total:
            self._finish_async_export()
            return

        if self._export_view is None or not self._export_context:
            self._finish_async_export()
            return

        task = self._export_tasks[self._export_index]
        year_label = str(task.get("year_label") or self.current_year).strip() or self.current_year
        row_name = str(task.get("row_name") or "XZ 前").strip() or "XZ 前"

        try:
            try:
                overlay = load_strategy_inspection_overlay(
                    self.facility_code,
                    run_id=self.run_id,
                    display_year=year_label,
                )
            except Exception as exc:
                print("[UpgradeSpecialInspectionResultPage] load async overlay failed:", year_label, exc)
                overlay = {}

            self._export_view.clear_inspection_overlay()
            self._export_view.load_for_facility(
                facility_code=self.facility_code,
                context=self._export_context,
                year_label=year_label,
                row_name=row_name,
            )
            if hasattr(self._export_view, "set_inspection_overlay"):
                self._export_view.set_inspection_overlay(overlay)
            QApplication.processEvents()

            image_path = build_strategy_image_path(
                facility_code=self.facility_code,
                run_id=self.run_id,
                page_code="upgrade_special_inspection_result",
                image_type="elevation_risk",
                year_label=year_label,
                row_name=row_name,
            )
            saved_path = self._export_view.export_current_scene_to_png(str(image_path))

            save_strategy_image_record(
                facility_code=self.facility_code,
                run_id=self.run_id,
                page_code="upgrade_special_inspection_result",
                image_type="elevation_risk",
                year_label=year_label,
                row_name=row_name,
                image_path=saved_path,
                remark="更新风险结果页异步导出模型立面风险图",
            )

            self._export_index += 1
            print(
                f"[UpgradeSpecialInspectionResultPage] async risk image export progress: {self._export_index}/{self._export_total}")

        except Exception as exc:
            print(
                f"[UpgradeSpecialInspectionResultPage] async risk image export failed: year={year_label}, row={row_name}, err={exc}")
            self._export_index += 1

    def _finish_async_export(self):
        """结束异步导出并清理离屏视图。"""
        try:
            if self._export_timer.isActive():
                self._export_timer.stop()
        except Exception:
            pass

        if self._export_view is not None:
            try:
                self._export_view.deleteLater()
            except Exception:
                pass

        self._export_tasks = []
        self._export_index = 0
        self._export_total = 0
        self._export_view = None
        self._export_context = None
        self._export_key = None

        print("[UpgradeSpecialInspectionResultPage] async risk image export finished")

    def _load_result_data(self):
        bundle = self._result_service.load_result_bundle(self.facility_code, self.run_id)
        self._result_bundle = bundle or {}

        if not bundle:
            self._set_detail_rows(self.table_comp, [], is_node=False)
            self._set_detail_rows(self.table_node, [], is_node=True)
            self._clear_summary_table(self.summary_comp)
            self._clear_summary_table(self.summary_node)
            self._apply_row_limit()
            if hasattr(self, "elevation_view"):
                self.elevation_view._draw_message("当前没有可用的特检结果")
            return

        context = bundle.get("context") or {}

        self._set_detail_rows(self.table_comp, bundle.get("member_risk_rows_full", []), is_node=False)
        self._set_detail_rows(self.table_node, bundle.get("node_risk_rows_full", []), is_node=True)
        self._fill_component_summary(context)
        self._fill_node_summary(context)
        self._apply_row_limit()

        self._overlay_bundle = load_strategy_inspection_overlay(
            self.facility_code,
            run_id=self.run_id,
            display_year=self.current_year,
        )
        self._refresh_elevation_view()
        # 浏览页面时不导出/保存图片；报告图片在点击“生成特检策略报告”时统一导出。

    def _set_detail_rows(self, table: QTableWidget, rows: list[dict[str, str]], *, is_node: bool):
        start = self.HEADER_ROWS
        data_rows = max(len(rows), 1)
        table.setRowCount(start + data_rows)
        table.setProperty("detail_row_count", data_rows)
        for r in range(start, table.rowCount()):
            table.setRowHeight(r, 24)

        if not rows:
            rows = [{}]

        for idx, row in enumerate(rows):
            r = start + idx
            if not is_node:
                vals = [
                    row.get("joint_a", ""),
                    row.get("joint_b", ""),
                    row.get("member_type", ""),
                    row.get("consequence_level", ""),
                    row.get("a", ""),
                    row.get("b", ""),
                    row.get("rm", ""),
                    row.get("vr", ""),
                    row.get("pf", ""),
                    row.get("collapse_prob_level", ""),
                    row.get("risk_level", ""),
                ]
            else:
                vals = [
                    row.get("joint_a", ""),
                    row.get("joint_b", ""),
                    row.get("weld_type", ""),
                    row.get("consequence_level", ""),
                    row.get("a", ""),
                    row.get("b", ""),
                    row.get("rm", ""),
                    row.get("vr", ""),
                    row.get("pf", ""),
                    row.get("collapse_prob_level", ""),
                    row.get("risk_level", ""),
                ]
            for c, value in enumerate(vals):
                item = QTableWidgetItem(self._display_cell(value))
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, item)

    def _clear_summary_table(self, table: QTableWidget):
        labels = list(table.property("summary_labels") or [])
        for i in range(len(labels)):
            base_r = 1 + i * 4
            for k in range(5):
                table.setItem(base_r + 1, 1 + k, QTableWidgetItem(""))
                table.item(base_r + 1, 1 + k).setTextAlignment(Qt.AlignCenter)
                table.setItem(base_r + 2, 1 + k, QTableWidgetItem(""))
                table.item(base_r + 2, 1 + k).setTextAlignment(Qt.AlignCenter)

    def _fill_summary_block(self, table: QTableWidget, block_index: int, counts: dict[str, Any],
                            ratios: dict[str, Any]):
        base_r = 1 + block_index * 4
        for k, risk in enumerate(self.RISK_LABELS):
            count_item = QTableWidgetItem(self._display_cell(counts.get(risk, "")))
            count_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(base_r + 1, 1 + k, count_item)

            ratio_item = QTableWidgetItem(self._display_cell(ratios.get(risk, "")))
            ratio_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(base_r + 2, 1 + k, ratio_item)

    def _fill_component_summary(self, context: dict):
        self._clear_summary_table(self.summary_comp)
        self._fill_summary_block(
            self.summary_comp,
            0,
            context.get("member_risk_counts", {}),
            context.get("member_risk_ratios", {}),
        )

    def _fill_node_summary(self, context: dict):
        self._clear_summary_table(self.summary_node)
        labels = list(self.summary_node.property("summary_labels") or [])
        label_to_index = {label: idx for idx, label in enumerate(labels)}
        for block in context.get("node_summary_blocks", []):
            context_label = str(block.get("time_node", "")).strip()
            display_label = self._year_mapper.to_display_label(context_label)
            if not display_label or display_label not in label_to_index:
                continue
            idx = label_to_index[display_label]
            self._fill_summary_block(
                self.summary_node,
                idx,
                block.get("counts", {}),
                block.get("ratios", {}),
            )

    def _apply_row_limit(self):
        choice = self.cb_rows.currentText()
        limit = None if choice == "全部" else int(choice)

        def apply(table: QTableWidget):
            start = self.HEADER_ROWS
            total_rows = int(table.property("detail_row_count") or max(table.rowCount() - start, 1))
            for r in range(start, table.rowCount()):
                table.setRowHidden(r, (limit is not None and (r - start) >= limit))
            visible_rows = total_rows if limit is None else min(limit, total_rows)
            self._set_detail_table_height(table, visible_rows)

        apply(self.table_comp)
        apply(self.table_node)
        # self._sync_current_tab_height()

    def _sync_current_tab_height(self, _index: int | None = None) -> None:
        return
        # if not hasattr(self, "tabs"):
        #     return
        # page = self.tabs.currentWidget()
        # if page is None:
        #     return
        # layout = page.layout()
        # if layout is not None:
        #     layout.activate()
        # page.adjustSize()
        # page_height = page.sizeHint().height()
        # tab_bar_height = self.tabs.tabBar().sizeHint().height()
        # self.tabs.setFixedHeight(tab_bar_height + page_height + 8)

    def _set_report_running(self, running: bool, text: str = ""):
        self._report_running = bool(running)
        if hasattr(self, "btn_generate_report"):
            self.btn_generate_report.setEnabled(not running)

        if running:
            if self._report_progress is None:
                dlg = QProgressDialog("正在导出报告图片并生成特检策略报告，请稍候...", None, 0, 0, self)
                dlg.setWindowTitle("生成报告")
                dlg.setWindowModality(Qt.NonModal)
                dlg.setCancelButton(None)
                dlg.setMinimumDuration(0)
                dlg.setAutoClose(False)
                dlg.setAutoReset(False)
                self._report_progress = dlg
            self._report_progress.setLabelText(
                text or "正在导出报告图片并生成特检策略报告，请稍候..."
            )
            self._report_progress.show()
        else:
            # 不在 QProcess.finished 回调中立即 deleteLater 进度框。
            # 部分 Windows/PyQt 环境下，进度框刚关闭又立刻弹 QMessageBox，容易触发底层 Qt 崩溃。
            # 这里仅隐藏，下一次生成报告时复用该对话框。
            if self._report_progress is not None:
                self._report_progress.hide()

    def _report_export_script_module(self) -> str:
        return "services.report_image_batch_export_process"

    def _extract_report_output_path_from_log(self, log_text: str) -> Path | None:
        for raw_line in reversed((log_text or "").splitlines()):
            line = raw_line.strip()
            if not line:
                continue
            match = re.search(r"report generated:\s*(.+)$", line, flags=re.IGNORECASE)
            if not match:
                continue
            try:
                candidate = Path(match.group(1).strip()).resolve()
            except Exception:
                continue
            return candidate
        return None

    @staticmethod
    def _decode_report_process_output(data: bytes) -> str:
        if not data:
            return ""

        for encoding in ("utf-8", "gb18030", "cp936"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def _open_report_output_location(self, file_path: Path | None) -> bool:
        if file_path is None:
            return False

        target = Path(file_path)
        try:
            if target.exists() and QProcess.startDetached("explorer", ["/select,", str(target)]):
                return True
        except Exception:
            pass

        folder = target.parent if target.suffix else target
        try:
            return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))
        except Exception:
            return False

    def _show_report_generated_dialog(self, report_path: Path | None) -> None:
        pdf_path = report_path.with_suffix(".pdf") if report_path is not None else None
        message_lines = ["特检策略报告已生成。"]

        if report_path is not None:
            message_lines.append(f"Word：\n{report_path}")
        if pdf_path is not None and pdf_path.exists():
            message_lines.append(f"PDF：\n{pdf_path}")

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("生成报告")
        msg.setText("\n\n".join(message_lines))

        open_target = report_path if report_path is not None else (pdf_path if pdf_path is not None and pdf_path.exists() else None)
        open_btn = None
        if open_target is not None:
            open_btn = msg.addButton("查看文件", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)
        msg.exec_()

        if open_btn is not None and msg.clickedButton() is open_btn:
            if not self._open_report_output_location(open_target):
                QMessageBox.warning(self, "打开失败", "未能打开生成文件所在位置。")

    def _on_report(self):
        """点击生成报告：在独立子进程中先导出图片，再生成报告。"""
        if getattr(self, "_report_running", False):
            QMessageBox.information(self, "生成报告", "报告正在生成中，请稍候。")
            return

        if not str(self.facility_code or "").strip():
            QMessageBox.warning(self, "生成报告失败", "当前设施编码为空，无法生成报告。")
            return

        if self._report_export_process is not None:
            QMessageBox.information(self, "生成报告", "报告进程正在运行，请稍候。")
            return

        project_root = Path(__file__).resolve().parents[1]
        args = [
            "-m",
            self._report_export_script_module(),
            "--facility-code",
            str(self.facility_code or ""),
            "--generate-report",
        ]
        if self.run_id is not None:
            args.extend(["--run-id", str(int(self.run_id))])

        proc = QProcess(self)
        proc.setWorkingDirectory(str(project_root))
        proc.setProgram(sys.executable)
        proc.setArguments(args)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUTF8", "1")
        proc.setProcessEnvironment(env)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_report_process_output)
        proc.finished.connect(self._on_report_process_finished)
        proc.errorOccurred.connect(self._on_report_process_error)

        self._report_export_log = []
        self._report_export_process = proc
        self._set_report_running(
            True,
            "正在导出报告图片并生成特检策略报告，请稍候...",
        )
        proc.start()

    def _on_report_process_output(self):
        proc = self._report_export_process
        if proc is None:
            return
        try:
            data = self._decode_report_process_output(bytes(proc.readAllStandardOutput()))
        except Exception:
            data = ""
        if not data:
            return
        self._report_export_log.append(data)
        print(data, end="")

        # 进度框只保持固定提示，不再把子进程日志实时追加到界面上。
        # 日志仍然保留在 self._report_export_log 中，失败时用于错误提示。
        if self._report_progress is not None:
            self._report_progress.setLabelText("正在导出报告图片并生成特检策略报告，请稍候...")

    def _on_report_process_error(self, error):
        print("[UpgradeSpecialInspectionResultPage] report process error:", error)

    def _on_report_process_finished(self, exit_code: int, exit_status):
        proc = self._report_export_process
        self._report_export_process = None
        if proc is not None:
            try:
                # 不在 finished 信号栈内立即析构 QProcess，延后释放，避免 Windows 下偶发 C++ 层崩溃。
                QTimer.singleShot(1500, proc.deleteLater)
            except Exception:
                pass

        log_text = "".join(getattr(self, "_report_export_log", []))[-6000:]
        self._set_report_running(False)

        if exit_code != 0 or exit_status != QProcess.NormalExit:
            QMessageBox.warning(
                self,
                "生成报告失败",
                f"报告图片导出或报告生成失败，退出码：{exit_code}。\n\n最近日志：\n{log_text}",
            )
            return

        report_path = self._extract_report_output_path_from_log(log_text)
        self._show_report_generated_dialog(report_path)
