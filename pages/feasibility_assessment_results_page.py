# -*- coding: utf-8 -*-
# pages/feasibility_assessment_results_page.py
#
# 结构强度 -> WC19-1DPPA平台强度/改造可行性评估评估结果
#
# - 左侧：上方“快速评估汇总信息”表（含合并标题单元格）
#         下方：标签页（构件/节点冲剪/桩应力/操作工况桩基承载力/极端工况桩基承载力） + “快速评估信息”表（含合并标题单元格）
#         左下：生成评估报告按钮
# - 右侧：自动加载 INP，显示线框投影（无额外操作）
#
# 说明：本页面只负责 UI 与基础占位逻辑；真实的结果解析/着色显示可后续接入。

import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Tuple
from urllib import error, request


from PyQt5.QtCore import Qt, QTimer, QRectF

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

from core.base_page import BasePage

from sqlalchemy import create_engine, text
from pages.sacs_compare_view import SacsComparePanel


from shiyou_db.runtime_db import get_mysql_url

from core.dropdown_bar import DropdownBar
from feasibility_analysis_services.history_rebuild_service import build_history_rebuild_summary, get_history_rebuild_projects
from feasibility_analysis_services.oilfield_env_service import (
    get_env_profile_id,
    load_metric_items,
    load_platform_strength_marine_items,
    load_platform_strength_pile_items,
    load_platform_strength_splash_items,
    load_water_level_items,
)
from services.inspection_business_db_adapter import load_facility_profile, list_inspection_projects
from services.inspection_business_db_adapter import load_platform_load_information_items
from services.file_db_adapter import DOC_MAN_MODULE_CODE, list_files_by_prefix

from pages.sacs_storage_service import get_job_runtime_dir, get_job_source_dir

