# -*- coding: utf-8 -*-
# pages/feasibility_assessment_page.py
#
# 结构强度 -> WC19-1DPPA平台强度/改造可行性评估
#
# 本版改动：
# - 三张表格采用“表内多行表头 + 合并单元格（setSpan）”来匹配原型图样式
# - “高程及连接形式”列使用 QComboBox，并保证宽度可显示完整文本
# - 每张表格右上角保留“保存”按钮（在表格外的 header 区域）

import os
import shutil
import subprocess
from typing import List, Optional, cast

from PyQt5.QtCore import QEvent, QTimer, Qt, QUrl
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

from base_page import BasePage
from dropdown_bar import DropdownBar
from pages.feasibility_assessment_results_page import FeasibilityAssessmentResultsPage


SONGTI_FONT_FALLBACK = '"SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"'


class FeasibilityAssessmentPage(BasePage):
    """
    WC19-1DPPA平台强度/改造可行性评估（feasibility_assessment_page）
    """
    CONNECT_OPTIONS = ["焊接", "无连接", "导向连接"]
    ELEVATIONS1 = [36, 31, 27, 23, 18, 7, -12, -34, -58, -83, -109]
    ELEVATIONS2 = [7, -12, -34, -58, -83, -109, -122.4]

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

    def __init__(self, main_window,facility_code, parent=None):
        if parent is None:
            parent = main_window
        super().__init__("", parent)
        self.facility_code = facility_code
        self.main_window = main_window
        self._hover_combo_boxes = []
        self._combo_hover_meta = {}
        self._dynamic_table_meta = {}
        self._build_ui()

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
        body_layout.addWidget(self._build_table_1(), 1)  # 权重设为1，允许表格组块纵向伸展填满留白
        body_layout.addWidget(self._build_table_2(), 1)
        body_layout.addWidget(self._build_table_3(), 1)

        body_layout.addWidget(self._build_bottom_actions(), 0)

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

    def _set_combo_cell(self, table: QTableWidget, row: int, col: int, default: str = "无连接"):
        cell_wrap = QWidget()
        cell_wrap.setStyleSheet("background: #ffffff; border: 1px solid #e6e6e6;")
        cell_lay = QHBoxLayout(cell_wrap)
        cell_lay.setContentsMargins(0, 0, 0, 0)
        cell_lay.setSpacing(0)

        combo = QComboBox(cell_wrap)
        combo.addItems(self.CONNECT_OPTIONS)
        combo.setFont(self._songti_small_four_font())
        if default in self.CONNECT_OPTIONS:
            combo.setCurrentText(default)
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
        for i, elevation in enumerate(self.ELEVATIONS1):
            default = "焊接" if elevation in (27, 23, 18) else "无连接"
            self._set_combo_cell(self.tbl1, row, start + i, default=default)

    def _populate_table2_row(self, row: int):
        base_cols = 1 + 2 + 2 + 2 + 2
        self._set_cell(self.tbl2, row, 0, "", bg=QColor("#e9eef5"), editable=False)
        for col in range(1, base_cols):
            self.tbl2.setItem(row, col, self._make_empty_item(bg=self.DATA_BG, editable=True))
        start = base_cols
        for i, elevation in enumerate(self.ELEVATIONS2):
            default = "焊接" if elevation in (27, 23) else "无连接"
            self._set_combo_cell(self.tbl2, row, start + i, default=default)

    def _populate_table3_row(self, row: int):
        self._set_cell(self.tbl3, row, 0, "", bg=QColor("#e9eef5"), editable=False)
        for col in range(1, self.tbl3.columnCount()):
            self.tbl3.setItem(row, col, self._make_empty_item(bg=self.DATA_BG, editable=True))

    def _insert_dynamic_row(self, table_key: str):
        meta = self._dynamic_table_meta.get(table_key)
        if not meta:
            return
        table = meta["table"]
        row = table.rowCount()
        self._insert_dynamic_row_at(table_key, row)

    def _insert_dynamic_row_at(self, table_key: str, row: int):
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

    def _remove_dynamic_row(self, table_key: str):
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

    def _remove_dynamic_row_at(self, table_key: str, row: int):
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

    def _show_row_context_menu(self, table_key: str, pos):
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

    def _make_group_header(self, title: str, on_save) -> QWidget:
        head = QWidget()
        lay = QHBoxLayout(head)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lab = QLabel(title)
        lab.setFont(self._songti_small_four_font(bold=True))
        lab.setStyleSheet("font-family: %s; font-size: 12pt; font-weight: bold; color: #1d2b3a;" % SONGTI_FONT_FALLBACK)
        lay.addWidget(lab, 0)
        lay.addStretch(1)

        btn = self._make_save_button()
        btn.clicked.connect(on_save)
        lay.addWidget(btn, 0)
        return head

    # ---------------- 表1：新增井槽信息（合并表头） ----------------
    def _build_table_1(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(self._make_group_header("新增井槽信息", self._on_save_table1), 0)

        # 表内表头：2 行
        header_rows = 2
        data_rows = 3

        # 列布局（与原型一致）
        # 编号 | 水平面坐标(X,Y) | 井槽尺寸(OD,WT) | 支撑结构(OD,WT) | 垂向载荷Fz | 高程及连接形式(7列)
        base_cols = 1 + 2 + 2 + 2 + 1
        cols = base_cols + len(self.ELEVATIONS1)

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

        self.tbl1.setSpan(0, c, 1, len(self.ELEVATIONS1))
        self._set_cell(self.tbl1, 0, c, "高程及连接形式", bg=self.HEADER_BG, bold=True, editable=False)
        for k in range(1, len(self.ELEVATIONS1)):
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

        for e in self.ELEVATIONS1:
            self._set_cell(self.tbl1, 1, c, str(e), bg=self.SUBHDR_BG, bold=True, editable=False)
            c += 1

        # --- 数据区 ---
        demo = [
            ["1", "1.314", "1.714", "914", "25", "406", "19", "1000"],
            ["2", "1.314", "-0.572", "610", "25", "406", "19", "1000"],
            ["3", "1.314", "-2.858", "610", "25", "406", "19", "1000"],
        ]
        for r in range(data_rows):
            rr = header_rows + r
            # 编号
            self._set_cell(self.tbl1, rr, 0, demo[r][0], bg=QColor("#e9eef5"), editable=False)
            # 基础字段
            for c in range(1, base_cols):
                self._set_cell(self.tbl1, rr, c, demo[r][c], bg=self.DATA_BG, editable=True)

            # 连接形式下拉
            start = base_cols
            for i, e in enumerate(self.ELEVATIONS1):
                col = start + i
                default = "焊接" if e in (27, 23, 18) else "无连接"
                self._set_combo_cell(self.tbl1, rr, col, default=default)

        # 在 _build_table_1 中，调用 _auto_fit_columns 之前定义分组
        groups_tbl1 = [
            [1, 2],  # X, Y
            [3, 4],  # 井槽尺寸 OD, WT
            [5, 6],  # 支撑结构 OD, WT
            list(range(8, 8 + len(self.ELEVATIONS1)))  # 高程列（可选，使所有高程列等宽）
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
        self.tbl1.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tbl1.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._install_row_hover_actions(self.tbl1, "tbl1", header_rows)
        lay.addWidget(self.tbl1, 1)

        #lay.addWidget(self.tbl1, 1)
        return box

    # ---------------- 表2：立管/电缆信息（合并表头） ----------------
    def _build_table_2(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(self._make_group_header("新增立管/电缆信息", self._on_save_table2), 0)

        header_rows = 2
        data_rows = 3

        # 编号 | 工作平面坐标(2) | 立管/电缆尺寸(2) | 支撑结构(2) | 倾斜度(2) | 高程及连接形式(7)
        base_cols = 1 + 2 + 2 + 2 + 2
        cols = base_cols + len(self.ELEVATIONS2)

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

        self.tbl2.setSpan(0, c, 1, len(self.ELEVATIONS2))
        self._set_cell(self.tbl2, 0, c, "高程及连接形式", bg=self.HEADER_BG, bold=True, editable=False)
        for k in range(1, len(self.ELEVATIONS2)):
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
        for e in self.ELEVATIONS2:
            self._set_cell(self.tbl2, 1, c, str(e), bg=self.SUBHDR_BG, bold=True, editable=False)
            c += 1

        # 数据区
        demo = [
            ["1", "1.314", "1.714", "914", "25", "406", "19", "0.1", "0.1"],
            ["2", "1.314", "-0.572", "610", "25", "406", "19", "0.1", "0.1"],
            ["3", "1.314", "-2.858", "610", "25", "406", "19", "0.1", "0.1"],
        ]
        for r in range(data_rows):
            rr = header_rows + r
            self._set_cell(self.tbl2, rr, 0, demo[r][0], bg=QColor("#e9eef5"), editable=False)
            for c in range(1, base_cols):
                self._set_cell(self.tbl2, rr, c, demo[r][c], bg=self.DATA_BG, editable=True)
            start = base_cols
            for i, e in enumerate(self.ELEVATIONS2):
                col = start + i
                default = "焊接" if e in (27, 23) else "无连接"
                self._set_combo_cell(self.tbl2, rr, col, default=default)


        groups_tbl2 = [
            [1, 2],  # X, Y
            [3, 4],  # 立管/电缆尺寸 OD, WT
            [5, 6],  # 支撑结构 OD, WT
            [7, 8],  # 倾斜度 X方向, Y方向
            list(range(9, 9 + len(self.ELEVATIONS2)))  # 高程列
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
        self.tbl2.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tbl2.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._install_row_hover_actions(self.tbl2, "tbl2", header_rows)
        lay.addWidget(self.tbl2, 1)
        #lay.addWidget(self.tbl2, 1)
        return box

    # ---------------- 表3：新增组块载荷信息（合并表头） ----------------
    def _build_table_3(self) -> QWidget:
        box = QGroupBox()
        box.setTitle("")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(self._make_group_header("新增组块载荷信息", self._on_save_table3), 0)

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

        demo = [
            ["1", "1.314", "1.714", "10", "5"],
            ["2", "1.314", "-0.572", "10", "5"],
            ["3", "1.314", "-2.858", "10", "5"],
            ["4", "-24", "1.714", "10", "5"],
            ["5", "-24", "-0.572", "10", "5"],
            ["6", "-24", "-2.858", "10", "5"],
        ]
        for r in range(data_rows):
            rr = header_rows + r
            self._set_cell(self.tbl3, rr, 0, demo[r][0], bg=QColor("#e9eef5"), editable=False)
            self._set_cell(self.tbl3, rr, 1, demo[r][1], bg=self.DATA_BG, editable=True)
            self._set_cell(self.tbl3, rr, 2, demo[r][2], bg=self.DATA_BG, editable=True)
            self._set_cell(self.tbl3, rr, 3, demo[r][3], bg=self.DATA_BG, editable=True)
            self._set_cell(self.tbl3, rr, 4, demo[r][4], bg=self.DATA_BG, editable=True)

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
        # === 2. 替换为直接添加表格，并明确启用表格自身的滚动条 ===
        self.tbl3.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tbl3.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._install_row_hover_actions(self.tbl3, "tbl3", header_rows)
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

        self.btn_create = mk("创建新模型")
        self.btn_run = mk("计算分析")
        self.btn_view = mk("查看结果")

        self.btn_create.clicked.connect(self._on_create_model)
        self.btn_run.clicked.connect(self._on_run_analysis)
        self.btn_view.clicked.connect(self._on_view_result)

        lay.addStretch(1)
        lay.addWidget(self.btn_create, 0)
        lay.addWidget(self.btn_run, 0)
        lay.addWidget(self.btn_view, 0)
        lay.addStretch(1)
        return wrap

    # ---------------- 保存按钮：导出当前表格数据 ----------------
    def _on_save_table1(self):
        self._save_table_as_csv(self.tbl1, header_rows=2, default_name="新增井槽信息.csv",
                                with_combo_cols=True, combo_start_col=8)

    def _on_save_table2(self):
        self._save_table_as_csv(self.tbl2, header_rows=2, default_name="立管电缆信息.csv",
                                with_combo_cols=True, combo_start_col=9)

    def _on_save_table3(self):
        self._save_table_as_csv(self.tbl3, header_rows=2, default_name="新增组块载荷信息.csv",
                                with_combo_cols=False, combo_start_col=0)

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
        base_path, _ = QFileDialog.getOpenFileName(self, "选择基准结构计算文件（示例：.inp/.sacs/.dat）", "", "All Files (*)")
        if not base_path:
            return
        out_path, _ = QFileDialog.getSaveFileName(self, "保存新模型文件", "WC19-1DPPA_new_model.txt", "All Files (*)")
        if not out_path:
            return

        try:
            shutil.copyfile(base_path, out_path)
            with open(out_path, "a", encoding="utf-8", errors="ignore") as f:
                f.write("\n\n")
                f.write("** ----------------------------\n")
                f.write("** MODIFICATIONS (Generated by FeasibilityAssessmentPage)\n")
                f.write("** ----------------------------\n\n")
                f.write(self._dump_table_block("新增井槽信息", self.tbl1, header_rows=2, with_combo_cols=True, combo_start_col=8))
                f.write("\n")
                f.write(self._dump_table_block("立管/电缆信息", self.tbl2, header_rows=2, with_combo_cols=True, combo_start_col=9))
                f.write("\n")
                f.write(self._dump_table_block("新增组块载荷信息", self.tbl3, header_rows=2, with_combo_cols=False, combo_start_col=0))
                f.write("\n")

            QMessageBox.information(self, "创建完成", f"已生成新模型文件：\n{out_path}\n\n（当前为占位写入方式，后续可替换为真实 SACS/结构文件写入逻辑）")
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

    def _on_run_analysis(self):
        model_path, _ = QFileDialog.getOpenFileName(self, "选择需要分析的模型文件", "", "All Files (*)")
        if not model_path:
            return

        exe = os.environ.get("SACS_ENGINEANALYSIS", "").strip()
        if (not exe) or (not os.path.exists(exe)):
            exe, _ = QFileDialog.getOpenFileName(self, "选择 SACS engineanalysis 可执行文件", "", "All Files (*)")
            if not exe:
                return

        try:
            proc = subprocess.run([exe, model_path], capture_output=True, text=True, timeout=60 * 30)
            ok = (proc.returncode == 0)
            title = "分析完成" if ok else "分析失败"
            detail = (proc.stdout or "")[-3000:] + ("\n" + (proc.stderr or "")[-3000:] if proc.stderr else "")
            if not detail.strip():
                detail = "(无输出)"
            self._show_text_dialog(title, detail)
        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "超时", "engineanalysis 运行超时（30分钟）。")
        except Exception as e:
            QMessageBox.critical(self, "运行失败", f"调用 engineanalysis 失败：\n{e}")

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
        """查看结果 - 跳转到可行性评估结果页面"""
        title = f"{self.facility_code}平台强度/改造可行性评估结果"

        mw = self.window()
        if hasattr(mw, "tab_widget"):
            # 去重：同一个设施编码只开一个
            key = f"feasibility_results::{self.facility_code}"
            #补全去重跳转逻辑，防止多次点击"查看结果"打开无数个重复的 Tab
            if hasattr(mw, "page_tab_map") and key in mw.page_tab_map:
                w = mw.page_tab_map[key]
                idx = mw.tab_widget.indexOf(w)
                if idx != -1:
                    mw.tab_widget.setCurrentIndex(idx)
                    return
            page = FeasibilityAssessmentResultsPage(mw, self.facility_code)
            idx = mw.tab_widget.addTab(page, title)
            mw.tab_widget.setCurrentIndex(idx)
            if hasattr(mw, "page_tab_map"):
                mw.page_tab_map[key] = page
        else:
            QMessageBox.information(self, "提示", "未检测到主窗口Tab组件，无法打开页面。")

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

    def _open_local_file(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
