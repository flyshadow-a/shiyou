# -*- coding: utf-8 -*-
# pages/important_history_rebuild_info_page.py

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from base_page import BasePage
from dropdown_bar import DropdownBar
from .construction_docs_widget import ConstructionDocsWidget


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class FolderTile(QFrame):
    clicked = pyqtSignal()

    TILE_W, TILE_H = 160, 140
    ICON_W, ICON_H = 64, 56
    PADDING = (12, 12, 12, 12)
    SPACING = 8

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
        text_font = self.text_label.font()
        text_font.setPointSize(14)
        self.text_label.setFont(text_font)
        self.text_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)

        self.setStyleSheet(
            """
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
                color: #e11d48;
            }
            """
        )

    def set_selected(self, on: bool):
        self.setProperty("selected", bool(on))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class HistoryEventsHomeDocsWidget(ConstructionDocsWidget):
    folderSelected = pyqtSignal(str)

    def _build_folder_tree(self):
        return {
            "历史改造信息": {"type": "folder", "children": {}},
            "特检延寿": {"type": "folder", "children": {}},
            "台风&损伤": {"type": "folder", "children": {}},
        }

    def _build_demo_file_records(self):
        return {}

    def _on_folder_clicked(self, folder_name: str):
        self.folderSelected.emit(folder_name)


class ImportantHistoryDetailWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._folder_icon_path = os.path.join(self._project_root, "pict", "wenjian.png")
        self._breadcrumb_font_ratio = 0.015
        self._demo_history_data = self._build_demo_history_data()
        self._current_projects = []

        self._build_ui()

    def _init_table_common(self, table: QTableWidget):
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(False)
        table.setShowGrid(True)

        table_font = table.font()
        table_font.setPointSize(10)
        table.setFont(table_font)

        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setHighlightSections(False)
        header.setSectionResizeMode(QHeaderView.Stretch)

        table.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #d0d0d0;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                border-bottom: 1px solid #d0d0d0;
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #cce8ff;
            }
            """
        )

    def _set_center_item(self, table: QTableWidget, row: int, col: int, text: str):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)

    def _build_demo_history_data(self):
        return {
            "历史改造信息": {
                "projects": [
                    {
                        "index": 1,
                        "name": "WC19-1WHPC平台增加调压井改造",
                        "year": "2009年",
                        "conclusion": "完成井口流程和局部结构补强校核后，新增调压井改造满足运行要求，可按现状继续使用。",
                        "files": [
                            {"name": "调压井改造方案说明书.pdf", "type": "PDF", "updated": "2009-06-18", "note": "方案版"},
                            {"name": "调压井结构校核报告.docx", "type": "Word", "updated": "2009-06-24", "note": "校核结论"},
                            {"name": "调压井改造总图.dwg", "type": "CAD", "updated": "2009-06-25", "note": "施工图"},
                        ],
                    },
                    {
                        "index": 2,
                        "name": "WC19-1油田产能释放改造",
                        "year": "2016年",
                        "conclusion": "经复核，上部组块荷载增长在可控范围内，配套加固后满足产能释放改造需求。",
                        "files": [
                            {"name": "产能释放改造请示.pdf", "type": "PDF", "updated": "2016-03-08", "note": "立项材料"},
                            {"name": "产能释放新增设备清单.xlsx", "type": "Excel", "updated": "2016-03-12", "note": "设备统计"},
                            {"name": "产能释放结构复核报告.pdf", "type": "PDF", "updated": "2016-03-28", "note": "复核报告"},
                        ],
                    },
                    {
                        "index": 3,
                        "name": "WC19-1详细设计项目旧平台结构改造",
                        "year": "2011年",
                        "conclusion": "原平台结构经补强设计后可承接新增模块荷载，施工条件和后续运行条件均满足要求。",
                        "files": [
                            {"name": "旧平台结构改造设计说明.docx", "type": "Word", "updated": "2011-04-16", "note": "设计说明"},
                            {"name": "旧平台节点补强详图.dwg", "type": "CAD", "updated": "2011-04-18", "note": "详图文件"},
                            {"name": "旧平台结构改造计算书.pdf", "type": "PDF", "updated": "2011-04-20", "note": "计算成果"},
                        ],
                    },
                    {
                        "index": 4,
                        "name": "WC19-1平台增加救生筏和逃生软梯安装甲板",
                        "year": "2016年",
                        "conclusion": "新增逃生设施对应的局部甲板和支撑构件校核通过，改造后安全疏散能力得到提升。",
                        "files": [
                            {"name": "救生设施改造布置图.pdf", "type": "PDF", "updated": "2016-09-02", "note": "布置图"},
                            {"name": "逃生软梯安装方案.docx", "type": "Word", "updated": "2016-09-06", "note": "施工方案"},
                            {"name": "甲板补强复核单.xlsx", "type": "Excel", "updated": "2016-09-08", "note": "校核记录"},
                        ],
                    },
                    {
                        "index": 5,
                        "name": "WC19-1平台A3井增加放空管线",
                        "year": "2011年",
                        "conclusion": "新增放空管线对现有平台整体影响较小，完成支架优化后可满足长期运行要求。",
                        "files": [
                            {"name": "A3井放空管线改造图.dwg", "type": "CAD", "updated": "2011-11-10", "note": "施工图"},
                            {"name": "放空管线材料统计表.xlsx", "type": "Excel", "updated": "2011-11-12", "note": "材料表"},
                            {"name": "放空管线改造总结.pdf", "type": "PDF", "updated": "2011-11-20", "note": "总结材料"},
                        ],
                    },
                ]
            },
            "特检延寿": {
                "projects": [
                    {
                        "index": 1,
                        "name": "平台特检延寿评估项目",
                        "year": "2022年",
                        "conclusion": "结合近年检测和校核结果，平台延寿条件基本具备，建议按整改闭环后进入延寿实施阶段。",
                        "files": [
                            {"name": "特检延寿评估报告.pdf", "type": "PDF", "updated": "2022-05-16", "note": "评估结论"},
                            {"name": "延寿整改项清单.xlsx", "type": "Excel", "updated": "2022-05-18", "note": "整改项"},
                        ],
                    }
                ]
            },
            "特殊事件检测（台风、碰撞等）": {
                "projects": [
                    {
                        "index": 1,
                        "name": "台风后损伤复核项目",
                        "year": "2020年",
                        "conclusion": "本次台风造成局部附属构件受损，主体结构未见明显失效，完成修复后可恢复正常生产。",
                        "files": [
                            {"name": "台风后巡检记录.pdf", "type": "PDF", "updated": "2020-08-23", "note": "巡检记录"},
                            {"name": "损伤修复方案.docx", "type": "Word", "updated": "2020-08-25", "note": "修复方案"},
                        ],
                    }
                ]
            },
        }

    def _build_placeholder_project(self, folder_name: str):
        return [
            {
                "index": 1,
                "name": f"{folder_name}示例项目",
                "year": "待补充",
                "conclusion": f"{folder_name}的结论内容当前先使用演示文案占位，后续可替换为实际评估或审批结论。",
                "files": [
                    {"name": f"{folder_name}资料汇总.pdf", "type": "PDF", "updated": "待补充", "note": "演示文件"},
                    {"name": f"{folder_name}附件清单.xlsx", "type": "Excel", "updated": "待补充", "note": "演示文件"},
                ],
            }
        ]

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("PathBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 3, 10, 3)
        header_layout.setSpacing(6)

        icon_label = QLabel(header)
        pix = QPixmap(self._folder_icon_path)
        if not pix.isNull():
            pix = pix.scaled(20, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(pix)
        icon_label.setObjectName("PathIcon")

        self.lbl_home = ClickableLabel("首页", header)
        self.lbl_home.setObjectName("Breadcrumb")

        self.lbl_sep = QLabel(">", header)
        self.lbl_sep.setObjectName("BreadcrumbArrow")
        self.lbl_sep.setContentsMargins(4, 0, 4, 0)

        self.lbl_folder = QLabel("历史改造信息", header)
        self.lbl_folder.setObjectName("BreadcrumbCurrent")

        header_layout.addWidget(icon_label)
        header_layout.addSpacing(4)
        header_layout.addWidget(self.lbl_home)
        header_layout.addSpacing(4)
        header_layout.addWidget(self.lbl_sep)
        header_layout.addSpacing(4)
        header_layout.addWidget(self.lbl_folder)
        header_layout.addStretch()

        main_layout.addWidget(header, 0)

        content = QFrame(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 8)
        content_layout.setSpacing(10)

        self.top_table = QTableWidget(0, 3, content)
        self.top_table.setHorizontalHeaderLabels(["序号", "改造项目", "年份"])
        self._init_table_common(self.top_table)
        self.top_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.top_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.top_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.top_table.setColumnWidth(0, 90)
        self.top_table.setColumnWidth(2, 120)
        self.top_table.setMinimumHeight(220)
        self.top_table.itemSelectionChanged.connect(self._on_project_selection_changed)
        content_layout.addWidget(self.top_table, 0)

        self.desc_frame = QFrame(content)
        self.desc_frame.setObjectName("HistoryDescFrame")
        desc_layout = QVBoxLayout(self.desc_frame)
        desc_layout.setContentsMargins(14, 12, 14, 12)
        desc_layout.setSpacing(6)

        self.desc_title = QLabel("当前改造项目结论", self.desc_frame)
        self.desc_title.setObjectName("HistoryDescTitle")

        self.desc_label = QLabel(self.desc_frame)
        self.desc_label.setObjectName("HistoryDescLabel")
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        desc_font = self.desc_label.font()
        desc_font.setPointSize(10)
        self.desc_label.setFont(desc_font)

        desc_layout.addWidget(self.desc_title)
        desc_layout.addWidget(self.desc_label)
        content_layout.addWidget(self.desc_frame, 0)

        file_frame = QFrame(content)
        file_layout = QVBoxLayout(file_frame)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(8)

        file_header = QHBoxLayout()
        file_header.setContentsMargins(0, 0, 0, 0)
        file_header.setSpacing(8)

        self.file_title = QLabel("改造项目文件列表", file_frame)
        self.file_title.setObjectName("HistorySectionTitle")

        self.upload_button = QPushButton("上传文件", file_frame)
        self.upload_button.setObjectName("PrimaryActionButton")
        self.upload_button.clicked.connect(self._upload_demo_file)

        self.download_button = QPushButton("下载选中文件", file_frame)
        self.download_button.setObjectName("SecondaryActionButton")
        self.download_button.clicked.connect(self._download_selected_file)

        file_header.addWidget(self.file_title)
        file_header.addStretch()
        file_header.addWidget(self.upload_button)
        file_header.addWidget(self.download_button)
        file_layout.addLayout(file_header)

        self.files_table = QTableWidget(0, 4, file_frame)
        self.files_table.setHorizontalHeaderLabels(["文件名称", "文件类型", "更新时间", "说明"])
        self._init_table_common(self.files_table)
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.files_table.setMinimumHeight(220)
        self.files_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        file_layout.addWidget(self.files_table, 1)

        self.file_status_label = QLabel("", file_frame)
        self.file_status_label.setObjectName("HistoryFileStatus")
        self.file_status_label.setWordWrap(True)
        file_layout.addWidget(self.file_status_label)

        content_layout.addWidget(file_frame, 1)
        main_layout.addWidget(content, 1)

        self.setStyleSheet(
            """
            QFrame#PathBar {
                background-color: #006bb3;
            }
            QLabel#PathIcon {
                background-color: #004a87;
                border-radius: 3px;
            }
            QLabel#Breadcrumb {
                color: #ffffff;
                background-color: transparent;
            }
            QLabel#Breadcrumb:hover {
                text-decoration: underline;
            }
            QLabel#BreadcrumbCurrent {
                font-weight: bold;
                color: #ffffff;
                background-color: transparent;
            }
            QLabel#BreadcrumbArrow {
                color: #ffffff;
                background-color: transparent;
            }
            QFrame#HistoryDescFrame {
                background-color: #0b78d0;
                border-radius: 8px;
            }
            QLabel#HistoryDescTitle {
                font-size: 12px;
                font-weight: bold;
                color: #dbeafe;
                background-color: transparent;
            }
            QLabel#HistoryDescLabel {
                color: #ffffff;
                line-height: 1.6;
                background-color: transparent;
            }
            QLabel#HistorySectionTitle {
                font-size: 13px;
                font-weight: bold;
                color: #1f2937;
            }
            QPushButton#PrimaryActionButton,
            QPushButton#SecondaryActionButton {
                min-height: 32px;
                padding: 0 14px;
                border-radius: 6px;
                border: 1px solid #0b78d0;
            }
            QPushButton#PrimaryActionButton {
                background-color: #0b78d0;
                color: #ffffff;
            }
            QPushButton#PrimaryActionButton:hover {
                background-color: #0968b3;
            }
            QPushButton#SecondaryActionButton {
                background-color: #ffffff;
                color: #0b78d0;
            }
            QPushButton#SecondaryActionButton:hover {
                background-color: #eff6ff;
            }
            QLabel#HistoryFileStatus {
                min-height: 22px;
                color: #4b5563;
            }
            """
        )

        self._update_breadcrumb_font_scale()

        self.load_history_event("历史改造信息")

    def _update_breadcrumb_font_scale(self):
        font_size = max(11.0, min(20.0, self.width() * self._breadcrumb_font_ratio - 2.0))
        for widget in (self.lbl_home, self.lbl_sep, self.lbl_folder):
            font = widget.font()
            font.setPointSizeF(font_size)
            widget.setFont(font)

    def load_history_event(self, folder_name: str):
        self.lbl_folder.setText(folder_name)
        folder_data = self._demo_history_data.get(folder_name)
        if folder_data is None:
            folder_data = {"projects": self._build_placeholder_project(folder_name)}
            self._demo_history_data[folder_name] = folder_data

        self._current_projects = folder_data["projects"]
        self.file_status_label.clear()

        self.top_table.blockSignals(True)
        self.top_table.clearContents()
        self.top_table.setRowCount(len(self._current_projects))
        for row, project in enumerate(self._current_projects):
            self._set_center_item(self.top_table, row, 0, project["index"])
            name_item = QTableWidgetItem(project["name"])
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.top_table.setItem(row, 1, name_item)
            self._set_center_item(self.top_table, row, 2, project["year"])
        self.top_table.blockSignals(False)

        if self._current_projects:
            self.top_table.selectRow(0)
            self._refresh_project_detail(0)
        else:
            self.desc_label.setText("当前暂无改造项目结论。")
            self._populate_files_table([])

    def _on_project_selection_changed(self):
        row = self.top_table.currentRow()
        if row < 0 and self.top_table.rowCount():
            row = 0
        self._refresh_project_detail(row)

    def _refresh_project_detail(self, row: int):
        if row < 0 or row >= len(self._current_projects):
            self.desc_label.setText("当前暂无改造项目结论。")
            self._populate_files_table([])
            return

        project = self._current_projects[row]
        self.desc_label.setText(f"{project['name']}：{project['conclusion']}")
        self._populate_files_table(project["files"])

    def _populate_files_table(self, files):
        self.files_table.clearContents()
        self.files_table.setRowCount(len(files))
        for row, file_info in enumerate(files):
            values = (
                file_info["name"],
                file_info["type"],
                file_info["updated"],
                file_info["note"],
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                align = Qt.AlignLeft | Qt.AlignVCenter if col in (0, 3) else Qt.AlignCenter
                item.setTextAlignment(align)
                self.files_table.setItem(row, col, item)

        if files:
            self.files_table.selectRow(0)

    def _get_selected_project(self):
        row = self.top_table.currentRow()
        if row < 0 or row >= len(self._current_projects):
            return None
        return self._current_projects[row]

    def _upload_demo_file(self):
        project = self._get_selected_project()
        if not project:
            self.file_status_label.setText("请先选择一个改造项目。")
            return

        next_index = len(project["files"]) + 1
        demo_file = {
            "name": f"{project['name']}-补充资料{next_index}.pdf",
            "type": "PDF",
            "updated": "演示新增",
            "note": "上传占位文件",
        }
        project["files"].append(demo_file)
        self._populate_files_table(project["files"])
        self.file_status_label.setText(f"已为“{project['name']}”追加演示文件：{demo_file['name']}")

    def _download_selected_file(self):
        project = self._get_selected_project()
        row = self.files_table.currentRow()
        if not project or row < 0 or row >= len(project["files"]):
            self.file_status_label.setText("请先在下方文件列表中选择一个文件。")
            return

        file_info = project["files"][row]
        self.file_status_label.setText(f"已模拟下载文件：{file_info['name']}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_breadcrumb_font_scale()


class ImportantHistoryEventsPage(BasePage):
    def __init__(self, parent=None):
        super().__init__("", parent)
        self._build_ui()
        self._hide_base_title_if_any()

    def _hide_base_title_if_any(self):
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
        self.main_layout.setSpacing(8)

        self.stack = QStackedWidget(self)
        self.main_layout.addWidget(self.stack)

        self.home_page = self._build_home_page()
        self.stack.addWidget(self.home_page)

        self.detail_widget = ImportantHistoryDetailWidget(self)
        self.detail_widget.lbl_home.clicked.connect(self._go_home)
        self.stack.addWidget(self.detail_widget)
        self.stack.setCurrentIndex(0)

    def _build_home_page(self) -> QWidget:
        page = QFrame(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        fields = [
            {"key": "branch", "label": "分公司", "options": ["湛江分公司"], "default": "湛江分公司"},
            {"key": "op_company", "label": "作业公司", "options": ["文昌油田群作业公司"], "default": "文昌油田群作业公司"},
            {"key": "oilfield", "label": "油气田", "options": ["文昌19-1油田"], "default": "文昌19-1油田"},
            {"key": "facility_code", "label": "设施编号", "options": ["WC19-1WHPC"], "default": "WC19-1WHPC"},
            {"key": "facility_name", "label": "设施名称", "options": ["文昌19-1WHPC井口平台"], "default": "文昌19-1WHPC井口平台"},
            {"key": "facility_type", "label": "设施类型", "options": ["平台"], "default": "平台"},
            {"key": "category", "label": "分类", "options": ["井口平台"], "default": "井口平台"},
            {"key": "start_time", "label": "投产时间", "options": ["2013-07-15"], "default": "2013-07-15"},
            {"key": "design_life", "label": "设计年限", "options": ["15"], "default": "15"},
        ]
        self.dropdown_bar = DropdownBar(fields, parent=page)
        layout.addWidget(self.dropdown_bar, 0)

        card = QFrame(page)
        card.setObjectName("HomeCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.home_docs = HistoryEventsHomeDocsWidget(card)
        self.home_docs.folderSelected.connect(self._enter_detail)

        card_layout.addWidget(self.home_docs)
        layout.addWidget(card, 1)
        return page

    def _enter_detail(self, folder_name: str):
        self.detail_widget.load_history_event(folder_name)
        self.stack.setCurrentIndex(1)

    def _go_home(self):
        self.stack.setCurrentIndex(0)
