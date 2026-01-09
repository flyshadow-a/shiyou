# -*- coding: utf-8 -*-
# pages/important_history_rebuild_info_page.py

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import (
    QFrame,
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QStackedWidget,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)

from base_page import BasePage
from dropdown_bar import DropdownBar

# ✅ 关键：直接引用 ConstructionDocsWidget 的“文件夹布局格式代码”
from .construction_docs_widget import ConstructionDocsWidget


# ======================================================================
# 小工具类：可点击的 QLabel，用于面包屑“首页”
# ======================================================================
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


# ======================================================================
# 小工具类：文件夹图标 + 文字（保留：不删除原逻辑与文字）
# ======================================================================
class FolderTile(QFrame):
    clicked = pyqtSignal()

    # ✅ 这里三组值就是“文件夹大小格式”的核心：改成你在 ConstructionDocsWidget 里那套即可
    TILE_W, TILE_H = 160, 140          # 文件夹卡片大小
    ICON_W, ICON_H = 64, 56            # 文件夹图标显示大小（KeepAspectRatio）
    PADDING = (12, 12, 12, 12)         # 内边距
    SPACING = 8                        # 图标与文字间距

    def __init__(self, text: str, icon_path: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

        self.setObjectName("FolderTile")
        self.setProperty("selected", False)
        self.setFixedSize(self.TILE_W, self.TILE_H)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*self.PADDING)
        layout.setSpacing(self.SPACING)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.icon_label = QLabel(self)
        self.icon_label.setObjectName("FolderIcon")
        pix = QPixmap(icon_path)
        if not pix.isNull():
            pix = pix.scaled(self.ICON_W, self.ICON_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.icon_label.setPixmap(pix)
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.text_label = QLabel(text, self)
        self.text_label.setObjectName("FolderText")
        f = self.text_label.font()
        f.setPointSize(11)             # ✅ 文件夹名称字号（改成你那套）
        f.setBold(False)
        self.text_label.setFont(f)
        self.text_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)

        # ✅ 默认 / 悬停 / 选中：文件夹卡片与文字样式
        self.setStyleSheet("""
            QFrame#FolderTile {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 10px;
            }
            QFrame#FolderTile QLabel#FolderText {
                color: #111827;
            }

            QFrame#FolderTile:hover {
                background: #f3f4f6;
                border: 1px solid #d1d5db;
            }
            QFrame#FolderTile:hover QLabel#FolderText {
                color: #0074c9;
            }

            QFrame#FolderTile[selected="true"] {
                background: #e6f3ff;
                border: 1px solid #0074c9;
            }
            QFrame#FolderTile[selected="true"] QLabel#FolderText {
                color: #e11d48;   /* 选中文字变红：如果你不想红就改回 #0074c9 或 #111827 */
            }
        """)

    def set_selected(self, on: bool):
        self.setProperty("selected", bool(on))
        # 触发样式刷新
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


# ======================================================================
# ✅ 直接复用 ConstructionDocsWidget 的文件夹布局（QToolButton 那套）
#    但把点击行为改为“发信号”，交给外部页面做 stack 切换
# ======================================================================
class HistoryEventsHomeDocsWidget(ConstructionDocsWidget):
    folderSelected = pyqtSignal(str)

    def _build_folder_tree(self):
        # 首页三个文件夹：让 ConstructionDocsWidget 自己渲染文件夹布局
        # 这里用 folder 类型即可（不进入 files_page），我们拦截点击发信号
        return {
            "历史改造信息": {"type": "folder", "children": {}},
            "特检延寿": {"type": "folder", "children": {}},
            "台风&损伤": {"type": "folder", "children": {}},
        }

    def _build_demo_file_records(self):
        # 不需要文件表格数据（这里只做入口），保持空
        return {}

    def _on_folder_clicked(self, folder_name: str):
        # ✅ 关键：不走 ConstructionDocsWidget 原有“进入下一层/进入表格页”的逻辑
        # 直接把 folder_name 抛给外部页面处理（进入详情页）
        self.folderSelected.emit(folder_name)


