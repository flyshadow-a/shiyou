# -*- coding: utf-8 -*-
# pages/summary_information_table_page.py
import csv
import os
from typing import List, Dict, Any

import pandas as pd

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QScrollArea, QMessageBox,
    QHeaderView, QToolTip
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QColor, QFontMetrics

from pages.hover_tip_table import HoverTipTable
from base_page import BasePage



class SummaryInformationTablePage(BasePage):
    """
    载荷信息管理 - 汇总信息表（示例页面）
    - 合并表头：使用“表格内部两行表头 + setSpan()”
    - 表头样式统一：补齐表头两行所有格子的背景与边框
    - 表格自适应窗口：列宽 Stretch，随窗口缩放
    - 示例数据导入：
        * 默认读取 data/summary_information_table_demo.csv
        * 若不存在，会自动生成一份模拟数据（30行）
    - 行数很多时的展示策略：
        * 行数 <= 50：表格高度自动扩展（外层 QScrollArea 滚动）
        * 行数 > 50：表格保持合理高度（表格内部滚动更流畅）
    """

    EXCEL_NAME = "平台汇总信息样表.xls"
    MAX_EXPAND_ROWS = 50

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.data_dir = os.path.join(os.getcwd(), "data")
        self._build_ui()
        self.load_from_excel(self._default_excel_path())

    def _build_ui(self):
        # 更贴近示例图：浅蓝灰底、细边框、表头同色
        self.setStyleSheet("""
            QWidget { background: #e6eef7; }

            QPushButton {
                background: #e8eef7;
                border: 1px solid #2f3a4a;
                border-radius: 4px;
                padding: 4px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background: #ffffff; }

            QTableWidget {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
                border: 1px solid #2f3a4a;
            }
            QTableWidget::item {
                border-bottom: 1px solid #d0d0d0;
                border-right:  1px solid #d0d0d0;
            }
            QTableWidget::item:selected { background-color: #dbe9ff; color: #000000; }
            QTableWidget::item:focus { outline: none; }
        """)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.main_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # 顶部操作条（右上角按钮）
        top_bar = QHBoxLayout()
        top_bar.addStretch(1)

        self.btn_save = QPushButton("保存")
        self.btn_export = QPushButton("导出数据")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_export.clicked.connect(self._on_export)

        top_bar.addWidget(self.btn_save)
        top_bar.addWidget(self.btn_export)
        root.addLayout(top_bar)

        # 主表格（先只建表头；数据通过 load_from_csv 导入）
        self.table = self._build_table_skeleton()
        root.addWidget(self.table, 1)

        # 填表说明
        note = QLabel(
            "填表说明\n"
            "1、变化总重=变化量×重心；变化率、重心、桩基承载力安全系数、是否整体评估：每年更新一次，填写最新数据。\n"
            "2、变化量=变化总重/建造总操作重量。\n"
            f"（数据来源：平台汇总信息样表.xls；本页从样表筛选字段并映射到当前表格列）"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#111827; font-size:12px; padding:6px;")
        root.addWidget(note, 0)

    # ---------- merged header helpers ----------
    def _mk_item(self, text: str, *, bold: bool = False, bg: QColor | None = None, fg: QColor | None = None) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setTextAlignment(Qt.AlignCenter)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)
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
            "作业单元",
            "设施名称",
            "投产时间",
            "设计年限",
            "建造总操作重量,MT",
            "变化总重量,MT",
            "变化率,%",
            "不可超载重量,MT",
            "重心,m",
            "重心不可超载半径,m",
            "桩基承载力安全系数(最小)-操作",
            "桩基承载力安全系数(最小)-极端",
            "整体评估次数",
        ]

    def _build_table_skeleton(self) -> QTableWidget:
        cols = self._columns()
        header_rows = 2

        table = HoverTipTable(header_rows, len(cols))
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)  # 用表内两行表头模拟合并表头

        # ✅ 列宽自适应窗口：Stretch
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # 行高：两行表头（接近截图）
        table.setRowHeight(0, 34)  # 分组表头
        table.setRowHeight(1, 54)  # 子表头

        # 表头背景（浅蓝灰）
        bg_header = QColor("#eef2ff")
        bg_group = QColor("#eef2ff")

        # ---- 纵向合并：0-5 & 15（跨两行表头）----
        for c in list(range(0, 6)) + [15]:
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
        table.setItem(0, 12, self._mk_item("桩基承载力\n安全系数\n（最小）", bold=True, bg=bg_group))
        table.setItem(1, 12, self._mk_item("操作", bold=True, bg=bg_header))
        table.setItem(1, 13, self._mk_item("极端", bold=True, bg=bg_header))

        table.setSpan(0,14,2,1)
        table.setItem(0,14,self._mk_item("整体评估次数", bold=True, bg=bg_header))
        # ✅ 补齐表头两行背景（样式完全一致）
        self._fill_bg_for_row(table, 0, bg_group)
        self._fill_bg_for_row(table, 1, bg_header)

        return table

    def _header_label_for_col(self, c: int) -> str:
        # 对应截图中换行表头
        labels = {
            0: "序号",
            1: "分公司",
            2: "作业单元",
            3: "设施名称",
            4: "投产时间",
            5: "设计年限",
            6: "建造总操作\n重量,MT",
            7: "变化总重\n量,MT·m",
            8: "变化率,%",
            9: "不可超载\n重量,MT",
            10: "重心,m",
            11: "重心不可超\n载半径,m",
            14: "整体评估\n次数",
        }
        return labels.get(c, "")

    # ---------- data import ----------
    def _default_excel_path(self) -> str:
        """默认从 data/平台汇总信息样表.xls 读取；若不存在，尝试从当前工作目录读取同名文件。"""
        p1 = os.path.join(self.data_dir, self.EXCEL_NAME)
        if os.path.exists(p1):
            return p1
        p2 = os.path.join(os.getcwd(), self.EXCEL_NAME)
        if os.path.exists(p2):
            return p2
        return p1  # 默认返回 data 路径（用于报错提示）

    def load_from_excel(self, excel_path: str):
        """
        从“平台汇总信息样表.xls”导入数据，并筛选/映射到当前表格 16 列（表格设计不变）。
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
            "作业单元": "作业公司",
            "设施名称": "设施名称",
            "投产时间": "投产时间",
            "设计年限": "设计年限",
            "建造总操作重量,MT": "上部组块操作重量(t)",
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
        header_rows = 2
        total_rows = header_rows + len(rows)

        self.table.setRowCount(total_rows)

        # 设置数据行行高
        for rr in range(header_rows, total_rows):
            self.table.setRowHeight(rr, 48)

        # 写入数据
        green = QColor(0, 170, 0)
        for i, row in enumerate(rows):
            rr = i + header_rows
            for c, val in enumerate(row):
                it = self._mk_item(val)
                if i == 0 and val:
                    it.setForeground(green)
                self.table.setItem(rr, c, it)

        # 行数多时：不强制无限增高，避免卡顿；行数少时：自动扩展更像“表格自然增长”
        data_n = len(rows)
        if data_n <= self.MAX_EXPAND_ROWS:
            self._fit_table_height_expand_all()
            self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self._fit_table_height_reasonable()
            self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

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
        QMessageBox.information(self, "保存", "示例：保存当前汇总信息表（后续接真实存储逻辑）。")

    def _on_export(self):
        # 导出当前表格（不含两行表头的“合并表头行”，仅导出数据）
        export_path = os.path.join(self.data_dir, "summary_information_table_export.csv")
        header = self._columns()

        header_rows = 2
        data_rows = self.table.rowCount() - header_rows
        if data_rows <= 0:
            QMessageBox.information(self, "导出数据", "当前无数据可导出。")
            return

        with open(export_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in range(header_rows, self.table.rowCount()):
                row = []
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    row.append(it.text() if it else "")
                w.writerow(row)

        QMessageBox.information(self, "导出数据", f"已导出：{export_path}")