# -*- coding: utf-8 -*-
# pages/platform_structure_info_page.py

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
    QToolButton,
    QMenu,
    QStackedWidget,
    QSizePolicy,
)

from base_page import BasePage
from dropdown_bar import DropdownBar


class PlatformStructureInfoPage(BasePage):
    """
    平台基本信息 -> 结构信息 页面

    顶部：复用 DropdownBar 下拉条
    中部：
        - 上方：阶段切换按钮（新建竣工 / 第一次改造 / 第二次改造 / ...）
        - 下方：对应阶段的内容页：
            * 相关文件 表格
            * 载荷信息及评估结果 表格
            * 改造概述（一个大单元格表格）
    """

    def __init__(self, parent=None):
        super().__init__("结构信息", parent)
        self.phase_tables = {}  # {phase_name: {"files": table1, "load": table2, "remark": table3}}
        self.phase_buttons = {}
        self.phase_index_map = {"new": 0, "first": 1, "second": 2}
        self.current_phase = "new"
        self._build_ui()

    # ------------------------------------------------------------------
    # 通用表格工具
    # ------------------------------------------------------------------
    def _init_table_common(self, table: QTableWidget):
        """通用表格基础样式。"""
        table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)

        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                border-bottom: 1px solid #d0d0d0;
                border-right:  1px solid #d0d0d0;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                border: 0px;
                border-bottom: 1px solid #d0d0d0;
                border-right:  1px solid #d0d0d0;
                padding: 4px 8px;
            }
        """)

        hh = table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setHighlightSections(False)

        table.verticalHeader().setVisible(False)

    def _set_center_item(self, table: QTableWidget, row: int, col: int, text):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)

    def _auto_fit_columns_with_padding(self, table: QTableWidget, padding: int = 24):
        """
        让表格列宽适配【表头文字】宽度，并在此基础上加上一点 padding 像素。
        """
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        table.resizeColumnsToContents()

        fm = QFontMetrics(table.font())
        for col in range(table.columnCount()):
            head_item = table.horizontalHeaderItem(col)
            if head_item is None:
                continue
            text = head_item.text()
            text_width = fm.horizontalAdvance(text)
            base_width = max(table.columnWidth(col), text_width + padding)
            table.setColumnWidth(col, base_width)

        header.setSectionResizeMode(QHeaderView.Fixed)

    def _auto_fit_row_height(self, table: QTableWidget, padding: int = 10):
        """根据字体高度调整默认行高，额外增加一点 padding。"""
        fm = QFontMetrics(table.font())
        h = fm.height() + padding
        table.verticalHeader().setDefaultSectionSize(h)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        # 整体样式
        self.setStyleSheet("""
            QFrame#CardFrame {
                background-color: #f3f4f6;
                border-radius: 6px;
                border: 1px solid #d1d5db;
            }
            QGroupBox {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                margin-top: 18px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                background-color: transparent;
            }
            QPushButton.TabButton {
                background-color: #e5e7eb;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 4px 16px;
                font-size: 13px;
            }
            QPushButton.TabButton:checked {
                background-color: #0090d0;
                border-color: #007ab3;
                color: #ffffff;
            }
            QPushButton.TabButton:hover {
                background-color: #dbe3f0;
            }
            QToolButton#MoreButton {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 4px 10px;
                background-color: #e5e7eb;
            }
        """)

        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # ---------- 顶部下拉条 ----------
        fields = [
            {"key": "branch",         "label": "分公司",   "options": ["渤江分公司"],             "default": "渤江分公司"},
            {"key": "op_company",     "label": "作业公司", "options": ["文昌油田群作业公司"],     "default": "文昌油田群作业公司"},
            {"key": "oilfield",       "label": "油气田",   "options": ["文昌19-1油田"],          "default": "文昌19-1油田"},
            {"key": "facility_code",  "label": "设施编号", "options": ["WC19-1WHPC"],           "default": "WC19-1WHPC"},
            {"key": "facility_name",  "label": "设施名称", "options": ["文昌19-1WHPC井口平台"],   "default": "文昌19-1WHPC井口平台"},
            {"key": "facility_type",  "label": "设施类型", "options": ["平台"],                  "default": "平台"},
            {"key": "category",       "label": "分类",     "options": ["井口平台"],              "default": "井口平台"},
            {"key": "start_time",     "label": "投产时间", "options": ["2013-07-15"],           "default": "2013-07-15"},
            {"key": "design_life",    "label": "设计年限", "options": ["15"],                   "default": "15"},
        ]
        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        # ---------- 中部卡片 ----------
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 12)
        card_layout.setSpacing(10)

        # ---- 阶段切换按钮行 ----
        tab_bar = QHBoxLayout()
        tab_bar.setContentsMargins(0, 0, 0, 0)
        tab_bar.setSpacing(8)

        self.btn_phase_new = self._create_tab_button("新建竣工", "new", checked=True)
        self.btn_phase_1st = self._create_tab_button("第一次改造", "first", checked=False)
        self.btn_phase_2nd = self._create_tab_button("第二次改造", "second", checked=False)

        tab_bar.addWidget(self.btn_phase_new)
        tab_bar.addWidget(self.btn_phase_1st)
        tab_bar.addWidget(self.btn_phase_2nd)

        # 右侧的 “...” 更多按钮（弹出菜单即可）
        more_btn = QToolButton()
        more_btn.setObjectName("MoreButton")
        more_btn.setText("...")
        more_btn.setPopupMode(QToolButton.InstantPopup)
        more_menu = QMenu(more_btn)
        more_menu.addAction("新增改造阶段（占位）")
        more_menu.addAction("管理改造阶段（占位）")
        more_btn.setMenu(more_menu)

        tab_bar.addStretch()
        tab_bar.addWidget(more_btn)

        card_layout.addLayout(tab_bar)

        # ---- 阶段内容堆叠 ----
        self.phase_stack = QStackedWidget()
        self.phase_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout.addWidget(self.phase_stack, 1)

        # 三个阶段页面
        page_new = self._build_phase_page("新建竣工")
        page_1st = self._build_phase_page("第一次改造")
        page_2nd = self._build_phase_page("第二次改造")

        self.phase_stack.addWidget(page_new)
        self.phase_stack.addWidget(page_1st)
        self.phase_stack.addWidget(page_2nd)
        self.phase_stack.setCurrentIndex(0)

        self.main_layout.addWidget(card, 1)

    # ------------------------------------------------------------------
    # 阶段按钮 & 页面
    # ------------------------------------------------------------------
    def _create_tab_button(self, text: str, key: str, checked: bool) -> QPushButton:
        """创建一个阶段按钮，并注册到 self.phase_buttons 中。"""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setProperty("class", "TabButton")
        btn.setObjectName("TabButton")

        # 点按钮时，调用统一的 _on_phase_clicked，而不是直接 setCurrentIndex
        btn.clicked.connect(lambda _=False, k=key: self._on_phase_clicked(k))

        self.phase_buttons[key] = btn
        return btn

    def _on_phase_clicked(self, phase_key: str):
        """点击某个阶段按钮：切换 stack + 统一刷新按钮选中状态。"""
        self.current_phase = phase_key

        # 1）切换下面的 stack 页面
        index = self.phase_index_map.get(phase_key, 0)
        self.phase_stack.setCurrentIndex(index)

        # 2）只有当前阶段按钮是 checked=True，其余全部 False
        for key, btn in self.phase_buttons.items():
            btn.setChecked(key == phase_key)

    def _build_phase_page(self, phase_name: str):
        """
        为某个阶段（新建竣工 / 第一次改造 / 第二次改造）创建一页：
        - 上方：相关文件 表格
        - 下方：载荷信息及评估结果 表格（最后一行是“改造概述”）
        """
        page = QFrame()
        page.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        group_result = QGroupBox("载荷信息及评估结果")
        group_layout = QVBoxLayout(group_result)
        group_layout.setContentsMargins(8, 6, 8, 8)
        group_layout.setSpacing(4)

        # 行数由 _fill_phase_load_table 设置，这里先给 0 行、4 列
        table_load = QTableWidget(0, 4, group_result)
        table_load.setHorizontalHeaderLabels(["序号", "内容", "最大值UC", "结论"])
        self._init_table_common(table_load)
        self._fill_phase_load_table(phase_name, table_load)

        group_layout.addWidget(table_load)
        layout.addWidget(group_result)

        layout.addStretch()

        # 保存引用，后续如果要更新数据可以用
        self.phase_tables[phase_name] = {
            "load": table_load,
        }

        return page


    # ------------------------------------------------------------------
    # 阶段数据填充（目前写死示例，后续可改为外部传入）
    # ------------------------------------------------------------------


    def _get_phase_load_demo_data(self, phase_name: str):
        """
        载荷信息及评估结果示例数据。
        后续可以根据不同阶段返回不同的数据。
        """
        return [
            {"index": 1, "content": "构件应力校核",   "uc": 0.78, "result": "满足"},
            {"index": 2, "content": "节点冲剪校核",   "uc": 0.81, "result": "满足"},
            {"index": 3, "content": "桩基承载力校核", "uc": 2,    "result": "满足"},
        ]

    def _fill_phase_load_table(self, phase_name: str, table: QTableWidget):
        """
        填充“载荷信息及评估结果”表格：
        - 前几行是常规载荷校核结果；
        - 最后一行是“改造概述”，第 0 列显示文字，后面三列合并为一个大单元格。
        """
        records = self._get_phase_load_demo_data(phase_name)

        # 前面 N 行放载荷信息 + 1 行改造概述
        n = len(records)
        table.setRowCount(n + 1)

        # 前 N 行：载荷信息
        for row, rec in enumerate(records):
            self._set_center_item(table, row, 0, rec["index"])
            self._set_center_item(table, row, 1, rec["content"])
            self._set_center_item(table, row, 2, rec["uc"])
            self._set_center_item(table, row, 3, rec["result"])

        # 最后一行：改造概述
        last = n

        # 第 0 列：写“改造概述”
        label_item = QTableWidgetItem("改造概述")
        label_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(last, 0, label_item)

        # 合并第 1~3 列为一个大单元格
        table.setSpan(last, 1, 1, 3)

        # 合并后的单元格里放一段可编辑文字（你可以改成空字符串）
        desc_item = QTableWidgetItem("在此填写该阶段的整体改造说明、评估结论等。")
        desc_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table.setItem(last, 1, desc_item)

        # 自适应列宽和行高
        self._auto_fit_columns_with_padding(table, padding=32)
        self._auto_fit_row_height(table, padding=12)

