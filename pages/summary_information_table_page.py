# -*- coding: utf-8 -*-
# pages/summary_information_table_page.py
import csv
import ctypes
import os
import subprocess
import sys
from typing import List, Dict, Any

import pandas as pd

from PyQt5.QtWidgets import (
    QAbstractItemView,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox,
    QFileDialog, QFrame, QToolTip,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont

from core.app_paths import external_path, first_existing_path
from core.table_clipboard import TableClipboardController
from pages.hover_tip_table import HoverTipTable
from core.base_page import BasePage
from services.inspection_business_db_adapter import (
    load_platform_load_information_items,
    save_platform_load_summary_snapshot,
)
from services.platform_summary_source import load_platform_summary_source



class SummaryInformationTablePage(BasePage):
    """
    载荷信息管理 - 汇总信息表（示例页面）
    - 合并表头：使用“表格内部两行表头 + setSpan()”
    - 表头样式统一：补齐表头两行所有格子的背景与边框
    - 表格自适应窗口：列宽 Stretch，随窗口缩放
    - 示例数据导入：
        * 默认读取 data/summary_information_table_demo.csv
        * 若不存在，会自动生成一份模拟数据（30行）
    - 行数很多时的展示策略：表格自身显示横向/纵向滚动条。
    """

    EXCEL_NAME = "platform_total.xls"
    MAX_EXPAND_ROWS = 50
    HEADER_ROWS = 2
    EDITABLE_DATA_START_COL = 6
    COLUMN_WIDTHS = [
        60,   # 序号
        130,  # 分公司
        160,  # 作业公司
        190,  # 设施名称
        110,  # 投产时间
        90,   # 设计年限
        145,  # 建造总操作重量
        145,  # 变化总重量
        95,   # 变化率
        145,  # 不可超载重量
        155,  # 重心
        160,  # 重心不可超载半径
        130,  # 操作工况安全系数
        130,  # 极端工况安全系数
        110,  # 整体评估次数
    ]

    @staticmethod
    def _songti_small_four_font(bold: bool = False) -> QFont:
        font = QFont("SimSun")
        font.setPointSize(12)
        font.setBold(bold)
        return font

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.data_dir = first_existing_path("data")
        self.output_data_dir = external_path("data")
        self._build_ui()
        self.refresh_from_file_summary_page()

    def _build_ui(self):
        # 表格视觉复用“文件管理 > 汇总信息”的白色卡片、浅蓝表头与细网格风格。
        self.setObjectName("LoadSummaryRoot")
        self.setStyleSheet("""
            QWidget#LoadSummaryRoot,
            QWidget#LoadSummaryTopBar {
                background: #f4f7fb;
            }

            QFrame#SummaryTablePanel {
                background: #ffffff;
                border-radius: 16px;
                border: 1px solid #dce6f2;
            }
            /* 顶部按钮风格：参照 platform_load_information_page */
            QPushButton#TopActionBtn {
                background: #f6a24a;
                border: 1px solid #2f3a4a;
                border-radius: 3px;
                padding: 6px 16px;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton#TopActionBtn:hover { background: #ffb86b; }

            QTableWidget {
                background: #ffffff;
                border: none;
                gridline-color: #e5ebf2;
                alternate-background-color: #f8fbff;
                selection-background-color: #d6e9ff;
                selection-color: #102a43;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QTableWidget::item:selected { background-color: #d6e9ff; color: #102a43; }
            QTableWidget::item:focus { outline: none; }
        """)

        # 顶部操作条（右上角按钮） - 固定在顶部
        top_bar_wrap = QWidget()
        top_bar_wrap.setObjectName("LoadSummaryTopBar")
        top_bar = QHBoxLayout(top_bar_wrap)
        top_bar.setContentsMargins(10, 5, 10, 0)
        top_bar.addStretch(1)

        self.btn_save = QPushButton("保存")
        self.btn_export = QPushButton("导出数据")

        for b in (self.btn_save, self.btn_export):
            b.setObjectName("TopActionBtn")
            b.setFont(self._songti_small_four_font(bold=True))
            b.setMinimumHeight(32)

        self.btn_save.clicked.connect(self._on_save)
        self.btn_export.clicked.connect(self._on_export)

        top_bar.addWidget(self.btn_save)
        top_bar.addWidget(self.btn_export)
        self.main_layout.addWidget(top_bar_wrap, 0)

        table_panel = QFrame()
        table_panel.setObjectName("SummaryTablePanel")
        root = QVBoxLayout(table_panel)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 创建表格（表头结构不变）
        self.table = self._build_table_skeleton()
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        root.addWidget(self.table, 1)
        self.main_layout.addWidget(table_panel, 1)

        # 填表说明 - 固定在底部，不随滚动条移动
        self.note_label = QLabel(
            "填表说明\n"
            "1、变化率、重心、桩基承载力安全系数、是否整体评估：每年更新一次，填写最新数据。\n"
            "2、变化量=变化总重/建造总操作重量。\n"
        )
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet("color:#111827; font-size:12pt; padding:10px; background: #f4f7fb; border-top: 1px solid #d8e3ef;")
        self.note_label.setFont(self._songti_small_four_font())
        self.main_layout.addWidget(self.note_label, 0)

    # ---------- merged header helpers ----------
    def _mk_item(
        self,
        text: str,
        *,
        bold: bool = False,
        bg: QColor | None = None,
        fg: QColor | None = None,
        editable: bool = False,
    ) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setTextAlignment(Qt.AlignCenter)
        flags = it.flags()
        if editable:
            flags |= Qt.ItemIsEditable | Qt.ItemIsSelectable
        else:
            flags &= ~Qt.ItemIsEditable
        it.setFlags(flags)
        it.setFont(self._songti_small_four_font(bold=bold))
        if bg is not None:
            it.setBackground(bg)
        if fg is not None:
            it.setForeground(fg)
        return it

    def _fill_bg_for_row(self, table: QTableWidget, row: int, bg: QColor):
        # 给整行补背景，避免合并后“空白格”颜色不一致
        for c in range(table.columnCount()):
            if table.item(row, c) is None:
                table.setItem(row, c, self._mk_item("", bg=bg))
            else:
                table.item(row, c).setBackground(bg)

    def _columns(self) -> List[str]:
        # 数据列（与CSV列顺序一致，16列）
        return [
            "序号",
            "分公司",
            "作业公司",
            "设施名称",
            "投产时间",
            "设计年限",
            "建造总操作重量\n(MT)",
            "变化总重量\n(MT)",
            "变化率\n(%)",
            "不可超载重量\n(MT)",
            "重心\n(m)",
            "重心不可超载半径\n(m)",
            "桩基承载力安全系数(最小)-操作",
            "桩基承载力安全系数(最小)-极端",
            "整体评估次数",
        ]

    def _build_table_skeleton(self) -> QTableWidget:
        cols = self._columns()
        header_rows = self.HEADER_ROWS

        table = HoverTipTable(header_rows, len(cols))
        table.setFont(self._songti_small_four_font())
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)  # 用表内两行表头模拟合并表头
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # 行高：两行表头（接近截图）
        table.setRowHeight(0, 52)  # 分组表头：支持两行长标题完整显示
        table.setRowHeight(1, 72)  # 子表头：长字段按三行显示，避免截断

        # 表头背景复用文件管理汇总页的浅蓝色。
        bg_header = QColor("#edf4fb")
        bg_group = QColor("#edf4fb")

        # ---- 纵向合并：0-5（跨两行表头）----
        for c in range(0, 6):
            table.setSpan(0, c, 2, 1)
            table.setItem(0, c, self._mk_item(self._header_label_for_col(c), bold=True, bg=bg_header))

        # ---- 横向合并：上部组块重控（6~11）----
        table.setSpan(0, 6, 1, 6)
        table.setItem(0, 6, self._mk_item("上部组块重控", bold=True, bg=bg_group))

        # 子表头（6~12）
        for c in range(6, 12):
            table.setItem(1, c, self._mk_item(self._header_label_for_col(c), bold=True, bg=bg_header))

        # ---- 横向合并：桩基承载力安全系数（最小）（12~13）----
        table.setSpan(0, 12, 1, 2)
        table.setItem(0, 12, self._mk_item("桩基承载力\n安全系数（最小）", bold=True, bg=bg_group))
        table.setItem(1, 12, self._mk_item("操作", bold=True, bg=bg_header))
        table.setItem(1, 13, self._mk_item("极端", bold=True, bg=bg_header))

        table.setSpan(0,14,2,1)
        table.setItem(0,14,self._mk_item("整体评估次数", bold=True, bg=bg_header))
        # ✅ 补齐表头两行背景（样式完全一致）
        self._fill_bg_for_row(table, 0, bg_group)
        self._fill_bg_for_row(table, 1, bg_header)
        self._install_table_clipboard(table)

        return table

    def _apply_stable_column_widths(self) -> None:
        """使用固定语义列宽，避免长内容把单列异常撑宽。"""
        for c, width in enumerate(self.COLUMN_WIDTHS):
            if c >= self.table.columnCount():
                break
            self.table.setColumnWidth(c, width)

        self.table.setMinimumWidth(0)
        self.table.setMaximumWidth(16777215)

    def _install_table_clipboard(self, table: QTableWidget) -> None:
        controller = TableClipboardController(
            table,
            can_paste_cell=lambda row, col, target=table: self._can_paste_table_cell(target, row, col),
            on_paste_rows_ignored=lambda count, target=table: self._show_table_tip(
                target,
                f"粘贴内容超出现有数据区，已忽略 {count} 行。",
            ),
            on_paste_cells_skipped=lambda count, target=table: self._show_table_tip(
                target,
                f"部分单元格不可粘贴，已跳过 {count} 个单元格。",
            ),
        )
        table._table_clipboard = controller

    def _can_paste_table_cell(self, table: QTableWidget, row: int, col: int) -> bool:
        if row < self.HEADER_ROWS:
            return False
        if col < self.EDITABLE_DATA_START_COL:
            return False
        if table.cellWidget(row, col) is not None:
            return False
        item = table.item(row, col)
        if item is None:
            return True
        return bool(item.flags() & Qt.ItemIsEditable)

    def _show_table_tip(self, table: QTableWidget, message: str) -> None:
        rect = table.viewport().rect()
        pos = table.viewport().mapToGlobal(rect.center())
        QToolTip.showText(pos, message, table, rect, 2500)

    def _header_label_for_col(self, c: int) -> str:
        # 对应截图中换行表头
        labels = {
            0: "序号",
            1: "分公司",
            2: "作业公司",
            3: "设施名称",
            4: "投产时间",
            5: "设计年限",
            6: "建造总操作\n重量\n(MT)",
            7: "变化总重量\n(MT)",
            8: "变化率\n(%)",
            9: "不可超载重量\n(MT)",
            10: "重心\n(m)",
            11: "重心不可超载\n半径\n(m)",
            14: "整体评估\n次数",
        }
        return labels.get(c, "")

    # ---------- data import ----------
    def _default_excel_path(self) -> str:
        """默认从 data/platform_total.xls 读取；若不存在，尝试从当前工作目录读取同名文件。"""
        p1 = os.path.join(self.data_dir, self.EXCEL_NAME)
        if os.path.exists(p1):
            return p1
        p2 = first_existing_path(self.EXCEL_NAME)
        if os.path.exists(p2):
            return p2
        return os.path.join(self.output_data_dir, self.EXCEL_NAME)  # 默认返回外部 data 路径（用于报错提示）

    def refresh_from_file_summary_page(self):
        profiles = self._profiles_from_open_file_summary_page()
        if profiles is None:
            try:
                profiles = self._profiles_from_saved_platform_summary_snapshot()
            except Exception as exc:
                QMessageBox.warning(self, "读取失败", f"读取平台汇总信息快照失败：\n{exc}")
                profiles = []

        rows = []
        if profiles:
            rows = [self._build_summary_row(profile, index) for index, profile in enumerate(profiles, start=1)]
        self._apply_data(rows)

    def refresh_from_database(self, show_warning: bool = True):
        self.refresh_from_file_summary_page()

    def _profiles_from_open_file_summary_page(self) -> List[Dict[str, Any]] | None:
        mw = self.window()
        tab_widget = getattr(mw, "tab_widget", None)
        if tab_widget is not None:
            for index in range(tab_widget.count()):
                page = tab_widget.widget(index)
                if page is self:
                    continue
                getter = getattr(page, "current_facility_profiles", None)
                if callable(getter):
                    return getter()

        session_cache = getattr(mw, "platform_summary_profiles_cache", None) if mw is not None else None
        if isinstance(session_cache, list):
            return session_cache
        return None

    def _profiles_from_saved_platform_summary_snapshot(self) -> List[Dict[str, Any]]:
        return load_platform_summary_source(snapshot_key="latest").profiles

    def _build_summary_row(self, profile: Dict[str, Any], index: int) -> List[str]:
        facility_code = str(profile.get("facility_code") or "").strip()
        load_rows = load_platform_load_information_items(facility_code) if facility_code else []
        latest = self._pick_latest_load_row(load_rows)
        latest_weight = self._to_float((latest or {}).get("total_weight_mt"))
        delta_weight = self._to_float((latest or {}).get("weight_delta_mt"))

        change_rate = ""
        if latest_weight not in (None, 0) and delta_weight is not None:
            change_rate = self._fmt_number(delta_weight / latest_weight * 100)

        overall_count = sum(
            1 for row in load_rows
            if str(row.get("overall_assessment") or "").strip() not in ("", "\\", "/", "否", "0")
        )

        return [
            str(index),
            str(profile.get("branch") or ""),
            str(profile.get("op_company") or ""),
            str(profile.get("facility_name") or profile.get("facility_code") or ""),
            str(profile.get("start_time") or ""),
            str(profile.get("design_life") or ""),
            self._fmt_number(latest_weight),
            self._fmt_number(delta_weight),
            change_rate,
            str((latest or {}).get("weight_limit_mt") or ""),
            self._normalize_center_xyz_text((latest or {}).get("center_xyz") or ""),
            str((latest or {}).get("center_radius_m") or ""),
            str((latest or {}).get("safety_op") or ""),
            str((latest or {}).get("safety_extreme") or ""),
            str(overall_count),
        ]

    def _pick_latest_load_row(self, rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
        if not rows:
            return None
        return sorted(rows, key=lambda row: int(row.get("sort_order") or row.get("seq_no") or 0))[-1]

    def _to_float(self, value: Any) -> float | None:
        text = str(value or "").strip().replace(",", "")
        if not text or text in ("\\", "/"):
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _fmt_number(self, value: float | None) -> str:
        if value is None:
            return ""
        return f"{value:.3f}".rstrip("0").rstrip(".")

    def _normalize_center_xyz_text(self, value: Any) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            return ""
        return text.replace("，", ",")

    def load_from_excel(self, excel_path: str):
        """
        从“platform_total.xls”导入数据，并筛选/映射到当前表格 16 列（表格设计不变）。
        - 样表字段很多：这里只取少量字段填入；其余列留空，后续可按真实口径继续补齐映射/计算逻辑。
        """
        if not os.path.exists(excel_path):
            QMessageBox.warning(self, "提示", f"未找到数据文件：{excel_path}")
            return

        # 读取 Excel：
        # - .xls 通常需要 xlrd 引擎（pip install xlrd==2.0.1）
        # - 有些文件虽然扩展名是 .xls，但实际上是 xlsx，这里也做兼容尝试
        df = None
        last_err = None

        # 先按 .xls 方式读
        try:
            df = pd.read_excel(excel_path, header=1, engine="xlrd")
        except Exception as e:
            last_err = e

        # 再尝试不指定 engine（让 pandas 自动推断）
        if df is None:
            try:
                df = pd.read_excel(excel_path, header=1)
                last_err = None
            except Exception as e:
                last_err = e

        if df is None:
            msg = str(last_err) if last_err else "未知错误"
            QMessageBox.critical(self, "读取失败","读取 Excel 失败。如果是 .xls 文件，请先安装：xlrd==2.0.1 命令：pip install xlrd==2.0.1"f"错误详情：{msg}")
            return

        # 清理列名空格
        df.columns = [str(c).strip() for c in df.columns]

        # 样表可能存在空行/备注行：以“设施名称”非空为准过滤
        if "设施名称" in df.columns:
            df = df[df["设施名称"].notna()]
        df = df.copy()

        # 映射：当前表格 15 列 -> 样表字段（能找到就填，找不到留空）
        col_map = {
            "分公司": "分公司",
            "作业公司": "作业公司",
            "设施名称": "设施名称",
            "投产时间": "投产时间",
            "设计年限": "设计年限",
            "建造总操作重量,(MT)": "上部组块操作重量(t)",
            # 其余列暂留空：后续你给我口径/字段名再补齐
        }

        def fmt(v) -> str:
            if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
                return ""
            # 时间
            if hasattr(v, "strftime"):
                return v.strftime("%Y-%m-%d")
            return str(v)

        out_cols = self._columns()
        rows: List[List[str]] = []
        for i, (_, r) in enumerate(df.iterrows(), start=1):
            rd: Dict[str, Any] = r.to_dict()
            out_row = []
            for out_col in out_cols:
                if out_col == "序号":
                    out_row.append(str(i))
                    continue
                src = col_map.get(out_col)
                out_row.append(fmt(rd.get(src)) if src else "")
            rows.append(out_row)

        self._apply_data(rows)

    def _apply_data(self, rows: List[List[str]]):
        header_rows = self.HEADER_ROWS
        total_rows = header_rows + len(rows)

        self.table.setRowCount(total_rows)

        # 设置数据行行高
        for rr in range(header_rows, total_rows):
            self.table.setRowHeight(rr, 48)

        # 写入数据
        for i, row in enumerate(rows):
            rr = i + header_rows
            for c, val in enumerate(row):
                it = self._mk_item(val, editable=c >= self.EDITABLE_DATA_START_COL)
                self.table.setItem(rr, c, it)

        # # 行数多时：不强制无限增高，避免卡顿；行数少时：自动扩展更像“表格自然增长”
        # data_n = len(rows)
        # if data_n <= self.MAX_EXPAND_ROWS:
        #     self._fit_table_height_expand_all()
        #     self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # else:
        #     self._fit_table_height_reasonable()
        #     self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.table.setMinimumHeight(0)
        self.table.setMaximumHeight(16777215)

        self._apply_stable_column_widths()

    def _fit_table_height_expand_all(self):
        h = 0
        for r in range(self.table.rowCount()):
            h += self.table.rowHeight(r)
        h += 12
        self.table.setMinimumHeight(h)

    def _fit_table_height_reasonable(self):
        # 两行表头 + 12行数据左右（可按需要调大/调小）
        header_h = self.table.rowHeight(0) + self.table.rowHeight(1)
        data_rows_show = 12
        data_h = data_rows_show * 48
        self.table.setMinimumHeight(header_h + data_h + 20)

    # ---------- actions ----------
    def _on_save(self):
        rows = self._collect_data_rows()
        if not rows:
            QMessageBox.information(self, "保存", "当前无汇总数据可保存。")
            return
        try:
            result = save_platform_load_summary_snapshot(
                rows,
                snapshot_key="latest",
                snapshot_name="载荷汇总信息",
            )
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"保存载荷汇总信息失败：\n{exc}")
            return
        QMessageBox.information(
            self,
            "保存成功",
            f"已保存当前载荷汇总信息，共 {result.get('row_count', len(rows))} 条记录。",
        )

    def _collect_data_rows(self) -> List[Dict[str, str]]:
        header = self._columns()
        header_rows = 2
        rows: List[Dict[str, str]] = []
        for r in range(header_rows, self.table.rowCount()):
            values: Dict[str, str] = {}
            has_content = False
            for c, name in enumerate(header):
                item = self.table.item(r, c)
                text = item.text() if item else ""
                values[name] = text
                if text.strip():
                    has_content = True
            if has_content:
                rows.append(values)
        return rows

    def _on_export(self):
        header = self._columns()

        data = self._collect_data_rows()
        if not data:
            QMessageBox.information(self, "导出数据", "当前无数据可导出。")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出载荷汇总信息",
            "载荷汇总信息.xlsx",
            "Excel 文件 (*.xlsx)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"

        rows = [[row.get(name, "") for name in header] for row in data]

        try:
            pd.DataFrame(rows, columns=header).to_excel(file_path, index=False)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"写入 Excel 失败：\n{exc}")
            return

        self._show_exported_file(file_path)

    def _show_exported_file(self, file_path: str):
        normalized = os.path.normpath(file_path)
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer.exe", f"/select,{normalized}"])
                self._raise_explorer_window()
            else:
                folder = os.path.dirname(normalized) or "."
                if sys.platform == "darwin":
                    subprocess.Popen(["open", folder])
                else:
                    subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    def _raise_explorer_window(self):
        if not sys.platform.startswith("win"):
            return

        def _activate():
            try:
                user32 = ctypes.windll.user32
                handles = []

                @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                def enum_proc(hwnd, _lparam):
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    class_name = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_name, 256)
                    if class_name.value in ("CabinetWClass", "ExploreWClass"):
                        handles.append(hwnd)
                    return True

                user32.EnumWindows(enum_proc, 0)
                if handles:
                    hwnd = handles[-1]
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        QTimer.singleShot(400, _activate)
