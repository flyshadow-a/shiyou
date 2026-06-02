# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pages.doc_man import DocManWidget
from pages.file_management_ui_constants import FILE_MANAGEMENT_SIDEBAR_WIDTH
from services.file_db_adapter import FileBackendError, is_file_db_configured, load_docman_record_list


DOCUMENT_LIBRARY_QSS = """
QFrame#DocumentLibraryRoot {
    background-color: #f3f6fb;
    border: none;
}
QFrame#DocumentSidebar {
    background-color: #ffffff;
    border: 1px solid #d7e1ec;
    border-radius: 10px;
}
QLabel#DocumentSidebarTitle {
    color: #12344d;
    font-size: 13pt;
    font-weight: 700;
}
QPushButton[class="DocumentNavButton"] {
    min-height: 32px;
    padding: 4px 10px;
    border: none;
    border-radius: 7px;
    background-color: transparent;
    color: #1f2937;
    font-size: 12pt;
    text-align: left;
}
QPushButton[class="DocumentNavButton"]:hover {
    background-color: #e8f2ff;
    color: #0f5ea5;
}
QPushButton[class="DocumentNavButton"][selected="true"] {
    background-color: #d8ebff;
    color: #12344d;
    border: 1px solid #7fb8e8;
    font-weight: 700;
}
QTreeWidget#DocumentTree {
    border: none;
    background: transparent;
    color: #12344d;
    font-size: 12pt;
}
QTreeWidget#DocumentTree::item {
    min-height: 30px;
    padding: 4px 6px;
    border-radius: 6px;
}
QTreeWidget#DocumentTree::item:hover {
    background-color: #e8f2ff;
}
QTreeWidget#DocumentTree::item:selected {
    background-color: #d8ebff;
    color: #12344d;
    border: 1px solid #7fb8e8;
}
QFrame#DocumentContentCard {
    background-color: #ffffff;
    border: 1px solid #d7e1ec;
    border-radius: 10px;
}
QLabel#DocumentContentTitle {
    color: #12344d;
    font-size: 14pt;
    font-weight: 700;
}
QLabel#DocumentContentHint {
    color: #5f6f82;
    font-size: 11pt;
}
QFrame#DocumentDescriptionCard {
    background-color: #e8f2ff;
    border: 1px solid #b9d9f4;
    border-radius: 12px;
}
QLabel#DocumentDescriptionTitle {
    color: #12344d;
    font-size: 12pt;
    font-weight: 700;
    background: transparent;
}
QLabel#DocumentDescriptionText {
    color: #12344d;
    font-size: 12pt;
    background: transparent;
}
QPushButton#DescriptionEditButton {
    min-height: 28px;
    padding: 0 14px;
    border: none;
    border-radius: 5px;
    background-color: #ffffff;
    color: #0f5ea5;
    font-size: 11pt;
    font-weight: 600;
}
QPushButton#DescriptionEditButton:hover {
    background-color: #e8f2ff;
}
"""


