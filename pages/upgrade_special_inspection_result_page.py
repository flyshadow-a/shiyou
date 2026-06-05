# -*- coding: utf-8 -*-
# pages/upgrade_special_inspection_result_page.py

from pathlib import Path
from typing import Any
import os
import json

from PyQt5.QtCore import QObject, Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QComboBox, QTabWidget, QSizePolicy, QMessageBox, QSlider, QApplication,
    QDialog, QProgressBar, QProgressDialog, QFileDialog,
)

from core.base_page import BasePage
from core.message_boxes import ask_yes_no
from services.special_strategy_services import NodeYearLabelMapper, SpecialStrategyResultService
from pages.sacs_elevation_risk_view import SacsElevationRiskView
from services.special_strategy_inspection_overlay_service import load_strategy_inspection_overlay
from services.special_strategy_image_service import build_strategy_image_path, save_strategy_image_record
from services.special_strategy_state_db import list_strategy_risk_images

NODE_SUMMARY_DISPLAY_LABELS = ["当前", "+5年", "+10年", "+15年", "+20年", "+25年"]
NODE_SUMMARY_CONTEXT_MAP = {
    "当前": "当前",
    "+5年": "第5年",
    "+10年": "第10年",
    "+15年": "第15年",
    "+20年": "第20年",
    "+25年": "第25年",
}


class _SpecialStrategyReportWorker(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, facility_code: str, run_id: int | None = None, output_path: str | None = None):
        super().__init__()
        self._facility_code = facility_code
        self._run_id = run_id
        self._output_path = output_path

    def run(self) -> None:
        try:
            service = SpecialStrategyResultService()
            report_path = service.generate_report(
                self._facility_code,
                run_id=self._run_id,
                output_path=self._output_path,
            )
            self.finished.emit(str(report_path))
        except Exception as exc:
            self.failed.emit(str(exc))


class _SpecialStrategyResultLoadWorker(QObject):
    finished = pyqtSignal(int, object, object)
    failed = pyqtSignal(int, str)

    def __init__(self, token: int, facility_code: str, run_id: int | None, display_year: str):
        super().__init__()
        self._token = int(token)
        self._facility_code = facility_code
        self._run_id = run_id
        self._display_year = display_year

    def run(self) -> None:
        try:
            service = SpecialStrategyResultService()
            bundle = service.load_result_bundle(self._facility_code, self._run_id) or {}
            overlay = {}
            if bundle:
                overlay = load_strategy_inspection_overlay(
                    self._facility_code,
                    run_id=self._run_id,
                    display_year=self._display_year,
                )
        except Exception as exc:
            self.failed.emit(self._token, str(exc))
            return
        self.finished.emit(self._token, bundle, overlay)


