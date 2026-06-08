# -*- coding: utf-8 -*-
# pages/history_events_inspection_page.py

import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.base_page import BasePage
from core.message_boxes import ask_yes_no
from pages.construction_docs_widget import ConstructionDocsWidget
from pages.file_management_platforms import (
    apply_platform_defaults_to_fields,
    default_platform,
    sync_platform_dropdowns,
)
from pages.file_management_filter_search_bar import FileManagementFilterSearchBar
from pages.file_management_ui_constants import FILE_MANAGEMENT_SIDEBAR_WIDTH
from pages.important_history_rebuild_info_page import ImportantHistoryEventsPage
from pages.history_inspection_summary_page import (
    HistoryInspectionSummaryPage,
    InspectionProjectEditDialog,
    InspectionFindingDialog,
)
from pages.doc_man import DocManWidget, apply_docman_table_style
from services.file_db_adapter import (
    DOC_MAN_MODULE_CODE,
    is_file_db_configured,
)
from services.inspection_business_db_adapter import (
    create_inspection_project,
    list_inspection_findings,
    list_inspection_projects,
    replace_inspection_findings,
    soft_delete_inspection_project_with_files,
    update_inspection_project,
)


INSPECTION_LEVELS = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ"]
INSPECTION_LEVEL_COLUMN = 1
INSPECTION_LEVEL_ALIASES = {
    "1": "Ⅰ",
    "I": "Ⅰ",
    "Ⅰ": "Ⅰ",
    "2": "Ⅱ",
    "II": "Ⅱ",
    "Ⅱ": "Ⅱ",
    "3": "Ⅲ",
    "III": "Ⅲ",
    "Ⅲ": "Ⅲ",
    "4": "Ⅳ",
    "IV": "Ⅳ",
    "Ⅳ": "Ⅳ",
}


def normalize_inspection_level(value: str) -> str:
    text = str(value or "").strip()
    return INSPECTION_LEVEL_ALIASES.get(text.upper(), text)


class InspectionLevelDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.addItems(INSPECTION_LEVELS)
        font = combo.font()
        font.setPointSize(max(font.pointSize(), 14))
        combo.setFont(font)
        line_edit = combo.lineEdit()
        line_edit.setReadOnly(True)
        line_edit.setAlignment(Qt.AlignCenter)
        line_edit.setFrame(False)
        line_edit.setCursor(Qt.ArrowCursor)
        for row in range(combo.count()):
            combo.setItemData(row, Qt.AlignCenter, Qt.TextAlignmentRole)
        combo.activated.connect(lambda _index, editor=combo: self._commit_and_close(editor))
        QTimer.singleShot(0, combo.showPopup)
        return combo

    def setEditorData(self, editor, index) -> None:
        value = normalize_inspection_level(index.data(Qt.DisplayRole) or index.data(Qt.EditRole) or "")
        selected = editor.findText(value)
        editor.setCurrentIndex(selected if selected >= 0 else 0)

    def setModelData(self, editor, model, index) -> None:
        model.setData(index, editor.currentText(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index) -> None:
        editor.setGeometry(option.rect)

    def _commit_and_close(self, editor) -> None:
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QAbstractItemDelegate.NoHint)


class _FacilityCodeMirror:
    def __init__(self):
        self.facility_code = ""

    def set_facility_code(self, facility_code: str) -> None:
        self.facility_code = facility_code


