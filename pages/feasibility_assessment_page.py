# -*- coding: utf-8 -*-
# pages/feasibility_assessment_page.py
#
# 结构强度 -> WC19-1DPPA平台强度/改造可行性评估
#
# 本版改动：
# - 三张表格采用“表内多行表头 + 合并单元格（setSpan）”来匹配原型图样式
# - “高程及连接形式”列使用 QComboBox，并保证宽度可显示完整文本
# - 取消三张表格各自保存按钮，底部统一使用“保存数据”按钮；保存后才能创建新模型

import os
import shutil
import subprocess
import time
from typing import List, Optional, cast

from PyQt5.QtCore import QEvent, QTimer, Qt, QUrl,QProcess
from PyQt5.QtGui import QBrush, QColor, QFont, QFontMetrics, QMouseEvent
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QMenu,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QWidget,
    QPushButton,
    QScrollArea,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QDialog,
    QTextEdit,
    QHeaderView,
)
from PyQt5.QtGui import QDesktopServices

from sqlalchemy import create_engine, text

from core.base_page import BasePage

from pages.feasibility_assessment_results_page import FeasibilityAssessmentResultsPage
from pages.sacs_create_model_service import create_new_model_files
from core.app_paths import first_existing_path

from pages.sacs_runtime_service import ensure_analysis_bat, find_result_file, rewrite_runx_input_file_names

from shiyou_db.runtime_db import get_mysql_url

from pages.sacs_storage_service import get_job_runtime_dir, stage_support_files_for_job
from services.history_rebuild_auto_service import (
    prepare_latest_rebuild_runtime_for_analysis,
    prepare_original_runtime_for_analysis,
)

SONGTI_FONT_FALLBACK = '"SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"'


class ScrollSafeComboBox(QComboBox):
    def wheelEvent(self, event):
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        event.ignore()