# ======================================================================
# 详细页面：上表 + 中间描述 + 下表（保留原逻辑与文字）
# ======================================================================
class ImportantHistoryDetailWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._folder_icon_path = os.path.join(self._project_root, "pict", "wenjian.png")

        self._build_ui()

    # ---------- 公共表格样式 ----------
    def _init_table_common(self, table: QTableWidget):
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(False)
        table.setShowGrid(True)

        # 放大字体
        font = table.font()
        font.setPointSize(10)
        table.setFont(font)

        table.verticalHeader().setVisible(False)
        hh = table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setHighlightSections(False)
        # 默认：所有列一起自适应填充宽度
        hh.setSectionResizeMode(QHeaderView.Stretch)

        # 选中时是淡蓝色
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                border-bottom: 1px solid #d0d0d0;   /* 表头下面的下划线就在这里 */
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #cce8ff;
            }
        """)

    def _set_center_item(self, table: QTableWidget, row: int, col: int, text: str):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)

    # ---------- UI ----------
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ✅ 顶格：不要让 header 和内容之间多出空白
        main_layout.setSpacing(0)

        # 1) 顶部蓝色面包屑条
        header = QFrame(self)
        header.setObjectName("HistoryHeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 3, 10, 3)
        header_layout.setSpacing(6)

        icon_label = QLabel(header)
        pix = QPixmap(self._folder_icon_path)
        if not pix.isNull():
            pix = pix.scaled(20, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(pix)

        self.lbl_home = ClickableLabel("首页", header)
        font_home = self.lbl_home.font()
        font_home.setPointSize(font_home.pointSize() + 1)
        self.lbl_home.setFont(font_home)
        self.lbl_home.setStyleSheet("color: white;")

        sep1 = QLabel(">", header)
        sep1.setStyleSheet("color: white;")
        sep1.setContentsMargins(4, 0, 4, 0)

        self.lbl_folder = QLabel("历史改造信息", header)
        font_folder = self.lbl_folder.font()
        font_folder.setPointSize(font_folder.pointSize() + 1)
        self.lbl_folder.setFont(font_folder)
        self.lbl_folder.setStyleSheet("color: white;")

        header_layout.addWidget(icon_label)
        header_layout.addSpacing(4)
        header_layout.addWidget(self.lbl_home)
        header_layout.addSpacing(4)
        header_layout.addWidget(sep1)
        header_layout.addSpacing(4)
        header_layout.addWidget(self.lbl_folder)
        header_layout.addStretch()

        main_layout.addWidget(header, 0)

        # 2) 中间内容区域：上表 + 描述 + 下表
        content = QFrame(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 8)
        content_layout.setSpacing(8)

        # 2.1) 上表：序号 / 项目名称 / 年份
        self.top_table = QTableWidget(0, 3, content)
        self.top_table.setHorizontalHeaderLabels(["序号", "项目名称", "年份"])
        self._init_table_common(self.top_table)

        # ✅ 上表列宽控制：
        #    第 0、2 列：可手动设置宽度
        #    第 1 列：自适应拉伸，占满剩余空间
        header_view = self.top_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Interactive)
        header_view.setSectionResizeMode(1, QHeaderView.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.Interactive)

        # 在这里改“序号”和“年份”的宽度（像素）
        self.top_table.setColumnWidth(0, 120)   # 序号列宽度
        self.top_table.setColumnWidth(2, 160)   # 年份列宽度

        self.top_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        content_layout.addWidget(self.top_table, 0)

        # 2.2) 中间蓝底简介文本
        self.desc_frame = QFrame(content)
        self.desc_frame.setObjectName("HistoryDescFrame")
        desc_layout = QVBoxLayout(self.desc_frame)
        desc_layout.setContentsMargins(10, 8, 10, 8)
        desc_layout.setSpacing(4)

        self.desc_label = QLabel(self.desc_frame)
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font_desc = self.desc_label.font()
        font_desc.setPointSize(10)
        self.desc_label.setFont(font_desc)
        self.desc_label.setStyleSheet("color: white;")

        desc_layout.addWidget(self.desc_label)
        content_layout.addWidget(self.desc_frame, 0)

        # 2.3) 下表：板块/因素/节点/信息来源/备注
        self.bottom_table = QTableWidget(0, 5, content)
        self.bottom_table.setHorizontalHeaderLabels(
            ["观察板块", "观察因素", "重要节点", "信息来源", "备注"]
        )
        self._init_table_common(self.bottom_table)
        self.bottom_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.bottom_table, 1)

        main_layout.addWidget(content, 1)

        # 整体样式
        self.setStyleSheet("""
            QFrame#HistoryHeaderBar {
                background-color: #0074c9;
            }
            QFrame#HistoryDescFrame {
                background-color: #0074c9;
                border-radius: 0px;
            }
        """)

        # 默认加载“历史改造信息”的示例数据
        self.load_history_event("历史改造信息")

    # ---------- 数据填充 ----------
    def load_history_event(self, folder_name: str):
        """根据点击的文件夹名，刷新上表、说明文字和下表内容"""
        # 更新面包屑中的文件夹名称
        self.lbl_folder.setText(folder_name)

        if folder_name == "历史改造信息":
            # 这里可以替换成你自己想要的示例数据
            records = [
                (1, "xxx平台建造和投产", "1998年"),
                (2, "xxx平台进行结构加固", "2006年"),
                (3, "xxx油田开发工程项目依托改造", "2011年"),
                (4, "xxx平台增加救生筏和逃生软梯安装甲板", "2016年"),
                (5, "xxx平台A3井增加放空管线", "2011年")
            ]
            desc_text = (
                "xxx平台于2006年安装并投产，平台原设计寿命15年，在投产后平台进行了"
                "一系列的改造，其中较大的改造包括xxx油田开发工程项目依托电缆护管和立管、"
                "增加结构房间、2016年增加救生筏和逃生软梯、xxx油田产能释放项目等。"
                "结果显示所有杆件UC值小于1.0，桩基承载力安全系数大于1.5，满足规范要求；"
                "极限强度分析结果显示最小RSR为2.1，满足规范要求。综合以上结论，认为增加隔水套管可行。"
            )
            bottom_rows = [
                ("构件", "", "", "", ""),
                ("节点冲剪", "", "", "", ""),
                ("桩应力", "", "", "", ""),
                ("节点疲劳", "", "", "", ""),
                ("桩承载力操作抗压", "", "", "", ""),
                ("桩承载力操作抗拔", "", "", "", ""),
                ("桩承载力极端抗压", "", "", "", ""),
                ("桩承载力极端抗拔", "", "", "", ""),
            ]
        else:
            # 其它两个文件夹暂时展示占位内容
            records = [
                (1, f"{folder_name}相关重要历史事件（示例）", ""),
            ]
            desc_text = (
                f"当前文件夹“{folder_name}”暂未录入详细的历史事件数据，可在后续阶段根据实际"
                "评估结果补充上表与下表的具体信息。"
            )
            bottom_rows = [
                ("", "", "", "", ""),
            ]

        # 填充上表
        self.top_table.setRowCount(len(records))
        for r, (idx, name, year) in enumerate(records):
            self._set_center_item(self.top_table, r, 0, idx)
            item_name = QTableWidgetItem(name)
            item_name.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.top_table.setItem(r, 1, item_name)
            self._set_center_item(self.top_table, r, 2, year)

        # 描述文本
        self.desc_label.setText(desc_text)

        # 填充下表
        self.bottom_table.setRowCount(len(bottom_rows))
        for r, (c1, c2, c3, c4, c5) in enumerate(bottom_rows):
            for col, val in enumerate((c1, c2, c3, c4, c5)):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.bottom_table.setItem(r, col, item)


# ======================================================================
# 整个页面：上级 BasePage，包含“文件夹首页” + “详细内容”两个子页面
# ======================================================================
class ImportantHistoryEventsPage(BasePage):
    """
    文件管理 -> 重要历史事件记录

    - 进入页面时：先看到“首页”，中间三个文件夹：
        * 历史改造信息
        * 特检延寿
        * 台风&损伤
      顶部有 DropdownBar 下拉条。
    - 点击任一文件夹：切换到详细界面（无下拉条），显示上表+简介+下表。
    - 详细界面顶部的“首页”文字可点击，点击后返回到三个文件夹界面。
    """

    def __init__(self, parent=None):
        # ✅ 顶格：避免 BasePage 顶部标题占位导致“多一条空白”
        super().__init__("", parent)
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._folder_icon_path = os.path.join(self._project_root, "pict", "wenjian.png")
        self._build_ui()
        self._hide_base_title_if_any()

    def _hide_base_title_if_any(self):
        """兜底：兼容不同 BasePage 实现，尽量把顶部标题 QLabel 隐藏掉"""
        for attr in ("title_label", "lbl_title", "label_title", "page_title_label"):
            w = getattr(self, attr, None)
            if isinstance(w, QLabel):
                w.hide()
        for obj_name in ("PageTitle", "pageTitle", "titleLabel", "lblTitle"):
            w = self.findChild(QLabel, obj_name)
            if w:
                w.hide()

    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 整个页面用一个堆叠：0 = 三个文件夹首页；1 = 详细界面
        self.stack = QStackedWidget(self)
        self.main_layout.addWidget(self.stack)

        # 0) 文件夹首页
        self.home_page = self._build_home_page()
        self.stack.addWidget(self.home_page)

        # 1) 详细界面
        self.detail_widget = ImportantHistoryDetailWidget(self)
        # 点击“首页”返回
        self.detail_widget.lbl_home.clicked.connect(self._go_home)
        self.stack.addWidget(self.detail_widget)

        # 默认显示首页
        self.stack.setCurrentIndex(0)

    # ---------- 首页：三个文件夹 ----------
    def _build_home_page(self) -> QWidget:
        page = QFrame(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        # ✅ 顶格：去掉 DropdownBar 和下面内容之间的额外空白（原来是 8）
        layout.setSpacing(0)

        # 顶部下拉条
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
        self.dropdown_bar = DropdownBar(fields, parent=page)
        layout.addWidget(self.dropdown_bar, 0)

        # =========================================================
        # ✅ 直接引用 ConstructionDocsWidget 的“文件夹布局格式代码”
        #    首页三个文件夹的排布/间距/样式/路径栏都由 ConstructionDocsWidget 管
        # =========================================================
        card = QFrame(page)
        card.setObjectName("HomeCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.home_docs = HistoryEventsHomeDocsWidget(card)
        # 点击任意文件夹 -> 进入你的详情页逻辑
        self.home_docs.folderSelected.connect(self._enter_detail)

        card_layout.addWidget(self.home_docs)
        layout.addWidget(card, 1)

        return page

    # ---------- 逻辑：进入/返回 ----------
    def _enter_detail(self, folder_name: str):
        # 加载对应的数据
        self.detail_widget.load_history_event(folder_name)
        # 切到详细页面
        self.stack.setCurrentIndex(1)

    def _go_home(self):
        # 返回“首页”（三个文件夹）
        self.stack.setCurrentIndex(0)
