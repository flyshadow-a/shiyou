# -*- coding: utf-8 -*-
# pages/oilfield_water_level_page.py

from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QStackedWidget, QWidget, QLabel
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

        # 子页 1：水深水位
        water_page = self.build_water_level_page()
        # 子页 2：风参数
        wind_page = self.build_wind_param_page()
        # 子页 3：波浪参数
        wave_page = self.build_wave_param_page()
        # 子页 4：海流参数
        current_page = self.build_current_param_page()

        self.tab_pages.addWidget(water_page)
        self.tab_pages.addWidget(wind_page)
        self.tab_pages.addWidget(wave_page)
        self.tab_pages.addWidget(current_page)

        self.main_layout.addWidget(self.tab_pages)

        # 绑定按钮切换逻辑
        for index, btn in enumerate(self.tab_buttons):
            btn.clicked.connect(lambda checked, i=index: self.switch_tab(i))

        # 默认选中第一个
        self.switch_tab(0)

    # ----------------- 子页构建 ----------------- #
    def build_water_level_page(self) -> QWidget:
        """
        水深水位子页：使用表格展示固定的水位信息。
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

        table = QTableWidget(10, 3, frame)
        table.setHorizontalHeaderLabels(["", "元素", "相对海图基准面 (m)"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #cccccc;
                background-color: #ffffff;
            }
        """)

        data = [
            ("最高水位", "海图基准面 (CD)", "0.00"),
            ("", "最高天文潮 (HAT)", "2.55"),
            ("", "最低天文潮 (LAT)", "0.00"),
            ("", "平均海平面 (MSL)", "1.20"),
            ("最高水位", "1年回归周期", "2.68"),
            ("", "50年回归周期", "2.91"),
            ("", "100年回归周期", "2.96"),
            ("", "1000年回归周期", "3.16"),
            ("最低水位", "1年回归周期", "-0.14"),
            ("", "1000年回归周期", "-0.55"),
        ]

        for row, (c0, c1, c2) in enumerate(data):
            table.setItem(row, 0, QTableWidgetItem(c0))
            table.setItem(row, 1, QTableWidgetItem(c1))
            table.setItem(row, 2, QTableWidgetItem(c2))

        table.resizeColumnsToContents()

        frame_layout.addWidget(table)
        layout.addWidget(frame)

        return page

    def build_wind_param_page(self) -> QWidget:
        """
        风参数子页：可以根据实际需求改成表格或表单。
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        lbl = QLabel("风参数配置页面，可在此录入或维护风速、风向等设计参数。")
        lbl.setWordWrap(True)

        layout.addWidget(lbl)
        layout.addStretch()

        return page

    def build_wave_param_page(self) -> QWidget:
        """
        波浪参数子页。
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        lbl = QLabel("波浪参数配置页面，可在此维护有效波高、周期等设计参数。")
        lbl.setWordWrap(True)

        layout.addWidget(lbl)
        layout.addStretch()

        return page

    def build_current_param_page(self) -> QWidget:
        """
        海流参数子页。
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        lbl = QLabel("海流参数配置页面，可在此录入流速、流向等设计参数。")
        lbl.setWordWrap(True)

        layout.addWidget(lbl)
        layout.addStretch()

        return page

    # ----------------- 选项卡切换逻辑 ----------------- #
    def switch_tab(self, index: int):
        """
        切换顶部选项卡，同时调整按钮选中状态。
        """
        for i, btn in enumerate(self.tab_buttons):
            btn.setChecked(i == index)
        self.tab_pages.setCurrentIndex(index)