def _resolve_result_model_paths(self):
    runtime_dir = os.path.normpath(get_job_runtime_dir(self.job_name))
    source_dir = os.path.normpath(get_job_source_dir(self.job_name))

    original_model = os.path.join(source_dir, "sacinp.JKnew")
    new_model = os.path.join(runtime_dir, "sacinp.M1")

    # 新模型不存在时，临时回退到原模型，避免右侧空白
    preview_model = new_model if os.path.exists(new_model) else original_model

    return {
        "original_model": original_model if os.path.exists(original_model) else "",
        "new_model": new_model if os.path.exists(new_model) else "",
        "preview_model": preview_model if os.path.exists(preview_model) else "",
    }

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
    DETAIL_HEADERS = {
        "构件": ["序号", "构件名称", "最大UC值", "对应工况", "是否满足"],
        "节点冲剪": ["序号", "节点名称", "最大UC值", "对应工况", "是否满足"],
        "桩应力": ["序号", "桩头ID", "距离桩头(m)", "最大UC值", "对应工况", "是否满足"],
        "操作工况桩基承载力": ["序号", "构件名称", "最大（最小） UC值", "对应工况", "是否满足"],
        "极端工况桩基承载力": ["序号", "构件名称", "最大（最小） UC值", "对应工况", "是否满足"],
    }
    PILE_CAPACITY_STATIC_ROWS = [
        ["P101", "110887", "117019", "6864.3", "OL37", "37389", "-", "-", "2.51", "-"],
        ["P201", "110887", "117019", "6864.3", "OL36", "35407.2", "-", "-", "2.62", "-"],
        ["P301", "110887", "117019", "6864.3", "OL36", "31457", "-", "-", "2.89", "-"],
        ["P104", "110887", "117019", "6864.3", "OL47", "40428.6", "-", "-", "2.34", "-"],
        ["P204", "110887", "117019", "6864.3", "OL48", "36717.9", "-", "-", "2.54", "-"],
        ["P304", "110887", "117019", "6864.3", "OL48", "32869.2", "-", "-", "2.79", "-"],
        ["P105", "110887", "117019", "6864.3", "OL13", "36638.8", "-", "-", "2.55", "-"],
        ["P205", "110887", "117019", "6864.3", "OL14", "34679.9", "-", "-", "2.67", "-"],
        ["P305", "110887", "117019", "6864.3", "OL14", "30875.3", "-", "-", "2.94", "-"],
        ["P108", "110887", "117019", "6864.3", "OL23", "39901", "-", "-", "2.37", "-"],
        ["P208", "110887", "117019", "6864.3", "OL22", "36242.6", "-", "-", "2.57", "-"],
        ["P308", "110887", "117019", "6864.3", "OL22", "32245.5", "-", "-", "2.84", "-"],
    ]
    INSPECTION_RECORD_SUMMARY_PLACEHOLDER = (
        "来自检验记录最近一次检验（包括定期检验1-N和特殊事件检测）的信息和结论"
        "（可在事件名称后增加“描述”一栏））"
    )
    DEFAULT_REPORT_API_URL = "http://127.0.0.1:8000/generate-report"

    def __init__(self, main_window, facility_code, job_name="", mysql_url="", platform_overview_text="", inspection_record_summary_text="", env_branch="", env_op_company="", env_oilfield="", parent=None):
        if parent is None:
            parent = main_window
        super().__init__("", parent)

        self.main_window = main_window
        self.facility_code = facility_code
        self.job_name = job_name or facility_code
        self.mysql_url = (mysql_url or get_mysql_url()).strip()
        self.platform_overview_text = str(platform_overview_text or "").strip()
        self.inspection_record_summary_text = str(inspection_record_summary_text or "").strip()
        self.env_branch = str(env_branch or "").strip()
        self.env_op_company = str(env_op_company or "").strip()
        self.env_oilfield = str(env_oilfield or "").strip()
        self.current_tab = "构件"

        self._build_ui()
        QTimer.singleShot(0, self.reload_model_view)

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
        lay.setSpacing(6)

        self.model_panel = SacsComparePanel(frame)
        lay.addWidget(self.model_panel, 1)

        return frame

    # def _autoload_inp_to_view(self):
    #     here = os.path.dirname(os.path.abspath(__file__))
    #     candidates = [
    #         first_existing_path("data", "demo_platform_jacket.inp"),
    #         first_existing_path("upload", "demo_platform_jacket.inp"),
    #         os.path.normpath(os.path.join(here, "..", "data", "demo_platform_jacket.inp")),
    #         os.path.normpath(os.path.join(here, "..", "upload", "demo_platform_jacket.inp")),
    #         first_existing_path("demo_platform_jacket.inp"),
    #     ]
    #     path = next((p for p in candidates if os.path.exists(p)), "")
    #     if not path:
    #         self.inp_view.clear_view("未找到 INP：demo_platform_jacket.inp\n请放到 data/ 或 upload/ 目录")
    #         return
    #     try:
    #         self.inp_view.load_inp(path)
    #     except Exception as e:
    #         self.inp_view.clear_view(f"INP 加载失败：\n{e}")

    # ---------------- 表格通用样式 ----------------
    def _init_table_common(self, table: QTableWidget):
        # 强制在代码层面设置 table 字体为 12pt，防止 TableWidgetItem 获取默认 QFont 时丢失大小信息
        font = table.font()
        font.setFamily("SimSun")
        font.setPointSize(12)
        table.setFont(font)

        table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)

        table.setStyleSheet("""
                    QTableWidget {
                        background-color: #ffffff;
                        gridline-color: #d0d0d0;
                        font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                        font-size: 12pt;
                    }
                    QTableWidget::item { border: 1px solid #e6e6e6; padding: 6px; }
                    QTableWidget::item:selected { background-color: #dbe9ff; color: #000000; }
                    QTableWidget::item:focus { outline: none; }
                    QHeaderView::section {
                        background-color: #f3f6fb;
                        border: 1px solid #e6e6e6;
                        padding: 6px;
                        font-weight: normal;
                        font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                        font-size: 12pt;
                    }
                """)
        # 隐藏默认 header，用“表内表头”实现合并单元格
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)

        table.horizontalHeader().setStretchLastSection(False)
        # table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        table.verticalHeader().setDefaultSectionSize(32)

    # 设置单元格内容
    def _set_cell(self, table: QTableWidget, r: int, c: int, text: str, bg: QColor = None, bold: bool = False, align_center: bool = True, editable: bool = True):
        it = QTableWidgetItem(str(text))
        if align_center:
            it.setTextAlignment(Qt.AlignCenter)
        if bg is not None:
            it.setBackground(QBrush(bg))
            
        f = it.font()
        f.setFamily("SimSun")
        f.setPointSize(12) # 强制给每个创建的 item 单独指定大小
        f.setBold(False)
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

        headers = ["核校内容", "位置", "最大UC值/最小安全系数", "对应工况", "是否满足"]
        for c, h in enumerate(headers):
            self._set_cell(self.tbl_summary, 1, c, h, bg=self.HDR_BG, bold=True, editable=False)

        # 数据行（与原型图可见内容一致）
        items = [
            "构件",
            "节点冲剪",
            "桩应力",
            "操作工况桩基抗压",
            "操作工况桩基抗拔",
            "极端工况桩基抗压",
            "极端工况桩基抗拔"
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
        self.tbl_summary.setRowHeight(0, 34)
        for r in range(1, rows):
            self.tbl_summary.setRowHeight(r, 32)

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

        tabs = ["构件", "节点冲剪", "桩应力", "操作工况桩基承载力", "极端工况桩基承载力"]

        # 准备堆叠容器存放不同的表格 (保留你之前的 QStackedWidget 逻辑)
        self.table_stack = QStackedWidget()
        self.detail_tables = {}

        for i, t in enumerate(tabs):
            btn = QPushButton(t)
            btn.setCheckable(True)
            btn.setFixedHeight(36)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            # 新增：必须在计算 text_width 之前，先将按钮的字体设为 12pt 加粗，否则会按默认的小字体计算导致宽度不够
            f = btn.font()
            f.setFamily("SimSun")
            f.setPointSize(12)
            f.setBold(False)
            btn.setFont(f)

            # 【修改点】：根据文字的实际绘制长度动态分配宽度，外加 30 像素的留白
            text_width = btn.fontMetrics().horizontalAdvance(t)
            btn.setMinimumWidth(text_width + 24)
            # 【关键点2】样式中必须有 border-right: none; 这样按钮才能无缝拼接，且中间边框不会变粗
            btn.setStyleSheet("""
                        QPushButton {
                            background: #efefef;
                            color: #1f2a36;
                            border: 1px solid #3b3b3b;
                            border-right: none;  /* 隐藏右边框 */
                            padding: 0 8px;
                            font-weight: normal;
                            font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                            font-size: 12pt;
                        }
                        QPushButton:hover {
                            background: #f5f5f5;
                        }
                        QPushButton:pressed {
                            background: #e6e6e6;
                        }
                        QPushButton:checked {
                            background: #d6f0d0;
                            color: #1f2a36;
                            border: 1px solid #3b3b3b;
                            border-right: none;
                            font-weight: bold;
                        }
                        QPushButton:checked:hover {
                            background: #d6f0d0;
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

        # 【关键点3】因为所有按钮都没了右边框，末尾必须加一个固定大小的块来“封口"
        spacer = QWidget()
        spacer.setStyleSheet("border: 1px solid #3b3b3b; border-left:none; background:#efefef;")
        spacer.setFixedSize(12, 36)  # 宽度32（可调），高度和按钮保持一致
        tab_lay.addWidget(spacer)

        # 【关键点4】在最右侧增加弹簧。它会吸收所有剩余的空白空间，将左侧的所有按钮紧紧地向左挤压
        tab_lay.addStretch(1)

        # ====== 新增：右侧“显示行数”控件 ======
        lbl_rows = QLabel("显示行数：")
        lbl_rows.setStyleSheet("font-size: 12pt; color: #333; font-weight: normal;")
        tab_lay.addWidget(lbl_rows, 0)

        self.cb_row_limit = QComboBox()
        self.cb_row_limit.addItems(["10", "20", "50", "100", "全部"])
        self.cb_row_limit.setFixedHeight(32)
        self.cb_row_limit.setStyleSheet("""
                    QComboBox {
                        border: 1px solid #b9c6d6;
                        border-radius: 3px;
                        padding: 3px 10px 3px 5px;
                        background: #ffffff;
                        min-width: 60px;
                        font-size: 12pt;
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
        if tab_name in {"操作工况桩基承载力", "极端工况桩基承载力"}:
            return self._create_pile_capacity_table(tab_name)

        headers = self.DETAIL_HEADERS.get(tab_name, self.DETAIL_HEADERS["构件"])
        cols = len(headers)
        # 初始只创建 2 行（标题行 + 表头行），数据行留给动态方法生成
        tbl = QTableWidget(2, cols)
        self._init_table_common(tbl)

        tbl.setSpan(0, 0, 1, cols)
        self._set_cell(tbl, 0, 0, f"{tab_name} - 快速评估信息", bg=self.TITLE_BG, bold=True, editable=False)

        for c, h in enumerate(headers):
            self._set_cell(tbl, 1, c, h, bg=self.HDR_BG, bold=True, editable=False)

        # ====== 列宽自适应与滚动条策略 ======
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tbl.resizeColumnsToContents()

        header = tbl.horizontalHeader()
        for c in range(cols):
            header.setSectionResizeMode(c, QHeaderView.Interactive)
            ideal_width = tbl.columnWidth(c)
            tbl.setColumnWidth(c, max(100, ideal_width + 30))

        header.setStretchLastSection(True)
        # ====================================

        tbl.setRowHeight(0, 34)
        tbl.setRowHeight(1, 32)
        tbl.setProperty("header_rows", 2)
        tbl.setProperty("static_mode", False)

        return tbl

    def _create_pile_capacity_table(self, tab_name: str) -> QTableWidget:
        cols = 10
        header_rows = 3
        rows = header_rows + len(self.PILE_CAPACITY_STATIC_ROWS)

        tbl = QTableWidget(rows, cols)
        self._init_table_common(tbl)

        # 第0行：标题
        tbl.setSpan(0, 0, 1, cols)
        self._set_cell(tbl, 0, 0, f"{tab_name} - 快速评估信息", bg=self.TITLE_BG, bold=True, editable=False)

        # 第1行：一级表头
        tbl.setSpan(1, 0, 2, 1)
        self._set_cell(tbl, 1, 0, "桩头ID", bg=self.HDR_BG, bold=True, editable=False)

        tbl.setSpan(1, 1, 1, 2)
        self._set_cell(tbl, 1, 1, "桩基承载能力(kN)", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 1, 2, "", bg=self.HDR_BG, editable=False)

        self._set_cell(tbl, 1, 3, "桩自重", bg=self.HDR_BG, bold=True, editable=False)

        tbl.setSpan(1, 4, 1, 4)
        self._set_cell(tbl, 1, 4, "设计载荷", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 1, 5, "", bg=self.HDR_BG, editable=False)
        self._set_cell(tbl, 1, 6, "", bg=self.HDR_BG, editable=False)
        self._set_cell(tbl, 1, 7, "", bg=self.HDR_BG, editable=False)

        tbl.setSpan(1, 8, 1, 2)
        self._set_cell(tbl, 1, 8, "安全系数", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 1, 9, "", bg=self.HDR_BG, editable=False)

        # 第2行：二级表头
        self._set_cell(tbl, 2, 1, "抗压", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 2, 2, "抗拔", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 2, 3, "（kN）", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 2, 4, "工况", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 2, 5, "压力(kN)", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 2, 6, "工况", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 2, 7, "拉力(kN)", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 2, 8, "抗压", bg=self.HDR_BG, bold=True, editable=False)
        self._set_cell(tbl, 2, 9, "抗拔", bg=self.HDR_BG, bold=True, editable=False)

        # 数据区（静态示例）
        for i, row_data in enumerate(self.PILE_CAPACITY_STATIC_ROWS):
            rr = header_rows + i
            for c, v in enumerate(row_data):
                bg = self.INDEX_BG if c == 0 else None
                editable = (c != 0)
                self._set_cell(tbl, rr, c, v, bg=bg, editable=editable)

        for r in range(rows):
            tbl.setRowHeight(r, 32)

        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tbl.resizeColumnsToContents()

        header = tbl.horizontalHeader()
        for c in range(cols):
            header.setSectionResizeMode(c, QHeaderView.Interactive)
            ideal_width = tbl.columnWidth(c)
            tbl.setColumnWidth(c, max(96, ideal_width + 24))

        header.setStretchLastSection(True)

        tbl.setProperty("header_rows", header_rows)
        tbl.setProperty("static_mode", True)
        return tbl

    # ------------------- 表格行数控制与事件 --------------------
    def _update_current_table_rows(self):
        """根据下拉框的值，动态调整当前显示表格的行数并填充空单元格"""
        # 静态样表页（操作工况桩基承载力、极端工况桩基承载力）不参与动态行数切换
        idx = self.table_stack.currentIndex()
        if idx == -1:
            return
        current_tbl = self.table_stack.widget(idx)
        if bool(current_tbl.property("static_mode")):
            return

        limit_text = self.cb_row_limit.currentText()
        if limit_text == "全部":
            limit = 200  # UI占位：假设"全部"对应200行测试数据
        else:
            limit = int(limit_text)

        header_rows = int(current_tbl.property("header_rows") or 2)

        # 目标总行数 = 2行表头 + 数据行
        target_rows = header_rows + limit
        current_tbl.setRowCount(target_rows)

        # 补充新增出来的行数据（如果是减少行数，setRowCount 会自动截断）
        for i in range(limit):
            r = header_rows + i
            current_tbl.setRowHeight(r, 32)

            # 判断第0列（序号）是否为空，为空说明是新生成的行，需要初始化格式
            if current_tbl.item(r, 0) is None:
                self._set_cell(current_tbl, r, 0, str(i + 1), bg=self.INDEX_BG, bold=False, editable=False)
                for c in range(1, current_tbl.columnCount()):
                    header_item = current_tbl.item(header_rows - 1, c)
                    header_text = header_item.text() if header_item else ""
                    align_center = ("名称" not in header_text)
                    self._set_cell(current_tbl, r, c, "", bg=None, align_center=align_center)

    def closeEvent(self, event):
        try:
            if hasattr(self, "model_panel") and self.model_panel is not None:
                self.model_panel.safe_close()
                self.model_panel.deleteLater()
                self.model_panel = None
        except Exception:
            pass
        super().closeEvent(event)

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
        btn.setFixedHeight(50)
        btn.setMinimumWidth(220)
        btn.setStyleSheet("""
            QPushButton {
                background: #2aa9df;
                border: 2px solid #1b2a3a;
                border-radius: 6px;
                font-size: 12pt;
                font-weight: normal;
            }
            QPushButton:hover { background: #4bbbe8; }
        """)
        btn.clicked.connect(self._on_generate_report)

        lay.addWidget(btn, 0, Qt.AlignLeft)
        lay.addStretch(1)
        return wrap

    def _get_engine(self):
        if not self.mysql_url:
            raise ValueError("MYSQL_URL 未配置")
        return create_engine(self.mysql_url, future=True, pool_pre_ping=True)

    def _get_current_job_factor_path(self) -> str:
        runtime_dir = os.path.normpath(get_job_runtime_dir(self.job_name))
        factor_path = os.path.join(runtime_dir, "psilst.factor")
        if not os.path.exists(factor_path):
            raise FileNotFoundError(
                "未找到当前任务生成的结果文件："
                f"{factor_path}\n请先完成当前任务的“计算分析”。"
            )
        return factor_path

    def _build_report_payload(self) -> dict:
        factor_path = self._get_current_job_factor_path()

        platform_overview = ""
        platform_overview_blocks = []
        facility_profile = load_facility_profile(self.facility_code)
        platform_description = str(facility_profile.get("description_text") or "").strip()
        if not platform_description:
            raise ValueError(
                f"当前平台 {self.facility_code} 未维护平台描述，请先在“建设阶段完工文件”页面补充“平台描述”后再生成报告。"
            )
        platform_overview_blocks.append(
            {
                "text": platform_description,
                "anchor_prefix": "例子：",
                "anchor_occurrence": 1,
            }
        )

        history_rebuild_summary = build_history_rebuild_summary(
            self.facility_code,
            mysql_url=self.mysql_url,
        )
        history_rebuild_projects = get_history_rebuild_projects(
            self.facility_code,
            mysql_url=self.mysql_url,
        )
        if history_rebuild_summary:
            platform_overview_blocks.append(
                {
                    "text": history_rebuild_summary,
                    "anchor_prefix": "（第二部分：来自历次改造信息里每一个改造项目的信息和结论）",
                    "replace_next_paragraph": True,
                    "preserve_anchor_style": True,
                }
            )

        inspection_record_summary_text = self._build_latest_inspection_record_summary()
        if not inspection_record_summary_text:
            inspection_record_summary_text = (
                self.inspection_record_summary_text or self.INSPECTION_RECORD_SUMMARY_PLACEHOLDER
            )
        if inspection_record_summary_text:
            platform_overview_blocks.append(
                {
                    "text": inspection_record_summary_text,
                    "anchor_prefix": "例子：",
                    "anchor_occurrence": 3,
                    "preserve_anchor_style": True,
                }
            )

        if platform_overview_blocks:
            platform_overview = {
                "mode": "replace_region",
                "blocks": platform_overview_blocks,
            }

        chapter_1_3 = {
            "cover_meta": {
                "platform_name": self._build_cover_platform_name(facility_profile),
            },
            "platform_overview": platform_overview,
            "retrofit_history": {
                "table_rows": [
                    {
                        "index": project.get("index", ""),
                        "name": project.get("name", ""),
                        "year": project.get("year", ""),
                    }
                    for project in history_rebuild_projects
                ]
            },
            "platform_evaluation_conclusion": self._build_platform_evaluation_conclusion_section(),
            "basis_data": self._build_basis_data_section(),
            "load_information": self._build_load_information_section(facility_profile),
            "environment_conditions": self._build_environment_conditions_section(),
            "analysis_model": "",
        }

        return {
            "factor_path": factor_path,
            "output_filename": f"{self.facility_code}_可行性评估报告.docx",
            "chapter_1_3": chapter_1_3,
        }

    def _build_cover_platform_name(self, facility_profile: dict) -> str:
        facility_name = str(facility_profile.get("facility_name") or "").strip()
        if facility_name.endswith("平台"):
            facility_name = facility_name[:-2].strip()
        return facility_name or self.facility_code

    def _build_platform_evaluation_conclusion_section(self) -> dict:
        statistics = self._load_platform_evaluation_statistics()
        return {
            "well_slot_count": statistics["well_slot_count"],
            "riser_count": statistics["riser_count"],
            "topside_weight_sum_t": statistics["topside_weight_sum_t"],
        }

    def _build_basis_data_section(self) -> dict:
        construction_files = self._list_basis_data_files(
            [
                ["详细设计"],
                ["完工文件"],
                ["安装文件"],
            ]
        )
        history_rebuild_files = self._list_basis_data_files(
            [["历史改造信息"], ["历史改造文件"]]
        )
        inspection_files = self._list_basis_data_files(
            [
                ["定期检测"],
                ["定期检测1-N"],
                ["特殊事件检测"],
                ["特殊事件检测（台风、碰撞等）"],
            ]
        )
        return {
            "mode": "replace_region",
            "blocks": [
                {
                    "text": self._format_basis_data_file_paragraph(construction_files),
                    "anchor_prefix": "1）建设阶段完工文件",
                    "replace_next_paragraph": True,
                    "keep_anchor_paragraph": True,
                    "preserve_anchor_style": True,
                },
                {
                    "text": self._format_basis_data_file_paragraph(history_rebuild_files),
                    "anchor_prefix": "2）历次改造文件",
                    "replace_next_paragraph": True,
                    "keep_anchor_paragraph": True,
                    "preserve_anchor_style": True,
                },
                {
                    "text": self._format_basis_data_file_paragraph(inspection_files),
                    "anchor_prefix": "3）检测记录文件",
                    "replace_next_paragraph": True,
                    "keep_anchor_paragraph": True,
                    "preserve_anchor_style": True,
                },
            ],
        }

    def _build_load_information_section(self, facility_profile: dict) -> dict:
        load_information_rows = []
        try:
            rows = load_platform_load_information_items(self.facility_code)
        except Exception:
            rows = []

        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            load_information_rows.append(
                {
                    "seq_no": str(row.get("seq_no") or index - 1),
                    "project_name": str(row.get("project_name") or "").strip(),
                    "rebuild_time": str(row.get("rebuild_time") or "").strip(),
                    "rebuild_content": str(row.get("rebuild_content") or "").strip(),
                    "total_weight_mt": str(row.get("total_weight_mt") or "").strip(),
                    "weight_limit_mt": str(row.get("weight_limit_mt") or "").strip(),
                    "weight_delta_mt": str(row.get("weight_delta_mt") or "").strip(),
                    "center_xyz": str(row.get("center_xyz") or "").strip(),
                    "center_radius_m": str(row.get("center_radius_m") or "").strip(),
                    "fx_kn": str(row.get("fx_kn") or "").strip(),
                    "fy_kn": str(row.get("fy_kn") or "").strip(),
                    "fz_kn": str(row.get("fz_kn") or "").strip(),
                    "mx_kn_m": str(row.get("mx_kn_m") or "").strip(),
                    "my_kn_m": str(row.get("my_kn_m") or "").strip(),
                    "mz_kn_m": str(row.get("mz_kn_m") or "").strip(),
                    "safety_op": str(row.get("safety_op") or "").strip(),
                    "safety_extreme": str(row.get("safety_extreme") or "").strip(),
                    "overall_assessment": str(row.get("overall_assessment") or "").strip(),
                    "assessment_org": str(row.get("assessment_org") or "").strip(),
                }
            )

        return {
            "mode": "replace_region",
            "load_information_meta": {
                "branch": str(facility_profile.get("branch") or "").strip(),
                "op_company": str(facility_profile.get("op_company") or "").strip(),
                "oilfield": str(facility_profile.get("oilfield") or "").strip(),
                "facility_name": str(facility_profile.get("facility_name") or "").strip(),
                "start_time": str(facility_profile.get("start_time") or "").strip(),
                "design_life": str(facility_profile.get("design_life") or "").strip(),
            },
            "load_information_rows": load_information_rows,
        }

    def _iter_basis_data_logical_prefixes(self, path_segments: List[str]):
        normalized_segments = [str(segment or "").strip().strip("/\\") for segment in path_segments]
        normalized_segments = [segment for segment in normalized_segments if segment]
        if not normalized_segments:
            return

        raw_prefix = "/".join(normalized_segments)
        yield raw_prefix

        facility_code = str(getattr(self, "facility_code", "") or "").strip().strip("/\\")
        if facility_code:
            yield f"{facility_code}/{raw_prefix}"

    def _list_basis_data_files(self, path_prefixes: List[List[str]]) -> List[str]:
        if not self.facility_code:
            return []
        file_names: List[str] = []
        seen = set()
        for path_segments in path_prefixes:
            for logical_prefix in self._iter_basis_data_logical_prefixes(path_segments):
                try:
                    rows = list_files_by_prefix(
                        module_code=DOC_MAN_MODULE_CODE,
                        logical_path_prefix=logical_prefix,
                        facility_code=self.facility_code,
                    )
                except Exception:
                    rows = []
                for row in rows:
                    name = str(row.get("original_name") or "").strip()
                    if not name or name in seen:
                        continue
                    seen.add(name)
                    file_names.append(name)
        return file_names

    @staticmethod
    def _format_basis_data_file_paragraph(file_names: List[str]) -> str:
        if not file_names:
            return "暂无文件。"
        return "；".join(f"（{index}）{name}" for index, name in enumerate(file_names, start=1)) + "。"

    def _load_platform_evaluation_statistics(self) -> dict:
        if not self.mysql_url or not self.job_name:
            return {
                "well_slot_count": 0,
                "riser_count": 0,
                "topside_weight_sum_t": 0.0,
            }

        engine = self._get_engine()
        statistics_sql = text(
            """
            SELECT
                (SELECT COUNT(*) FROM well_slots WHERE job_name = :job_name) AS well_slot_count,
                (SELECT COUNT(*) FROM risers WHERE job_name = :job_name) AS riser_count,
                (SELECT COALESCE(SUM(weight_t), 0) FROM topside_weights WHERE job_name = :job_name) AS topside_weight_sum_t
            """
        )
        try:
            with engine.connect() as conn:
                row = conn.execute(statistics_sql, {"job_name": self.job_name}).mappings().first() or {}
        except Exception:
            return {
                "well_slot_count": 0,
                "riser_count": 0,
                "topside_weight_sum_t": 0.0,
            }

        return {
            "well_slot_count": int(row.get("well_slot_count") or 0),
            "riser_count": int(row.get("riser_count") or 0),
            "topside_weight_sum_t": float(row.get("topside_weight_sum_t") or 0.0),
        }

    def _build_latest_inspection_record_summary(self) -> str:
        projects = []
        for project_type in ("periodic", "special_event"):
            try:
                rows = list_inspection_projects(self.facility_code, project_type)
            except Exception:
                rows = []
            for row in rows:
                summary_text = str(row.get("summary_text") or "").strip()
                year_value = self._extract_inspection_project_year(row)
                if not summary_text or year_value is None:
                    continue
                projects.append(
                    {
                        "year": year_value,
                        "project_name": str(row.get("project_name") or "").strip(),
                        "summary_text": summary_text.rstrip("；;。"),
                    }
                )

        if not projects:
            return ""

        latest_year = max(project["year"] for project in projects)
        latest_projects = []
        for project in projects:
            if project["year"] != latest_year:
                continue
            latest_projects.append(project)

        if not latest_projects:
            return ""

        named_projects = [project["project_name"] for project in latest_projects if project["project_name"]]
        conclusion_fragments = []
        for project in latest_projects:
            summary_text = project["summary_text"]
            conclusion_fragments.append(summary_text)

        if named_projects:
            if len(named_projects) == 1:
                project_intro = named_projects[0]
            else:
                project_intro = "和".join(named_projects)
        else:
            project_intro = "检验结果"
        return f"{latest_year}年{project_intro}显示，" + "；".join(conclusion_fragments) + "。"

    @staticmethod
    def _extract_inspection_project_year(row: dict) -> int | None:
        for raw_value in (row.get("project_year"), row.get("event_date")):
            text = str(raw_value or "").strip()
            if not text:
                continue
            match = re.search(r"(19|20)\d{2}", text)
            if match:
                return int(match.group(0))
        return None

    def _build_environment_conditions_section(self) -> dict:
        if not (self.mysql_url and self.env_branch and self.env_op_company and self.env_oilfield):
            return {}

        profile_id = get_env_profile_id(
            branch=self.env_branch,
            op_company=self.env_op_company,
            oilfield=self.env_oilfield,
            mysql_url=self.mysql_url,
            create_if_missing=False,
        )
        if not profile_id:
            return {}

        water_level_rows = load_water_level_items(profile_id, mysql_url=self.mysql_url)
        wind_rows = load_metric_items("oilfield_wind_param_item", profile_id, mysql_url=self.mysql_url)
        wave_rows = load_metric_items("oilfield_wave_param_item", profile_id, mysql_url=self.mysql_url)
        current_rows = load_metric_items("oilfield_current_param_item", profile_id, mysql_url=self.mysql_url)
        marine_growth_rows = load_platform_strength_marine_items(
            profile_id,
            self.facility_code,
            mysql_url=self.mysql_url,
        )
        pile_rows = load_platform_strength_pile_items(
            profile_id,
            self.facility_code,
            mysql_url=self.mysql_url,
        )
        splash_zone_rows = load_platform_strength_splash_items(
            profile_id,
            self.facility_code,
            mysql_url=self.mysql_url,
        )
        foundation_scour_text = self._extract_foundation_scour_text(pile_rows)

        if not (
            water_level_rows
            or wind_rows
            or wave_rows
            or current_rows
            or marine_growth_rows
            or splash_zone_rows
            or foundation_scour_text
        ):
            return {}

        section = {
            "water_level_rows": [self._normalize_environment_row(row) for row in water_level_rows],
            "wind_rows": [self._normalize_environment_row(row) for row in wind_rows],
            "wave_rows": [self._normalize_environment_row(row) for row in wave_rows],
            "current_rows": [self._normalize_environment_row(row) for row in current_rows],
            "marine_growth_rows": [self._normalize_environment_row(row) for row in marine_growth_rows],
            "splash_zone_rows": [self._normalize_environment_row(row) for row in splash_zone_rows],
        }
        if foundation_scour_text:
            section["blocks"] = [
                {
                    "text": f"在分析中，考虑{foundation_scour_text}m（来自平台基本信息的桩基信息基础冲刷）冲刷深度。",
                    "anchor_prefix": "在分析中，考虑",
                    "preserve_anchor_style": True,
                }
            ]
        return section

    def _validate_environment_conditions_for_report(self) -> str:
        if not (self.env_branch and self.env_op_company and self.env_oilfield):
            return "当前平台未关联完整的环境条件上下文，缺少分公司/作业公司/油气田信息，无法生成包含第 2.5 节的报告。"

        if not self.mysql_url:
            return "MYSQL_URL 未配置，无法校验当前油气田的环境条件数据。"

        profile_id = get_env_profile_id(
            branch=self.env_branch,
            op_company=self.env_op_company,
            oilfield=self.env_oilfield,
            mysql_url=self.mysql_url,
            create_if_missing=False,
        )
        if not profile_id:
            return f"当前油气田“{self.env_oilfield}”未配置环境条件数据，无法填充报告第 2.5 节。"

        missing_tables = []
        if not load_water_level_items(profile_id, mysql_url=self.mysql_url):
            missing_tables.append("水深水位表")
        if not load_metric_items("oilfield_wave_param_item", profile_id, mysql_url=self.mysql_url):
            missing_tables.append("波浪参数表")
        if not load_metric_items("oilfield_current_param_item", profile_id, mysql_url=self.mysql_url):
            missing_tables.append("海流参数表")
        if not load_metric_items("oilfield_wind_param_item", profile_id, mysql_url=self.mysql_url):
            missing_tables.append("风参数表")
        if not load_platform_strength_marine_items(profile_id, self.facility_code, mysql_url=self.mysql_url):
            missing_tables.append("海生物信息表")
        pile_rows = load_platform_strength_pile_items(
            profile_id,
            self.facility_code,
            mysql_url=self.mysql_url,
        )
        if not self._extract_foundation_scour_text(pile_rows):
            missing_tables.append("桩基信息表（基础冲刷）")
        if not load_platform_strength_splash_items(profile_id, self.facility_code, mysql_url=self.mysql_url):
            missing_tables.append("飞溅区腐蚀余量表")
        if missing_tables:
            return f"当前油气田“{self.env_oilfield}”环境条件数据不完整，缺少{'、'.join(missing_tables)}，无法完整生成报告第 2.5 节。"
        return ""

    @staticmethod
    def _format_report_number(value) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        try:
            decimal_value = Decimal(text)
        except (InvalidOperation, ValueError):
            return text
        normalized = format(decimal_value, "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return "0" if normalized in {"", "-0", "+0"} else normalized

    def _extract_foundation_scour_text(self, pile_rows: List[dict]) -> str:
        for row in pile_rows:
            scour_text = self._format_report_number(row.get("scour_depth_m"))
            if scour_text:
                return scour_text
        return ""

    def _normalize_environment_row(self, row: dict) -> dict:
        return {
            "group_name": str(row.get("group_name") or "").strip(),
            "item_name": str(row.get("item_name") or "").strip(),
            "return_period": "" if row.get("return_period") is None else str(row.get("return_period")).strip(),
            "value": "" if row.get("value") is None else str(row.get("value")).strip(),
            "unit": str(row.get("unit") or "").strip(),
            "layer_no": "" if row.get("layer_no") is None else str(row.get("layer_no")).strip(),
            "upper_limit_m": "" if row.get("upper_limit_m") is None else str(row.get("upper_limit_m")).strip(),
            "lower_limit_m": "" if row.get("lower_limit_m") is None else str(row.get("lower_limit_m")).strip(),
            "thickness_mm": "" if row.get("thickness_mm") is None else str(row.get("thickness_mm")).strip(),
            "density_t_per_m3": "" if row.get("density_t_per_m3") is None else str(row.get("density_t_per_m3")).strip(),
            "corrosion_allowance_mm_per_y": "" if row.get("corrosion_allowance_mm_per_y") is None else str(row.get("corrosion_allowance_mm_per_y")).strip(),
        }

    def _post_report_request(self, payload: dict) -> dict:
        api_url = self.DEFAULT_REPORT_API_URL
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            api_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            if "Permission denied" in detail and ".docx" in detail:
                try:
                    detail_payload = json.loads(detail)
                    raw_detail = str(detail_payload.get("detail", "")).strip()
                except Exception:
                    raw_detail = detail.strip()
                locked_file = raw_detail.split(":", 1)[-1].strip().strip("'\"")
                raise RuntimeError(
                    "报告生成失败：目标 Word 文件正被占用，请先关闭已打开的报告后重试。\n"
                    f"被占用文件：{locked_file}"
                ) from exc
            raise RuntimeError(f"报告服务返回错误：HTTP {exc.code}\n{detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"无法连接报告服务，请确认 WordTemplate_v2 API 已启动：{self.DEFAULT_REPORT_API_URL}") from exc

    def _get_report_mode(self) -> str:
        mode = str(os.environ.get("REPORT_GENERATION_MODE", "auto")).strip().lower()
        return mode if mode in {"auto", "http", "local"} else "auto"

    def _get_wordtemplate_project_root(self) -> Path:
        return Path(__file__).resolve().parents[2] / "WordTemplate_v2"

    def _generate_report_locally(self, payload: dict) -> dict:
        project_root = self._get_wordtemplate_project_root()
        if not (project_root / "src").exists():
            raise FileNotFoundError(f"未找到本地报告项目源码目录：{project_root / 'src'}")
        project_root_text = str(project_root)
        if project_root_text not in sys.path:
            sys.path.insert(0, project_root_text)
        from src.report_service import generate_report_with_project_defaults

        output_filename = str(payload.get("output_filename", "")).strip()
        output_path = str(project_root / "output" / output_filename) if output_filename else None
        result = generate_report_with_project_defaults(
            project_root=project_root,
            chapter_1_3_sources=payload.get("chapter_1_3", {}),
            factor_path=payload.get("factor_path"),
            template_path=payload.get("template_path"),
            output_path=output_path,
        )
        return {"message": "report generated (local)", "output_path": result}

    def _generate_report(self, payload: dict) -> dict:
        mode = self._get_report_mode()
        if mode == "http":
            return self._post_report_request(payload)
        if mode == "local":
            return self._generate_report_locally(payload)
        try:
            return self._post_report_request(payload)
        except RuntimeError as exc:
            if "无法连接报告服务" not in str(exc):
                raise
        return self._generate_report_locally(payload)

    def _fetch_model_paths(self):
        sql = text("""
            SELECT model_file, new_model_file, workpoint
            FROM wizard_model_info
            WHERE job_name = :job_name
            ORDER BY id DESC
            LIMIT 1
        """)

        engine = self._get_engine()
        with engine.begin() as conn:
            row = conn.execute(sql, {"job_name": self.job_name}).mappings().first()

        if row is None:
            raise ValueError(f"wizard_model_info 中未找到 job_name={self.job_name} 的记录")

        old_file = str(row["model_file"] or "").strip()
        new_file = str(row["new_model_file"] or "").strip()
        workpoint = float(row["workpoint"]) if row["workpoint"] is not None else 9.1

        return old_file, new_file, workpoint

    def reload_model_view(self):
        try:
            old_file, new_file, workpoint = self._fetch_model_paths()
            self.model_panel.load_files(old_file, new_file, target_z=workpoint)
        except Exception as e:
            if hasattr(self, "model_panel"):
                self.model_panel.path_label.setText("模型加载失败")
                self.model_panel.compare_view.clear_view(f"右侧模型加载失败：\n{e}")

    def _on_generate_report(self):
        try:
            environment_error = self._validate_environment_conditions_for_report()
            if environment_error:
                QMessageBox.warning(self, "环境条件缺失", environment_error)
                return

            payload = self._build_report_payload()
            result = self._generate_report(payload)
            output_path = str(result.get("output_path", "")).strip()
            if not output_path:
                raise RuntimeError(f"报告服务返回异常：{result}")
            QMessageBox.information(self, "生成成功", f"报告已生成：\n{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "生成报告失败", str(e))
