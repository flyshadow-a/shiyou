# -*- coding: utf-8 -*-
# pages/important_history_rebuild_info_page.py

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.base_page import BasePage
from core.message_boxes import ask_yes_no
from services.inspection_business_db_adapter import list_inspection_projects
from services.file_db_adapter import (
    DOC_MAN_MODULE_CODE,
    create_rebuild_directory,
    delete_rebuild_directory_with_files,
    is_file_db_configured,
    list_rebuild_directories,
    update_rebuild_directory,
)
from shiyou_db.document_code_parser import OTHER_FILE_CLASS_NAMES, parse_document_code_from_name
from .file_management_filter_search_bar import FileManagementFilterSearchBar
from .file_management_ui_constants import FILE_MANAGEMENT_SIDEBAR_WIDTH
from .file_management_platforms import (
    apply_platform_defaults_to_fields,
    default_platform,
    sync_platform_dropdowns,
)
from .construction_docs_widget import ConstructionDocsWidget
from .doc_man import DocManWidget, apply_docman_table_style
from .file_path_bar import PathBreadcrumbBar


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


class InspectionProjectDialog(QDialog):
    def __init__(
        self,
        *,
        title_text: str,
        project_name: str = "",
        project_year: str = "",
        summary_text: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.resize(520, 320)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        self.name_edit = QLineEdit(self)
        self.name_edit.setText(project_name)
        self.year_edit = QLineEdit(self)
        self.year_edit.setText(project_year)
        form.addRow("项目名称", self.name_edit)
        form.addRow("年份", self.year_edit)
        layout.addLayout(form)

        self.summary_edit = QTextEdit(self)
        self.summary_edit.setPlaceholderText("请输入项目说明或结论")
        self.summary_edit.setPlainText(summary_text or "")
        layout.addWidget(self.summary_edit, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self):
        if not self.name_edit.text().strip():
            QMessageBox.information(self, "提示", "项目名称不能为空。")
            return
        self.accept()

    def get_values(self) -> dict[str, str]:
        return {
            "project_name": self.name_edit.text().strip(),
            "project_year": self.year_edit.text().strip(),
            "summary_text": self.summary_edit.toPlainText().strip(),
        }


class ImportantHistoryDetailWidget(QWidget):
    homeClicked = pyqtSignal()

    _STRUCTURAL_FOLDERS = {
        "SPC": "规格书",
        "RPT": "报告",
        "DWG": "图纸",
        "MAL": "料单",
        "BOD": "设计基础",
    }
    _GENERAL_FOLDERS = {
        "DWG": "图纸",
        "SPC": "规格书",
        "RPT": "报告",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._folder_icon_path = os.path.join(self._project_root, "pict", "wenjian.png")
        self._breadcrumb_font_ratio = 0.015
        self._current_projects = []
        self._project_nav_buttons = []
        self._current_folder_name = "历史改造信息"
        self._path_bar_show_home = True
        self.facility_code = ""

        self._build_ui()

    def _init_table_common(self, table: QTableWidget):
        apply_docman_table_style(table)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(False)
        table.setShowGrid(True)

        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setHighlightSections(False)
        header.setSectionResizeMode(QHeaderView.Stretch)

    def _set_center_item(self, table: QTableWidget, row: int, col: int, text: str):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)
        item.setToolTip(item.text())
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

        self.path_bar = PathBreadcrumbBar(self._folder_icon_path, self)
        self.path_bar.pathClicked.connect(self._on_breadcrumb_path_clicked)
        self.path_bar.setVisible(False)
        self.path_bar.setFixedHeight(0)
        main_layout.addWidget(self.path_bar, 0)

        content = QFrame(self)
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 8)
        content_layout.setSpacing(12)

        self.project_sidebar = QFrame(content)
        self.project_sidebar.setObjectName("HistoryProjectSidebar")
        self.project_sidebar.setFixedWidth(FILE_MANAGEMENT_SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(self.project_sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        sidebar_title = QLabel("历次改造文件", self.project_sidebar)
        sidebar_title.setObjectName("HistorySidebarTitle")
        sidebar_layout.addWidget(sidebar_title)

        self.btn_add_project = QPushButton("＋ 新增改造", self.project_sidebar)
        self.btn_add_project.setProperty("class", "DocManBlueButton")
        self.btn_add_project.setCursor(Qt.PointingHandCursor)
        self.btn_add_project.clicked.connect(self._add_project)
        sidebar_layout.addWidget(self.btn_add_project)

        self.project_tree = QTreeWidget(self.project_sidebar)
        self.project_tree.setObjectName("HistoryProjectTree")
        self.project_tree.setHeaderHidden(True)
        self.project_tree.setIndentation(18)
        self.project_tree.setExpandsOnDoubleClick(False)
        self.project_tree.itemClicked.connect(self._on_project_tree_item_clicked)
        self.project_tree.itemDoubleClicked.connect(self._on_project_tree_item_double_clicked)
        sidebar_layout.addWidget(self.project_tree, 1)

        sidebar_actions = QHBoxLayout()
        sidebar_actions.setContentsMargins(0, 0, 0, 0)
        sidebar_actions.setSpacing(6)
        self.btn_edit_project = QPushButton("编辑", self.project_sidebar)
        self.btn_edit_project.setProperty("class", "DocManBlueButton")
        self.btn_edit_project.setCursor(Qt.PointingHandCursor)
        self.btn_edit_project.clicked.connect(self._edit_project)
        sidebar_actions.addWidget(self.btn_edit_project)
        self.btn_delete_project = QPushButton("删除", self.project_sidebar)
        self.btn_delete_project.setProperty("class", "DocManBlueButton")
        self.btn_delete_project.setCursor(Qt.PointingHandCursor)
        self.btn_delete_project.clicked.connect(self._delete_project)
        sidebar_actions.addWidget(self.btn_delete_project)
        sidebar_layout.addLayout(sidebar_actions)

        content_layout.addWidget(self.project_sidebar, 0)

        right_content = QFrame(content)
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

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
        self.top_table.hide()

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
        right_layout.addWidget(self.desc_frame, 0)

        file_frame = QFrame(content)
        file_layout = QVBoxLayout(file_frame)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(8)

        self.file_title = QLabel("改造目录文件列表", file_frame)
        self.file_title.setObjectName("HistorySectionTitle")
        self.file_title.hide()

        self.doc_man_widget = DocManWidget(self._get_doc_man_upload_dir, file_frame)
        file_layout.addWidget(self.doc_man_widget, 1)

        right_layout.addWidget(file_frame, 1)
        content_layout.addWidget(right_content, 1)
        main_layout.addWidget(content, 1)

        self.setStyleSheet(
            """
            QFrame#HistoryDescFrame {
                background-color: #e8f2ff;
                border: 1px solid #b9d9f4;
                border-radius: 8px;
            }
            QLabel#HistoryDescTitle {
                font-size: 12px;
                font-weight: bold;
                color: #12344d;
                background-color: transparent;
            }
            QLabel#HistoryDescLabel {
                color: #12344d;
                line-height: 1.6;
                background-color: transparent;
            }
            QLabel#HistorySectionTitle {
                font-size: 13px;
                font-weight: bold;
                color: #1f2937;
            }
            QFrame#HistoryProjectSidebar {
                background-color: #ffffff;
                border: 1px solid #d9e2ec;
                border-radius: 10px;
            }
            QLabel#HistorySidebarTitle {
                font-size: 14px;
                font-weight: 700;
                color: #12344d;
            }
            QPushButton[class="HistoryProjectNavButton"] {
                min-height: 36px;
                padding: 0 10px;
                border: 1px solid transparent;
                border-radius: 7px;
                background-color: #f3f7fb;
                color: #12344d;
                text-align: left;
                font-size: 12pt;
            }
            QPushButton[class="HistoryProjectNavButton"]:hover {
                background-color: #e5f2ff;
                border-color: #b9d9f4;
            }
            QPushButton[class="HistoryProjectNavButton"][selected="true"] {
                background-color: #d8ebff;
                border-color: #7fb8e8;
                font-weight: 600;
            }
            QTreeWidget#HistoryProjectTree {
                border: none;
                background: transparent;
                color: #12344d;
                font-size: 12pt;
            }
            QTreeWidget#HistoryProjectTree::item {
                min-height: 30px;
                padding: 4px 6px;
                border-radius: 6px;
            }
            QTreeWidget#HistoryProjectTree::item:hover {
                background-color: #e8f2ff;
            }
            QTreeWidget#HistoryProjectTree::item:selected {
                background-color: #d8ebff;
                color: #12344d;
                border: 1px solid #7fb8e8;
            }
            QPushButton[class="DocManBlueButton"] {
                min-height: 32px;
                padding: 0 18px;
                border: none;
                border-radius: 6px;
                background-color: #1677c5;
                color: #ffffff;
                font-size: 12pt;
                font-weight: 600;
            }
            QPushButton[class="DocManBlueButton"]:hover {
                background-color: #2186d4;
            }
            """
        )

        self._update_breadcrumb_font_scale()

        self.load_history_event("历史改造信息")

    def _on_breadcrumb_path_clicked(self, path_prefix: list[str]):
        if not path_prefix:
            self.homeClicked.emit()

    def _update_breadcrumb_font_scale(self):
        if hasattr(self, "path_bar"):
            self.path_bar.update_font_scale()

    def _folder_project_type(self, folder_name: str) -> str | None:
        mapping = {
            "历史改造信息": "history_rebuild",
            "特检延寿": "life_extension",
            "台风&损伤": "special_event",
            "特殊事件检测（台风、碰撞等）": "special_event",
        }
        return mapping.get(folder_name)

    def _default_project_name(self, folder_name: str, next_index: int) -> str:
        mapping = {
            "历史改造信息": "历史改造项目",
            "特检延寿": "特检延寿项目",
            "台风&损伤": "特殊事件项目",
            "特殊事件检测（台风、碰撞等）": "特殊事件项目",
        }
        return f"{mapping.get(folder_name, '检测项目')}{next_index}"

    def _project_storage_segments(self, project: dict | None) -> list[str]:
        folder_name = self._current_folder_name or "历史改造信息"
        if not project:
            return [folder_name]
        project_id = project.get("id")
        if project_id:
            return [folder_name, f"directory_{project_id}"]
        return [folder_name, project.get("name") or "project"]

    def _history_file_sections(self) -> list[dict]:
        structural = [
            ("规格书", "规格书"),
            ("报告", "报告"),
            ("图纸", "图纸"),
            ("料单", "材料清单"),
            ("设计基础", "设计基础数据"),
        ]
        general = [
            ("图纸", "图纸"),
            ("规格书", "规格书"),
            ("报告", "报告"),
        ]
        sections: list[dict] = []
        for name, category in structural:
            sections.append(
                {
                    "tree_path": ["结构(ST)", name],
                    "path_segments": ["结构(ST)", name],
                    "categories": [category, "其他"],
                }
            )
        for name, category in general:
            sections.append(
                {
                    "tree_path": ["总体(GE)", name],
                    "path_segments": ["总体(GE)", name],
                    "categories": [category, "其他"],
                }
            )
        sections.append(
            {
                "tree_path": ["其他"],
                "path_segments": ["其他"],
                "categories": ["未分类/其他", *OTHER_FILE_CLASS_NAMES, "其他"],
            }
        )
        return sections

    def _history_section_for_tree_path(self, tree_path: list[str]) -> dict | None:
        parts = [str(part).strip() for part in tree_path if str(part).strip()]
        if not parts:
            return None
        categories: list[str] = []
        for section in self._history_file_sections():
            section_path = [
                str(part).strip()
                for part in section.get("tree_path") or []
                if str(part).strip()
            ]
            if len(section_path) < len(parts) or section_path[: len(parts)] != parts:
                continue
            for category in section.get("categories") or []:
                if category and category not in categories:
                    categories.append(category)
        if not categories:
            return None
        return {
            "tree_path": parts,
            "path_segments": parts,
            "categories": categories,
        }

    def _build_project_view_models(self, rows: list[dict]) -> list[dict]:
        projects: list[dict] = []
        for idx, row in enumerate(rows, start=1):
            year = str(row.get("project_year") or "").strip()
            if not year:
                event_date = str(row.get("event_date") or "").strip()
                year = f"{event_date[:4]}年" if len(event_date) >= 4 else ""
            projects.append(
                {
                    "id": row.get("id"),
                    "index": int(row.get("seq_no") or idx),
                    "name": row.get("directory_name") or row.get("project_name") or f"项目{idx}",
                    "year": year,
                    "conclusion": row.get("summary_text") or row.get("conclusion_text") or "",
                }
            )
        return projects

    def _load_rebuild_directory_rows(self, facility_code: str, project_type: str) -> list[dict]:
        try:
            rows = list_rebuild_directories(facility_code, project_type=project_type)
        except Exception:
            rows = []
        if rows:
            return rows

        # Compatibility: migrate legacy inspection project rows into the new
        # document directory table on first view, so existing data remains visible.
        legacy_rows = list_inspection_projects(facility_code, project_type)
        migrated: list[dict] = []
        for legacy in legacy_rows:
            try:
                migrated.append(
                    create_rebuild_directory(
                        facility_code,
                        project_type=project_type,
                        directory_name=legacy.get("project_name") or "",
                        project_name=legacy.get("project_name") or "",
                        project_year=legacy.get("project_year") or "",
                        summary_text=legacy.get("summary_text") or "",
                    )
                )
            except Exception:
                continue
        return migrated or list_rebuild_directories(facility_code, project_type=project_type)

    def load_history_event(self, folder_name: str):
        self._current_folder_name = folder_name
        self.path_bar.set_path([folder_name], show_home=self._path_bar_show_home)
        facility_code = self.facility_code or default_platform()["facility_code"]
        project_type = self._folder_project_type(folder_name)
        rows = self._load_rebuild_directory_rows(facility_code, project_type) if project_type else []
        self._current_projects = self._build_project_view_models(rows)

        self.top_table.blockSignals(True)
        self.top_table.clearContents()
        self.top_table.setRowCount(len(self._current_projects))
        for row, project in enumerate(self._current_projects):
            self._set_center_item(self.top_table, row, 0, project["index"])
            name_item = QTableWidgetItem(project["name"])
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            name_item.setToolTip(name_item.text())
            self.top_table.setItem(row, 1, name_item)
            self._set_center_item(self.top_table, row, 2, project["year"])
        self.top_table.blockSignals(False)
        self._rebuild_project_sidebar()

        if self._current_projects:
            self._select_project_row(0)
        else:
            self.desc_label.setText("当前暂无改造项目结论。")
            self._refresh_doc_man(None)

    def _reload_current_folder(self, *, selected_id: int | None = None):
        self.load_history_event(self._current_folder_name)
        if selected_id is None:
            return
        for row, project in enumerate(self._current_projects):
            if project.get("id") == selected_id:
                self._select_project_row(row)
                break

    def _notify_platform_load_rebuild_projects_changed(self) -> None:
        tab_widget = getattr(self.window(), "tab_widget", None)
        if tab_widget is None:
            return
        for index in range(tab_widget.count()):
            page = tab_widget.widget(index)
            refresh = getattr(page, "refresh_from_rebuild_projects", None)
            if callable(refresh):
                refresh()

    def _on_project_selection_changed(self):
        row = self.top_table.currentRow()
        if row < 0 and self.top_table.rowCount():
            row = 0
        self._select_project_row(row, update_table=False)

    def _rebuild_project_sidebar(self):
        if not hasattr(self, "project_tree"):
            return
        self.project_tree.clear()
        self._project_tree_items = {}
        if not self._current_projects:
            return

        for row, project in enumerate(self._current_projects):
            year = str(project.get("year") or "").strip()
            text = f"({project.get('index', row + 1)}) {project.get('name', '')}"
            if year:
                text = f"{text}\uff08{self._project_year_label(year)}\uff09"
            project_item = QTreeWidgetItem([text])
            project_item.setData(0, Qt.UserRole, {"row": row, "section": None})
            self.project_tree.addTopLevelItem(project_item)
            self._project_tree_items[(row, "")] = project_item
            node_by_path: dict[tuple[str, ...], QTreeWidgetItem] = {}
            for section in self._history_file_sections():
                parent_item = project_item
                parts_acc: list[str] = []
                for part in section.get("tree_path") or []:
                    parts_acc.append(str(part))
                    key = tuple(parts_acc)
                    item = node_by_path.get(key)
                    if item is None:
                        item = QTreeWidgetItem([str(part)])
                        parent_item.addChild(item)
                        node_by_path[key] = item
                    item.setData(
                        0,
                        Qt.UserRole,
                        {
                            "row": row,
                            "section": self._history_section_for_tree_path(parts_acc),
                        },
                    )
                    parent_item = item
                parent_item.setData(0, Qt.UserRole, {"row": row, "section": section})
            self.project_tree.expandItem(project_item)

    @staticmethod
    def _project_year_label(value: str) -> str:
        text = str(value or "").strip().strip("()\uff08\uff09")
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) >= 4:
            return digits[:4]
        return text.replace("\u5e74", "").strip()

    def _project_display_name(self, project: dict | None) -> str:
        if not project:
            return ""
        name = str(project.get("name") or "改造项目").strip()
        year = self._project_year_label(str(project.get("year") or ""))
        return f"{name}\uff08{year}\uff09" if year else name

    def _rebuild_project_label_map(self) -> dict[str, str]:
        labels: dict[str, str] = {}
        for project in self._current_projects:
            label = self._project_display_name(project)
            if not label:
                continue
            segments = self._project_storage_segments(project)
            keys = [
                segments,
                segments[1:],
                [project.get("name") or ""],
            ]
            project_id = project.get("id")
            if project_id:
                keys.append([f"directory_{project_id}"])
            for parts in keys:
                key = "/".join(str(part).strip("/\\") for part in parts if str(part).strip("/\\"))
                if key:
                    labels[key] = label
        return labels

    def _on_project_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.UserRole)
        if isinstance(data, dict):
            self._select_project_row(int(data.get("row", 0)), section=data.get("section"))

    @staticmethod
    def _on_project_tree_item_double_clicked(item: QTreeWidgetItem, _column: int) -> None:
        if item and item.childCount() > 0:
            item.setExpanded(not item.isExpanded())

    def _select_project_row(self, row: int, *, update_table: bool = True, section: dict | None = None):
        if row < 0 or row >= len(self._current_projects):
            return
        if update_table:
            self.top_table.blockSignals(True)
            self.top_table.selectRow(row)
            self.top_table.blockSignals(False)
        item = getattr(self, "_project_tree_items", {}).get((row, ""))
        if item is not None and section is None:
            self.project_tree.setCurrentItem(item)
        self._refresh_project_detail(row, section=section)

    def _refresh_project_detail(self, row: int, section: dict | None = None):
        if row < 0 or row >= len(self._current_projects):
            self.desc_label.setText("当前暂无改造项目结论。")
            self._current_file_project = None
            self._refresh_doc_man(None)
            return

        project = self._current_projects[row]
        self.desc_label.setText(f"{project['name']}：{project['conclusion']}")
        self._current_file_project = project
        self._refresh_doc_man(project, section=section)

    def _add_project(self):
        folder_name = self._current_folder_name or "历史改造信息"
        project_type = self._folder_project_type(folder_name)
        if not project_type:
            return
        facility_code = self.facility_code or default_platform()["facility_code"]
        next_index = len(self._current_projects) + 1
        default_name = self._default_project_name(folder_name, next_index)
        try:
            created = create_rebuild_directory(
                facility_code,
                project_type=project_type,
                directory_name=default_name,
                project_name=default_name,
                project_year="",
                summary_text="",
            )
        except Exception as exc:
            QMessageBox.warning(self, "新增失败", str(exc))
            return
        self._reload_current_folder(selected_id=created.get("id"))
        self._notify_platform_load_rebuild_projects_changed()

    def _get_doc_man_upload_dir(self, path_segments):
        root = os.path.join(self._project_root, "upload", "history_rebuild")
        return os.path.join(root, *path_segments)

    def _edit_project(self):
        project = self._get_selected_project()
        if not project or not project.get("id"):
            QMessageBox.information(self, "提示", "请先选择要编辑的项目。")
            return
        dialog = InspectionProjectDialog(
            title_text="编辑改造",
            project_name=project.get("name", ""),
            project_year=project.get("year", ""),
            summary_text=project.get("conclusion", ""),
            parent=self,
        )
        try:
            result = self._exec_dialog(dialog)
        except Exception as exc:
            QMessageBox.warning(self, "编辑失败", f"打开编辑窗口失败：\n{exc}")
            return
        if result != QDialog.Accepted:
            return
        values = dialog.get_values()
        try:
            update_rebuild_directory(
                int(project["id"]),
                directory_name=values["project_name"],
                project_name=values["project_name"],
                project_year=values["project_year"],
                summary_text=values["summary_text"],
            )
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self._reload_current_folder(selected_id=int(project["id"]))
        self._notify_platform_load_rebuild_projects_changed()

    @staticmethod
    def _exec_dialog(dialog: QDialog) -> int:
        if not isinstance(dialog, QDialog):
            raise TypeError(f"dialog is not a QDialog instance: {type(dialog)!r}")
        exec_method = getattr(dialog, "exec", None)
        if callable(exec_method):
            return int(exec_method())
        return int(dialog.exec_())

    def _delete_project(self):
        project = self._get_selected_project()
        if not project or not project.get("id"):
            QMessageBox.information(self, "提示", "请先选择要删除的项目。")
            return
        if not ask_yes_no(
            self,
            "确认删除",
            f"确定删除改造“{project.get('name', '')}”吗？",
        ):
            return
        try:
            delete_rebuild_directory_with_files(
                int(project["id"]),
                module_code=DOC_MAN_MODULE_CODE,
                logical_path_prefix="/".join(self._project_storage_segments(project)),
                facility_code=self.facility_code,
            )
        except Exception as exc:
            QMessageBox.warning(self, "删除失败", str(exc))
            return
        self._reload_current_folder()
        self._notify_platform_load_rebuild_projects_changed()
        QMessageBox.information(self, "删除成功", "删除成功")

    def set_facility_code(self, code: str):
        self.facility_code = (code or "").strip()
        self._reload_current_folder()

    def set_path_bar_home_visible(self, visible: bool):
        self._path_bar_show_home = bool(visible)
        if hasattr(self, "path_bar"):
            self.path_bar.setVisible(False)
            self.path_bar.setFixedHeight(0)
            self.path_bar.set_path(
                [self._current_folder_name],
                show_home=self._path_bar_show_home,
            )

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
                item.setToolTip(item.text())
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

    def _refresh_doc_man(self, project: dict | None, section: dict | None = None):
        if hasattr(self, "file_title"):
            title = "改造目录文件列表"
            if section:
                tree_path = " / ".join(str(x) for x in section.get("tree_path") or [])
                if tree_path:
                    title = f"{title} - {tree_path}"
            self.file_title.setText(title)
        path_segments = self._project_storage_segments(project)
        display_path_segments: list[str] = []
        if project:
            display_path_segments.append(self._project_display_name(project))
        if section:
            path_segments = path_segments + list(section.get("path_segments") or [])
            display_path_segments.extend(str(x) for x in section.get("tree_path") or [])
            categories = list(section.get("categories") or [])
        else:
            categories = [
                "结构(ST)-规格书",
                "结构(ST)-报告",
                "结构(ST)-图纸",
                "结构(ST)-料单",
                "结构(ST)-设计基础",
                "总体(GE)-图纸",
                "总体(GE)-规格书",
                "总体(GE)-报告",
                "其他",
            ]
        self.doc_man_widget.set_context(
            path_segments,
            [] if project else [],
            categories,
            facility_code=self.facility_code,
            hide_empty_templates=True,
            db_list_mode=True,
            display_profile="rebuild",
            path_root_label="历次改造文件",
            display_path_segments=display_path_segments,
            path_hint="历次改造文件按改造项目、专业和文件类别归档。",
            upload_path_resolver=self._resolve_rebuild_upload_target,
            context_project_name=self._project_display_name(project),
            rebuild_project_labels=self._rebuild_project_label_map(),
        )

    def _project_for_upload(self, item: dict, current_path: list[str]) -> dict | None:
        raw_logical = (
            item.get("logical_path")
            or (item.get("record") or {}).get("logical_path")
            or "/".join(str(part) for part in current_path)
        )
        logical = str(raw_logical or "").replace("\\", "/").strip("/")
        for project in self._current_projects:
            prefix = "/".join(self._project_storage_segments(project))
            if logical == prefix or logical.startswith(f"{prefix}/"):
                return project
        current = getattr(self, "_current_file_project", None)
        if current:
            prefix = "/".join(self._project_storage_segments(current))
            current_text = "/".join(str(part) for part in current_path).replace("\\", "/").strip("/")
            if current_text == prefix or current_text.startswith(f"{prefix}/"):
                return current
        return current

    def _resolve_rebuild_upload_target(self, item: dict, current_path: list[str], current_category: str) -> dict:
        project = self._project_for_upload(item, current_path)
        project_segments = self._project_storage_segments(project) if project else list(current_path)
        file_path = str(item.get("path") or "").strip()
        meta = dict(item.get("meta") or {})
        if not meta and file_path:
            meta = parse_document_code_from_name(os.path.basename(file_path))

        status = str(meta.get("recognition_status") or "").strip()
        file_class = str(meta.get("file_class_code") or "").strip().upper()
        discipline = str(meta.get("discipline_code") or "").strip().upper()
        file_class_name = str(meta.get("file_class_name") or "").strip()
        category = file_class_name or str(current_category or "").strip()

        if status == "unclassified" or not file_class or not discipline:
            return {
                "path_segments": project_segments + ["其他"],
                "category": "未分类/其他",
            }

        if discipline == "ST":
            folder = self._STRUCTURAL_FOLDERS.get(file_class)
            if folder:
                return {
                    "path_segments": project_segments + ["结构(ST)", folder],
                    "category": category or "其他",
                }
        elif discipline == "GE":
            folder = self._GENERAL_FOLDERS.get(file_class)
            if folder:
                return {
                    "path_segments": project_segments + ["总体(GE)", folder],
                    "category": category or "其他",
                }

        return {
            "path_segments": project_segments + ["其他"],
            "category": category or "未分类/其他",
        }

    def search_all_documents(self, code_query: str = "", name_query: str = "") -> None:
        code = (code_query or "").strip().lower()
        name = (name_query or "").strip().lower()
        if not code and not name:
            self._refresh_project_detail(self.top_table.currentRow())
            return
        if not is_file_db_configured():
            QMessageBox.information(self, "提示", "当前未配置文件数据库，无法跨分类搜索。")
            return
        self.file_title.setText("搜索结果")
        self.doc_man_widget.set_context(
            self._project_storage_segments(None),
            [],
            ["未分类/其他", "其他"],
            facility_code=self.facility_code,
            overlay_from_db=False,
            hide_empty_templates=False,
            db_list_mode=True,
            display_profile="rebuild",
            path_root_label="历次改造文件",
            display_path_segments=["搜索结果"],
            path_hint="按文件编码/文件名搜索历次改造文件。",
            upload_path_resolver=self._resolve_rebuild_upload_target,
            rebuild_project_labels=self._rebuild_project_label_map(),
            document_code_query=code,
            document_title_query=name,
        )

    @staticmethod
    def _record_matches_query(record: dict, code_query: str, name_query: str) -> bool:
        code_text = " ".join(str(record.get(key) or "") for key in ("document_code", "logical_path", "filename")).lower()
        name_text = " ".join(str(record.get(key) or "") for key in ("document_title", "filename", "logical_path")).lower()
        if code_query and code_query not in code_text:
            return False
        if name_query and name_query not in name_text:
            return False
        return True

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
        self.detail_widget.homeClicked.connect(self._go_home)
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
        platform_defaults = default_platform()
        apply_platform_defaults_to_fields(fields, platform_defaults)
        self.filter_search_bar = FileManagementFilterSearchBar(fields, page)
        self.dropdown_bar = self.filter_search_bar.dropdown_bar
        self.filter_search_bar.searchRequested.connect(self._search_documents)
        layout.addWidget(self.filter_search_bar, 0)

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
        self.filter_search_bar.valueChanged.connect(self.on_filter_changed)
        self._sync_platform_ui()
        return page

    def _enter_detail(self, folder_name: str):
        self.detail_widget.set_facility_code(self.dropdown_bar.get_value("facility_code"))
        self.detail_widget.load_history_event(folder_name)
        self.stack.setCurrentIndex(1)

    def _go_home(self):
        self.stack.setCurrentIndex(0)

    def on_filter_changed(self, key: str, value: str):
        self._sync_platform_ui(changed_key=key)

    def _search_documents(self, code: str = "", name: str = ""):
        self.detail_widget.search_all_documents(code, name)
        self.stack.setCurrentIndex(1)

    def _sync_platform_ui(self, changed_key: str | None = None):
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        self.home_docs.set_facility_code(platform["facility_code"])
        if hasattr(self, "detail_widget") and self.detail_widget is not None:
            self.detail_widget.set_facility_code(platform["facility_code"])

    def set_facility_code(self, code: str):
        self.dropdown_bar.set_value("facility_code", code)
        self._sync_platform_ui(changed_key="facility_code")