class FeasibilityAssessmentPage(BasePage):
    """
    WC19-1DPPA平台强度/改造可行性评估（feasibility_assessment_page）
    """
    CONNECT_OPTIONS = ["焊接", "无连接", "导向连接"]
    LEGACY_ELEVATIONS1 = [36, 31, 27, 23, 18, 7, -12, -34, -58, -83, -109]
    LEGACY_ELEVATIONS2 = [7, -12, -34, -58, -83, -109, -122.4]

    # 表头颜色
    HEADER_BG = QColor("#cfe4b5")   # 浅绿
    SUBHDR_BG = QColor("#cfe4b5")   # 同色（原型里基本一致）
    DATA_BG   = QColor("#ffffff")   # 白

    @staticmethod
    def _songti_small_four_font(bold: bool = False) -> QFont:
        font = QFont("SimSun", 12)
        font.setBold(bold)
        return font

    @staticmethod
    def _menu_qss() -> str:
        return """
            QMenu {
                background-color: #ffffff;
                color: #1d2b3a;
                border: 1px solid #cfd8e3;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 18px;
                background-color: transparent;
                color: #1d2b3a;
            }
            QMenu::item:selected {
                background-color: #dbe9ff;
                color: #1d2b3a;
            }
            QMenu::item:disabled {
                color: #8a94a6;
                background-color: #f7f9fc;
            }
        """

    def __init__(self, main_window, facility_code, elevations=None, platform_overview_text="", inspection_record_summary_text="", env_branch="", env_op_company="", env_oilfield="", overall_model_image_path="", parent=None):
        if parent is None:
            parent = main_window
        super().__init__("", parent)

        self.facility_code = facility_code
        self.main_window = main_window

        self._hover_combo_boxes = []
        self._combo_hover_meta = {}
        self._dynamic_table_meta = {}

        self.job_name = facility_code
        self.mysql_url = get_mysql_url()
        self.platform_overview_text = str(platform_overview_text or "").strip()
        self.inspection_record_summary_text = str(inspection_record_summary_text or "").strip()
        self.env_branch = str(env_branch or "").strip()
        self.env_op_company = str(env_op_company or "").strip()
        self.env_oilfield = str(env_oilfield or "").strip()
        self.overall_model_image_path = str(overall_model_image_path or "").strip()

        self.elevations = list(elevations) if elevations is not None else []
        self._use_dynamic_elevations = bool(elevations)
        if self._use_dynamic_elevations:
            dynamic_elevations = list(elevations or [])
            self.table1_elevations = dynamic_elevations
            self.table2_elevations = list(dynamic_elevations)
        else:
            self.table1_elevations = list(self.LEGACY_ELEVATIONS1)
            self.table2_elevations = list(self.LEGACY_ELEVATIONS2)

        # SACS 运行相关路径（统一指向 upload/model_files）
        self.model_files_root = first_existing_path("upload", "model_files")  # 仅保留兜底
        self.current_model_dir = get_job_runtime_dir(self.job_name)
        self.current_runx_file = ""
        self.current_bat_file = ""
        self.current_result_file = ""
        self.current_stdout_log = ""
        self.current_exitcode_file = ""

        self.analysis_process = None

        # 三个输入表格统一保存状态：
        # 用户可以只填写井槽/立管/组块载荷中的任意一种或任意组合，
        # 点击底部“保存数据”后统一写入数据库，之后才允许创建新模型。
        self._input_data_saved = False
        self._input_data_locked = False
        self._model_created_in_session = False

        self._build_ui()
        self._refresh_runtime_paths_from_disk()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # # 顶部 DropdownBar（同平台基本信息）
        # fields = [
        #     {"key": "branch", "label": "分公司", "options": ["湛江分公司"], "default": "湛江分公司"},
        #     {"key": "op_company", "label": "作业公司", "options": ["文昌油田群作业公司"], "default": "文昌油田群作业公司"},
        #     {"key": "oilfield", "label": "油气田", "options": ["文昌19-1油田"], "default": "文昌19-1油田"},
        #     {"key": "facility_code", "label": "设施编号", "options": ["WC19-1DPPA"], "default": "WC19-1DPPA"},
        #     {"key": "facility_name", "label": "设施名称", "options": ["WC19-1DPPA井口平台"], "default": "WC19-1DPPA井口平台"},
        #     {"key": "facility_type", "label": "设施类型", "options": ["平台"], "default": "平台"},
        #     {"key": "category", "label": "分类", "options": ["井口平台"], "default": "井口平台"},
        #     {"key": "start_time", "label": "投产时间", "options": ["2008-06-26"], "default": "2008-06-26"},
        #     {"key": "design_life", "label": "设计年限", "options": ["15"], "default": "15"},
        # ]
        # self.dropdown_bar = DropdownBar(fields, parent=self)
        # self.main_layout.addWidget(self.dropdown_bar, 0)

        # 页面主体（滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        self.main_layout.addWidget(scroll, 1)

        body = QWidget()
        scroll.setWidget(body)
        body.setFont(self._songti_small_four_font())
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 0, 8, 8)
        body_layout.setSpacing(10)

        # body_layout.addWidget(self._build_table_1(), 0)
        # body_layout.addWidget(self._build_table_2(), 0)
        # body_layout.addWidget(self._build_table_3(), 0)
        #
        # body_layout.addWidget(self._build_bottom_actions(), 0)
        # body_layout.addStretch(1)

        # ========== 修改前 ==========
        # body_layout.addWidget(self._build_table_1(), 0)
        # body_layout.addWidget(self._build_table_2(), 0)
        # body_layout.addWidget(self._build_table_3(), 0)
        # body_layout.addWidget(self._build_bottom_actions(), 0)
        # body_layout.addStretch(1)

        # ========== 修改后 ==========
        # body_layout.addWidget(self._build_table_1(), 1)  # 权重设为1，允许表格组块纵向伸展填满留白
        # body_layout.addWidget(self._build_table_2(), 1)
        # body_layout.addWidget(self._build_table_3(), 1)
        #
        # body_layout.addWidget(self._build_bottom_actions(), 0)
        body_layout.addWidget(self._build_table_1(), 0)
        body_layout.addWidget(self._build_table_2(), 0)
        body_layout.addWidget(self._build_table_3(), 0)
        body_layout.addWidget(self._build_bottom_actions(), 0)
        body_layout.addStretch(1)

    # ---------------- 通用表格风格 ----------------
    def _init_table_common(self, table: QTableWidget):
        table.setFont(self._songti_small_four_font())
        table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)

        table.setStyleSheet("""
                    QTableWidget { background-color: #ffffff; gridline-color: #d0d0d0; border: 1px solid #e6e6e6; }
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
        #table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed) 移除这一行，让列宽变得可调整
        table.verticalHeader().setDefaultSectionSize(26)

    def _set_cell(self, table: QTableWidget, r: int, c: int, text: str, *,
                  bg: Optional[QColor] = None, bold: bool = False, editable: bool = True, center: bool = True):
        it = QTableWidgetItem(str(text))
        if center:
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if bg is not None:
            it.setBackground(QBrush(bg))
        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)
        if not editable:
            flags = cast(Qt.ItemFlags, Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            it.setFlags(flags)
        table.setItem(r, c, it)
        return it

    def _set_combo_cell(self, table: QTableWidget, row: int, col: int, default: Optional[str] = None):
        cell_wrap = QWidget()
        cell_wrap.setStyleSheet("background: #ffffff; border: 1px solid #e6e6e6;")
        cell_lay = QHBoxLayout(cell_wrap)
        cell_lay.setContentsMargins(0, 0, 0, 0)
        cell_lay.setSpacing(0)

        combo = ScrollSafeComboBox(cell_wrap)
        combo.addItems(self.CONNECT_OPTIONS)
        combo.setFont(self._songti_small_four_font())

        if default and default in self.CONNECT_OPTIONS:
            combo.setCurrentText(default)
        else:
            combo.setCurrentIndex(-1)  # 不默认选中任何项

        combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        combo.setMinimumContentsLength(6)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        combo.setProperty("showDropdownIndicator", False)

        arrow_btn = QPushButton("▼", cell_wrap)
        arrow_btn.setFixedWidth(18)
        arrow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        arrow_btn.setFont(self._songti_small_four_font(bold=True))
        arrow_btn.setStyleSheet(
            """
            QPushButton {
                background: #eef4fb;
                color: #35506b;
                border: none;
                border-left: 1px solid #c8d3e1;
                padding: 0;
            }
            QPushButton:hover { background: #dbe9f6; }
            """
        )
        arrow_btn.hide()

        combo.installEventFilter(self)
        cell_wrap.installEventFilter(self)
        arrow_btn.installEventFilter(self)
        combo.view().installEventFilter(self)

        self._hover_combo_boxes.append(combo)
        self._combo_hover_meta[combo] = {
            "wrap": cell_wrap,
            "button": arrow_btn,
        }

        self._apply_combo_hover_style(combo, show_indicator=False)
        cell_lay.addWidget(combo)
        cell_lay.addWidget(arrow_btn)
        arrow_btn.clicked.connect(combo.showPopup)
        combo.destroyed.connect(lambda *_args, c=combo: self._cleanup_hover_combo(c))
        table.setCellWidget(row, col, cell_wrap)

    def _cleanup_hover_combo(self, combo: QComboBox):
        self._combo_hover_meta.pop(combo, None)
        self._hover_combo_boxes = [item for item in self._hover_combo_boxes if item is not combo]

    def _apply_combo_hover_style(self, combo: QComboBox, *, show_indicator: bool):
        if show_indicator:
            combo.setStyleSheet("""
                QComboBox {
                    background: #ffffff;
                    border: none;
                    padding: 1px 6px;
                }
                QComboBox::drop-down {
                    width: 0px;
                    border: none;
                }
            """)
        else:
            combo.setStyleSheet("""
                QComboBox {
                    background: #ffffff;
                    border: none;
                    padding: 1px 6px;
                }
                QComboBox::drop-down {
                    width: 0px;
                    border: none;
                }
                QComboBox::down-arrow {
                    image: none;
                    width: 0px;
                    height: 0px;
                }
            """)

    def _set_combo_hover_state(self, combo: QComboBox, show_indicator: bool):
        current = bool(combo.property("showDropdownIndicator"))
        if current == show_indicator:
            return
        combo.setProperty("showDropdownIndicator", show_indicator)
        self._apply_combo_hover_style(combo, show_indicator=show_indicator)
        meta = self._combo_hover_meta.get(combo)
        if meta:
            meta["button"].setVisible(show_indicator)

    def _sync_combo_hover_state(self, combo: QComboBox):
        meta = self._combo_hover_meta.get(combo)
        if not meta:
            return
        wrap = meta["wrap"]
        button = meta["button"]
        show_indicator = combo.view().isVisible() or wrap.underMouse() or combo.underMouse() or button.underMouse()
        self._set_combo_hover_state(combo, show_indicator)

    def _make_empty_item(self, *, bg: Optional[QColor] = None, editable: bool = True) -> QTableWidgetItem:
        item = QTableWidgetItem("")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if bg is not None:
            item.setBackground(QBrush(bg))
        if not editable:
            flags = cast(Qt.ItemFlags, Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setFlags(flags)
        return item

    def _install_row_hover_actions(self, table: QTableWidget, table_key: str, header_rows: int):
        viewport = table.viewport()
        viewport.setMouseTracking(True)
        viewport.installEventFilter(self)

        panel = QWidget(viewport)
        panel.hide()
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        add_btn = QPushButton("+")
        for btn in (add_btn,):
            btn.setFixedSize(20, 20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(self._songti_small_four_font(bold=True))
            btn.setStyleSheet(
                """
                QPushButton {
                    background: #2aa9df;
                    color: #ffffff;
                    border: 1px solid #1b2a3a;
                    border-radius: 10px;
                    font-family: %s;
                    font-size: 12pt;
                    font-weight: bold;
                    padding: 0;
                }
                QPushButton:hover { background: #4bbbe8; }
                """ % SONGTI_FONT_FALLBACK
            )
            layout.addWidget(btn)

        add_btn.clicked.connect(lambda: self._insert_dynamic_row(table_key))

        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, key=table_key: self._show_row_context_menu(key, pos)
        )

        self._dynamic_table_meta[table_key] = {
            "table": table,
            "viewport": viewport,
            "panel": panel,
            "header_rows": header_rows,
            "hover_row": None,
            "context_row": None,
        }

        table.horizontalScrollBar().valueChanged.connect(lambda _=0, key=table_key: self._update_hover_panel_position(key))
        table.verticalScrollBar().valueChanged.connect(lambda _=0, key=table_key: self._update_hover_panel_position(key))

    def _get_last_data_row(self, table_key: str) -> Optional[int]:
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return None
        table = meta["table"]
        header_rows = meta["header_rows"]
        if table.rowCount() <= header_rows:
            return None
        return table.rowCount() - 1

    def _renumber_dynamic_rows(self, table_key: str):
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return
        table = meta["table"]
        header_rows = meta["header_rows"]
        for row in range(header_rows, table.rowCount()):
            self._set_cell(
                table,
                row,
                0,
                str(row - header_rows + 1),
                bg=QColor("#e9eef5"),
                editable=False,
            )

    def _populate_table1_row(self, row: int):
        base_cols = 1 + 2 + 2 + 2 + 1
        self._set_cell(self.tbl1, row, 0, "", bg=QColor("#e9eef5"), editable=False)
        for col in range(1, base_cols):
            self.tbl1.setItem(row, col, self._make_empty_item(bg=self.DATA_BG, editable=True))

        start = base_cols
        for i, elevation in enumerate(self.table1_elevations):
            default = None
            if not self._use_dynamic_elevations:
                default = "焊接" if elevation in (27, 23, 18) else "无连接"
            self._set_combo_cell(self.tbl1, row, start + i, default=default)

    def _populate_table2_row(self, row: int):
        base_cols = 1 + 2 + 2 + 2 + 2
        self._set_cell(self.tbl2, row, 0, "", bg=QColor("#e9eef5"), editable=False)
        for col in range(1, base_cols):
            self.tbl2.setItem(row, col, self._make_empty_item(bg=self.DATA_BG, editable=True))

        start = base_cols
        for i, elevation in enumerate(self.table2_elevations):
            default = None
            if not self._use_dynamic_elevations:
                default = "焊接" if elevation in (27, 23) else "无连接"
            self._set_combo_cell(self.tbl2, row, start + i, default=default)

    def _populate_table3_row(self, row: int):
        self._set_cell(self.tbl3, row, 0, "", bg=QColor("#e9eef5"), editable=False)
        for col in range(1, self.tbl3.columnCount()):
            self.tbl3.setItem(row, col, self._make_empty_item(bg=self.DATA_BG, editable=True))

    def _insert_dynamic_row(self, table_key: str):
        if getattr(self, "_input_data_locked", False):
            return
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return
        table = meta["table"]
        row = table.rowCount()
        self._insert_dynamic_row_at(table_key, row)

    def _get_engine(self):
        if not self.mysql_url:
            raise ValueError("MYSQL_URL 未配置")
        return create_engine(self.mysql_url, future=True, pool_pre_ping=True)


    def _refresh_table_scroll_height(self, table_key: str, max_height: int = 210):
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return

        scroll = meta.get("scroll")
        table = meta.get("table")
        if scroll is None or table is None:
            return

        hbar_h = scroll.horizontalScrollBar().sizeHint().height()
        table_content_h = self._table_content_height(table)
        table.setFixedHeight(table_content_h)
        content_h = table_content_h + hbar_h + 4
        visible_h = min(content_h, max_height)

        scroll.setMinimumHeight(visible_h)
        scroll.setMaximumHeight(visible_h)

    def _insert_dynamic_row_at(self, table_key: str, row: int):
        if getattr(self, "_input_data_locked", False):
            return
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return
        table = meta["table"]
        header_rows = meta["header_rows"]
        if row < header_rows:
            row = header_rows
        if row > table.rowCount():
            row = table.rowCount()
        table.insertRow(row)

        if table_key == "tbl1":
            self._populate_table1_row(row)
        elif table_key == "tbl2":
            self._populate_table2_row(row)
        elif table_key == "tbl3":
            self._populate_table3_row(row)

        self._renumber_dynamic_rows(table_key)
        self._update_hover_panel_position(table_key)

        self._refresh_table_scroll_height(table_key)

    def _remove_dynamic_row(self, table_key: str):
        if getattr(self, "_input_data_locked", False):
            return
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return
        table = meta["table"]
        header_rows = meta["header_rows"]
        if table.rowCount() <= header_rows + 1:
            return
        table.removeRow(table.rowCount() - 1)
        self._renumber_dynamic_rows(table_key)
        self._update_hover_panel_position(table_key)

        self._refresh_table_scroll_height(table_key)

    def _remove_dynamic_row_at(self, table_key: str, row: int):
        if getattr(self, "_input_data_locked", False):
            return
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return
        table = meta["table"]
        header_rows = meta["header_rows"]
        if table.rowCount() <= header_rows + 1:
            QMessageBox.information(self, "提示", "表格至少保留一条数据行。")
            return
        if not (header_rows <= row < table.rowCount()):
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除第 {row - header_rows + 1} 行吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        table.removeRow(row)
        meta["context_row"] = None
        self._renumber_dynamic_rows(table_key)
        self._update_hover_panel_position(table_key)

        self._refresh_table_scroll_height(table_key)

    def _show_row_context_menu(self, table_key: str, pos):
        if getattr(self, "_input_data_locked", False):
            return
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return
        table = meta["table"]
        header_rows = meta["header_rows"]
        row = table.rowAt(pos.y())
        col = table.columnAt(pos.x())
        if col != 0 or row < header_rows:
            return

        meta["context_row"] = row
        menu = QMenu(table)
        menu.setStyleSheet(self._menu_qss())
        add_above_action = QAction("在上方新增一行", menu)
        add_action = QAction("在下方新增一行", menu)
        delete_action = QAction("删除当前行", menu)
        add_above_action.triggered.connect(lambda _=False, key=table_key, r=row: self._insert_dynamic_row_at(key, r))
        add_action.triggered.connect(lambda _=False, key=table_key, r=row + 1: self._insert_dynamic_row_at(key, r))
        delete_action.triggered.connect(lambda _=False, key=table_key, r=row: self._remove_dynamic_row_at(key, r))
        menu.addAction(add_above_action)
        menu.addAction(add_action)
        menu.addAction(delete_action)
        menu.exec_(table.viewport().mapToGlobal(pos))

    def _set_hover_row(self, table_key: str, row: Optional[int]):
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return
        meta["hover_row"] = row
        self._update_hover_panel_position(table_key)

    def _update_hover_panel_position(self, table_key: str):
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return
        table = meta["table"]
        panel = meta["panel"]
        hover_row = meta["hover_row"]
        if hover_row is None:
            panel.hide()
            return

        index = table.model().index(hover_row, 0)
        rect = table.visualRect(index)
        if not rect.isValid() or rect.isEmpty():
            panel.hide()
            return

        hint_x = rect.left() - panel.sizeHint().width() - 6
        x = max(2, hint_x)
        y = rect.bottom() - panel.sizeHint().height() + 2
        y = max(0, min(y, max(0, table.viewport().height() - panel.sizeHint().height())))
        panel.resize(panel.sizeHint())
        panel.move(x, y)
        panel.show()
        panel.raise_()

    def eventFilter(self, a0, a1):
        if isinstance(a0, QWidget):
            for combo in list(self._hover_combo_boxes):
                meta = self._combo_hover_meta.get(combo)
                if not meta:
                    continue
                try:
                    watched = (combo, meta["wrap"], meta["button"], combo.view())
                except RuntimeError:
                    self._cleanup_hover_combo(combo)
                    continue
                if a0 in watched:
                    if a1.type() == QEvent.Type.Enter:
                        self._set_combo_hover_state(combo, True)
                    elif a1.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
                        QTimer.singleShot(0, lambda c=combo: self._sync_combo_hover_state(c))
                    return super().eventFilter(a0, a1)

        for table_key, meta in self._dynamic_table_meta.items():
            if a0 is meta["viewport"]:
                if a1.type() == QEvent.Type.MouseMove and isinstance(a1, QMouseEvent):
                    if getattr(self, "_input_data_locked", False):
                        self._set_hover_row(table_key, None)
                        continue
                    row = meta["table"].rowAt(a1.pos().y())
                    last_row = self._get_last_data_row(table_key)
                    self._set_hover_row(table_key, row if row == last_row else None)
                elif a1.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
                    self._set_hover_row(table_key, None)
                elif a1.type() == QEvent.Type.Resize:
                    self._update_hover_panel_position(table_key)
                break
        return super().eventFilter(a0, a1)

    def _auto_fit_columns(self, table: QTableWidget, padding: int = 18, equal_width_groups: Optional[List[List[int]]] = None):
        fm = QFontMetrics(table.font())
        col_count = table.columnCount()
        col_widths = [38] * col_count

        print(f"\n=== 开始计算表格 {id(table)} 列宽 ===")
        for c in range(col_count):
            max_w = 38
            for r in range(table.rowCount()):
                # 处理单元格文本
                it = table.item(r, c)
                if it is not None and it.text():
                    text = it.text()
                    # 使用加粗字体测量（如果单元格是加粗的）
                    font = it.font() if it.font().bold() else table.font()
                    fm_cell = QFontMetrics(font)
                    lines = text.split('\n')
                    line_widths = [fm_cell.horizontalAdvance(line) for line in lines]
                    cell_width = max(line_widths) if line_widths else 0
                    # 打印详细信息（针对OD/WT列）
                    if r in (0, 1) and c in (3, 4, 5, 6):
                        print(
                            f"  调试: 表格 {id(table)} 行{r} 列{c} 文本='{text}' 使用字体加粗={font.bold()} 分割={lines} 行宽={line_widths} → 最大行宽={cell_width}")
                    max_w = max(max_w, cell_width + padding)

                # 处理QComboBox
                w = table.cellWidget(r, c)
                if isinstance(w, QComboBox):
                    txt = w.currentText() or ""
                    combo_width = fm.horizontalAdvance(txt) + padding + 24
                    max_w = max(max_w, combo_width)

            table.setColumnWidth(c, max_w)
            col_widths[c] = max_w
            print(f"  列 {c} 最终宽度 = {max_w}")

        # 等宽分组
        if equal_width_groups:
            for group in equal_width_groups:
                valid_group = [c for c in group if 0 <= c < col_count]
                if valid_group:
                    max_group_width = max(col_widths[c] for c in valid_group)
                    for c in valid_group:
                        table.setColumnWidth(c, max_group_width)
                    print(f"  分组 {group} 最大宽度 = {max_group_width}，应用于列 {valid_group}")

        # 编号列统一适当加宽，避免数字过于紧凑
        if col_count > 0:
            index_min_width = 62
            if table.columnWidth(0) < index_min_width:
                table.setColumnWidth(0, index_min_width)
                col_widths[0] = index_min_width
                print(f"  编号列最小宽度修正: 列 0 现在 = {index_min_width}")

        # 对表1的OD/WT列额外增加宽度
        if hasattr(self, 'tbl1') and table is self.tbl1:
            extra = 20
            for col in (3, 4, 5, 6):
                new_width = table.columnWidth(col) + extra
                table.setColumnWidth(col, new_width)
                print(f"  额外增加宽度: 列 {col} 现在 = {new_width}")

            # 垂向载荷列在小四字体下容易被压缩，设置更稳妥的最小宽度
            bold_font = QFont(table.font())
            bold_font.setBold(True)
            fm_bold = QFontMetrics(bold_font)
            load_min_width = max(96, fm_bold.horizontalAdvance("垂向载荷") + padding + 18)
            if table.columnWidth(7) < load_min_width:
                table.setColumnWidth(7, load_min_width)
                col_widths[7] = load_min_width
                print(f"  垂向载荷列最小宽度修正: 列 7 现在 = {load_min_width}")

        total_width = sum(table.columnWidth(c) for c in range(col_count))
        table.setMinimumWidth(total_width)
        print(f"表格 {id(table)} 总宽度 = {total_width}")
        print("=== 列宽计算完成 ===\n")

    def _table_content_height(self, table: QTableWidget) -> int:
        return sum(table.rowHeight(r) for r in range(table.rowCount())) + table.frameWidth() * 2 + 6

    def _wrap_table_in_scroll(self, table: QTableWidget, max_height: int = 210) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidgetResizable(False)

        # 滚动条由外层 scroll area 负责，不让 table 自己再出一套
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        table_content_h = self._table_content_height(table)
        table.setFixedHeight(table_content_h)
        scroll.setWidget(table)

        hbar_h = scroll.horizontalScrollBar().sizeHint().height()
        content_h = table_content_h + hbar_h + 4
        visible_h = min(content_h, max_height)

        scroll.setMinimumHeight(visible_h)
        scroll.setMaximumHeight(visible_h)
        return scroll

    def _make_save_button(self) -> QPushButton:
        btn = QPushButton("保存")
        btn.setFixedSize(90, 28)
        btn.setFont(self._songti_small_four_font(bold=True))
        btn.setStyleSheet("""
            QPushButton {
                background: #27a7d8;
                border: 1px solid #2f3a4a;
                border-radius: 3px;
                font-family: %s;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton:hover { background: #45b8e2; }
        """ % SONGTI_FONT_FALLBACK)
        return btn

    def _make_group_header(self, title: str, on_save=None) -> QWidget:
        """
        表格分组标题。

        原来每个分组右上角都有一个“保存”按钮；现在按业务要求取消，
        统一改为页面底部“保存数据”按钮一次性保存三个表格中的有效数据。
        on_save 参数保留只是为了兼容旧调用，不再使用。
        """
        head = QWidget()
        lay = QHBoxLayout(head)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lab = QLabel(title)
        lab.setFont(self._songti_small_four_font(bold=True))
        lab.setStyleSheet("font-family: %s; font-size: 12pt; font-weight: bold; color: #1d2b3a;" % SONGTI_FONT_FALLBACK)
        lay.addWidget(lab, 0)
        lay.addStretch(1)
        return head

    # ---------------- 表1：新增井槽信息（合并表头） ----------------
    def _build_table_1(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(self._make_group_header("新增井槽信息"), 0)

        # 表内表头：2 行
        header_rows = 2
        data_rows = 3

        # 列布局（与原型一致）
        # 编号 | 水平面坐标(X,Y) | 井槽尺寸(OD,WT) | 支撑结构(OD,WT) | 垂向载荷Fz | 高程及连接形式(7列)
        base_cols = 1 + 2 + 2 + 2 + 1
        cols = base_cols + len(self.table1_elevations)

        self.tbl1 = QTableWidget(header_rows + data_rows, cols, box)
        self._init_table_common(self.tbl1)

        # --- 第0行：大表头（合并） ---
        c = 0
        self.tbl1.setSpan(0, c, 2, 1)
        self._set_cell(self.tbl1, 0, c, "编号", bg=self.HEADER_BG, bold=True, editable=False); c += 1

        self.tbl1.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl1, 0, c, "水平面坐标", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl1, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl1.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl1, 0, c, "井槽尺寸", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl1, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl1.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl1, 0, c, "支撑结构", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl1, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl1.setSpan(0, c, 1, 1)
        self._set_cell(self.tbl1, 0, c, "垂向载荷", bg=self.HEADER_BG, bold=True, editable=False)
        c += 1

        self.tbl1.setSpan(0, c, 1, len(self.table1_elevations))
        self._set_cell(self.tbl1, 0, c, "高程及连接形式", bg=self.HEADER_BG, bold=True, editable=False)
        for k in range(1, len(self.table1_elevations)):
            self._set_cell(self.tbl1, 0, c+k, "", bg=self.HEADER_BG, editable=False)

        # --- 第1行：子表头 ---
        c = 1
        self._set_cell(self.tbl1, 1, c, "X(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl1, 1, c, "Y(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl1, 1, c, "OD(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl1, 1, c, "WT(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl1, 1, c, "OD(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl1, 1, c, "WT(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl1, 1, c, "Fz(kN)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        for e in self.table1_elevations:
            self._set_cell(self.tbl1, 1, c, str(e), bg=self.SUBHDR_BG, bold=True, editable=False)
            c += 1

        # --- 数据区 ---
        for r in range(data_rows):
            rr = header_rows + r
            # 编号
            self._set_cell(self.tbl1, rr, 0, str(r + 1), bg=QColor("#e9eef5"), editable=False)
            # 基础字段
            for c in range(1, base_cols):
                self._set_cell(self.tbl1, rr, c, "", bg=self.DATA_BG, editable=True)

            # 连接形式下拉
            start = base_cols
            for i, e in enumerate(self.table1_elevations):
                col = start + i
                default = None
                if not self._use_dynamic_elevations:
                    default = "焊接" if e in (27, 23, 18) else "无连接"
                self._set_combo_cell(self.tbl1, rr, col, default=default)

        # 在 _build_table_1 中，调用 _auto_fit_columns 之前定义分组
        groups_tbl1 = [
            [1, 2],  # X, Y
            [3, 4],  # 井槽尺寸 OD, WT
            [5, 6],  # 支撑结构 OD, WT
            list(range(8, 8 + len(self.table1_elevations)))  # 高程列（可选，使所有高程列等宽）
        ]
        self._auto_fit_columns(self.tbl1, padding=18, equal_width_groups=groups_tbl1)

        # 创建表格的滚动区域
        # table_scroll = QScrollArea()
        # table_scroll.setWidgetResizable(False)  # 让表格自身决定宽度
        # table_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # table_scroll.setWidget(self.tbl1)
        #
        # # 将滚动区域添加到 QGroupBox 布局
        # lay.addWidget(table_scroll, 1)  # 原来 lay.addWidget(self.tbl1, 1) 替换为滚动区域

        # === 2. 替换为直接添加表格，并明确启用表格自身的滚动条 ===
        # self.tbl1.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # self.tbl1.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # self._install_row_hover_actions(self.tbl1, "tbl1", header_rows)
        # lay.addWidget(self.tbl1, 1)
        self._install_row_hover_actions(self.tbl1, "tbl1", header_rows)

        tbl1_scroll = self._wrap_table_in_scroll(self.tbl1, max_height=210)
        lay.addWidget(tbl1_scroll, 0)

        # 保存一下，后面新增/删除行时可以刷新高度
        self._dynamic_table_meta["tbl1"]["scroll"] = tbl1_scroll

        #lay.addWidget(self.tbl1, 1)
        return box

    # ---------------- 表2：立管/电缆信息（合并表头） ----------------
    def _build_table_2(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(self._make_group_header("新增立管/电缆信息"), 0)

        header_rows = 2
        data_rows = 3

        # 编号 | 工作平面坐标(2) | 立管/电缆尺寸(2) | 支撑结构(2) | 倾斜度(2) | 高程及连接形式(7)
        base_cols = 1 + 2 + 2 + 2 + 2
        cols = base_cols + len(self.table2_elevations)

        self.tbl2 = QTableWidget(header_rows + data_rows, cols, box)
        self._init_table_common(self.tbl2)

        # 第0行大表头
        c = 0
        self.tbl2.setSpan(0, c, 2, 1)
        self._set_cell(self.tbl2, 0, c, "编号", bg=self.HEADER_BG, bold=True, editable=False); c += 1

        self.tbl2.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl2, 0, c, "工作平面坐标", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl2, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl2.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl2, 0, c, "立管/电缆尺寸", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl2, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl2.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl2, 0, c, "支撑结构", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl2, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        self.tbl2.setSpan(0, c, 1, 2)
        self._set_cell(self.tbl2, 0, c, "倾斜度", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl2, 0, c+1, "", bg=self.HEADER_BG, editable=False); c += 2

        # self.tbl2.setSpan(0, c, 2, 1)
        # self._set_cell(self.tbl2, 0, c, "倾斜度", bg=self.HEADER_BG, bold=True, editable=False); c += 1

        self.tbl2.setSpan(0, c, 1, len(self.table2_elevations))
        self._set_cell(self.tbl2, 0, c, "高程及连接形式", bg=self.HEADER_BG, bold=True, editable=False)
        for k in range(1, len(self.table2_elevations)):
            self._set_cell(self.tbl2, 0, c+k, "", bg=self.HEADER_BG, editable=False)

        # 第1行子表头
        c = 1
        self._set_cell(self.tbl2, 1, c, "X(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl2, 1, c, "Y(m)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl2, 1, c, "OD(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl2, 1, c, "WT(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl2, 1, c, "OD(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl2, 1, c, "WT(mm)", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        self._set_cell(self.tbl2, 1, c, "X方向", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1
        self._set_cell(self.tbl2, 1, c, "Y方向", bg=self.SUBHDR_BG, bold=True, editable=False); c += 1

        c = base_cols
        for e in self.table2_elevations:
            self._set_cell(self.tbl2, 1, c, str(e), bg=self.SUBHDR_BG, bold=True, editable=False)
            c += 1

        # 数据区
        for r in range(data_rows):
            rr = header_rows + r
            self._set_cell(self.tbl2, rr, 0, str(r + 1), bg=QColor("#e9eef5"), editable=False)
            for c in range(1, base_cols):
                self._set_cell(self.tbl2, rr, c, "", bg=self.DATA_BG, editable=True)
            start = base_cols
            for i, e in enumerate(self.table2_elevations):
                col = start + i
                default = None
                if not self._use_dynamic_elevations:
                    default = "焊接" if e in (27, 23) else "无连接"
                self._set_combo_cell(self.tbl2, rr, col, default=default)


        groups_tbl2 = [
            [1, 2],  # X, Y
            [3, 4],  # 立管/电缆尺寸 OD, WT
            [5, 6],  # 支撑结构 OD, WT
            [7, 8],  # 倾斜度 X方向, Y方向
            list(range(9, 9 + len(self.table2_elevations)))  # 高程列
        ]
        self._auto_fit_columns(self.tbl2, padding=18, equal_width_groups=groups_tbl2)

        # # 创建滚动区域容纳表格
        # table_scroll = QScrollArea()
        # table_scroll.setWidgetResizable(False)
        # table_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # table_scroll.setWidget(self.tbl2)
        # lay.addWidget

        # === 2. 替换为直接添加表格，并明确启用表格自身的滚动条 ===
        # self.tbl2.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # self.tbl2.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # self._install_row_hover_actions(self.tbl2, "tbl2", header_rows)
        # lay.addWidget(self.tbl2, 1)

        self._install_row_hover_actions(self.tbl2, "tbl2", header_rows)

        tbl2_scroll = self._wrap_table_in_scroll(self.tbl2, max_height=210)
        lay.addWidget(tbl2_scroll, 0)

        self._dynamic_table_meta["tbl2"]["scroll"] = tbl2_scroll
        #lay.addWidget(self.tbl2, 1)
        return box

    # ---------------- 表3：新增组块载荷信息（合并表头） ----------------
    def _build_table_3(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(self._make_group_header("新增组块载荷信息"), 0)

        header_rows = 2
        data_rows = 6

        # 编号 | 组块载荷坐标(3) | 重量(1)
        cols = 1 + 3 + 1
        self.tbl3 = QTableWidget(header_rows + data_rows, cols, box)
        self._init_table_common(self.tbl3)

        # 第0行大表头
        self.tbl3.setSpan(0, 0, 2, 1)
        self._set_cell(self.tbl3, 0, 0, "编号", bg=self.HEADER_BG, bold=True, editable=False)

        self.tbl3.setSpan(0, 1, 1, 3)
        self._set_cell(self.tbl3, 0, 1, "组块载荷坐标", bg=self.HEADER_BG, bold=True, editable=False)
        self._set_cell(self.tbl3, 0, 2, "", bg=self.HEADER_BG, editable=False)
        self._set_cell(self.tbl3, 0, 3, "", bg=self.HEADER_BG, editable=False)

        self.tbl3.setSpan(0, 4, 1, 1)
        self._set_cell(self.tbl3, 0, 4, "重量", bg=self.HEADER_BG, bold=True, editable=False)

        # 第1行子表头
        self._set_cell(self.tbl3, 1, 1, "X(m)", bg=self.SUBHDR_BG, bold=True, editable=False)
        self._set_cell(self.tbl3, 1, 2, "Y(m)", bg=self.SUBHDR_BG, bold=True, editable=False)
        self._set_cell(self.tbl3, 1, 3, "Z(m)", bg=self.SUBHDR_BG, bold=True, editable=False)
        self._set_cell(self.tbl3, 1, 4, "(t)", bg=self.SUBHDR_BG, bold=True, editable=False)

        for r in range(data_rows):
            rr = header_rows + r
            self._set_cell(self.tbl3, rr, 0, str(r + 1), bg=QColor("#e9eef5"), editable=False)
            self._set_cell(self.tbl3, rr, 1, "", bg=self.DATA_BG, editable=True)
            self._set_cell(self.tbl3, rr, 2, "", bg=self.DATA_BG, editable=True)
            self._set_cell(self.tbl3, rr, 3, "", bg=self.DATA_BG, editable=True)
            self._set_cell(self.tbl3, rr, 4, "", bg=self.DATA_BG, editable=True)

        groups_tbl3 = [
            [1, 2, 3]  # X, Y, Z
        ]
        self._auto_fit_columns(self.tbl3, padding=18, equal_width_groups=groups_tbl3)

        # table_scroll = QScrollArea()
        # table_scroll.setWidgetResizable(False)
        # table_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # table_scroll.setWidget(self.tbl3)
        # lay.addWidget(table_scroll, 1)

        # 让所有列自动拉伸以平分、填满表格宽度
        self.tbl3.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 单独把第0列（编号列）设置为按内容自适应，保持紧凑
        self.tbl3.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._install_row_hover_actions(self.tbl3, "tbl3", header_rows)
        self.tbl3.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tbl3.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        lay.addWidget(self.tbl3, 1)

        # lay.addWidget(self.tbl3, 1)
        return box

    # ---------------- 底部按钮 ----------------
    def _build_bottom_actions(self) -> QWidget:
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 10, 0, 0)
        lay.setSpacing(14)

        def mk(text: str):
            b = QPushButton(text)
            b.setFixedHeight(42)
            b.setMinimumWidth(160)
            b.setFont(self._songti_small_four_font(bold=True))
            b.setStyleSheet("""
                QPushButton {
                    background: #2aa9df;
                    border: 2px solid #1b2a3a;
                    border-radius: 6px;
                    font-family: %s;
                    font-size: 12pt;
                    font-weight: bold;
                }
                QPushButton:hover { background: #4bbbe8; }
            """ % SONGTI_FONT_FALLBACK)
            return b

        self.btn_save_data = mk("保存数据")
        self.btn_create = mk("创建新模型")
        self.btn_run = mk("计算分析")
        self.btn_view = mk("查看结果")

        self.btn_save_data.clicked.connect(self._on_save_all_input_data)
        self.btn_create.clicked.connect(self._on_create_model)
        self.btn_run.clicked.connect(self._on_run_analysis)
        self.btn_view.clicked.connect(self._on_view_result)

        # 创建新模型按钮保持可点击；如果用户尚未保存数据，点击时再给出提示。

        lay.addStretch(1)
        lay.addWidget(self.btn_save_data, 0)
        lay.addWidget(self.btn_create, 0)
        lay.addWidget(self.btn_run, 0)
        lay.addWidget(self.btn_view, 0)
        lay.addStretch(1)
        return wrap

    # ---------------- 保存按钮：导出当前表格数据 ----------------
    def _confirm_save_locked(self, data_name: str) -> bool:
        """
        保存前二次确认：
        点击“是”才继续保存；
        点击“否”直接取消保存，用户可以继续修改表格。
        """
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("确认保存")
        msg.setText(f"{data_name}保存之后将无法修改，是否确认保存？")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        # 强制按钮显示为中文“是 / 否”
        yes_btn = msg.button(QMessageBox.Yes)
        no_btn = msg.button(QMessageBox.No)
        if yes_btn is not None:
            yes_btn.setText("是")
        if no_btn is not None:
            no_btn.setText("否")

        return msg.exec_() == QMessageBox.Yes

    def _on_save_table1(self):
        if not self._confirm_save_locked("新增井槽信息"):
            return

        try:
            self._save_well_slots_to_db()
            QMessageBox.information(self, "保存成功", "新增井槽信息已写入数据库。")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"新增井槽信息保存失败：\n{e}")

    def _on_save_table2(self):
        if not self._confirm_save_locked("新增立管/电缆信息"):
            return

        try:
            self._save_risers_to_db()
            QMessageBox.information(self, "保存成功", "新增立管/电缆信息已写入数据库。")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"新增立管/电缆信息保存失败：\n{e}")

    def _on_save_table3(self):
        if not self._confirm_save_locked("新增组块载荷信息"):
            return

        try:
            self._save_topside_weights_to_db()
            QMessageBox.information(self, "保存成功", "新增组块载荷信息已写入数据库。")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"新增组块载荷信息保存失败：\n{e}")

    def _has_any_valid_input_data(self) -> bool:
        """
        判断三个输入表格中是否至少有一类构件/载荷填写了有效基础数据。
        只看基础字段，不把连接形式下拉框的默认值当作有效输入。
        """
        for r in range(2, self.tbl1.rowCount()):
            if self._table_has_any_data(self.tbl1, r, 1, 7):
                return True

        for r in range(2, self.tbl2.rowCount()):
            if self._table_has_any_data(self.tbl2, r, 1, 8):
                return True

        for r in range(2, self.tbl3.rowCount()):
            if self._table_has_any_data(self.tbl3, r, 1, 4):
                return True

        return False

    def _lock_input_tables_after_save(self) -> None:
        """保存后锁定三个表格，避免界面内容和数据库已保存内容不一致。"""
        self._input_data_locked = True

        for table in (self.tbl1, self.tbl2, self.tbl3):
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

            for r in range(table.rowCount()):
                for c in range(table.columnCount()):
                    w = table.cellWidget(r, c)
                    if w is None:
                        continue
                    combo = w.findChild(QComboBox)
                    if combo is not None:
                        combo.setEnabled(False)
                    w.setEnabled(False)

        for meta in self._dynamic_table_meta.values():
            panel = meta.get("panel")
            if panel is not None:
                panel.hide()

        if hasattr(self, "btn_save_data"):
            # 保存成功后不把“保存数据”按钮置灰。
            # 用户再次点击时，_on_save_all_input_data 会根据 _input_data_locked 给出
            # “数据已经保存，不能重复修改”的提示。
            self.btn_save_data.setEnabled(True)
            self.btn_save_data.setText("保存数据")
        if hasattr(self, "btn_create"):
            self.btn_create.setEnabled(True)

    def _on_save_all_input_data(self):
        """
        统一保存三个表格中的有效数据。

        用户可以只填写井槽、只填写立管/电缆、只填写组块载荷，
        也可以任意组合填写；保存时统一覆盖当前 job_name 下三类输入数据。
        """
        if getattr(self, "_input_data_locked", False):
            QMessageBox.information(self, "提示", "数据已经保存，不能重复修改。")
            return

        if not self._has_any_valid_input_data():
            QMessageBox.warning(
                self,
                "无法保存",
                "三个表格中没有填写任何有效数据。\n"
                "请至少填写井槽、立管/电缆或组块载荷中的一种数据后再保存。"
            )
            return

        if not self._confirm_save_locked("新增数据"):
            return

        try:
            self._save_well_slots_to_db()
            self._save_risers_to_db()
            self._save_topside_weights_to_db()

            self._input_data_saved = True
            self._lock_input_tables_after_save()

            QMessageBox.information(
                self,
                "保存成功",
                "新增数据已保存。"
            )
        except Exception as e:
            self._input_data_saved = False
            QMessageBox.critical(self, "保存失败", f"新增数据保存失败：\n{e}")

    def _save_table_as_csv(self, table: QTableWidget, header_rows: int, default_name: str,
                           with_combo_cols: bool, combo_start_col: int):
        path, _ = QFileDialog.getSaveFileName(self, "保存表格", default_name, "CSV (*.csv);;All Files (*)")
        if not path:
            return
        try:
            # 直接用第1行子表头作为列名（更接近真实字段）
            headers = []
            for c in range(table.columnCount()):
                it = table.item(1, c)
                headers.append(it.text().replace("\n", " ") if it else "")
            lines = [",".join(headers)]

            for r in range(header_rows, table.rowCount()):
                row_vals = []
                for c in range(table.columnCount()):
                    if with_combo_cols and c >= combo_start_col:
                        w = table.cellWidget(r, c)
                        row_vals.append(w.currentText() if isinstance(w, QComboBox) else "")
                    else:
                        it = table.item(r, c)
                        row_vals.append((it.text() if it else "").replace(",", " "))
                if all(v.strip() == "" for v in row_vals):
                    continue
                lines.append(",".join(row_vals))

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            QMessageBox.information(self, "保存成功", f"已保存：\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存失败：\n{e}")

    # ---------------- 业务按钮：占位实现（后续你定格式后再替换） ----------------
    def _on_create_model(self):
        try:
            if not getattr(self, "_input_data_saved", False):
                QMessageBox.warning(
                    self,
                    "请先保存数据",
                    "请先点击“保存数据”，确认保存新增数据后再创建新模型。"
                )
                return

            if not getattr(self, "job_name", "").strip():
                raise ValueError("job_name 为空，无法创建新模型")

            if not getattr(self, "mysql_url", "").strip():
                raise ValueError("MYSQL_URL 未配置，无法创建新模型")

            result = create_new_model_files(
                mysql_url=self.mysql_url,
                job_name=self.job_name,
                overwrite_job=True,
                generate_bat=True,  # 创建模型时同步复制 RUNX/PSIINP/JCNINP 并生成 bat
            )

            export_info = result.get("export", {})

            self.current_model_dir = export_info.get("model_dir", "").strip() or self.model_files_root
            self.current_runx_file = export_info.get("runx_file", "").strip()
            if not self.current_runx_file:
                self.current_runx_file = self._find_first_existing_file(
                    self.current_model_dir,
                    ["psiFACTOR.runx", "psifactor.runx"]
                )

            self.current_bat_file = export_info.get("bat_file", "").strip()
            self.current_psiinp_file = export_info.get("psiinp_file", "").strip()
            self.current_jcninp_file = export_info.get("jcninp_file", "").strip()

            new_model_file = export_info.get("new_model_file", "").strip()
            new_sea_file = export_info.get("new_sea_file", "").strip()

            msg_lines = ["创建新模型完成。"]

            if new_model_file:
                msg_lines.append(f"新模型文件：{new_model_file}")
            else:
                msg_lines.append("新模型文件：未生成")

            if new_sea_file:
                msg_lines.append(f"新海况文件：{new_sea_file}")
            else:
                msg_lines.append("新海况文件：未生成")

            if self.current_runx_file:
                msg_lines.append(f"RUNX文件：{self.current_runx_file}")
            if getattr(self, "current_psiinp_file", ""):
                msg_lines.append(f"PSIINP文件：{self.current_psiinp_file}")
            if getattr(self, "current_jcninp_file", ""):
                msg_lines.append(f"JCNINP文件：{self.current_jcninp_file}")
            if self.current_bat_file:
                msg_lines.append(f"BAT文件：{self.current_bat_file}")

            self._model_created_in_session = True
            QMessageBox.information(self, "创建完成", "\n".join(msg_lines))

        except Exception as e:
            QMessageBox.critical(self, "创建失败", f"创建新模型失败：\n{e}")

    def _dump_table_block(self, title: str, table: QTableWidget, header_rows: int,
                          with_combo_cols: bool, combo_start_col: int) -> str:
        lines = []
        lines.append(f"** [{title}]")
        for r in range(header_rows, table.rowCount()):
            row_vals = []
            for c in range(table.columnCount()):
                if with_combo_cols and c >= combo_start_col:
                    w = table.cellWidget(r, c)
                    row_vals.append(w.currentText() if isinstance(w, QComboBox) else "")
                else:
                    it = table.item(r, c)
                    row_vals.append(it.text() if it else "")
            if all(v.strip() == "" for v in row_vals):
                continue
            lines.append("** " + " | ".join(row_vals))
        return "\n".join(lines) + "\n"

    def _refresh_runtime_paths_from_disk(self):
        root = getattr(self, "current_model_dir", "").strip() or get_job_runtime_dir(self.job_name)
        self.current_model_dir = root

        if not os.path.isdir(root):
            self.current_runx_file = ""
            self.current_bat_file = ""
            self.current_result_file = ""
            return

        self.current_runx_file = self._find_first_existing_file(
            root,
            ["psiFACTOR.runx", "psifactor.runx"]
        )

        self.current_bat_file = self._find_first_existing_file(
            root,
            ["Autorun.bat"]
        )

        self.current_result_file = find_result_file(root)
    def _find_first_existing_file(self, root: str, candidate_names: list) -> str:
        for name in candidate_names:
            p = os.path.join(root, name)
            if os.path.exists(p):
                return p
        return ""

    def _find_result_file(self, root: str) -> str:
        if not os.path.isdir(root):
            return ""

        preferred = [
            "psilst.factor",
            "psilst.lst",
            "psilst",
        ]
        for name in preferred:
            p = os.path.join(root, name)
            if os.path.exists(p):
                return p

        # 兜底：找常见结果文件
        candidates = []
        for fn in os.listdir(root):
            low = fn.lower()
            if (
                    low.startswith("psilst")
                    or low.endswith(".lst")
                    or low.endswith(".lis")
                    or low.endswith(".listing")
                    or low.endswith(".factor")
            ):
                full = os.path.join(root, fn)
                try:
                    mtime = os.path.getmtime(full)
                except OSError:
                    mtime = 0
                candidates.append((mtime, full))

        if not candidates:
            return ""

        candidates.sort(reverse=True)
        return candidates[0][1]

    def _should_calculate_original_model(self) -> bool:
        """是否应直接计算原模型。

        业务规则：
        - 三个新增数据表均为空；
        - 本次没有点击“保存数据”；
        - 本次没有点击“创建新模型”。

        满足以上条件时，点击“计算分析”应计算原始上传模型，而不是默认计算
        最新历史改造项目下的 M1。
        """
        return (
            not self._has_any_valid_input_data()
            and not getattr(self, "_input_data_saved", False)
            and not getattr(self, "_input_data_locked", False)
            and not getattr(self, "_model_created_in_session", False)
        )

    def _archive_analysis_result_file(self, result_file: str, *, analysis_mode: str, runtime_bundle: dict) -> str:
        """把 SACS 计算结果文件归档到对应业务位置。

        规则：
        - 原模型计算结果：归档到【模型文件 / 当前模型 / 静力 / 结果 / 自动计算 / 原模型】；
        - 改造后计算结果：归档到最新历史改造项目下，和该项目的 sacinp.M1 / seainp.M1 放在一起。

        这样用户在“历史改造文件”中选中某个改造项目时，可以直接看到：
        1) 模型文件 sacinp.M1；
        2) 海况文件 seainp.M1；
        3) 本项目对应的计算结果文件。
        """
        result_file = os.path.normpath(str(result_file or "").strip())
        if not result_file or not os.path.isfile(result_file):
            return ""

        mode_label = "原模型" if analysis_mode == "original" else "改造后模型"
        source_label = str(runtime_bundle.get("project_name") or runtime_bundle.get("source") or "").strip()

        try:
            from services.file_db_adapter import (
                append_docman_file,
                load_docman_record_list,
                replace_docman_list_file,
                resolve_storage_path,
                upload_file,
            )
        except Exception:
            return ""

        # 改造后模型：结果文件保存到对应历史改造项目下。
        if analysis_mode != "original":
            project_id = runtime_bundle.get("project_id")
            try:
                project_id_int = int(project_id or 0)
            except Exception:
                project_id_int = 0

            if project_id_int > 0:
                path_segments = ["历史改造信息", f"project_{project_id_int}"]
                remark = (
                    f"{source_label or '历史改造项目'} 对应的结构强度/改造可行性评估计算结果；"
                    f"计算对象：{mode_label}"
                )

                try:
                    # 同一个历史改造项目重复计算时，优先覆盖该项目下已有的计算结果文件，
                    # 避免每次计算都新增一条重复的 psilst.factor。
                    existing_records = load_docman_record_list(
                        path_segments,
                        facility_code=self.job_name,
                    )
                    target_record = None
                    for rec in existing_records or []:
                        category = str(rec.get("category") or "").strip()
                        filename = str(rec.get("filename") or "").strip().lower()
                        remark_text = str(rec.get("remark") or "").strip()
                        if (
                            "计算结果" in category
                            or "静力分析结果" in category
                            or filename.startswith("psilst")
                            or "计算结果" in remark_text
                        ):
                            target_record = rec
                            break

                    if target_record and target_record.get("logical_path"):
                        record = replace_docman_list_file(
                            result_file,
                            logical_path=str(target_record.get("logical_path") or ""),
                            record_id=int(target_record.get("record_id") or 0) if target_record.get("record_id") else None,
                            category="计算结果文件",
                            work_condition=mode_label,
                            remark=remark,
                            facility_code=self.job_name,
                        )
                    else:
                        record = append_docman_file(
                            result_file,
                            path_segments=path_segments,
                            category="计算结果文件",
                            work_condition=mode_label,
                            remark=remark,
                            facility_code=self.job_name,
                        )
                    return resolve_storage_path(record) or result_file
                except Exception as exc:
                    print("[FeasibilityAssessmentPage] archive rebuild analysis result failed:", exc)
                    return ""

        # 原模型计算结果，或者找不到 project_id 的兜底情况：仍保存到模型文件页。
        logical_path = f"{self.job_name}/当前模型/静力/结果/自动计算/{mode_label}"
        remark = (
            f"结构强度/改造可行性评估计算结果；计算对象：{mode_label}；"
            f"来源：{source_label}"
        )

        try:
            record = upload_file(
                result_file,
                file_type_code="other",
                module_code="model_files",
                logical_path=logical_path,
                facility_code=self.job_name,
                category_name="静力分析结果文件",
                work_condition=mode_label,
                remark=remark,
            )
            return resolve_storage_path(record) or result_file
        except Exception as exc:
            print("[FeasibilityAssessmentPage] archive original analysis result failed:", exc)
            return ""

    def _rewrite_runx_for_current_analysis(self, runx_path: str, *, analysis_mode: str, runtime_bundle: dict) -> str:
        """根据当前计算对象修正 RUNX 中的模型/海况文件名。"""
        runx_path = os.path.normpath(str(runx_path or "").strip())
        if not runx_path:
            return ""

        if analysis_mode == "original":
            model_file = str(runtime_bundle.get("new_model_file") or runtime_bundle.get("runtime_model_file") or "")
            sea_file = str(runtime_bundle.get("new_sea_file") or runtime_bundle.get("runtime_sea_file") or "")
            model_filename = os.path.basename(model_file)
            sea_filename = os.path.basename(sea_file) if sea_file else ""
            return rewrite_runx_input_file_names(
                runx_path,
                model_filename=model_filename,
                sea_filename=sea_filename,
                model_candidates=[
                    os.path.basename(str(runtime_bundle.get("model_file") or "")),
                    "sacinp.M1",
                    "sacinp.JKnew",
                ],
                sea_candidates=[
                    os.path.basename(str(runtime_bundle.get("sea_file") or "")),
                    "seainp.M1",
                    "seainp.JKnew FACTOR",
                ],
            )

        # 改造后模型统一使用运行目录中的 M1 文件。
        return rewrite_runx_input_file_names(
            runx_path,
            model_filename="sacinp.M1",
            sea_filename="seainp.M1",
            model_candidates=[
                os.path.basename(str(runtime_bundle.get("model_file") or "")),
                os.path.basename(str(runtime_bundle.get("new_model_file") or "")),
                "sacinp.JKnew",
                "sacinp.M1",
            ],
            sea_candidates=[
                os.path.basename(str(runtime_bundle.get("sea_file") or "")),
                os.path.basename(str(runtime_bundle.get("new_sea_file") or "")),
                "seainp.JKnew FACTOR",
                "seainp.M1",
            ],
        )

    def _cleanup_previous_analysis_outputs(self, work_dir: str) -> None:
        """计算前清理旧的结果文件，避免把上一次/半截结果误判为本次结果。"""
        work_dir = os.path.normpath(str(work_dir or "").strip())
        if not work_dir or not os.path.isdir(work_dir):
            return

        delete_names = {
            "analysis_exitcode.txt",
            "analysis_summary.log",
            "analysis_stdout.log",
            "analysis_stderr.log",
        }
        for fn in list(os.listdir(work_dir)):
            low = fn.lower()
            full = os.path.join(work_dir, fn)
            should_delete = (
                low in delete_names
                or low.startswith("psilst")
                or low.endswith(".listing")
            )
            if not should_delete:
                continue
            try:
                if os.path.isdir(full):
                    shutil.rmtree(full, ignore_errors=True)
                else:
                    os.remove(full)
            except Exception as exc:
                print("[FeasibilityAssessmentPage] cleanup old analysis output failed:", full, exc)

    def _read_tail_text(self, path: str, max_bytes: int = 256 * 1024) -> str:
        path = os.path.normpath(str(path or "").strip())
        if not path or not os.path.isfile(path):
            return ""
        try:
            with open(path, "rb") as fp:
                fp.seek(0, os.SEEK_END)
                size = fp.tell()
                fp.seek(max(0, size - int(max_bytes)), os.SEEK_SET)
                data = fp.read()
            for enc in ("utf-8", "gbk", "cp1252", "latin-1"):
                try:
                    return data.decode(enc, errors="ignore")
                except Exception:
                    continue
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def _read_analysis_exit_code(self, work_dir: str) -> Optional[int]:
        """读取 Autorun.bat 写出的 SACS 退出码。

        当前 BAT 会在执行结束时写入：
        - analysis_exitcode.txt：只包含退出码；
        - analysis_summary.log：包含 ExitCode=...。

        如果读到了退出码，说明 BAT 已经执行到尾部。原来只等待
        analysis_stdout.log 中的固定英文完成标记，在 stdout 没有该标记时会
        卡在“等待结果写入...”。
        """
        work_dir = os.path.normpath(str(work_dir or "").strip())
        if not work_dir:
            return None

        exitcode_path = os.path.join(work_dir, "analysis_exitcode.txt")
        exit_text = self._read_tail_text(exitcode_path, max_bytes=8 * 1024).strip()
        if exit_text:
            # 通常内容就是一行 0；这里也兼容 ExitCode=0 等格式。
            for token in exit_text.replace("=", " ").replace(";", " ").replace(",", " ").split():
                token = token.strip()
                if token.lstrip("+-").isdigit():
                    try:
                        return int(token)
                    except Exception:
                        pass

        summary_path = os.path.join(work_dir, "analysis_summary.log")
        summary_text = self._read_tail_text(summary_path, max_bytes=64 * 1024)
        for raw_line in reversed(summary_text.splitlines()):
            line = raw_line.strip()
            if not line:
                continue
            low = line.lower().replace(" ", "")
            if not low.startswith("exitcode="):
                continue
            value = line.split("=", 1)[-1].strip()
            if value.lstrip("+-").isdigit():
                try:
                    return int(value)
                except Exception:
                    return None

        return None

    def _analysis_output_has_error(self, work_dir: str, result_file: str) -> str:
        """从退出码/日志/结果尾部识别明显错误。只做强错误判断，避免误杀正常结果。"""
        exit_code = self._read_analysis_exit_code(work_dir)
        if exit_code is not None and exit_code != 0:
            return f"ExitCode={exit_code}"

        paths = [
            os.path.join(work_dir, "analysis_stdout.log"),
            os.path.join(work_dir, "analysis_stderr.log"),
            os.path.join(work_dir, "analysis_summary.log"),
            result_file,
        ]
        joined = "\n".join(self._read_tail_text(path) for path in paths if path)
        low = joined.lower()
        strong_error_tokens = [
            "*** error in sacs execution ***",
            "please check output listing files",
            "fatal error",
            "severe error",
            "cannot open",
            "can not open",
            "could not open",
            "file not found",
            "no such file",
            "系统找不到指定的文件",
            "找不到指定的文件",
        ]
        for token in strong_error_tokens:
            if token in low:
                return token
        return ""

    def _analysis_runx_has_done_marker(self, work_dir: str) -> bool:
        """判断 RUNX/BAT 是否已经真正结束。

        优先依据 analysis_exitcode.txt / analysis_summary.log。只要 BAT 已经写出
        ExitCode，就说明它已经执行到尾部；stdout/stderr 中的完成文本只作为
        兼容旧版本 SACS 输出的兜底。
        """
        exit_code = self._read_analysis_exit_code(work_dir)
        if exit_code is not None:
            return True

        stdout_text = self._read_tail_text(os.path.join(work_dir, "analysis_stdout.log"), max_bytes=512 * 1024)
        stderr_text = self._read_tail_text(os.path.join(work_dir, "analysis_stderr.log"), max_bytes=512 * 1024)
        text = (stdout_text + "\n" + stderr_text).lower()
        return (
            "sacs linear static analysis finished" in text
            or "*** error in sacs execution ***" in text
            or "please check output listing files" in text
        )

    def _wait_for_fresh_result_file(
        self,
        *,
        work_dir: str,
        start_time: float,
        on_ready,
        max_wait_ms: int = 30 * 60 * 1000,
        interval_ms: int = 2000,
    ) -> None:
        """等待本次结果文件出现、RUNX 走完、且文件大小长时间稳定。

        之前“计算很快完成但 psilst.factor 没写完”的根因是：只等了文件大小连续短时间稳定。
        SACS 各模块之间可能存在较长间隔，导致中间文件被提前归档。

        新规则：
        1. psilst.factor 必须是本次计算后生成/更新；
        2. analysis_exitcode.txt / analysis_summary.log 写出 ExitCode，或 stdout/stderr 有完成标记；
        3. psilst.factor 大小必须连续较长时间稳定；
        4. 若退出码非 0 或出现强错误标记，后续 _analysis_output_has_error 会拦截归档。
        """
        work_dir = os.path.normpath(str(work_dir or "").strip())
        state = {
            "elapsed": 0,
            "last_path": "",
            "last_size": -1,
            "stable_count": 0,
            "last_debug": "",
        }

        # 2 秒检查一次，连续 8 次稳定约等于 16 秒。
        # 这个时间比原来的 3 秒保守很多，避免 SACS 模块间隔造成误判。
        required_stable_count = 8
        min_result_size = 8 * 1024

        timer = QTimer(self)
        timer.setInterval(max(500, int(interval_ms)))

        def check_once():
            state["elapsed"] += timer.interval()
            result_file = find_result_file(work_dir)
            runx_done = self._analysis_runx_has_done_marker(work_dir)

            if result_file and os.path.isfile(result_file):
                try:
                    mtime = os.path.getmtime(result_file)
                    size = os.path.getsize(result_file)
                except OSError:
                    mtime = 0
                    size = 0

                # 必须是本次计算开始后生成/更新的文件，避免误用旧结果。
                is_fresh = mtime >= float(start_time) - 2.0
                if is_fresh and size >= min_result_size:
                    if result_file == state["last_path"] and size == state["last_size"]:
                        state["stable_count"] += 1
                    else:
                        state["stable_count"] = 0
                        state["last_path"] = result_file
                        state["last_size"] = size

                    if runx_done and state["stable_count"] >= required_stable_count:
                        timer.stop()
                        timer.deleteLater()
                        on_ready(result_file, "")
                        return
                else:
                    state["stable_count"] = 0

            if state["elapsed"] >= int(max_wait_ms):
                timer.stop()
                timer.deleteLater()
                exit_code = self._read_analysis_exit_code(work_dir)
                detail = (
                    f"等待计算结果写入完成超时：{work_dir}\n"
                    f"result_file={result_file or ''}\n"
                    f"runx_done={runx_done}\n"
                    f"exit_code={'' if exit_code is None else exit_code}\n"
                    f"stable_count={state['stable_count']}/{required_stable_count}"
                )
                on_ready(result_file or "", detail)
                return

        timer.timeout.connect(check_once)
        timer.start()
        check_once()

    def _on_run_analysis(self):
        try:
            analysis_mode = "original" if self._should_calculate_original_model() else "rebuild"

            # 每次计算前都重新准备当前计算模型。
            # - 三张表为空、未保存、未创建新模型：计算原始上传模型；
            # - 否则：计算当前仍有效的最新历史改造 M1。
            try:
                if analysis_mode == "original":
                    runtime_bundle = prepare_original_runtime_for_analysis(
                        mysql_url=self.mysql_url,
                        job_name=self.job_name,
                    )
                else:
                    runtime_bundle = prepare_latest_rebuild_runtime_for_analysis(
                        mysql_url=self.mysql_url,
                        job_name=self.job_name,
                    )
                self.current_model_dir = str(runtime_bundle.get("model_dir") or "").strip() or get_job_runtime_dir(self.job_name)
            except Exception as exc:
                QMessageBox.warning(self, "计算模型准备失败", str(exc))
                return

            self._refresh_runtime_paths_from_disk()

            work_dir = getattr(self, "current_model_dir", "").strip() or self.model_files_root
            if not work_dir or not os.path.isdir(work_dir):
                QMessageBox.warning(self, "提示", "未找到模型运行目录，请先确认模型文件已上传。")
                return

            # 计算前再次从“当前模型/其他/用户上传/其他”复制必需辅助文件。
            # RUNX 文件复制后会根据计算对象修正其中引用的模型/海况文件名。
            support_files = stage_support_files_for_job(self.job_name, require_all=True)
            runx_path = support_files.get("runx", "") or getattr(self, "current_runx_file", "").strip()
            if runx_path:
                try:
                    runx_path = self._rewrite_runx_for_current_analysis(
                        runx_path,
                        analysis_mode=analysis_mode,
                        runtime_bundle=runtime_bundle,
                    )
                except Exception as exc:
                    QMessageBox.warning(self, "RUNX 文件修正失败", str(exc))
                    return
            self.current_runx_file = runx_path

            bat_path = ensure_analysis_bat(
                work_dir=work_dir,
                runx_path=runx_path,
                psiinp_path=support_files.get("psiinp", "") or os.path.join(work_dir, "psiinp.19-1d"),
                jcninp_path=support_files.get("jcninp", "") or os.path.join(work_dir, "Jcninp.19-1d"),
            )
            self.current_bat_file = bat_path

            # 计算前清理旧结果，并记录本次开始时间。
            # 否则 find_result_file 可能找到上一次或半截 psilst.factor，造成“秒完成但结果不完整”。
            self._cleanup_previous_analysis_outputs(work_dir)
            analysis_start_time = time.time()

            if self.analysis_process is not None:
                QMessageBox.information(self, "提示", "当前已有计算任务正在运行。")
                return

            self.btn_run.setEnabled(False)
            self.btn_run.setText("计算中...")

            process = QProcess(self)
            self.analysis_process = process
            process.setWorkingDirectory(work_dir)
            process.setProgram("cmd")
            process.setArguments(["/c", bat_path])
            # 不使用 MergedChannels，避免 SACS 大量输出阻塞 QProcess 管道。
            process.setProcessChannelMode(QProcess.SeparateChannels)

            def drain_stdout():
                try:
                    _ = bytes(process.readAllStandardOutput())
                except Exception:
                    pass

            def drain_stderr():
                try:
                    _ = bytes(process.readAllStandardError())
                except Exception:
                    pass

            process.readyReadStandardOutput.connect(drain_stdout)
            process.readyReadStandardError.connect(drain_stderr)

            def on_finished(exit_code, exit_status):
                self.analysis_process = None

                if exit_code != 0:
                    self.btn_run.setEnabled(True)
                    self.btn_run.setText("计算分析")
                    QMessageBox.critical(self, "提示", f"计算失败，退出码：{exit_code}\n请查看计算目录下的 analysis_stdout.log / analysis_stderr.log。")
                    return

                self.btn_run.setText("等待结果写入...")

                def on_result_ready(result_file: str, wait_error: str):
                    self.btn_run.setEnabled(True)
                    self.btn_run.setText("计算分析")
                    self.current_result_file = result_file or ""

                    if wait_error:
                        QMessageBox.warning(
                            self,
                            "计算结果未完成",
                            f"SACS 外层进程已结束，但结果文件没有在限定时间内稳定。\n{wait_error}\n"
                            f"请稍后打开计算目录检查：{work_dir}"
                        )
                        return

                    if not self.current_result_file:
                        QMessageBox.warning(
                            self,
                            "未找到计算结果",
                            f"SACS 进程已结束，但没有找到本次新生成的结果文件。\n计算目录：{work_dir}\n"
                            "请查看 analysis_stdout.log / analysis_stderr.log。"
                        )
                        return

                    error_token = self._analysis_output_has_error(work_dir, self.current_result_file)
                    if error_token:
                        QMessageBox.warning(
                            self,
                            "计算可能失败",
                            f"结果/日志中检测到错误标记：{error_token}\n"
                            f"结果文件暂不归档，请先检查：\n{self.current_result_file}"
                        )
                        return

                    archived_path = self._archive_analysis_result_file(
                        self.current_result_file,
                        analysis_mode=analysis_mode,
                        runtime_bundle=runtime_bundle,
                    )

                    mode_text = "原模型" if analysis_mode == "original" else "最新改造模型"
                    msg = f"计算完成。\n计算对象：{mode_text}\n结果文件：{self.current_result_file}"
                    if archived_path:
                        msg += f"\n服务器归档：{archived_path}"
                    QMessageBox.information(self, "提示", msg)

                self._wait_for_fresh_result_file(
                    work_dir=work_dir,
                    start_time=analysis_start_time,
                    on_ready=on_result_ready,
                )

            def on_error(_err):
                err_text = process.errorString()
                self.btn_run.setEnabled(True)
                self.btn_run.setText("计算分析")
                self.analysis_process = None
                QMessageBox.critical(self, "运行失败", f"启动计算进程失败：\n{err_text}")

            process.finished.connect(on_finished)
            process.errorOccurred.connect(on_error)
            process.start()

        except Exception as e:
            self.btn_run.setEnabled(True)
            self.btn_run.setText("计算分析")
            self.analysis_process = None
            QMessageBox.critical(self, "运行失败", f"调用 bat 计算失败：\n{e}")

    # def _on_view_result(self):
    #     path, _ = QFileDialog.getOpenFileName(self, "选择分析结果文件（psilst）", "", "All Files (*)")
    #     if not path:
    #         return
    #
    #     try:
    #         with open(path, "r", encoding="utf-8", errors="ignore") as f:
    #             content = f.read()
    #         head = content[:8000]
    #         tail = content[-8000:] if len(content) > 16000 else ""
    #         show = head + ("\n\n...（中间省略）...\n\n" + tail if tail else "")
    #         self._show_text_dialog("查看结果（预览）", show, extra_open_path=path)
    #     except Exception as e:
    #         QMessageBox.critical(self, "读取失败", f"读取结果文件失败：\n{e}")

    # 点击“查看结果”按钮，页面跳转到评估结果页面，目前不确定这个按钮到底是什么逻辑。暂时这么设计
    def _on_view_result(self):
        title = f"{self.facility_code}平台强度/改造可行性评估结果"

        if not getattr(self, "job_name", "").strip():
            QMessageBox.warning(self, "提示", "当前 job_name 为空，请先从平台强度页进入并创建新模型。")
            return

        if not getattr(self, "mysql_url", "").strip():
            QMessageBox.warning(self, "提示", "当前 MYSQL_URL 为空，无法读取新模型信息。")
            return

        mw = self.window()
        if not hasattr(mw, "tab_widget"):
            QMessageBox.information(self, "提示", "未检测到主窗口Tab组件，无法打开页面。")
            return

        key = f"feasibility_results::{self.facility_code}"

        try:
            if hasattr(mw, "page_tab_map") and key in mw.page_tab_map:
                old_page = mw.page_tab_map[key]
                old_idx = mw.tab_widget.indexOf(old_page)
                if old_idx != -1:
                    mw.tab_widget.removeTab(old_idx)

                try:
                    old_page.close()
                except Exception:
                    pass

                try:
                    old_page.deleteLater()
                except Exception:
                    pass

                del mw.page_tab_map[key]

            page = FeasibilityAssessmentResultsPage(
                mw,
                facility_code=self.facility_code,
                job_name=self.job_name,
                mysql_url=self.mysql_url,
                platform_overview_text=self.platform_overview_text,
                inspection_record_summary_text=self.inspection_record_summary_text,
                env_branch=self.env_branch,
                env_op_company=self.env_op_company,
                env_oilfield=self.env_oilfield,
                overall_model_image_path=self.overall_model_image_path,
            )

            idx = mw.tab_widget.addTab(page, title)
            mw.tab_widget.setCurrentIndex(idx)

            if hasattr(mw, "page_tab_map"):
                mw.page_tab_map[key] = page

        except Exception as e:
            QMessageBox.critical(self, "查看结果失败", f"打开结果页失败：\n{e}")

    def _show_text_dialog(self, title: str, text: str, extra_open_path: Optional[str] = None):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(900, 600)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        edt = QTextEdit()
        edt.setReadOnly(True)
        edt.setPlainText(text)
        v.addWidget(edt, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        if extra_open_path:
            btn_open = QPushButton("用系统打开")
            btn_open.clicked.connect(lambda: self._open_local_file(extra_open_path))
            btn_row.addWidget(btn_open)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)

        v.addLayout(btn_row)
        dlg.exec_()

    def _get_engine(self):
        if not self.mysql_url:
            raise ValueError("MYSQL_URL 未配置，请先在环境变量中设置 MYSQL_URL")
        return create_engine(self.mysql_url, future=True, pool_pre_ping=True)

    def _ensure_input_tables(self, engine) -> None:
        ddl_list = [
            """
            CREATE TABLE IF NOT EXISTS well_slots (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                job_name VARCHAR(100) NOT NULL,
                slot_no INT NOT NULL,
                x DOUBLE NULL,
                y DOUBLE NULL,
                conductor_od DOUBLE NULL,
                conductor_wt DOUBLE NULL,
                support_od DOUBLE NULL,
                support_wt DOUBLE NULL,
                top_load_fz DOUBLE NULL,
                KEY idx_ws_job_slot (job_name, slot_no)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS well_slot_connections (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                job_name VARCHAR(100) NOT NULL,
                slot_no INT NOT NULL,
                level_z DOUBLE NULL,
                connection_type VARCHAR(50) NULL,
                KEY idx_wsc_job_slot (job_name, slot_no),
                KEY idx_wsc_job_level (job_name, level_z)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS risers (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                job_name VARCHAR(100) NOT NULL,
                riser_no INT NOT NULL,
                x DOUBLE NULL,
                y DOUBLE NULL,
                riser_od DOUBLE NULL,
                riser_wt DOUBLE NULL,
                support_od DOUBLE NULL,
                support_wt DOUBLE NULL,
                batter_x DOUBLE NULL,
                batter_y DOUBLE NULL,
                KEY idx_risers_job_riser (job_name, riser_no)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS riser_connections (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                job_name VARCHAR(100) NOT NULL,
                riser_no INT NOT NULL,
                level_z DOUBLE NULL,
                connection_type VARCHAR(50) NULL,
                KEY idx_rc_job_riser (job_name, riser_no),
                KEY idx_rc_job_level (job_name, level_z)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS topside_weights (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                job_name VARCHAR(100) NOT NULL,
                weight_no INT NOT NULL,
                x DOUBLE NULL,
                y DOUBLE NULL,
                z DOUBLE NULL,
                weight_t DOUBLE NULL,
                KEY idx_tw_job_weight (job_name, weight_no)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        ]
        with engine.begin() as conn:
            for ddl in ddl_list:
                conn.execute(text(ddl))

    def _cell_text(self, table: QTableWidget, row: int, col: int) -> str:
        it = table.item(row, col)
        return (it.text() if it else "").strip()

    def _combo_text(self, table: QTableWidget, row: int, col: int) -> str:
        w = table.cellWidget(row, col)
        if isinstance(w, QWidget):
            combo = w.findChild(QComboBox)
            if combo is not None:
                return (combo.currentText() or "").strip()
        return ""

    def _to_float(self, text_value: str):
        txt = (text_value or "").strip()
        if txt == "":
            return None
        try:
            return float(txt)
        except Exception:
            raise ValueError(f"无法转换为数字：{txt}")

    def _table_has_any_data(self, table: QTableWidget, row: int, col_from: int, col_to: int) -> bool:
        for c in range(col_from, col_to + 1):
            if self._cell_text(table, row, c):
                return True
        return False

    def _delete_old_input_rows(self, conn, table_names: List[str]) -> None:
        for table_name in table_names:
            conn.execute(
                text(f"DELETE FROM {table_name} WHERE job_name = :job_name"),
                {"job_name": self.job_name}
            )

    def _get_level_headers(self, table: QTableWidget, start_col: int) -> List[tuple]:
        levels = []
        for c in range(start_col, table.columnCount()):
            txt = self._cell_text(table, 1, c)
            if not txt:
                continue
            try:
                z = float(txt)
            except Exception:
                continue
            levels.append((c, z))
        return levels

    def _save_well_slots_to_db(self):
        engine = self._get_engine()
        self._ensure_input_tables(engine)

        level_headers = self._get_level_headers(self.tbl1, 8)

        slot_rows = []
        conn_rows = []

        header_rows = 2
        for r in range(header_rows, self.tbl1.rowCount()):
            # 基础列完全空，就跳过
            if not self._table_has_any_data(self.tbl1, r, 1, 7):
                continue

            slot_no = int(float(self._cell_text(self.tbl1, r, 0) or 0))
            x = self._to_float(self._cell_text(self.tbl1, r, 1))
            y = self._to_float(self._cell_text(self.tbl1, r, 2))
            conductor_od = self._to_float(self._cell_text(self.tbl1, r, 3))
            conductor_wt = self._to_float(self._cell_text(self.tbl1, r, 4))
            support_od = self._to_float(self._cell_text(self.tbl1, r, 5))
            support_wt = self._to_float(self._cell_text(self.tbl1, r, 6))
            top_load_fz = self._to_float(self._cell_text(self.tbl1, r, 7))

            slot_rows.append({
                "job_name": self.job_name,
                "slot_no": slot_no,
                "x": x,
                "y": y,
                "conductor_od": conductor_od,
                "conductor_wt": conductor_wt,
                "support_od": support_od,
                "support_wt": support_wt,
                "top_load_fz": top_load_fz,
            })

            for col, z in level_headers:
                connection_type = self._combo_text(self.tbl1, r, col)
                if not connection_type:
                    continue
                conn_rows.append({
                    "job_name": self.job_name,
                    "slot_no": slot_no,
                    "level_z": z,
                    "connection_type": connection_type,
                })

        with engine.begin() as conn:
            self._delete_old_input_rows(conn, ["well_slot_connections", "well_slots"])

            if slot_rows:
                conn.execute(text("""
                    INSERT INTO well_slots (
                        job_name, slot_no, x, y,
                        conductor_od, conductor_wt,
                        support_od, support_wt,
                        top_load_fz
                    ) VALUES (
                        :job_name, :slot_no, :x, :y,
                        :conductor_od, :conductor_wt,
                        :support_od, :support_wt,
                        :top_load_fz
                    )
                """), slot_rows)

            if conn_rows:
                conn.execute(text("""
                    INSERT INTO well_slot_connections (
                        job_name, slot_no, level_z, connection_type
                    ) VALUES (
                        :job_name, :slot_no, :level_z, :connection_type
                    )
                """), conn_rows)

    def _save_risers_to_db(self):
        engine = self._get_engine()
        self._ensure_input_tables(engine)

        level_headers = self._get_level_headers(self.tbl2, 9)

        riser_rows = []
        conn_rows = []

        header_rows = 2
        for r in range(header_rows, self.tbl2.rowCount()):
            if not self._table_has_any_data(self.tbl2, r, 1, 8):
                continue

            riser_no = int(float(self._cell_text(self.tbl2, r, 0) or 0))
            x = self._to_float(self._cell_text(self.tbl2, r, 1))
            y = self._to_float(self._cell_text(self.tbl2, r, 2))
            riser_od = self._to_float(self._cell_text(self.tbl2, r, 3))
            riser_wt = self._to_float(self._cell_text(self.tbl2, r, 4))
            support_od = self._to_float(self._cell_text(self.tbl2, r, 5))
            support_wt = self._to_float(self._cell_text(self.tbl2, r, 6))
            batter_x = self._to_float(self._cell_text(self.tbl2, r, 7))
            batter_y = self._to_float(self._cell_text(self.tbl2, r, 8))

            riser_rows.append({
                "job_name": self.job_name,
                "riser_no": riser_no,
                "x": x,
                "y": y,
                "riser_od": riser_od,
                "riser_wt": riser_wt,
                "support_od": support_od,
                "support_wt": support_wt,
                "batter_x": batter_x,
                "batter_y": batter_y,
            })

            for col, z in level_headers:
                connection_type = self._combo_text(self.tbl2, r, col)
                if not connection_type:
                    continue
                conn_rows.append({
                    "job_name": self.job_name,
                    "riser_no": riser_no,
                    "level_z": z,
                    "connection_type": connection_type,
                })

        with engine.begin() as conn:
            self._delete_old_input_rows(conn, ["riser_connections", "risers"])

            if riser_rows:
                conn.execute(text("""
                    INSERT INTO risers (
                        job_name, riser_no, x, y,
                        riser_od, riser_wt,
                        support_od, support_wt,
                        batter_x, batter_y
                    ) VALUES (
                        :job_name, :riser_no, :x, :y,
                        :riser_od, :riser_wt,
                        :support_od, :support_wt,
                        :batter_x, :batter_y
                    )
                """), riser_rows)

            if conn_rows:
                conn.execute(text("""
                    INSERT INTO riser_connections (
                        job_name, riser_no, level_z, connection_type
                    ) VALUES (
                        :job_name, :riser_no, :level_z, :connection_type
                    )
                """), conn_rows)

    def _save_topside_weights_to_db(self):
        engine = self._get_engine()
        self._ensure_input_tables(engine)

        rows = []
        header_rows = 2
        for r in range(header_rows, self.tbl3.rowCount()):
            if not self._table_has_any_data(self.tbl3, r, 1, 4):
                continue

            weight_no = int(float(self._cell_text(self.tbl3, r, 0) or 0))
            x = self._to_float(self._cell_text(self.tbl3, r, 1))
            y = self._to_float(self._cell_text(self.tbl3, r, 2))
            z = self._to_float(self._cell_text(self.tbl3, r, 3))
            weight_t = self._to_float(self._cell_text(self.tbl3, r, 4))

            rows.append({
                "job_name": self.job_name,
                "weight_no": weight_no,
                "x": x,
                "y": y,
                "z": z,
                "weight_t": weight_t,
            })

        with engine.begin() as conn:
            self._delete_old_input_rows(conn, ["topside_weights"])

            if rows:
                conn.execute(text("""
                    INSERT INTO topside_weights (
                        job_name, weight_no, x, y, z, weight_t
                    ) VALUES (
                        :job_name, :weight_no, :x, :y, :z, :weight_t
                    )
                """), rows)

    def _open_local_file(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

