# -*- coding: utf-8 -*-
# pages/summary_information_table_page.py

import os
import csv
import random
from typing import List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QScrollArea, QMessageBox,
    QHeaderView, QToolTip
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QColor, QFontMetrics

from base_page import BasePage


class HoverTipTable(QTableWidget):
    """
    只在“内容显示不全（被截断）”时显示 Tooltip 的表格。
    - 对每个单元格，比较文本宽度与单元格可用宽度
    - 只有超出才弹出 Tooltip（满足你的要求：所有显示不全的内容悬停可看全称）
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            pos = event.pos()
            item = self.itemAt(pos)
            if item is None:
                QToolTip.hideText()
                return True

            text = item.text()
            if not text:
                QToolTip.hideText()
                return True

            rect = self.visualItemRect(item)
            # 估算单元格可用宽度（减去一点 padding）
            avail = max(0, rect.width() - 10)

            fm = QFontMetrics(item.font())
            lines = text.splitlines() or [text]
            text_w = max(fm.horizontalAdvance(line) for line in lines)

            # ✅仅当文本宽度超过可用宽度时显示 Tooltip
            if text_w > avail:
                QToolTip.showText(event.globalPos(), text, self)
            else:
                QToolTip.hideText()
            return True

        return super().viewportEvent(event)


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

    DEMO_CSV_NAME = "summary_information_table_demo.csv"
    MAX_EXPAND_ROWS = 50

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.data_dir = os.path.join(os.getcwd(), "data")
        self._build_ui()
        self._ensure_demo_csv()
        self.load_from_csv(os.path.join(self.data_dir, self.DEMO_CSV_NAME))

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
            f"（示例数据文件：data/{self.DEMO_CSV_NAME}，可自行替换为真实数据）"
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
            "变化总重重心,MT·m",
            "变化率,%",
            "变化总重,MT",
            "不可超载重量,MT",
            "重心,m",
            "重心不可超载半径,m",
            "桩基承载力安全系数(最小)-操作",
            "桩基承载力安全系数(最小)-校验",
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

        # ---- 横向合并：上部组块重控（6~12）----
        table.setSpan(0, 6, 1, 7)
        table.setItem(0, 6, self._mk_item("上部组块重控", bold=True, bg=bg_group))

        # 子表头（6~12）
        for c in range(6, 13):
            table.setItem(1, c, self._mk_item(self._header_label_for_col(c), bold=True, bg=bg_header))

        # ---- 横向合并：桩基承载力安全系数（最小）（13~14）----
        table.setSpan(0, 13, 1, 2)
        table.setItem(0, 13, self._mk_item("桩基承载力\n安全系数\n（最小）", bold=True, bg=bg_group))
        table.setItem(1, 13, self._mk_item("操作", bold=True, bg=bg_header))
        table.setItem(1, 14, self._mk_item("校验", bold=True, bg=bg_header))

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
            7: "变化总重\n重心,MT·m",
            8: "变化率,%",
            9: "变化总\n重,MT",
            10: "不可超载\n重量,MT",
            11: "重心,m",
            12: "重心不可超\n载半径,m",
            15: "整体评估\n次数",
        }
        return labels.get(c, "")

    # ---------- data import ----------
    def load_from_csv(self, csv_path: str):
        """
        从 CSV 导入数据。CSV 需包含 16 列（允许有表头）。
        """
        if not os.path.exists(csv_path):
            QMessageBox.warning(self, "提示", f"未找到数据文件：{csv_path}")
            return

        rows: List[List[str]] = []
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            all_rows = list(reader)

        if not all_rows:
            return

        start_idx = 0
        if all_rows[0] and "序号" in all_rows[0][0]:
            start_idx = 1

        for r in all_rows[start_idx:]:
            if not r:
                continue
            r = (r + [""] * 16)[:16]
            rows.append([str(x) for x in r])

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

    # ---------- demo data ----------
    def _ensure_demo_csv(self):
        os.makedirs(self.data_dir, exist_ok=True)
        demo_path = os.path.join(self.data_dir, self.DEMO_CSV_NAME)
        if os.path.exists(demo_path):
            return

        rows = self._generate_mock_rows(n=30, seed=202501)
        header = self._columns()

        with open(demo_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    def _generate_mock_rows(self, n: int = 30, seed: int = 0) -> List[List[str]]:
        rnd = random.Random(seed)

        companies = ["湛江分公司", "深圳分公司", "上海分公司", "海南分公司", "天津分公司"]
        units = ["涠洲作业公司", "文昌作业公司", "珠江作业公司", "渤海作业公司"]
        facilities = ["WC19-1WHPC", "WC19-2WHPC", "WC19-3WHPC", "WC9-7DPP", "WC19-1DPPA"]

        rows: List[List[str]] = []
        for i in range(1, n + 1):
            comp = rnd.choice(companies)
            unit = rnd.choice(units)
            fac = rnd.choice(facilities)
            # 故意做长一点，方便你验证“悬停显示全称”
            fac_name = f"{fac}井口平台-上部组块载荷汇总信息示例（第{i}条）"

            year = rnd.randint(2004, 2016)
            month = rnd.randint(1, 12)
            day = rnd.randint(1, 28)
            start_date = f"{year:04d}-{month:02d}-{day:02d}"
            design_life = rnd.choice([15, 20, 25, 30])

            base_weight = rnd.randint(5500, 18000)  # MT
            cog = rnd.uniform(8.0, 26.0)  # m
            change_weight = rnd.uniform(30, 260)  # MT
            change_cog = change_weight * cog  # MT·m
            change_rate = (change_weight / base_weight) * 100.0

            no_over = base_weight * rnd.uniform(0.80, 0.95)
            radius = rnd.uniform(6.0, 18.0)
            sf_op = rnd.uniform(1.10, 2.60)
            sf_chk = rnd.uniform(1.10, 2.60)
            eval_cnt = rnd.randint(0, 5)

            rows.append([
                str(i),
                comp,
                unit,
                fac_name,
                start_date,
                str(design_life),
                f"{base_weight:.0f}",
                f"{change_cog:.2f}",
                f"{change_rate:.2f}",
                f"{change_weight:.2f}",
                f"{no_over:.2f}",
                f"{cog:.2f}",
                f"{radius:.2f}",
                f"{sf_op:.2f}",
                f"{sf_chk:.2f}",
                str(eval_cnt),
            ])
        return rows

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