class AddInspectionProjectDialog(QDialog):
    def __init__(self, default_project_type: str = "periodic", parent=None):
        super().__init__(parent)
        self.setWindowTitle("新增检测项目")
        self.setModal(True)
        self.resize(440, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.type_combo = QComboBox(self)
        self.type_combo.addItem("定期检测", "periodic")
        self.type_combo.addItem("特殊事件检测", "special_event")
        index = self.type_combo.findData(default_project_type)
        self.type_combo.setCurrentIndex(index if index >= 0 else 0)

        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("例如：第一次检测 / 台风检测")
        self.description_edit = QLineEdit(self)
        self.description_edit.setPlaceholderText("请输入检测描述")
        self.year_edit = QLineEdit(self)
        self.year_edit.setPlaceholderText("例如：2025")

        form.addRow("检测类型", self.type_combo)
        form.addRow("项目名称", self.name_edit)
        form.addRow("描述", self.description_edit)
        form.addRow("年份", self.year_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.information(self, "提示", "请先填写项目名称。")
            return
        if not self.year_edit.text().strip():
            QMessageBox.information(self, "提示", "请先填写年份。")
            return
        self.accept()

    def get_values(self) -> dict[str, str]:
        return {
            "project_type": str(self.type_combo.currentData() or "periodic"),
            "project_name": self.name_edit.text().strip(),
            "summary_text": self.description_edit.text().strip(),
            "project_year": self.year_edit.text().strip(),
        }


class _CombinedHistoryHomeWidget(ConstructionDocsWidget):
    folderSelected = pyqtSignal(str, str)

    def _build_folder_tree(self):
        return {
            "\u5b8c\u5de5\u68c0\u6d4b": {"type": "folder", "children": {}},
            "\u5b9a\u671f\u68c0\u6d4b1-N": {"type": "folder", "children": {}},
            "\u7279\u6b8a\u4e8b\u4ef6\u68c0\u6d4b\uff08\u53f0\u98ce\u3001\u78b0\u649e\u7b49\uff09": {"type": "folder", "children": {}},
        }

    def _build_demo_file_records(self):
        return {}

    def _on_folder_clicked(self, folder_name: str):
        inspection = {
            "\u5b8c\u5de5\u68c0\u6d4b": "complete",
            "\u5b9a\u671f\u68c0\u6d4b1-N": "periodic",
            "\u7279\u6b8a\u4e8b\u4ef6\u68c0\u6d4b\uff08\u53f0\u98ce\u3001\u78b0\u649e\u7b49\uff09": "history_sampling",
        }
        if folder_name in inspection:
            self.folderSelected.emit("inspection", inspection[folder_name])


class _EventsPage(ImportantHistoryEventsPage):
    goHomeRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hide_dropdown_if_any()

    def _hide_dropdown_if_any(self):
        bar = getattr(self, "dropdown_bar", None)
        if bar is not None:
            bar.setVisible(False)
            bar.setFixedHeight(0)

    def _go_home(self):
        self.goHomeRequested.emit()

    def open_folder(self, folder_name: str):
        self._enter_detail(folder_name)


class _InspectionPage(HistoryInspectionSummaryPage):
    goHomeRequested = pyqtSignal()

    def __init__(self, parent=None):
        self._allow_internal_home = True
        super().__init__(parent)
        self._allow_internal_home = False
        self._hide_dropdown_if_any()

    def _hide_dropdown_if_any(self):
        bar = getattr(self, "dropdown_bar", None)
        if bar is not None:
            bar.setVisible(False)
            bar.setFixedHeight(0)

    def _switch_to(self, folder_key: str):
        if folder_key == "home":
            if self._allow_internal_home:
                super()._switch_to(folder_key)
                return
            self.goHomeRequested.emit()
            return
        super()._switch_to(folder_key)

    def open_folder(self, folder_key: str):
        super()._switch_to(folder_key)


class HistoryEventsInspectionPage(BasePage):
    """
    File Management -> History Events and Inspection

    Combines the folder entry points from ImportantHistoryEventsPage and
    HistoryInspectionSummaryPage on the same page. Functionality is unchanged.
    """

    def __init__(self, parent=None):
        # Use empty title to avoid extra header space above child pages.
        super().__init__("", parent)
        self._build_ui()
        self._hide_base_title_if_any()

    def _hide_base_title_if_any(self):
        for attr in ("title_label", "lbl_title", "label_title", "page_title_label"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.hide()
                except Exception:
                    pass

    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        fields = [
            {"key": "branch", "label": "\u5206\u516c\u53f8", "options": ["\u6e2d\u6c5f\u5206\u516c\u53f8"], "default": "\u6e2d\u6c5f\u5206\u516c\u53f8"},
            {"key": "op_company", "label": "\u4f5c\u4e1a\u516c\u53f8", "options": ["\u6587\u660c\u6cb9\u7530\u7fa4\u4f5c\u4e1a\u516c\u53f8"], "default": "\u6587\u660c\u6cb9\u7530\u7fa4\u4f5c\u4e1a\u516c\u53f8"},
            {"key": "oilfield", "label": "\u6cb9\u6c14\u7530", "options": ["\u6587\u660c19-1\u6cb9\u7530"], "default": "\u6587\u660c19-1\u6cb9\u7530"},
            {"key": "facility_code", "label": "\u8bbe\u65bd\u7f16\u53f7", "options": ["WC19-1WHPC"], "default": "WC19-1WHPC"},
            {"key": "facility_name", "label": "\u8bbe\u65bd\u540d\u79f0", "options": ["\u6587\u660c19-1WHPC\u4e95\u53e3\u5e73\u53f0"], "default": "\u6587\u660c19-1WHPC\u4e95\u53e3\u5e73\u53f0"},
            {"key": "facility_type", "label": "\u8bbe\u65bd\u7c7b\u578b", "options": ["\u5e73\u53f0"], "default": "\u5e73\u53f0"},
            {"key": "category", "label": "\u5206\u7c7b", "options": ["\u4e95\u53e3\u5e73\u53f0"], "default": "\u4e95\u53e3\u5e73\u53f0"},
            {"key": "start_time", "label": "\u6295\u4ea7\u65f6\u95f4", "options": ["2013-07-15"], "default": "2013-07-15"},
            {"key": "design_life", "label": "\u8bbe\u8ba1\u5e74\u9650", "options": ["15"], "default": "15"},
        ]
        platform_defaults = default_platform()
        apply_platform_defaults_to_fields(fields, platform_defaults)
        self.filter_search_bar = FileManagementFilterSearchBar(fields, self)
        self.dropdown_bar = self.filter_search_bar.dropdown_bar
        self.filter_search_bar.searchRequested.connect(self._search_documents)
        self.main_layout.addWidget(self.filter_search_bar, 0)

        content_root = QFrame(self)
        content_root.setObjectName("HistoryInspectionLibraryRoot")
        content_layout = QHBoxLayout(content_root)
        content_layout.setContentsMargins(12, 8, 12, 12)
        content_layout.setSpacing(12)

        sidebar = QFrame(content_root)
        sidebar.setObjectName("HistoryInspectionSidebar")
        sidebar.setFixedWidth(FILE_MANAGEMENT_SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)
        sidebar_title = QLabel("检测记录分类", sidebar)
        sidebar_title.setObjectName("HistoryInspectionSidebarTitle")
        sidebar_layout.addWidget(sidebar_title)

        self.btn_add_project = QPushButton("＋ 新增检测项目", sidebar)
        self.btn_add_project.setProperty("class", "DocManBlueButton")
        self.btn_add_project.setCursor(Qt.PointingHandCursor)
        self.btn_add_project.clicked.connect(self._add_inspection_project)
        sidebar_layout.addWidget(self.btn_add_project)

        self._sidebar_items = {}
        self.sidebar_tree = QTreeWidget(sidebar)
        self.sidebar_tree.setObjectName("HistoryInspectionTree")
        self.sidebar_tree.setHeaderHidden(True)
        self.sidebar_tree.setIndentation(18)
        self.sidebar_tree.itemClicked.connect(self._on_sidebar_item_clicked)
        sidebar_layout.addWidget(self.sidebar_tree, 1)

        sidebar_actions = QHBoxLayout()
        sidebar_actions.setContentsMargins(0, 0, 0, 0)
        sidebar_actions.setSpacing(6)
        self.btn_edit_project = QPushButton("编辑", sidebar)
        self.btn_edit_project.setProperty("class", "DocManBlueButton")
        self.btn_edit_project.setCursor(Qt.PointingHandCursor)
        self.btn_edit_project.clicked.connect(self._edit_inspection_project)
        sidebar_actions.addWidget(self.btn_edit_project)
        self.btn_delete_project = QPushButton("删除", sidebar)
        self.btn_delete_project.setProperty("class", "DocManBlueButton")
        self.btn_delete_project.setCursor(Qt.PointingHandCursor)
        self.btn_delete_project.clicked.connect(self._delete_inspection_project)
        sidebar_actions.addWidget(self.btn_delete_project)
        sidebar_layout.addLayout(sidebar_actions)

        content_layout.addWidget(sidebar, 0)

        right_content = QFrame(content_root)
        right_content.setObjectName("HistoryInspectionContentCard")
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(14, 12, 14, 14)
        right_layout.setSpacing(8)

        self.desc_frame = QFrame(right_content)
        self.desc_frame.setObjectName("InspectionDescFrame")
        desc_layout = QVBoxLayout(self.desc_frame)
        desc_layout.setContentsMargins(14, 10, 14, 10)
        desc_layout.setSpacing(6)
        self.desc_title = QLabel("检测描述", self.desc_frame)
        self.desc_title.setObjectName("InspectionDescTitle")
        self.desc_label = QLabel("当前暂无检测描述。", self.desc_frame)
        self.desc_label.setObjectName("InspectionDescLabel")
        self.desc_label.setWordWrap(True)
        self.desc_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        desc_layout.addWidget(self.desc_title)
        desc_layout.addWidget(self.desc_label)
        right_layout.addWidget(self.desc_frame, 0)

        self.doc_man_widget = DocManWidget(self._get_doc_man_upload_dir, right_content)
        # Backward-compatible state mirrors for existing callers/tests that
        # checked the old stacked child pages' selected facility code.
        self.home_widget = _FacilityCodeMirror()
        self.page_inspection = _FacilityCodeMirror()
        right_layout.addWidget(self.doc_man_widget, 6)

        findings_frame = QFrame(right_content)
        findings_layout = QVBoxLayout(findings_frame)
        findings_layout.setContentsMargins(0, 0, 0, 0)
        findings_layout.setSpacing(8)

        self.findings_title = QLabel("抽检记录", findings_frame)
        self.findings_title.setObjectName("InspectionFindingTitle")
        findings_layout.addWidget(self.findings_title, 0)

        findings_action_row = QHBoxLayout()
        findings_action_row.setContentsMargins(0, 0, 0, 0)
        findings_action_row.setSpacing(8)
        findings_action_row.addStretch()
        self.btn_add_finding = QPushButton("新增记录", findings_frame)
        self.btn_add_finding.setProperty("class", "DocManBlueButton")
        self.btn_add_finding.clicked.connect(self._add_finding)
        findings_action_row.addWidget(self.btn_add_finding)
        self.btn_delete_finding = QPushButton("删除记录", findings_frame)
        self.btn_delete_finding.setProperty("class", "DocManBlueButton")
        self.btn_delete_finding.clicked.connect(self._delete_finding)
        findings_action_row.addWidget(self.btn_delete_finding)
        self.btn_edit_finding = QPushButton("编辑记录", findings_frame)
        self.btn_edit_finding.setProperty("class", "DocManBlueButton")
        self.btn_edit_finding.clicked.connect(self._edit_finding)
        findings_action_row.addWidget(self.btn_edit_finding)

        self.findings_table = QTableWidget(0, 3, findings_frame)
        self.findings_table.setHorizontalHeaderLabels(["节点号", "检验等级", "检验结论"])
        self.findings_table.verticalHeader().setVisible(False)
        self.findings_table.setAlternatingRowColors(False)
        self.findings_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.findings_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.findings_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.findings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.findings_table.verticalHeader().setDefaultSectionSize(
            self.findings_table.verticalHeader().defaultSectionSize() + 10
        )
        self._finding_level_delegate = InspectionLevelDelegate(self.findings_table)
        self.findings_table.setItemDelegateForColumn(INSPECTION_LEVEL_COLUMN, self._finding_level_delegate)
        self.findings_table.setMinimumHeight(170)
        self.findings_table.itemChanged.connect(self._on_finding_item_changed)
        apply_docman_table_style(self.findings_table)
        findings_layout.addWidget(self.findings_table, 1)
        findings_layout.addLayout(findings_action_row)
        right_layout.addWidget(findings_frame, 4)

        self._selected_project: dict | None = None
        self._loading_findings = False
        content_layout.addWidget(right_content, 1)

        self.content_scroll = QScrollArea(self)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_scroll.setWidget(content_root)
        self.main_layout.addWidget(self.content_scroll, 1)

        self.filter_search_bar.valueChanged.connect(self.on_filter_changed)
        self.setStyleSheet(
            """
            QFrame#HistoryInspectionLibraryRoot {
                background-color: #f3f6fb;
            }
            QFrame#HistoryInspectionSidebar {
                background-color: #ffffff;
                border: 1px solid #d7e1ec;
                border-radius: 10px;
            }
            QFrame#HistoryInspectionContentCard {
                background-color: #ffffff;
                border: 1px solid #d7e1ec;
                border-radius: 10px;
            }
            QLabel#HistoryInspectionSidebarTitle {
                color: #12344d;
                font-size: 13pt;
                font-weight: 700;
            }
            QLabel#InspectionFindingTitle {
                min-height: 30px;
                padding: 0 10px;
                border-radius: 4px;
                background-color: #e8f2ff;
                color: #12344d;
                border: 1px solid #b9d9f4;
                font-size: 12pt;
                font-weight: 600;
            }
            QFrame#InspectionDescFrame {
                background-color: #e8f2ff;
                border: 1px solid #b9d9f4;
                border-radius: 8px;
            }
            QLabel#InspectionDescTitle {
                color: #12344d;
                background-color: transparent;
                font-size: 12pt;
                font-weight: 700;
            }
            QLabel#InspectionDescLabel {
                color: #12344d;
                background-color: transparent;
                font-size: 11pt;
            }
            QTreeWidget#HistoryInspectionTree {
                border: none;
                background: transparent;
                color: #12344d;
                font-size: 12pt;
            }
            QTreeWidget#HistoryInspectionTree::item {
                min-height: 30px;
                padding: 4px 6px;
                border-radius: 6px;
            }
            QTreeWidget#HistoryInspectionTree::item:hover {
                background-color: #e8f2ff;
            }
            QTreeWidget#HistoryInspectionTree::item:selected {
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
        self._sync_platform_ui()

    def _group_label(self, project_type: str) -> str:
        return "定期检测" if project_type == "periodic" else "特殊事件检测"

    def _path_root_label(self) -> str:
        values = self.dropdown_bar.get_all_values() if hasattr(self.dropdown_bar, "get_all_values") else {}
        branch = values.get("branch") or self.dropdown_bar.get_value("branch")
        oilfield = values.get("oilfield") or self.dropdown_bar.get_value("oilfield")
        facility = values.get("facility_code") or self.dropdown_bar.get_value("facility_code")
        parts = [branch, oilfield, facility, "检测记录文件"]
        return " / ".join(str(part).strip() for part in parts if str(part or "").strip())

    def _project_storage_segments(self, project_type: str, project: dict | None) -> list[str]:
        root = self._group_label(project_type)
        if not project or not project.get("id"):
            return [root]
        return [root, f"project_{int(project['id'])}"]

    def _file_categories(self) -> list[str]:
        return ["检测文档", "图纸", "Excel", "CAD", "其他"]

    def _get_doc_man_upload_dir(self, path_segments: list[str]) -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        facility = (self.dropdown_bar.get_value("facility_code") or default_platform()["facility_code"]).strip()
        target = os.path.join(project_root, "upload", "history_inspection", facility, *path_segments)
        os.makedirs(target, exist_ok=True)
        return target

    def _reload_sidebar_projects(self, *, selected_type: str | None = None, selected_id: int | None = None):
        self.sidebar_tree.clear()
        self._sidebar_items = {}
        facility_code = self.dropdown_bar.get_value("facility_code") or default_platform()["facility_code"]

        first_project_item = None
        for project_type in ("periodic", "special_event"):
            group_item = QTreeWidgetItem([self._group_label(project_type)])
            group_item.setData(0, Qt.UserRole, {"project_type": project_type, "project": None})
            self.sidebar_tree.addTopLevelItem(group_item)
            self._sidebar_items[project_type] = group_item

            try:
                rows = list_inspection_projects(facility_code, project_type)
            except Exception:
                rows = []
            for index, row in enumerate(rows, start=1):
                project = {
                    "id": row.get("id"),
                    "title": row.get("project_name") or f"检测项目{index}",
                    "year": row.get("project_year") or row.get("event_date") or "",
                    "summary_text": row.get("summary_text") or "",
                    "project_type": project_type,
                }
                text = f"({index}) {project['title']}"
                if project["year"]:
                    text = f"{text}\uff08{self._project_year_label(project['year'])}\uff09"
                item = QTreeWidgetItem([text])
                item.setData(0, Qt.UserRole, {"project_type": project_type, "project": project})
                group_item.addChild(item)
                if first_project_item is None:
                    first_project_item = item
                if selected_type == project_type and selected_id is not None and int(project.get("id") or 0) == int(selected_id):
                    first_project_item = item
            self.sidebar_tree.expandItem(group_item)

        if first_project_item is not None:
            self.sidebar_tree.setCurrentItem(first_project_item)
            self._show_project_files(first_project_item.data(0, Qt.UserRole))
            return

        first_group = self._sidebar_items.get("periodic")
        if first_group is not None:
            self.sidebar_tree.setCurrentItem(first_group)
            self._show_project_files(first_group.data(0, Qt.UserRole))

    def _on_sidebar_item_clicked(self, item: QTreeWidgetItem, _column: int):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, dict):
            self._show_project_files(data)

    @staticmethod
    def _project_year_label(value: str) -> str:
        text = str(value or "").strip().strip("()\uff08\uff09")
        digits = "".join(ch for ch in text[:10] if ch.isdigit())
        if len(digits) >= 4:
            return digits[:4]
        return text.replace("\u5e74", "").strip()

    def _show_project_files(self, data: dict):
        project_type = data.get("project_type") or "periodic"
        project = data.get("project")
        project_name = project.get("title") if project else ""
        self._selected_project = project
        self._update_project_description(project)
        display_segments = [self._group_label(project_type)]
        if project_name:
            display_segments.append(project_name)
        self.doc_man_widget.set_context(
            self._project_storage_segments(project_type, project),
            [],
            self._file_categories(),
            facility_code=self.dropdown_bar.get_value("facility_code"),
            hide_empty_templates=True,
            db_list_mode=True,
            display_profile="inspection",
            path_root_label=self._path_root_label(),
            display_path_segments=display_segments,
            path_hint="检测项目文件按当前检测类型和项目归档，可上传、下载、删除并查看详情。",
            default_work_condition=project_name or self._group_label(project_type),
        )
        self.doc_man_widget.facility_code = self.dropdown_bar.get_value("facility_code")
        self._load_findings(project_type, project)

    def _update_project_description(self, project: dict | None) -> None:
        text = str((project or {}).get("summary_text") or "").strip()
        self.desc_label.setText(text or "当前暂无检测描述。")

    def _current_project_type(self) -> str:
        item = self.sidebar_tree.currentItem()
        if item is not None:
            data = item.data(0, Qt.UserRole)
            if isinstance(data, dict) and data.get("project_type"):
                return str(data.get("project_type"))
        return "periodic"

    def _add_inspection_project(self):
        dialog = AddInspectionProjectDialog(self._current_project_type(), self)
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.get_values()
        project_type = values["project_type"]
        try:
            created = create_inspection_project(
                facility_code=self.dropdown_bar.get_value("facility_code") or default_platform()["facility_code"],
                project_type=project_type,
                project_name=values["project_name"],
                project_year=values["project_year"],
                summary_text=values["summary_text"],
            )
        except Exception as exc:
            QMessageBox.warning(self, "新增失败", str(exc))
            return
        self._reload_sidebar_projects(selected_type=project_type, selected_id=created.get("id") if isinstance(created, dict) else None)

    def _selected_project_data(self) -> tuple[str, dict | None]:
        item = self.sidebar_tree.currentItem()
        if item is None:
            return self._current_project_type(), None
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, dict):
            return self._current_project_type(), None
        return str(data.get("project_type") or self._current_project_type()), data.get("project")

    def _edit_inspection_project(self) -> None:
        project_type, project = self._selected_project_data()
        if not project or not project.get("id"):
            QMessageBox.information(self, "提示", "请先选择一个检测项目。")
            return
        dialog = InspectionProjectEditDialog(
            title_text="编辑检测项目",
            project_name=project.get("title", ""),
            project_year=project.get("year", ""),
            summary_text=project.get("summary_text", ""),
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.get_values()
        try:
            update_inspection_project(
                int(project["id"]),
                project_name=values["project_name"],
                project_year=values["project_year"],
                summary_text=values["summary_text"],
            )
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self._reload_sidebar_projects(selected_type=project_type, selected_id=int(project["id"]))

    def _delete_inspection_project(self) -> None:
        project_type, project = self._selected_project_data()
        if not project or not project.get("id"):
            QMessageBox.information(self, "提示", "请先选择一个检测项目。")
            return
        project_name = str(project.get("title") or "")
        if not ask_yes_no(
            self,
            "删除检测项目",
            f"确认删除检测项目“{project_name}”吗？相关文件会一并隐藏。",
        ):
            return
        try:
            soft_delete_inspection_project_with_files(
                int(project["id"]),
                module_code=DOC_MAN_MODULE_CODE,
                logical_path_prefix="/".join(self._project_storage_segments(project_type, project)),
                facility_code=self.dropdown_bar.get_value("facility_code"),
            )
        except Exception as exc:
            QMessageBox.warning(self, "删除失败", str(exc))
            return
        self._reload_sidebar_projects(selected_type=project_type)
        QMessageBox.information(self, "删除成功", "删除成功")

    def _set_findings_enabled(self, enabled: bool) -> None:
        self.btn_add_finding.setEnabled(enabled)
        self.btn_delete_finding.setEnabled(enabled)
        self.btn_edit_finding.setEnabled(enabled)
        self.findings_table.setEnabled(enabled)

    def _load_findings(self, project_type: str, project: dict | None) -> None:
        project_name = str((project or {}).get("title") or "").strip()
        self.findings_title.setText(f"{project_name}抽检记录" if project_name else "抽检记录")
        self._loading_findings = True
        self.findings_table.clearContents()
        self.findings_table.setRowCount(0)
        project_id = (project or {}).get("id")
        if not project_id:
            self._set_findings_enabled(False)
            self._loading_findings = False
            return
        self._set_findings_enabled(True)
        try:
            rows = list_inspection_findings(int(project_id))
        except Exception as exc:
            self._loading_findings = False
            QMessageBox.warning(self, "加载抽检记录失败", str(exc))
            return
        self.findings_table.setRowCount(len(rows))
        for row, info in enumerate(rows):
            self._set_finding_text_item(row, 0, str(info.get("item_code") or ""))
            self._set_finding_text_item(row, INSPECTION_LEVEL_COLUMN, str(info.get("risk_level") or ""))
            self._set_finding_text_item(row, 2, str(info.get("conclusion") or ""))
        self._loading_findings = False

    def _set_finding_text_item(self, row: int, col: int, text: str) -> None:
        if col == INSPECTION_LEVEL_COLUMN:
            text = normalize_inspection_level(text)
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        if col == INSPECTION_LEVEL_COLUMN:
            font = item.font()
            font.setPointSize(max(font.pointSize(), 14))
            item.setFont(font)
        item.setToolTip(item.text())
        self.findings_table.setItem(row, col, item)

    def _finding_cell_text(self, row: int, col: int) -> str:
        item = self.findings_table.item(row, col)
        return item.text().strip() if item else ""

    def _collect_findings(self) -> list[dict]:
        rows: list[dict] = []
        for row in range(self.findings_table.rowCount()):
            values = [self._finding_cell_text(row, col) for col in range(3)]
            if any(values):
                rows.append(
                    {
                        "item_code": values[0],
                        "risk_level": values[1],
                        "conclusion": values[2],
                    }
                )
        return rows

    def _save_findings(self) -> None:
        project_id = (self._selected_project or {}).get("id")
        if not project_id:
            return
        replace_inspection_findings(int(project_id), self._collect_findings())

    def _add_finding(self) -> None:
        if not (self._selected_project or {}).get("id"):
            QMessageBox.information(self, "提示", "请先选择一个检测项目。")
            return
        self._loading_findings = True
        row = self.findings_table.rowCount()
        self.findings_table.insertRow(row)
        self._set_finding_text_item(row, 0, "")
        self._set_finding_text_item(row, INSPECTION_LEVEL_COLUMN, "Ⅰ")
        self._set_finding_text_item(row, 2, "")
        self._loading_findings = False
        self._save_findings()

    def _delete_finding(self) -> None:
        row = self.findings_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条抽检记录。")
            return
        self._loading_findings = True
        self.findings_table.removeRow(row)
        self._loading_findings = False
        self._save_findings()

    def _edit_finding(self) -> None:
        if not (self._selected_project or {}).get("id"):
            QMessageBox.information(self, "提示", "请先选择一个检测项目。")
            return
        row = self.findings_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条抽检记录。")
            return
        values = [self._finding_cell_text(row, col) for col in range(3)]
        dialog = InspectionFindingDialog(
            title_text="编辑抽检记录",
            item_code=values[0],
            risk_level=values[1],
            conclusion=values[2],
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        result = dialog.get_values()
        self._loading_findings = True
        self._set_finding_text_item(row, 0, result["item_code"])
        self._set_finding_text_item(row, INSPECTION_LEVEL_COLUMN, result["risk_level"])
        self._set_finding_text_item(row, 2, result["conclusion"])
        self._loading_findings = False
        self._save_findings()

    def _on_finding_item_changed(self, _item: QTableWidgetItem) -> None:
        if self._loading_findings:
            return
        self._save_findings()

    def _set_dropdown_visible(self, visible: bool):
        self.filter_search_bar.set_filter_visible(visible)

    def on_filter_changed(self, key: str, value: str):
        self._sync_platform_ui(changed_key=key)

    def _search_documents(self, code: str = "", name: str = ""):
        code = (code or "").strip().lower()
        name = (name or "").strip().lower()
        if not code and not name:
            current = self.sidebar_tree.currentItem()
            if current is not None:
                self._show_project_files(current.data(0, Qt.UserRole))
            return
        if not is_file_db_configured():
            QMessageBox.information(self, "提示", "当前未配置文件数据库，无法跨分类搜索。")
            return
        self.doc_man_widget.set_context(
            [],
            [],
            self._file_categories(),
            facility_code=self.dropdown_bar.get_value("facility_code"),
            overlay_from_db=False,
            hide_empty_templates=False,
            db_list_mode=True,
            display_profile="inspection",
            path_root_label=self._path_root_label(),
            display_path_segments=["搜索结果"],
            path_hint="按文件编码/文件名搜索检测记录文件。",
            default_work_condition="搜索结果",
            document_code_query=code,
            document_title_query=name,
            logical_path_prefixes=["定期检测", "特殊事件检测"],
        )

    def _sync_platform_ui(self, changed_key: str | None = None):
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        platform_name = platform["facility_name"]
        facility_code = platform["facility_code"]
        self.home_widget.set_facility_code(facility_code)
        self.page_inspection.set_facility_code(facility_code)
        self.doc_man_widget.facility_code = facility_code
        if hasattr(self, "sidebar_tree"):
            self._reload_sidebar_projects()
        window = self.window()
        if hasattr(window, "set_current_platform_name"):
            window.set_current_platform_name(platform_name)

    def get_current_platform_name(self):
        return self.dropdown_bar.get_value("facility_name")

    def _project_name_from_logical_path(self, logical_path: str) -> str:
        project_id = ""
        for part in str(logical_path or "").replace("\\", "/").split("/"):
            if part.startswith("project_"):
                project_id = part[len("project_") :]
                break
        if not project_id:
            return ""
        for top_index in range(self.sidebar_tree.topLevelItemCount()):
            group_item = self.sidebar_tree.topLevelItem(top_index)
            for child_index in range(group_item.childCount()):
                child = group_item.child(child_index)
                data = child.data(0, Qt.UserRole)
                if not isinstance(data, dict):
                    continue
                project = data.get("project") or {}
                if str(project.get("id") or "") == project_id:
                    return str(project.get("title") or "").strip()
        return ""
