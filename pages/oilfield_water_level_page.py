# -*- coding: utf-8 -*-
# pages/oilfield_water_level_page.py

from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QStackedWidget, QWidget, QLabel, QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt
from base_page import BasePage


class OilfieldWaterLevelPage(BasePage):
    """
    油气田信息页面：
    - 顶部：分公司 / 作业公司 / 油气田 下拉选择 + 保存按钮
    - 中部：水深水位、风参数、波浪参数、海流参数 四个子页
            用按钮模拟选项卡 + 内部 QStackedWidget 切换
    """
    def __init__(self, parent=None):
        super().__init__("油气田信息", parent)
        self.tab_buttons = []
        self.tab_pages = None
        self.build_ui()

    def build_ui(self):
        # 顶部筛选条
        top_bar = QFrame()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(10)

        cb_division = QComboBox()
        cb_division.addItems(["渤江分公司", "南海分公司", "东海分公司"])

        cb_company = QComboBox()
        cb_company.addItems(["文昌油田群作业公司", "测试作业公司"])

        cb_field = QComboBox()
        cb_field.addItems(["文昌19-1油田", "文昌X油田"])

        btn_save = QPushButton("保存")

        top_bar_layout.addWidget(cb_division)
        top_bar_layout.addWidget(cb_company)
        top_bar_layout.addWidget(cb_field)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(btn_save)

        self.main_layout.addWidget(top_bar)

        # 选项卡按钮条
        tab_bar = QFrame()
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        def create_tab_button(text: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setMinimumHeight(36)
            btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #888;
                    border-bottom: none;
                    padding: 6px 18px;
                    background-color: #f0f0f0;
                }
                QPushButton:checked {
                    background-color: #ffffff;
                    font-weight: bold;
                }
            """)
            return btn

        btn_water = create_tab_button("水深水位")
        btn_wind = create_tab_button("风参数")
        btn_wave = create_tab_button("波浪参数")
        btn_current = create_tab_button("海流参数")

        self.tab_buttons = [btn_water, btn_wind, btn_wave, btn_current]

        for btn in self.tab_buttons:
            tab_layout.addWidget(btn)
        tab_layout.addStretch()

        self.main_layout.addWidget(tab_bar)

        # 选项卡内容区域
        self.tab_pages = QStackedWidget()

        water_page = self.build_water_level_page()
        wind_page = self.build_wind_param_page()
        wave_page = self.build_wave_param_page()
        current_page = self.build_current_param_page()

        self.tab_pages.addWidget(water_page)
        self.tab_pages.addWidget(wind_page)
        self.tab_pages.addWidget(wave_page)
        self.tab_pages.addWidget(current_page)

        self.main_layout.addWidget(self.tab_pages)

        for index, btn in enumerate(self.tab_buttons):
            btn.clicked.connect(lambda checked, i=index: self.switch_tab(i))

        self.switch_tab(0)

    # ---------- 小工具：设置单元格 ----------
    def _set_item(self, table: QTableWidget, r: int, c: int, text: str,
                  align=Qt.AlignCenter, bold: bool = False):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(align)
        if bold:
            f = item.font()
            f.setBold(True)
            item.setFont(f)
        table.setItem(r, c, item)

    def _finalize_table_style(self, table: QTableWidget):
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)  # ✅ 关键：去掉顶部 1..n
        table.setCornerButtonEnabled(False)

        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setShowGrid(True)

        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d9d9d9;
                background-color: #ffffff;
            }
            QTableWidget::item {
                border: 1px solid #ffffff;
        }
        """)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def _fit_table_height(self, table: QTableWidget):
        # 固定高度：刚好容纳所有行，避免滚动条
        total_h = table.frameWidth() * 2 + 2
        for r in range(table.rowCount()):
            total_h += table.rowHeight(r)
        table.setFixedHeight(total_h)

    # ----------------- 子页构建 ----------------- #
    def build_water_level_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)  # ✅ 顶对齐，避免上方留空

        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #cfd8e3; }")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        frame_layout.setAlignment(Qt.AlignTop)  # ✅ 顶对齐

        # 2行表头 + 12行数据 = 14行，3列：分组 | 元素 | 值
        table = QTableWidget(14, 3, frame)
        self._finalize_table_style(table)

        # 行高
        for r in range(table.rowCount()):
            table.setRowHeight(r, 34)
        table.setRowHeight(0, 40)
        table.setRowHeight(1, 36)

        # ===== 表头（合并）=====
        # 左侧“元素”跨2行2列（0-1行，0-1列）
        table.setSpan(0, 0, 2, 2)
        self._set_item(table, 0, 0, "元素", bold=True)

        # 右侧表头：相对海图基准面 + 单位m
        self._set_item(table, 0, 2, "相对海图基准面", bold=True)
        self._set_item(table, 1, 2, "m", bold=True)

        # ===== 基础元素 4 行（行2~5）=====
        base_rows = [
            ("海图基准面 (CD)", "0.00"),
            ("最高天文潮 (HAT)", "2.55"),
            ("最低天文潮 (LAT)", "0.00"),
            ("平均海平面 (MSL)", "1.20"),
        ]
        start = 2
        for i, (elem, val) in enumerate(base_rows):
            rr = start + i
            self._set_item(table, rr, 0, "")  # 分组列留空
            self._set_item(table, rr, 1, elem, align=Qt.AlignCenter)
            self._set_item(table, rr, 2, val)

        # ===== 最高水位（行6~9）=====
        table.setSpan(6, 0, 4, 1)
        self._set_item(table, 6, 0, "最高水位")

        high_rows = [
            ("1年回归周期", "2.68"),
            ("50年回归周期", "2.91"),
            ("100年回归周期", "2.96"),
            ("1000年回归周期", "3.16"),
        ]
        for i, (elem, val) in enumerate(high_rows):
            rr = 6 + i
            self._set_item(table, rr, 1, elem)
            self._set_item(table, rr, 2, val)

        # ===== 最低水位（行10~13）=====
        table.setSpan(10, 0, 4, 1)
        self._set_item(table, 10, 0, "最低水位")

        low_rows = [
            ("1年回归周期", "-0.14"),
            ("50年回归周期", "-0.43"),
            ("100年回归周期", "-0.49"),
            ("1000年回归周期", "-0.55"),
        ]
        for i, (elem, val) in enumerate(low_rows):
            rr = 10 + i
            self._set_item(table, rr, 1, elem)
            self._set_item(table, rr, 2, val)

        # 列宽：分组列适中，元素列拉伸，值列固定
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        table.setColumnWidth(0, 160)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        table.setColumnWidth(2, 220)

        # 固定表格高度避免滚动
        self._fit_table_height(table)

        # ✅ 强制顶贴
        frame_layout.addWidget(table, 0, Qt.AlignTop)
        layout.addWidget(frame, 0, Qt.AlignTop)
        return page

    def build_wind_param_page(self) -> QWidget:
        """
        风参数子页：表格 + 数据（风速@10m）。
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #888; }")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # 结构：标题行 + 表头两行 + 12行数据 = 15 行
        # 列：组别 | 时长 | 1 | 10 | 25 | 50 | 100 = 7 列
        table = QTableWidget(15, 7, frame)
        self._finalize_table_style(table)

        # 行高（你可按审美调）
        for r in range(table.rowCount()):
            table.setRowHeight(r, 32)
        table.setRowHeight(0, 34)
        table.setRowHeight(1, 32)
        table.setRowHeight(2, 32)

        # 顶部标题（跨全列）
        table.setSpan(0, 0, 1, 7)
        self._set_item(table, 0, 0, "风速 @10m (m/s)", bold=True)

        # 表头：左侧“元素”跨两列两行；右侧“回归周期(年)”跨5列
        table.setSpan(1, 0, 2, 2)
        self._set_item(table, 1, 0, "元素", bold=True)

        table.setSpan(1, 2, 1, 5)
        self._set_item(table, 1, 2, "回归周期 (年)", bold=True)

        periods = ["1", "10", "25", "50", "100"]
        for i, p in enumerate(periods):
            self._set_item(table, 2, 2 + i, p, bold=True)

        # 数据
        groups = [
            ("主极值", [
                ("1 h",   ["30.3", "35.5", "39.1", "41.3", "43.4"]),
                ("10 min",["33.4", "39.5", "43.7", "46.4", "48.9"]),
                ("1 min", ["37.4", "44.6", "49.6", "52.9", "55.9"]),
                ("3 s",   ["42.5", "51.2", "57.4", "61.4", "65.1"]),
            ]),
            ("波浪主极值下条件极值", [
                ("1 h",   ["28.4", "33.5", "37.2", "39.6", "41.8"]),
                ("10 min",["31.2", "37.2", "41.5", "44.5", "47"]),
                ("1 min", ["34.9", "42.1", "47.1", "50.8", "53.9"]),
                ("3 s",   ["39.8", "48.3", "54.5", "58.9", "62.7"]),
            ]),
            ("海流主极值下条件极值", [
                ("1 h",   ["29", "33.8", "36.7", "38.6", "40.2"]),
                ("10 min",["32", "37.5", "41.1", "43.4", "45.2"]),
                ("1 min", ["35.6", "42.4", "46.7", "49.5", "51.8"]),
                ("3 s",   ["40.6", "48.7", "54", "57.4", "60.3"]),
            ]),
        ]

        r0 = 3
        for gname, rows in groups:
            table.setSpan(r0, 0, len(rows), 1)
            self._set_item(table, r0, 0, gname)

            for k, (dur, vals) in enumerate(rows):
                rr = r0 + k
                self._set_item(table, rr, 1, dur)
                for j, v in enumerate(vals):
                    self._set_item(table, rr, 2 + j, v)
            r0 += len(rows)

        # 列宽策略
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 左侧“主极值/条件极值”
        header.setSectionResizeMode(1, QHeaderView.Fixed)  # ✅ 元素列别拉太宽
        table.setColumnWidth(1, 260)  # ✅ 这里调元素列宽度(240~320都行)

        for c in range(2, 7):
            header.setSectionResizeMode(c, QHeaderView.Stretch)  # ✅ 数值列均分填满

        self._fit_table_height(table)

        # ✅ 加这两行：让布局顶对齐（防止上方留空）
        layout.setAlignment(Qt.AlignTop)
        frame_layout.setAlignment(Qt.AlignTop)

        # ✅ 把 addWidget 改成带 AlignTop 的版本
        layout.setAlignment(Qt.AlignTop)
        frame_layout.setAlignment(Qt.AlignTop)

        layout.setAlignment(Qt.AlignTop)
        frame_layout.setAlignment(Qt.AlignTop)

        frame_layout.addWidget(table, 0, Qt.AlignTop)
        layout.addWidget(frame, 0, Qt.AlignTop)

        return page

    def build_wave_param_page(self) -> QWidget:
        """
        波浪参数子页：表格 + 数据。
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #888; }")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # 标题行 + 表头两行 + 16行数据 = 19行
        # 列：组别 | 元素 | 1 | 10 | 25 | 50 | 100 = 7 列
        table = QTableWidget(19, 7, frame)
        self._finalize_table_style(table)

        for r in range(table.rowCount()):
            table.setRowHeight(r, 32)
        table.setRowHeight(0, 34)

        table.setSpan(0, 0, 1, 7)
        self._set_item(table, 0, 0, "波浪参数", bold=True)

        table.setSpan(1, 0, 2, 2)
        self._set_item(table, 1, 0, "元素", bold=True)

        table.setSpan(1, 2, 1, 5)
        self._set_item(table, 1, 2, "回归周期 (年)", bold=True)

        periods = ["1", "10", "25", "50", "100"]
        for i, p in enumerate(periods):
            self._set_item(table, 2, 2 + i, p, bold=True)

        groups = [
            ("主极值", [
                ("有义波高 Hs(m)",   ["7.3", "10", "11.2", "12", "12.8"]),
                ("波峰高度 Crest(m)",["8", "11", "12.4", "13.2", "14"]),
                ("最大波高 Hmax(m)", ["12.5", "17.2", "19.3", "20.7", "21.9"]),
                ("跨零周期 Tz(s)",   ["9.3", "10.6", "11.1", "11.4", "11.7"]),
                ("谱峰周期 Tp(s)",   ["12", "13.5", "14", "14.4", "14.8"]),
                ("平均周期 Tm(s)",   ["11.8", "13.5", "14.1", "14.5", "14.9"]),
            ]),
            ("风主极值条件下极值", [
                ("有义波高 Hs(m)",   ["6.5", "9.2", "10.6", "11.7", "12.5"]),
                ("最大波高 Hmax(m)", ["11.2", "15.8", "18.2", "20.2", "21.5"]),
                ("跨零周期 Tz(s)",   ["8.8", "10.2", "10.8", "11.3", "11.6"]),
                ("谱峰周期 Tp(s)",   ["11.5", "13.1", "13.8", "14.3", "14.6"]),
                ("平均周期 Tm(s)",   ["11.2", "13", "13.7", "14.3", "14.7"]),
            ]),
            ("海流主极值条件下极值", [
                ("有义波高 Hs(m)",   ["6.6", "9.2", "10.4", "11.6", "12.2"]),
                ("最大波高 Hmax(m)", ["11.4", "15.8", "17.8", "20", "21"]),
                ("跨零周期 Tz(s)",   ["8.9", "10.2", "10.7", "11.2", "11.5"]),
                ("谱峰周期 Tp(s)",   ["11.5", "13.1", "13.7", "14.2", "14.5"]),
                ("平均周期 Tm(s)",   ["11.3", "13", "13.6", "14.2", "14.5"]),
            ]),
        ]

        r0 = 3
        for gname, rows in groups:
            table.setSpan(r0, 0, len(rows), 1)
            self._set_item(table, r0, 0, gname)

            for k, (elem, vals) in enumerate(rows):
                rr = r0 + k
                self._set_item(table, rr, 1, elem, align=Qt.AlignLeft | Qt.AlignVCenter)
                for j, v in enumerate(vals):
                    self._set_item(table, rr, 2 + j, v)
            r0 += len(rows)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 左侧分组
        header.setSectionResizeMode(1, QHeaderView.Fixed)  # ✅ “表层/中层/底层/+1m@ASB”列固定
        table.setColumnWidth(1, 260)  # ✅ 这里调分层列宽度

        for c in range(2, 7):
            header.setSectionResizeMode(c, QHeaderView.Stretch)  # ✅ 数值列均分

        self._fit_table_height(table)

        layout.setAlignment(Qt.AlignTop)
        frame_layout.setAlignment(Qt.AlignTop)

        frame_layout.addWidget(table, 0, Qt.AlignTop)
        layout.addWidget(frame, 0, Qt.AlignTop)

        return page

    def build_current_param_page(self) -> QWidget:
        """
        海流参数子页：表格 + 数据（海流速度）。
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #888; }")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # 标题行 + 表头两行 + 12行数据 = 15行
        # 列：组别 | 分层 | 1 | 10 | 25 | 50 | 100
        table = QTableWidget(15, 7, frame)
        self._finalize_table_style(table)

        for r in range(table.rowCount()):
            table.setRowHeight(r, 32)
        table.setRowHeight(0, 34)

        table.setSpan(0, 0, 1, 7)
        self._set_item(table, 0, 0, "海流速度（m/s）", bold=True)

        table.setSpan(1, 0, 2, 2)
        self._set_item(table, 1, 0, "元素", bold=True)

        table.setSpan(1, 2, 1, 5)
        self._set_item(table, 1, 2, "回归周期 (年)", bold=True)

        periods = ["1", "10", "25", "50", "100"]
        for i, p in enumerate(periods):
            self._set_item(table, 2, 2 + i, p, bold=True)

        groups = [
            ("主极值", [
                ("表层 (0.1倍水深)", ["124", "174", "200", "218", "236"]),
                ("中层 (0.5倍水深)", ["100", "140", "161", "175", "192"]),
                ("底层 (0.9倍水深)", ["55", "77", "89", "97", "107"]),
                ("+1m@ASB",          ["53", "74", "81", "88", "96"]),
            ]),
            ("风主极值条件下极值", [
                ("表层 (0.1倍水深)", ["114", "158", "184", "201", "221"]),
                ("中层 (0.5倍水深)", ["92", "124", "141", "151", "163"]),
                ("底层 (0.9倍水深)", ["46", "69", "77", "80", "86"]),
                ("+1m@ASB",          ["45", "64", "70", "76", "83"]),
            ]),
            ("波浪主极值条件下极值", [
                ("表层 (0.1倍水深)", ["117", "158", "182", "199", "217"]),
                ("中层 (0.5倍水深)", ["92", "127", "143", "151", "161"]),
                ("底层 (0.9倍水深)", ["48", "69", "76", "79", "83"]),
                ("+1m@ASB",          ["45", "62", "68", "74", "81"]),
            ]),
        ]

        r0 = 3
        for gname, rows in groups:
            table.setSpan(r0, 0, len(rows), 1)
            self._set_item(table, r0, 0, gname)

            for k, (layer, vals) in enumerate(rows):
                rr = r0 + k
                self._set_item(table, rr, 1, layer, align=Qt.AlignLeft | Qt.AlignVCenter)
                for j, v in enumerate(vals):
                    self._set_item(table, rr, 2 + j, v)
            r0 += len(rows)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for c in range(2, 7):
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)

        self._fit_table_height(table)

        layout.setAlignment(Qt.AlignTop)
        frame_layout.setAlignment(Qt.AlignTop)

        frame_layout.addWidget(table, 0, Qt.AlignTop)
        layout.addWidget(frame, 0, Qt.AlignTop)

        return page

    # ----------------- 选项卡切换逻辑 ----------------- #
    def switch_tab(self, index: int):
        """
        切换顶部选项卡，同时调整按钮选中状态。
        """
        for i, btn in enumerate(self.tab_buttons):
            btn.setChecked(i == index)
        self.tab_pages.setCurrentIndex(index)