class _SpecialStrategyOverlayLoadWorker(QObject):
    finished = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str, str)

    def __init__(self, token: int, facility_code: str, run_id: int | None, display_year: str):
        super().__init__()
        self._token = int(token)
        self._facility_code = facility_code
        self._run_id = run_id
        self._display_year = display_year

    def run(self) -> None:
        try:
            overlay = load_strategy_inspection_overlay(
                self._facility_code,
                run_id=self._run_id,
                display_year=self._display_year,
            )
        except Exception as exc:
            self.failed.emit(self._token, self._display_year, str(exc))
            return
        self.finished.emit(self._token, self._display_year, overlay)


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
        self._start_overlay_load(self.current_year)

    def _apply_elevation_level_visibility(self):
        if hasattr(self, "btn_toggle_level_ii") and self.btn_toggle_level_ii is not None:
            self.btn_toggle_level_ii.setText("隐藏二级" if self._show_level_ii_in_view else "显示二级")
        if hasattr(self, "elevation_view") and self.elevation_view is not None:
            try:
                if hasattr(self.elevation_view, "set_show_level_ii"):
                    self.elevation_view.set_show_level_ii(bool(self._show_level_ii_in_view))
            except Exception as exc:
                print("[UpgradeSpecialInspectionResultPage] apply level-II visibility failed:", exc)

    def _on_toggle_level_ii(self):
        self._show_level_ii_in_view = not bool(getattr(self, "_show_level_ii_in_view", False))
        self._apply_elevation_level_visibility()

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
        self._show_level_ii_in_view = False

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
        self._pending_report_after_risk_export = False

        # 生成报告相关状态：先导出检验等级图，再生成 Word/PDF 报告
        self._pending_report_output_path = ""
        self.btn_report = None
        self._report_progress = None
        self._report_progress_base_text = ""
        self._report_progress_tick = 0
        self._report_thread = None
        self._report_worker = None
        self._report_progress_timer = QTimer(self)
        self._report_progress_timer.setInterval(320)
        self._report_progress_timer.timeout.connect(self._update_report_progress_text)
        self._result_load_token = 0
        self._result_load_jobs = []
        self._overlay_load_token = 0
        self._overlay_load_jobs = []

        # run_id 为 None 时，表示从“特检策略”主页右上角“查看结果”进入：
        # 优先读取“生成特检策略报告”时已经上传到服务器的最新风险等级缓存图。
        # run_id 不为空时，表示从“新增特检策略”更新风险等级后进入：
        # 必须实时绘制本次更新结果，不能读取旧缓存。
        self._cached_risk_image_records = None
        self._cached_risk_latest_group_key = None
        self._is_refreshing_elevation = False

        self._build_ui()
        self._start_result_data_load()

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
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)

        t.resizeColumnsToContents()
        for c in range(cols):
            w = t.columnWidth(c)
            t.setColumnWidth(c, max(80, w + 10))

        header.setStretchLastSection(True)
        # ============================================

        # row heights
        t.setRowHeight(0, 26)
        t.setRowHeight(1, 26)
        for r in range(2, t.rowCount()):
            t.setRowHeight(r, 24)

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

        green = QColor("#cfe6b8")
        for r, text in enumerate(labels):
            t.setSpan(r * 4, 0, 1, 6)
            self._set_cell(t, r * 4, 0, text, green, True)

        # Year blocks
        for i, _year in enumerate(labels):
            base_r = 1 + i * 4

            for k in range(5):
                it = QTableWidgetItem(self.RISK_LABELS[k])
                it.setTextAlignment(Qt.AlignCenter)
                it.setBackground(self.RISK_COLORS[k])
                f = it.font()
                f.setBold(True)
                it.setFont(f)
                t.setItem(base_r, 1 + k, it)

            # row base_r: 风险等级
            self._set_cell(t, base_r, 0, "风险等级", QColor("#e3e7ef"), True)

            # row base_r+1: 数量
            self._set_cell(t, base_r + 1, 0, "数量", QColor("#e3e7ef"), True)
            for k in range(5):
                self._set_cell(t, base_r + 1, 1 + k, "", None, False)

            # row base_r+2: 占比
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

        title = QLabel("模型立面检验等级图")
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
        top_row.addSpacing(12)

        self.btn_toggle_level_ii = QPushButton("显示二级")
        self.btn_toggle_level_ii.setFixedSize(92, 30)
        self.btn_toggle_level_ii.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_level_ii.setStyleSheet("""
            QPushButton {
                background: #ffffff;
                color: #1d2b3a;
                border: 1px solid #b9c6d6;
                border-radius: 3px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover { background: #f1f6fb; }
        """)
        self.btn_toggle_level_ii.clicked.connect(self._on_toggle_level_ii)
        top_row.addWidget(self.btn_toggle_level_ii, 0)

        top_row.addStretch(1)

        self.btn_elevation_fullscreen = QPushButton("全屏")
        self.btn_elevation_fullscreen.setFixedSize(72, 30)
        self.btn_elevation_fullscreen.setCursor(Qt.PointingHandCursor)
        self.btn_elevation_fullscreen.setStyleSheet("""
            QPushButton {
                background: #2aa9df;
                color: #ffffff;
                border: 1px solid #1b6f91;
                border-radius: 3px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover { background: #42bce9; }
        """)
        self.btn_elevation_fullscreen.clicked.connect(self._on_elevation_fullscreen)
        top_row.addWidget(self.btn_elevation_fullscreen, 0)

        outer.addLayout(top_row, 0)

        self.elevation_hint_label = QLabel("当前显示：立面轮廓图 + 检验等级；滚轮缩放，双击恢复初始视图。")
        self.elevation_hint_label.setWordWrap(False)
        self.elevation_hint_label.setFixedHeight(24)
        self.elevation_hint_label.setStyleSheet("color:#5d6f85; font-size:12px;")
        outer.addWidget(self.elevation_hint_label, 0)

        # ===== 图像区域：和特检策略页保持同样的结构 =====
        VIEW_SIZE = 620

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

        self._apply_elevation_level_visibility()

        v.addWidget(frame, 1)

        btn = QPushButton("生成特检策略报告")
        btn.setObjectName("ReportBtn")
        btn.clicked.connect(self._on_report)
        self.btn_report = btn
        v.addWidget(btn, 0)

        return panel

    def _on_elevation_fullscreen(self):
        if not hasattr(self, "elevation_view") or self.elevation_view is None:
            return
        try:
            row_name = self.row_combo.currentText().strip() if hasattr(self, "row_combo") else ""
            year_name = self.year_combo.currentText().strip() if hasattr(self, "year_combo") else ""
            title = "模型立面检验等级图"
            if row_name or year_name:
                title = f"模型立面检验等级图 {row_name} {year_name}".strip()
            self.elevation_view.open_fullscreen_window(title)
        except Exception as exc:
            QMessageBox.warning(self, "全屏显示失败", f"打开全屏窗口失败：\n{exc}")

    # ---------------- real data fill ----------------
    @staticmethod
    def _display_cell(value: object) -> str:
        if value in ("", None):
            return ""
        return str(value)

    def _is_new_strategy_result_entry(self) -> bool:
        """run_id 不为空：从“新增特检策略”页面查看本次更新结果，必须实时绘图。"""
        return self.run_id is not None

    def _is_history_latest_entry(self) -> bool:
        """run_id 为空：从“特检策略”主页右上角查看历史最新结果，优先读缓存图。"""
        return self.run_id is None

    def _show_realtime_draw_busy_dialog(self, message: str | None = None) -> QDialog:
        """显示结果加载提示窗口。

        这里只保留一个提示文案，避免标题和正文重复。
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("正在加载结果")
        dlg.setModal(True)
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dlg.setFixedSize(360, 118)
        dlg.setStyleSheet("""
            QDialog { background: #ffffff; }
            QLabel {
                color: #1d2b3a;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 13pt;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #b9c6d6;
                border-radius: 4px;
                background: #eef3f8;
                height: 18px;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background: #2aa9df;
            }
        """)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(14)

        title = QLabel("正在加载结果")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        bar = QProgressBar()
        bar.setRange(0, 0)
        layout.addWidget(bar)

        dlg.show()
        QApplication.processEvents()
        return dlg

    @staticmethod
    def _normalize_image_text(value: object) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_run_group(value: object) -> str:
        if value in (None, ""):
            return "__none__"
        try:
            return str(int(value))
        except Exception:
            return str(value).strip()

    @staticmethod
    def _hotspot_meta_path_for_image(image_path: str) -> str:
        path = os.path.normpath(str(image_path or "").strip())
        if not path:
            return ""
        return f"{path}.hotspots.json"

    def _load_hotspots_for_cached_image(self, image_path: str) -> list[dict]:
        meta_path = self._hotspot_meta_path_for_image(image_path)
        if not meta_path or not os.path.exists(meta_path):
            return []
        try:
            with open(meta_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            hotspots = data.get("hotspots") if isinstance(data, dict) else data
            return list(hotspots or [])
        except Exception as exc:
            print("[UpgradeSpecialInspectionResultPage] load cached hotspot metadata failed:", exc)
            return []

    def _save_hotspots_for_exported_image(self, image_path: str, view: SacsElevationRiskView) -> None:
        meta_path = self._hotspot_meta_path_for_image(image_path)
        if not meta_path or view is None:
            return
        try:
            data = {}
            if hasattr(view, "build_hotspot_metadata_for_export"):
                data = view.build_hotspot_metadata_for_export(margin=24) or {}
            if not data:
                data = {"hotspots": []}
            data["image_path"] = os.path.normpath(str(image_path or ""))
            data["facility_code"] = self.facility_code
            data["run_id"] = self.run_id
            data["page_code"] = "upgrade_special_inspection_result"
            data["image_type"] = "elevation_risk"
            folder = os.path.dirname(meta_path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            with open(meta_path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
        except Exception as exc:
            print("[UpgradeSpecialInspectionResultPage] save hotspot metadata failed:", exc)

    def _load_latest_cached_risk_image_records(self, *, force: bool = False) -> list[dict]:
        """读取服务器中“最新一次生成报告”导出的检验等级图记录。

        只在 run_id=None 的历史最新入口使用。这里不按当前页面 run_id 过滤，
        而是从该平台所有 upgrade_special_inspection_result/elevation_risk 记录中，
        取更新时间最新的一组 run_id 作为“历史最新一次结果缓存”。
        """
        if (not force) and self._cached_risk_image_records is not None:
            return list(self._cached_risk_image_records)

        try:
            rows = list_strategy_risk_images(
                self.facility_code,
                page_code="upgrade_special_inspection_result",
                limit=2000,
            ) or []
        except Exception as exc:
            print("[UpgradeSpecialInspectionResultPage] list cached risk images failed:", exc)
            rows = []

        valid: list[dict] = []
        for row in rows:
            if str(row.get("image_type") or "").strip() != "elevation_risk":
                continue
            path = os.path.normpath(str(row.get("image_path") or "").strip())
            if not path or not os.path.exists(path):
                continue
            item = dict(row)
            item["image_path"] = path
            valid.append(item)

        if not valid:
            self._cached_risk_image_records = []
            self._cached_risk_latest_group_key = None
            return []

        latest_group_key = self._normalize_run_group(valid[0].get("run_id"))
        latest_records = [
            row for row in valid
            if self._normalize_run_group(row.get("run_id")) == latest_group_key
        ]

        self._cached_risk_image_records = latest_records
        self._cached_risk_latest_group_key = latest_group_key
        print(
            "[UpgradeSpecialInspectionResultPage] cached risk images:",
            "group=", latest_group_key,
            "count=", len(latest_records),
        )
        return list(latest_records)

    def _cached_rows_for_year(self, year_label: str) -> list[str]:
        records = self._load_latest_cached_risk_image_records()
        target_year = self._normalize_image_text(year_label)
        out: list[str] = []
        seen: set[str] = set()
        for row in records:
            if self._normalize_image_text(row.get("year_label")) != target_year:
                continue
            row_name = self._normalize_image_text(row.get("row_name"))
            if not row_name or row_name in seen:
                continue
            seen.add(row_name)
            out.append(row_name)
        return out

    def _sync_row_combo_from_cached_images(self) -> None:
        if not hasattr(self, "row_combo"):
            return
        rows = self._cached_rows_for_year(self.current_year)
        if not rows:
            return

        current = self.row_combo.currentText().strip()
        old_options = [self.row_combo.itemText(i) for i in range(self.row_combo.count())]

        self.row_combo.blockSignals(True)
        try:
            if old_options != rows:
                self.row_combo.clear()
                self.row_combo.addItems(rows)
            if current in rows:
                self.row_combo.setCurrentText(current)
            else:
                self.row_combo.setCurrentText(rows[0])
        finally:
            self.row_combo.blockSignals(False)

    def _find_cached_risk_image_for_current_view(self) -> dict | None:
        records = self._load_latest_cached_risk_image_records()
        if not records:
            return None

        self._sync_row_combo_from_cached_images()
        year_label = self._normalize_image_text(self.current_year)
        row_name = self.row_combo.currentText().strip() if hasattr(self, "row_combo") else "XZ 前"

        for row in records:
            if self._normalize_image_text(row.get("year_label")) != year_label:
                continue
            if self._normalize_image_text(row.get("row_name")) != row_name:
                continue
            path = self._normalize_image_text(row.get("image_path"))
            if path and os.path.exists(path):
                return row
        return None

    def _try_load_cached_risk_image(self) -> bool:
        """历史最新入口优先显示服务器缓存图。成功返回 True。"""
        record = self._find_cached_risk_image_for_current_view()
        if not record:
            return False

        row_name = self._normalize_image_text(record.get("row_name")) or (
            self.row_combo.currentText().strip() if hasattr(self, "row_combo") else "XZ 前"
        )
        image_path = self._normalize_image_text(record.get("image_path"))

        hotspots = self._load_hotspots_for_cached_image(image_path)
        if hasattr(self.elevation_view, "display_cached_image"):
            ok = self.elevation_view.display_cached_image(
                image_path,
                row_name=row_name,
                description="历史最新检验等级缓存图",
                hotspots=hotspots,
            )
        else:
            ok = False

        if ok:
            if self.elevation_hint_label is not None:
                self.elevation_hint_label.setText(
                    f"当前显示：{row_name} 历史最新检验等级缓存图；滚轮缩放，双击恢复初始视图。"
                )
            return True
        return False

    def _refresh_elevation_view(self):
        if not hasattr(self, "elevation_view"):
            return
        if getattr(self, "_is_refreshing_elevation", False):
            return

        self._is_refreshing_elevation = True
        try:
            bundle = self._result_bundle or {}
            context = bundle.get("context") or {}
            if not context:
                self.elevation_view._draw_message("当前没有可用的特检结果")
                return

            # 当前页面需要支持“默认只看 III/IV，按钮切换是否显示 II”的交互能力，
            # 因此这里统一实时绘制，不再直接显示旧缓存图片。
            busy = self._show_realtime_draw_busy_dialog()

            try:
                QApplication.setOverrideCursor(Qt.WaitCursor)
                QApplication.processEvents()

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
                self._apply_elevation_level_visibility()

                # 页面浏览阶段不再导出/上传检验等级图；报告图片统一在“生成特检策略报告”时处理。

            finally:
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    pass
                try:
                    busy.close()
                    busy.deleteLater()
                except Exception:
                    pass
                QApplication.processEvents()

        except Exception as exc:
            print("[UpgradeSpecialInspectionResultPage] refresh elevation failed:", exc)
            self.elevation_view._draw_message(f"立面图加载失败：{exc}")
        finally:
            self._is_refreshing_elevation = False

    def _save_current_elevation_image(self):
        """导出当前右侧模型立面检验等级图，并把图片路径写入数据库。"""
        if not hasattr(self, "elevation_view"):
            return

        row_name = self.row_combo.currentText().strip() if hasattr(self, "row_combo") else "XZ 前"
        if not row_name:
            row_name = "XZ 前"

        try:
            image_path = build_strategy_image_path(
                facility_code=self.facility_code,
                run_id=self.run_id,
                page_code="upgrade_special_inspection_result",
                image_type="elevation_risk",
                year_label=self.current_year,
                row_name=row_name,
            )
            saved_path = self.elevation_view.export_current_scene_to_png(str(image_path))
            self._save_hotspots_for_exported_image(saved_path, self.elevation_view)
            save_strategy_image_record(
                facility_code=self.facility_code,
                run_id=self.run_id,
                page_code="upgrade_special_inspection_result",
                image_type="elevation_risk",
                year_label=self.current_year,
                row_name=row_name,
                image_path=saved_path,
                remark="更新风险结果页模型立面检验等级图",
            )
            print("[UpgradeSpecialInspectionResultPage] elevation image saved:", saved_path)
        except Exception as exc:
            # 图片导出失败不应影响页面显示。
            print("[UpgradeSpecialInspectionResultPage] save elevation image failed:", exc)

    def _batch_export_key(self, context: dict | None) -> tuple:
        state = (self._result_bundle or {}).get("state") or (
            (context or {}).get("state") if isinstance(context, dict) else {}
        )
        if not isinstance(state, dict):
            state = {}
        source_key = (
            str(state.get("intermediate_workbook") or "")
            or str((context or {}).get("intermediate_workbook") or "")
            or str((context or {}).get("source_workbook") or "")
        )
        return (
            "upgrade_special_inspection_result",
            str(self.facility_code or ""),
            int(self.run_id) if self.run_id else 0,
            source_key,
        )

    def _schedule_export_all_elevation_images(self, context: dict | None, *, force: bool = False):
        """结果页异步批量导出所有年份/所有面，不阻塞界面。

        force=True 用于“生成特检策略报告”按钮，确保点击按钮时重新导出检验等级图。
        """
        if not context:
            return

        key = self._batch_export_key(context)
        if force and key in self._batch_exported_keys:
            self._batch_exported_keys.discard(key)
        if key in self._batch_exported_keys:
            if self._pending_report_after_risk_export:
                QTimer.singleShot(0, self._do_generate_report_after_risk_export)
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
            if hasattr(self._export_view, "set_show_level_ii"):
                self._export_view.set_show_level_ii(bool(self._show_level_ii_in_view))

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
            if hasattr(self._export_view, "set_show_level_ii"):
                self._export_view.set_show_level_ii(bool(self._show_level_ii_in_view))
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
            self._save_hotspots_for_exported_image(saved_path, self._export_view)

            save_strategy_image_record(
                facility_code=self.facility_code,
                run_id=self.run_id,
                page_code="upgrade_special_inspection_result",
                image_type="elevation_risk",
                year_label=year_label,
                row_name=row_name,
                image_path=saved_path,
                remark="更新风险结果页异步导出模型立面检验等级图",
            )

            self._export_index += 1
            print(
                f"[UpgradeSpecialInspectionResultPage] async risk image export progress: "
                f"{self._export_index}/{self._export_total}"
            )

            if self._export_index >= self._export_total:
                self._finish_async_export()
            else:
                self._export_timer.start(600)

        except Exception as exc:
            print(
                f"[UpgradeSpecialInspectionResultPage] async risk image export failed: "
                f"year={year_label}, row={row_name}, err={exc}"
            )
            self._export_index += 1
            if self._export_index >= self._export_total:
                self._finish_async_export()
            else:
                self._export_timer.start(600)

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

        if self._pending_report_after_risk_export:
            QTimer.singleShot(0, self._do_generate_report_after_risk_export)

    def _forget_result_load_thread(self, thread: QThread) -> None:
        self._result_load_jobs = [job for job in self._result_load_jobs if job[0] is not thread]

    def _forget_overlay_load_thread(self, thread: QThread) -> None:
        self._overlay_load_jobs = [job for job in self._overlay_load_jobs if job[0] is not thread]

    def _set_result_loading(self, loading: bool) -> None:
        if hasattr(self, "btn_report") and self.btn_report is not None:
            self.btn_report.setEnabled(not loading)
        if loading and hasattr(self, "elevation_view"):
            self.elevation_view._draw_message("正在加载特检结果...")

    def _start_result_data_load(self) -> None:
        self._result_load_token += 1
        token = self._result_load_token
        self._set_result_loading(True)
        thread = QThread(self)
        worker = _SpecialStrategyResultLoadWorker(
            token,
            self.facility_code,
            self.run_id,
            self.current_year,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_result_data_loaded)
        worker.failed.connect(self._on_result_data_load_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda t=thread: self._forget_result_load_thread(t))
        self._result_load_jobs.append((thread, worker, token))
        thread.start()

    def _on_result_data_loaded(self, token: int, bundle: object, overlay: object) -> None:
        if int(token) != self._result_load_token:
            return
        self._set_result_loading(False)
        self._apply_result_data(bundle if isinstance(bundle, dict) else {}, overlay if isinstance(overlay, dict) else {})

    def _on_result_data_load_failed(self, token: int, message: str) -> None:
        if int(token) != self._result_load_token:
            return
        self._set_result_loading(False)
        self._apply_result_data({}, {})
        QMessageBox.warning(self, "加载失败", message or "特检结果加载失败。")

    def _start_overlay_load(self, display_year: str) -> None:
        self._overlay_load_token += 1
        token = self._overlay_load_token
        thread = QThread(self)
        worker = _SpecialStrategyOverlayLoadWorker(
            token,
            self.facility_code,
            self.run_id,
            display_year,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_overlay_loaded)
        worker.failed.connect(self._on_overlay_load_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda t=thread: self._forget_overlay_load_thread(t))
        self._overlay_load_jobs.append((thread, worker, token))
        thread.start()

    def _on_overlay_loaded(self, token: int, display_year: str, overlay: object) -> None:
        if int(token) != self._overlay_load_token:
            return
        if str(display_year or "").strip() != self.current_year:
            return
        self._overlay_bundle = overlay if isinstance(overlay, dict) else {}
        self._refresh_elevation_view()

    def _on_overlay_load_failed(self, token: int, display_year: str, message: str) -> None:
        if int(token) != self._overlay_load_token:
            return
        if str(display_year or "").strip() != self.current_year:
            return
        print("[UpgradeSpecialInspectionResultPage] load overlay failed:", message)
        self._overlay_bundle = {}
        self._refresh_elevation_view()

    def _load_result_data(self):
        self._start_result_data_load()

    def _apply_result_data(self, bundle: dict, overlay: dict | None = None):
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

        self._overlay_bundle = overlay or {}
        self._refresh_elevation_view()
        # 页面浏览阶段不再批量导出检验等级图；报告图片统一在“生成特检策略报告”按钮中处理。

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

    def _sync_current_tab_height(self, _index: int | None = None) -> None:
        return

    def _set_report_button_busy(self, busy: bool, text: str = "生成特检策略报告") -> None:
        btn = getattr(self, "btn_report", None)
        if btn is None:
            return
        btn.setEnabled(not busy)
        btn.setText(text if busy else "生成特检策略报告")
        if busy:
            self._show_report_progress(text)
        else:
            self._close_report_progress()

    def _show_report_progress(self, text: str) -> None:
        self._report_progress_base_text = (text or "正在处理").rstrip(".。 ")
        self._report_progress_tick = 0
        message = f"{self._report_progress_base_text}..."
        progress = self._report_progress
        if progress is None:
            progress = QProgressDialog(message, None, 0, 0, self)
            progress.setWindowTitle("生成特检策略报告")
            progress.setWindowModality(Qt.WindowModal)
            progress.setCancelButton(None)
            progress.setMinimumDuration(0)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            self._report_progress = progress
        else:
            progress.setLabelText(message)
        progress.show()
        if not self._report_progress_timer.isActive():
            self._report_progress_timer.start()
        QApplication.processEvents()

    def _update_report_progress_text(self) -> None:
        if self._report_progress is None or not self._report_progress_base_text:
            return
        dot_count = (self._report_progress_tick % 3) + 1
        self._report_progress.setLabelText(f"{self._report_progress_base_text}{'.' * dot_count}")
        self._report_progress_tick += 1

    def _close_report_progress(self) -> None:
        if self._report_progress_timer.isActive():
            self._report_progress_timer.stop()
        if self._report_progress is not None:
            try:
                self._report_progress.close()
            except Exception:
                pass
            self._report_progress = None
        self._report_progress_base_text = ""
        self._report_progress_tick = 0

    def _on_report_thread_finished(self) -> None:
        self._report_thread = None
        self._report_worker = None

    def _start_report_generation_worker(self, output_path: str) -> None:
        thread = QThread(self)
        worker = _SpecialStrategyReportWorker(self.facility_code, self.run_id, output_path=output_path)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_report_generation_finished)
        worker.failed.connect(self._on_report_generation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._on_report_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._report_thread = thread
        self._report_worker = worker
        thread.start()

    def _select_report_output_path(self) -> str:
        default_path = Path(self._result_service.default_report_path(self.facility_code))
        default_name = str(default_path)
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择特检策略报告保存路径",
            default_name,
            "Word 文档 (*.docx)",
        )
        selected_path = str(selected_path or "").strip()
        if not selected_path:
            return ""
        output_path = Path(selected_path)
        if output_path.suffix.lower() != ".docx":
            output_path = output_path.with_suffix(".docx")
        existing_paths = [path for path in (output_path, output_path.with_suffix(".pdf")) if path.exists()]
        if existing_paths:
            existing_text = "\n".join(str(path) for path in existing_paths)
            if not ask_yes_no(
                self,
                "文件已存在",
                f"目标位置已存在同名输出文件：\n{existing_text}\n\n是否替换？",
            ):
                return ""
        return str(output_path)

    def _on_report(self):
        """
        图二按钮：先上传检验等级图，再生成特检策略报告。
        轮廓图不在这里上传。
        """
        context = (self._result_bundle or {}).get("context") or {}
        if not context:
            QMessageBox.warning(self, "生成报告失败", "当前没有可用的特检策略结果，无法导出检验等级图。")
            return

        if self._export_timer.isActive():
            QMessageBox.information(self, "提示", "检验等级图正在导出，请稍候。")
            return

        if self._report_thread is not None and self._report_thread.isRunning():
            QMessageBox.information(self, "提示", "特检策略报告正在生成，请稍候。")
            return

        output_path = self._select_report_output_path()
        if not output_path:
            return

        self._pending_report_after_risk_export = True
        self._pending_report_output_path = output_path
        self._set_report_button_busy(True, "正在导出检验等级图...")
        self._schedule_export_all_elevation_images(context, force=True)

    def _do_generate_report_after_risk_export(self):
        self._pending_report_after_risk_export = False

        if self._report_thread is not None and self._report_thread.isRunning():
            return

        output_path = self._pending_report_output_path
        self._pending_report_output_path = ""

        if not output_path:
            self._set_report_button_busy(False)
            return

        self._set_report_button_busy(True, "正在生成报告...")
        self._start_report_generation_worker(output_path)

    def _on_report_generation_finished(self, report_path_text: str) -> None:
        self._set_report_button_busy(False)
        word_path = Path(str(report_path_text)).resolve()
        pdf_path = word_path.with_suffix(".pdf")

        if pdf_path.exists():
            QMessageBox.information(
                self,
                "生成报告",
                f"特检策略报告已生成：\nWord：{word_path}\nPDF：{pdf_path}",
            )
            return

        QMessageBox.information(
            self,
            "生成报告",
            f"特检策略报告已生成：\nWord：{word_path}",
        )

    def _on_report_generation_failed(self, message: str) -> None:
        self._set_report_button_busy(False)
        QMessageBox.warning(self, "生成报告失败", f"特检策略报告生成失败：\n{message}")