class DocumentLibraryWidget(QFrame):
    navigationStateChanged = pyqtSignal(bool)
    descriptionEditRequested = pyqtSignal()

    def __init__(
        self,
        sections: list[dict[str, Any]],
        *,
        module_code: str = "doc_man",
        show_description: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("DocumentLibraryRoot")
        self.setStyleSheet(DOCUMENT_LIBRARY_QSS)
        self._sections = [dict(item) for item in sections]
        self._module_code = module_code
        self._selected_index = 0 if self._sections else -1
        self.facility_code = ""
        self.platform_name = ""
        self.platform_description = ""
        self._show_description = bool(show_description)
        self._nav_buttons: list[QPushButton] = []
        self._section_items: dict[int, QTreeWidgetItem] = {}
        self._current_context_signature: tuple[int, str, str] | None = None
        self._pending_initial_select = False
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 8, 12, 12)
        root_layout.setSpacing(12)

        sidebar = QFrame(self)
        sidebar.setObjectName("DocumentSidebar")
        sidebar.setFixedWidth(FILE_MANAGEMENT_SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        title = QLabel("设计文件", sidebar)
        title.setObjectName("DocumentSidebarTitle")
        sidebar_layout.addWidget(title)

        self.nav_tree = QTreeWidget(sidebar)
        self.nav_tree.setObjectName("DocumentTree")
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setIndentation(18)
        self.nav_tree.itemClicked.connect(self._on_tree_item_clicked)
        sidebar_layout.addWidget(self.nav_tree, 1)
        self._build_tree_nav()
        root_layout.addWidget(sidebar, 0)

        content = QFrame(self)
        content.setObjectName("DocumentContentCard")
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 12, 14, 14)
        content_layout.setSpacing(8)

        if self._show_description:
            self.description_card = QFrame(content)
            self.description_card.setObjectName("DocumentDescriptionCard")
            desc_layout = QVBoxLayout(self.description_card)
            desc_layout.setContentsMargins(16, 12, 16, 12)
            desc_layout.setSpacing(6)
            desc_title = QLabel("平台描述", self.description_card)
            desc_title.setObjectName("DocumentDescriptionTitle")
            self.description_label = QLabel(self.description_card)
            self.description_label.setObjectName("DocumentDescriptionText")
            self.description_label.setWordWrap(True)
            desc_layout.addWidget(desc_title)
            desc_layout.addWidget(self.description_label)
            desc_action = QHBoxLayout()
            desc_action.setContentsMargins(0, 2, 0, 0)
            desc_action.addStretch()
            self.description_edit_button = QPushButton("编辑平台描述", self.description_card)
            self.description_edit_button.setObjectName("DescriptionEditButton")
            self.description_edit_button.clicked.connect(self.descriptionEditRequested.emit)
            desc_action.addWidget(self.description_edit_button, 0, Qt.AlignRight)
            desc_layout.addLayout(desc_action)
            content_layout.addWidget(self.description_card)

        self.content_title = QLabel(content)
        self.content_title.setObjectName("DocumentContentTitle")
        self.content_title.setVisible(False)
        content_layout.addWidget(self.content_title)

        self.content_hint = QLabel(content)
        self.content_hint.setObjectName("DocumentContentHint")
        self.content_hint.setWordWrap(True)
        self.content_hint.setVisible(False)
        content_layout.addWidget(self.content_hint)

        self.doc_man_widget = DocManWidget(self._get_doc_man_upload_dir, content)
        content_layout.addWidget(self.doc_man_widget, 1)
        root_layout.addWidget(content, 1)

    def _build_tree_nav(self) -> None:
        self.nav_tree.clear()
        self._section_items.clear()
        node_by_path: dict[tuple[str, ...], QTreeWidgetItem] = {}
        for idx, section in enumerate(self._sections):
            raw_path = section.get("tree_path") or section.get("path_segments") or [section.get("label") or ""]
            tree_path = [str(part).strip() for part in raw_path if str(part).strip()]
            if not tree_path:
                continue
            parent_item: QTreeWidgetItem | None = None
            current_parts: list[str] = []
            for part in tree_path:
                current_parts.append(part)
                key = tuple(current_parts)
                item = node_by_path.get(key)
                if item is None:
                    item = QTreeWidgetItem([part])
                    item.setData(0, Qt.UserRole, None)
                    if parent_item is None:
                        self.nav_tree.addTopLevelItem(item)
                    else:
                        parent_item.addChild(item)
                    node_by_path[key] = item
                parent_item = item
            if parent_item is not None:
                parent_item.setData(0, Qt.UserRole, idx)
                self._section_items[idx] = parent_item
        self.nav_tree.collapseAll()

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        index = item.data(0, Qt.UserRole)
        if isinstance(index, int):
            self._select_section(index, force=True)

    def _get_doc_man_upload_dir(self, path_segments: list[str]) -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        facility = (self.facility_code or "default").strip() or "default"
        target = os.path.join(project_root, "upload", self._module_code, facility, *path_segments)
        os.makedirs(target, exist_ok=True)
        return target

    def _select_section(self, index: int, *, force: bool = False) -> None:
        if index < 0 or index >= len(self._sections):
            return
        self._selected_index = index
        if not self.facility_code:
            return
        signature = (index, self.facility_code, self._module_code)
        if not force and signature == self._current_context_signature:
            return
        item = self._section_items.get(index)
        if item is not None:
            self.nav_tree.setCurrentItem(item)

        section = self._sections[index]
        label = str(section.get("label") or "")
        hint = str(section.get("hint") or "")
        path_segments = list(section.get("path_segments") or [label])
        display_path_segments = list(section.get("tree_path") or path_segments)
        categories = list(section.get("categories") or ["其他"])
        records = list(section.get("records") or [])
        display_profile = str(section.get("display_profile") or "design")
        self.content_title.setText(label)
        self.content_hint.setText(hint)
        self.content_title.setVisible(False)
        self.content_hint.setVisible(False)
        self.doc_man_widget.set_context(
            path_segments,
            records,
            categories,
            facility_code=self.facility_code,
            hide_empty_templates=True,
            db_list_mode=True,
            display_profile=display_profile,
            path_root_label="设计文件",
            display_path_segments=display_path_segments,
            path_hint=hint,
        )
        self._current_context_signature = signature
        self.navigationStateChanged.emit(True)

    def clear_search(self) -> None:
        self._select_section(self._selected_index, force=True)

    def search_all_documents(self, code_query: str = "", name_query: str = "") -> None:
        code = (code_query or "").strip().lower()
        name = (name_query or "").strip().lower()
        if not code and not name:
            self.clear_search()
            return
        if not is_file_db_configured():
            QMessageBox.information(self, "提示", "当前未配置文件数据库，无法跨分类搜索。")
            return
        try:
            records = load_docman_record_list(
                [],
                facility_code=self.facility_code,
                document_code_query=code,
                document_title_query=name,
            )
        except FileBackendError as exc:
            QMessageBox.warning(self, "搜索失败", str(exc))
            return

        matched = records
        upload_path_segments: list[str] = []
        if 0 <= self._selected_index < len(self._sections):
            current_section = self._sections[self._selected_index]
            upload_path_segments = list(
                current_section.get("path_segments") or [current_section.get("label") or "搜索结果"]
            )
        self.content_title.setText("搜索结果")
        self.content_hint.setText(f"按文件编码/文件名搜索全部文件，共 {len(matched)} 条。")
        self.content_title.setVisible(False)
        self.content_hint.setVisible(False)
        self.doc_man_widget.set_context(
            upload_path_segments,
            matched,
            ["未分类/其他", "其他"],
            facility_code=self.facility_code,
            overlay_from_db=False,
            hide_empty_templates=False,
            db_list_mode=False,
            display_profile="design",
            path_root_label="设计文件",
            display_path_segments=["搜索结果"],
            path_hint=f"按文件编码/文件名搜索全部文件，共 {len(matched)} 条。",
        )

    @staticmethod
    def _record_matches_query(record: dict, code_query: str, name_query: str) -> bool:
        code_text = " ".join(
            str(record.get(key) or "")
            for key in ("document_code", "logical_path", "filename")
        ).lower()
        name_text = " ".join(
            str(record.get(key) or "")
            for key in ("document_title", "filename", "logical_path")
        ).lower()
        if code_query and code_query not in code_text:
            return False
        if name_query and name_query not in name_text:
            return False
        return True

    def set_facility_code(self, code: str) -> None:
        new_code = (code or "").strip()
        if new_code == self.facility_code and self._current_context_signature is not None:
            return
        self.facility_code = new_code
        self._current_context_signature = None
        self._schedule_select_current_section()

    def _schedule_select_current_section(self) -> None:
        if self._pending_initial_select:
            return
        self._pending_initial_select = True
        QTimer.singleShot(0, self._select_current_section_after_event_loop)

    def _select_current_section_after_event_loop(self) -> None:
        self._pending_initial_select = False
        self._select_section(self._selected_index, force=True)

    def set_platform_name(self, name: str) -> None:
        self.platform_name = name or ""

    def set_platform_description(self, description: str) -> None:
        self.platform_description = description or ""
        if hasattr(self, "description_label"):
            self.description_label.setText(self.platform_description)
            self.description_card.setVisible(bool(self.platform_description.strip()))

    def set_description_edit_visible(self, visible: bool) -> None:
        if hasattr(self, "description_edit_button"):
            self.description_edit_button.setVisible(bool(visible))
