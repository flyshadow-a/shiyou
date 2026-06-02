# -*- coding: utf-8 -*-

import os
import shutil
from typing import Callable, List, Optional

from PyQt5.QtCore import QDateTime, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.file_name_utils import (
    normalize_download_save_path,
    sanitize_download_filename,
    unique_download_target_path,
)
from services.file_db_adapter import (
    append_docman_file,
    FileBackendError,
    hard_delete_record,
    is_file_db_configured,
    load_docman_records,
    load_docman_record_list,
    replace_docman_list_file,
    replace_docman_file,
    resolve_storage_path,
    update_file_record,
)
from pages.file_management_platforms import find_platform
from shiyou_db.document_code_parser import parse_document_code_from_name


DOC_MAN_TABLE_QSS = """
QTableWidget {
    gridline-color: #d1d5db;
    background-color: #f9fafb;
    border: 1px solid #d9e2ec;
    border-radius: 8px;
}
QHeaderView::section {
    background-color: #eaf1f8;
    color: #12344d;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #d1d5db;
    border-bottom: 1px solid #d1d5db;
    font-weight: 600;
    font-size: 12pt;
}
QTableWidget::item {
    padding: 4px 6px;
    color: #1f2937;
}
QTableWidget::item:selected {
    background-color: #cfe7ff;
    color: #12344d;
}
"""

DOC_MAN_BLUE_BUTTON_QSS = """
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

DOC_MAN_CELL_BUTTON_QSS = """
QPushButton[class="DocManCellButton"] {
    min-height: 26px;
    padding: 0 10px;
    border: none;
    border-radius: 5px;
    background-color: #1677c5;
    color: #ffffff;
    font-size: 12pt;
    font-weight: 600;
}
QPushButton[class="DocManCellButton"]:hover {
    background-color: #2186d4;
}
"""


def apply_docman_table_style(table: QTableWidget) -> None:
    table_font = table.font()
    table_font.setPointSize(12)
    table.setFont(table_font)
    table.setAlternatingRowColors(False)
    table.setStyleSheet(DOC_MAN_TABLE_QSS)


class CheckBoxHeader(QHeaderView):
    toggled = pyqtSignal(bool)

    def __init__(self, orientation: Qt.Orientation, parent=None, check_column: int = 0):
        super().__init__(orientation, parent)
        self._check_column = check_column
        self._checked = False
        self._syncing_checkbox = False
        self.setSectionsClickable(True)
        self._checkbox = QCheckBox(self)
        self._checkbox.setFocusPolicy(Qt.NoFocus)
        self._checkbox.setCursor(Qt.PointingHandCursor)
        self._checkbox.setToolTip("全选/取消全选")
        self._checkbox.stateChanged.connect(self._on_checkbox_state_changed)
        self.sectionResized.connect(lambda *_args: self._sync_checkbox_geometry())
        self.geometriesChanged.connect(self._sync_checkbox_geometry)

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        if self._checked == checked and self._checkbox.isChecked() == checked:
            return
        self._checked = checked
        self._syncing_checkbox = True
        self._checkbox.setChecked(checked)
        self._syncing_checkbox = False
        self.updateSection(self._check_column)

    def _on_checkbox_state_changed(self, state: int) -> None:
        if self._syncing_checkbox:
            return
        checked = state == Qt.Checked
        if self._checked == checked:
            return
        self._checked = checked
        self.updateSection(self._check_column)
        self.toggled.emit(checked)

    def _sync_checkbox_geometry(self) -> None:
        section_x = self.sectionViewportPosition(self._check_column)
        section_w = self.sectionSize(self._check_column)
        if section_x < 0 or section_w <= 0:
            self._checkbox.hide()
            return
        hint = self._checkbox.sizeHint()
        width = max(18, hint.width())
        height = max(18, hint.height())
        self._checkbox.setGeometry(
            section_x + (section_w - width) // 2,
            (self.height() - height) // 2,
            width,
            height,
        )
        self._checkbox.show()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_checkbox_geometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_checkbox_geometry()

    def mousePressEvent(self, event) -> None:
        if self.logicalIndexAt(event.pos()) == self._check_column:
            checked = not self._checked
            self.setChecked(checked)
            self.toggled.emit(checked)
            return
        super().mousePressEvent(event)


class UploadStagingDialog(QDialog):
    COLS = [
        "序号",
        "文件名",
        "编码",
        "设计阶段",
        "专业类别",
        "专业",
        "文件分类",
        "单体",
        "模块",
        "图号",
        "状态",
        "路径",
    ]

    def __init__(self, *, default_category: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("待上传文件")
        self.resize(1180, 560)
        self._default_category = (default_category or "").strip()
        self._items: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background-color: #ffffff;
            }
            QLabel#UploadHint {
                color: #334155;
                font-size: 12pt;
            }
            """
            + DOC_MAN_TABLE_QSS
            + DOC_MAN_BLUE_BUTTON_QSS
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        hint = QLabel(
            "选择文件后，系统会按“设计阶段-文件分类-单体(模块)-专业-图号(次级序列号)”解析文件名，"
            "无法识别的文件会归入未分类/其他。",
            self,
        )
        hint.setObjectName("UploadHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.btn_pick_files = QPushButton("选择文件", self)
        self.btn_pick_files.setProperty("class", "DocManBlueButton")
        self.btn_pick_files.clicked.connect(self._pick_files)
        action_row.addWidget(self.btn_pick_files)
        layout.addLayout(action_row)

        self.table = QTableWidget(0, len(self.COLS), self)
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(36)
        apply_docman_table_style(self.table)
        layout.addWidget(self.table, 1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        ok_button = self.buttons.button(QDialogButtonBox.Ok)
        cancel_button = self.buttons.button(QDialogButtonBox.Cancel)
        ok_button.setText("确认上传")
        cancel_button.setText("取消")
        ok_button.setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择待上传文件", "", "所有文件 (*.*)")
        if not paths:
            return
        seen = {item["path"] for item in self._items}
        for path in paths:
            if path in seen:
                continue
            meta = parse_document_code_from_name(os.path.basename(path))
            category = str(meta.get("file_class_name") or "").strip()
            if not category:
                category = self._default_category or "未分类/其他"
            self._items.append(
                {
                    "path": path,
                    "category": category,
                    "meta": meta,
                }
            )
            seen.add(path)
        self._refresh_table()

    @staticmethod
    def _status_label(status: str) -> str:
        mapping = {
            "recognized": "已识别",
            "partial": "部分识别",
            "unclassified": "未分类",
        }
        return mapping.get(status or "", status or "")

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            meta = item["meta"]
            values = [
                str(row + 1),
                os.path.basename(item["path"]),
                str(meta.get("document_code") or ""),
                str(meta.get("design_stage_name") or ""),
                str(meta.get("discipline_group") or ""),
                str(meta.get("discipline_name") or ""),
                str(meta.get("file_class_name") or item.get("category") or ""),
                str(meta.get("asset_unit_name") or meta.get("asset_unit_code") or ""),
                str(meta.get("module_unit_name") or "上部组块"),
                str(meta.get("drawing_no") or ""),
                self._status_label(str(meta.get("recognition_status") or "")),
                item["path"],
            ]
            for col, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                align = Qt.AlignLeft | Qt.AlignVCenter if col in {1, 11} else Qt.AlignCenter
                table_item.setTextAlignment(int(align))
                table_item.setToolTip(value)
                self.table.setItem(row, col, table_item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self._items))

    def selected_items(self) -> list[dict]:
        return [dict(item) for item in self._items]


class DocManWidget(QFrame):
    COL_CHECK = 0
    COL_INDEX = 1
    COL_STAGE = 2
    COL_WORK_CONDITION = 3
    COL_FILENAME = 4
    COL_FMT = 5
    COL_MTIME = 6
    COL_CATEGORY = 7
    COL_REMARK = 8
    COL_DETAIL = 9

    def __init__(self, storage_dir_getter: Callable[[List[str]], str], parent=None):
        super().__init__(parent)
        self._storage_dir_getter = storage_dir_getter
        self._path_segments: List[str] = []
        self._records: List[dict] = []
        self._category_options: List[str] = []
        self._facility_code: str | None = None
        self._hide_empty_templates = False
        self._db_list_mode = False
        self._visible_row_indices: List[int] = []
        self._show_work_condition = False
        self._custom_upload_handler = None
        self._custom_new_upload_handler = None
        self._custom_delete_handler = None
        self._custom_download_handler = None
        self._page_size = 20
        self._current_page = 0
        self._display_profile = "generic"
        self._path_root_label = ""
        self._display_path_segments: List[str] = []
        self._path_hint = ""
        self._default_work_condition = ""
        self._context_load_token = 0
        self._build_ui()

    def set_action_handlers(
        self,
        *,
        upload_handler=None,
        new_upload_handler=None,
        delete_handler=None,
        download_handler=None,
    ):
        self._custom_upload_handler = upload_handler
        self._custom_new_upload_handler = new_upload_handler
        self._custom_delete_handler = delete_handler
        self._custom_download_handler = download_handler

    def _build_ui(self):
        self.setObjectName("DocManWidget")
        self.setStyleSheet(
            """
            QFrame#DocManWidget {
                background-color: #ffffff;
            }
            QFrame#DocManPathBar {
                background-color: #ffffff;
                border-top: none;
                border-bottom: 1px solid #d7e1ec;
                border-left: none;
                border-right: none;
                border-radius: 0;
            }
            QLabel#DocManPathLabel {
                color: #12344d;
                background-color: transparent;
                font-size: 13pt;
                font-weight: 700;
            }
            QLabel#DocManPathHint {
                color: #5f6f82;
                background-color: transparent;
                font-size: 10.5pt;
            }
            QCheckBox {
                spacing: 0px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            """
            + DOC_MAN_TABLE_QSS
            + DOC_MAN_BLUE_BUTTON_QSS
            + DOC_MAN_CELL_BUTTON_QSS
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.path_bar = QFrame(self)
        self.path_bar.setObjectName("DocManPathBar")
        path_layout = QVBoxLayout(self.path_bar)
        path_layout.setContentsMargins(12, 6, 12, 7)
        path_layout.setSpacing(2)
        self.path_label = QLabel("", self.path_bar)
        self.path_label.setObjectName("DocManPathLabel")
        self.path_label.setWordWrap(True)
        path_layout.addWidget(self.path_label, 0)
        self.path_hint_label = QLabel("", self.path_bar)
        self.path_hint_label.setObjectName("DocManPathHint")
        self.path_hint_label.setWordWrap(True)
        path_layout.addWidget(self.path_hint_label, 0)
        layout.addWidget(self.path_bar, 0)

        self.table = QTableWidget(0, 10, self)
        self._check_header = CheckBoxHeader(Qt.Horizontal, self.table, self.COL_CHECK)
        self._check_header.toggled.connect(self._set_visible_rows_checked)
        self.table.setHorizontalHeader(self._check_header)
        self._apply_profile_headers()
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        apply_docman_table_style(self.table)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._open_row_file)

        header = self.table.horizontalHeader()
        header.setMinimumHeight(34)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(self.COL_CHECK, header.Fixed)
        header.setSectionResizeMode(self.COL_INDEX, header.Fixed)
        header.setSectionResizeMode(self.COL_STAGE, header.Fixed)
        header.setSectionResizeMode(self.COL_WORK_CONDITION, header.Stretch)
        header.setSectionResizeMode(self.COL_FILENAME, header.Stretch)
        header.setSectionResizeMode(self.COL_FMT, header.Fixed)
        header.setSectionResizeMode(self.COL_MTIME, header.Fixed)
        header.setSectionResizeMode(self.COL_CATEGORY, header.Stretch)
        header.setSectionResizeMode(self.COL_REMARK, header.Stretch)
        header.setSectionResizeMode(self.COL_DETAIL, header.Fixed)
        self.table.setColumnWidth(self.COL_CHECK, 42)
        self.table.setColumnWidth(self.COL_INDEX, 64)
        self.table.setColumnWidth(self.COL_STAGE, 130)
        self.table.setColumnWidth(self.COL_WORK_CONDITION, 150)
        self.table.setColumnWidth(self.COL_FMT, 110)
        self.table.setColumnWidth(self.COL_MTIME, 150)
        self.table.setColumnWidth(self.COL_DETAIL, 80)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self._apply_column_visibility()
        layout.addWidget(self.table, 1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.addStretch()

        self.btn_add = QPushButton("上传", self)
        self.btn_add.setProperty("class", "DocManBlueButton")
        self.btn_add.clicked.connect(self._open_upload_staging)
        action_row.addWidget(self.btn_add)

        self.btn_delete = QPushButton("删除", self)
        self.btn_delete.setProperty("class", "DocManBlueButton")
        self.btn_delete.clicked.connect(self._delete_checked_rows)
        action_row.addWidget(self.btn_delete)

        self.btn_download = QPushButton("下载", self)
        self.btn_download.setProperty("class", "DocManBlueButton")
        self.btn_download.clicked.connect(self._download_checked_rows)
        action_row.addWidget(self.btn_download)

        self.btn_prev_page = QPushButton("上一页", self)
        self.btn_prev_page.setProperty("class", "DocManBlueButton")
        self.btn_prev_page.clicked.connect(self._go_prev_page)
        action_row.addWidget(self.btn_prev_page)

        self.page_label = QLabel("第 1 / 1 页", self)
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet("QLabel { color: #12344d; font-size: 12pt; padding: 0 8px; }")
        action_row.addWidget(self.page_label)

        self.btn_next_page = QPushButton("下一页", self)
        self.btn_next_page.setProperty("class", "DocManBlueButton")
        self.btn_next_page.clicked.connect(self._go_next_page)
        action_row.addWidget(self.btn_next_page)

        layout.addLayout(action_row)

    def set_context(
        self,
        path_segments: List[str],
        records: List[dict],
        category_options: List[str],
        facility_code: str | None = None,
        overlay_from_db: bool = True,
        hide_empty_templates: bool = False,
        db_list_mode: bool = False,
        show_work_condition: bool = False,
        display_profile: str = "generic",
        path_root_label: str = "",
        display_path_segments: Optional[List[str]] = None,
        path_hint: str = "",
        default_work_condition: str = "",
    ):
        self._path_segments = list(path_segments)
        self._path_root_label = (path_root_label or "").strip()
        self._display_path_segments = (
            [str(part) for part in display_path_segments]
            if display_path_segments is not None
            else [str(part) for part in path_segments]
        )
        self._path_hint = (path_hint or "").strip()
        self._default_work_condition = (default_work_condition or "").strip()
        self._db_list_mode = bool(db_list_mode)
        self._records = [dict(rec) for rec in records] if not self._db_list_mode else [
            dict(rec) for rec in records if self._record_has_content(rec)
        ]
        self._category_options = list(category_options)
        self._facility_code = (facility_code or "").strip() or None
        self._hide_empty_templates = bool(hide_empty_templates)
        self._show_work_condition = bool(show_work_condition)
        self._display_profile = self._normalize_display_profile(display_profile)
        self._current_page = 0
        self._context_load_token += 1
        token = self._context_load_token
        self._normalize_records()
        self._update_path_label()
        self.refresh()
        if self._db_list_mode or overlay_from_db:
            QTimer.singleShot(0, lambda token=token: self._finish_deferred_context_load(token))

    def _finish_deferred_context_load(self, token: int) -> None:
        if token != self._context_load_token:
            return
        if self._db_list_mode:
            self._load_record_list_from_db()
        else:
            self._overlay_records_from_db()
        self._normalize_records()
        self.refresh()

    def _update_path_label(self) -> None:
        if not hasattr(self, "path_label"):
            return
        parts: List[str] = self._platform_path_prefix()
        root_parts = self._split_display_path_label(self._path_root_label)
        if root_parts and not self._path_parts_include_facility(root_parts):
            parts.extend(root_parts)
        elif root_parts:
            parts = root_parts
        parts.extend(self._display_segment(part) for part in self._display_path_segments if str(part).strip())
        clean_parts = [part for part in parts if str(part).strip()]
        self.path_label.setText(" > ".join(clean_parts) if clean_parts else "未选择文件目录")
        if hasattr(self, "path_hint_label"):
            self.path_hint_label.setText(self._path_hint)
            self.path_hint_label.setVisible(bool(self._path_hint))

    def _platform_path_prefix(self) -> List[str]:
        if not self._facility_code:
            return []
        platform = find_platform(facility_code=self._facility_code)
        return [
            str(platform.get("branch") or "").strip(),
            str(platform.get("oilfield") or "").strip(),
            str(platform.get("facility_code") or self._facility_code).strip(),
        ]

    @staticmethod
    def _split_display_path_label(label: str) -> List[str]:
        text = str(label or "").replace(">", "/")
        return [part.strip() for part in text.split("/") if part.strip()]

    def _path_parts_include_facility(self, parts: List[str]) -> bool:
        code = str(self._facility_code or "").strip()
        return bool(code and any(part == code for part in parts))

    @staticmethod
    def _display_segment(segment: object) -> str:
        text = str(segment or "").strip()
        mapping = {
            "complete": "完工检测",
            "periodic": "定期检测1-N",
            "first": "第一次检测",
            "nth": "第N次检测",
            "history_sampling": "特殊事件检测",
            "search": "搜索结果",
        }
        return mapping.get(text, text)

    @staticmethod
    def _normalize_display_profile(profile: str) -> str:
        value = (profile or "generic").strip().lower()
        return value if value in {"generic", "design", "rebuild", "model", "inspection"} else "generic"

    def _apply_profile_headers(self) -> None:
        header_map = {
            "generic": [" ", "序号", "", "工况", "文件名", "文件格式", "修改时间", "类别", "备注", "操作"],
            "design": [" ", "序号", "", "编码", "名称", "设计阶段", "专业", "类别", "备注", "操作"],
            "rebuild": [" ", "序号", "", "编码", "名称", "设计阶段", "专业", "类别", "备注", "操作"],
            "model": [" ", "序号", "阶段", "名称", "分析类别", "文件格式", "修改时间", "模型类别", "备注", "操作"],
            "inspection": [" ", "序号", "", "检测项目名称", "文件名称", "文件格式", "修改时间", "类别", "备注", "操作"],
        }
        self.table.setHorizontalHeaderLabels(header_map.get(self._display_profile, header_map["generic"]))
        self._apply_profile_column_widths()

    def _apply_profile_column_widths(self) -> None:
        self.table.setColumnWidth(self.COL_CHECK, 42)
        self.table.setColumnWidth(self.COL_INDEX, 64)
        self.table.setColumnWidth(self.COL_DETAIL, 80)
        self.table.setColumnWidth(self.COL_STAGE, 130)
        if self._display_profile in {"design", "rebuild"}:
            self.table.setColumnWidth(self.COL_WORK_CONDITION, 210)
            self.table.setColumnWidth(self.COL_FMT, 170)
            self.table.setColumnWidth(self.COL_MTIME, 140)
            self.table.setColumnWidth(self.COL_CATEGORY, 140)
        elif self._display_profile == "model":
            self.table.setColumnWidth(self.COL_STAGE, 150)
            self.table.setColumnWidth(self.COL_WORK_CONDITION, 240)
            self.table.setColumnWidth(self.COL_FILENAME, 110)
            self.table.setColumnWidth(self.COL_FMT, 110)
            self.table.setColumnWidth(self.COL_MTIME, 150)
            self.table.setColumnWidth(self.COL_CATEGORY, 160)
        elif self._display_profile == "inspection":
            self.table.setColumnWidth(self.COL_WORK_CONDITION, 180)
            self.table.setColumnWidth(self.COL_FILENAME, 260)
            self.table.setColumnWidth(self.COL_CATEGORY, 140)
        else:
            self.table.setColumnWidth(self.COL_WORK_CONDITION, 150)
            self.table.setColumnWidth(self.COL_FMT, 110)
            self.table.setColumnWidth(self.COL_MTIME, 150)

    def _overlay_records_from_db(self):
        if not is_file_db_configured():
            return
        try:
            self._records = load_docman_records(
                self._path_segments,
                self._records,
                facility_code=self._facility_code,
            )
        except FileBackendError:
            pass

    def _load_record_list_from_db(self):
        if not is_file_db_configured():
            return
        try:
            self._records = load_docman_record_list(
                self._path_segments,
                facility_code=self._facility_code,
            )
        except FileBackendError:
            pass

    def _normalize_records(self):
        for index, rec in enumerate(self._records, start=1):
            rec["index"] = index
            rec.setdefault("checked", False)
            rec.setdefault("category", "")
            rec.setdefault("work_condition", "")
            rec.setdefault("fmt", "")
            rec.setdefault("filename", "")
            rec.setdefault("mtime", "")
            rec.setdefault("path", "")
            rec.setdefault("remark", "")
            rec.setdefault("logical_path", "")
            rec.setdefault("document_code", "")
            rec.setdefault("document_title", "")
            rec.setdefault("design_stage_name", "")
            rec.setdefault("discipline_name", "")
            rec.setdefault("file_class_name", "")
            rec.setdefault("recognition_status", "")
            rec.setdefault("recognition_message", "")
            if self._default_work_condition and not rec.get("work_condition"):
                rec["work_condition"] = self._default_work_condition
            if not rec.get("filename") and rec.get("path"):
                rec["filename"] = os.path.basename(rec["path"])

    @staticmethod
    def _record_has_content(rec: dict) -> bool:
        return any(
            bool(rec.get(key))
            for key in ("filename", "path", "mtime", "record_id", "remark", "work_condition")
        )

    def _record_index_for_row(self, row: int) -> int | None:
        if 0 <= row < len(self._visible_row_indices):
            return self._visible_row_indices[row]
        return None

    def refresh(self):
        all_visible_row_indices = []
        for idx, rec in enumerate(self._records):
            if not self._hide_empty_templates or self._record_has_content(rec) or rec.get("_force_visible"):
                all_visible_row_indices.append(idx)

        total_pages = max(1, (len(all_visible_row_indices) + self._page_size - 1) // self._page_size)
        self._current_page = max(0, min(self._current_page, total_pages - 1))
        start = self._current_page * self._page_size
        end = start + self._page_size
        self._visible_row_indices = all_visible_row_indices[start:end]

        self._apply_profile_headers()
        self._apply_column_visibility()
        self.table.blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(self._visible_row_indices))

        try:
            for row, record_index in enumerate(self._visible_row_indices):
                rec = self._records[record_index]
                self._set_check_cell(row, rec)
                self._set_index_item(row, row + 1)
                self._set_profile_cells(row, rec)
                self._set_detail_button(row, rec)
                self._set_remark_item(row, rec.get("remark", ""))
        finally:
            self.table.blockSignals(False)
        self._update_header_check_state()
        self._update_pagination_controls(len(all_visible_row_indices), total_pages)

    def _apply_column_visibility(self):
        force_show = self._display_profile in {"design", "rebuild", "model"}
        self.table.setColumnHidden(self.COL_STAGE, self._display_profile != "model")
        if self._display_profile == "inspection":
            self.table.setColumnHidden(self.COL_WORK_CONDITION, False)
            self.table.setColumnHidden(self.COL_FMT, True)
            self.table.setColumnHidden(self.COL_MTIME, True)
            return
        self.table.setColumnHidden(self.COL_WORK_CONDITION, not (force_show or self._show_work_condition))
        self.table.setColumnHidden(self.COL_FMT, False)
        self.table.setColumnHidden(self.COL_MTIME, False)

    def _set_profile_cells(self, row: int, rec: dict) -> None:
        self._set_category_cell(row, rec)

        if self._display_profile in {"design", "rebuild"}:
            self._set_readonly_item(
                row,
                self.COL_WORK_CONDITION,
                self._document_code_text(rec),
                Qt.AlignVCenter | Qt.AlignLeft,
            )
            self._set_readonly_item(
                row,
                self.COL_FILENAME,
                self._document_title_text(rec),
                Qt.AlignVCenter | Qt.AlignLeft,
            )
            self._set_readonly_item(row, self.COL_FMT, rec.get("design_stage_name", ""), Qt.AlignCenter)
            self._set_readonly_item(
                row,
                self.COL_MTIME,
                self._discipline_text(rec),
                Qt.AlignCenter,
            )
            return

        if self._display_profile == "model":
            self._set_readonly_item(row, self.COL_STAGE, self._model_stage_text(rec), Qt.AlignCenter)
            self._set_readonly_item(
                row,
                self.COL_WORK_CONDITION,
                rec.get("filename", ""),
                Qt.AlignVCenter | Qt.AlignLeft,
            )
            self._set_readonly_item(row, self.COL_FILENAME, self._model_analysis_text(rec), Qt.AlignCenter)
            self._set_readonly_item(row, self.COL_FMT, rec.get("fmt", ""), Qt.AlignCenter)
            self._set_readonly_item(row, self.COL_MTIME, rec.get("mtime", ""), Qt.AlignCenter)
            return

        if self._display_profile == "inspection":
            self._set_readonly_item(row, self.COL_WORK_CONDITION, rec.get("work_condition", ""), Qt.AlignCenter)
            self._set_readonly_item(row, self.COL_FILENAME, rec.get("filename", ""), Qt.AlignVCenter | Qt.AlignLeft)
            self._set_readonly_item(row, self.COL_FMT, rec.get("fmt", ""), Qt.AlignCenter)
            self._set_readonly_item(row, self.COL_MTIME, rec.get("mtime", ""), Qt.AlignCenter)
            return

        self._set_work_condition_item(row, rec.get("work_condition", ""))
        self._set_readonly_item(row, self.COL_FILENAME, rec.get("filename", ""), Qt.AlignVCenter | Qt.AlignLeft)
        self._set_readonly_item(row, self.COL_FMT, rec.get("fmt", ""), Qt.AlignCenter)
        self._set_readonly_item(row, self.COL_MTIME, rec.get("mtime", ""), Qt.AlignCenter)

    def _model_stage_text(self, rec: dict | None = None) -> str:
        root = ""
        logical_path = str((rec or {}).get("logical_path") or "").replace("\\", "/").strip("/")
        if logical_path:
            parts = [part for part in logical_path.split("/") if part]
            if self._facility_code and parts and parts[0] == self._facility_code:
                parts = parts[1:]
            if parts:
                root = parts[0].strip()
        if not root and self._display_path_segments:
            root = str(self._display_path_segments[0] or "").strip()
        if not root and self._path_segments:
            root = str(self._path_segments[0] or "").strip()
        if root == "当前模型":
            return "当前"
        if root == "详细设计模型":
            return "详细设计"
        return root[:-2] if root.endswith("模型") else root

    @staticmethod
    def _document_code_text(rec: dict) -> str:
        return str(rec.get("document_code") or "").strip()

    @staticmethod
    def _document_title_text(rec: dict) -> str:
        return str(rec.get("document_title") or "").strip()

    @staticmethod
    def _discipline_text(rec: dict) -> str:
        text = str(rec.get("discipline_name") or "").strip()
        if text:
            return text
        status = str(rec.get("recognition_status") or "").strip()
        return "未分类" if status == "unclassified" else ""

    def _model_analysis_text(self, rec: dict) -> str:
        text = " ".join(
            [
                " ".join(self._path_segments),
                str(rec.get("logical_path") or ""),
                str(rec.get("category") or ""),
                str(rec.get("filename") or ""),
            ]
        )
        for keyword in ("静力", "疲劳", "倒塌", "地震", "波浪", "结构模型"):
            if keyword in text:
                return keyword
        return str(rec.get("work_condition") or "").strip()

    def _set_check_cell(self, row: int, rec: dict):
        box = QCheckBox(self.table)
        box.setChecked(bool(rec.get("checked", False)))
        box.stateChanged.connect(lambda state, r=row: self._on_checked_changed(r, state))

        wrapper = QWidget(self.table)
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(box)
        self.table.setCellWidget(row, self.COL_CHECK, wrapper)

    def _set_index_item(self, row: int, display_index: int):
        item = QTableWidgetItem(str(display_index))
        item.setTextAlignment(int(Qt.AlignCenter))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setToolTip(item.text())
        self.table.setItem(row, self.COL_INDEX, item)

    def _default_category(self) -> str:
        for option in self._category_options:
            value = str(option or "").strip()
            if value:
                return value
        return ""

    def _category_display_text(self, rec: dict) -> str:
        category = str(rec.get("category") or "").strip()
        if category:
            return category
        if self._display_profile in {"design", "rebuild"}:
            file_class = str(rec.get("file_class_name") or "").strip()
            if file_class:
                return file_class
        return self._default_category()

    def _set_category_cell(self, row: int, rec: dict):
        item = QTableWidgetItem(self._category_display_text(rec))
        item.setTextAlignment(int(Qt.AlignCenter))
        item.setToolTip(item.text())
        self.table.setItem(row, self.COL_CATEGORY, item)

    def _set_work_condition_item(self, row: int, text: str):
        item = QTableWidgetItem(text)
        item.setTextAlignment(int(Qt.AlignVCenter | Qt.AlignLeft))
        item.setToolTip(item.text())
        self.table.setItem(row, self.COL_WORK_CONDITION, item)

    def _set_detail_button(self, row: int, rec: dict):
        btn = QPushButton("详情", self.table)
        btn.setProperty("class", "DocManCellButton")
        btn.setEnabled(bool(str(rec.get("path") or "").strip()))
        btn.clicked.connect(lambda _=False, r=row: self._open_row_file(r, self.COL_DETAIL))
        self.table.setCellWidget(row, self.COL_DETAIL, btn)

    def _set_remark_item(self, row: int, text: str):
        item = QTableWidgetItem(text)
        item.setTextAlignment(int(Qt.AlignVCenter | Qt.AlignLeft))
        item.setToolTip(item.text())
        self.table.setItem(row, self.COL_REMARK, item)

    def _set_readonly_item(self, row: int, col: int, text: str, align: Qt.AlignmentFlag):
        item = QTableWidgetItem(text)
        item.setTextAlignment(int(align))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setToolTip(item.text())
        self.table.setItem(row, col, item)

    def _on_checked_changed(self, row: int, state: int):
        record_index = self._record_index_for_row(row)
        if record_index is not None:
            self._records[record_index]["checked"] = state == Qt.Checked
            self._update_header_check_state()

    def _set_visible_rows_checked(self, checked: bool) -> None:
        for record_index in self._visible_row_indices:
            self._records[record_index]["checked"] = bool(checked)
        self.refresh()

    def _update_header_check_state(self) -> None:
        if not hasattr(self, "table"):
            return
        if hasattr(self, "_check_header"):
            checked = bool(self._visible_row_indices) and all(
                bool(self._records[idx].get("checked")) for idx in self._visible_row_indices
            )
            self._check_header.setChecked(checked)

    def _add_row(self):
        if self._hide_empty_templates:
            for rec in self._records:
                if not self._record_has_content(rec) and not rec.get("_force_visible"):
                    rec["_force_visible"] = True
                    self.refresh()
                    if self.table.rowCount():
                        self.table.scrollToBottom()
                    return
        self._records.append(
            {
                "index": len(self._records) + 1,
                "checked": False,
                "category": "",
                "work_condition": "",
                "fmt": "",
                "filename": "",
                "mtime": "",
                "path": "",
                "remark": "",
                "logical_path": "",
                "_force_visible": True,
            }
        )
        self._current_page = max(0, (len(self._records) - 1) // self._page_size)
        self.refresh()
        if self._records:
            self.table.scrollToBottom()

    def _open_upload_staging(self) -> None:
        if self._custom_upload_handler is not None:
            checked_indices = [idx for idx, rec in enumerate(self._records) if rec.get("checked")]
            if not checked_indices:
                if self._custom_new_upload_handler is not None:
                    self._custom_new_upload_handler(self._records)
                    self._normalize_records()
                    self.refresh()
                    return
                QMessageBox.information(self, "提示", "请先勾选要上传/修改的文件类别。")
                return
            record_index = checked_indices[0]
            self._custom_upload_handler(record_index, self._records[record_index], self._records)
            self._normalize_records()
            self.refresh()
            return

        dialog = UploadStagingDialog(default_category=self._default_category(), parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        items = dialog.selected_items()
        if not items:
            return

        ok_count = 0
        first_error = ""
        for item in items:
            try:
                self._upload_staged_file(item)
                ok_count += 1
            except Exception as exc:
                if not first_error:
                    first_error = str(exc)

        if self._db_list_mode and is_file_db_configured():
            self._load_record_list_from_db()
        self._normalize_records()
        self.refresh()
        if first_error:
            QMessageBox.warning(self, "上传完成但存在失败", f"成功上传 {ok_count} 个文件。\n首个失败原因：{first_error}")
        else:
            QMessageBox.information(self, "上传成功", f"成功上传 {ok_count} 个文件。")

    def _upload_staged_file(self, item: dict) -> None:
        file_path = str(item.get("path") or "").strip()
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(file_path or "文件不存在")
        category = str(item.get("category") or "").strip() or self._default_category()
        if self._display_profile in {"design", "rebuild"} and category == self._default_category():
            meta = item.get("meta") or {}
            category = str(meta.get("file_class_name") or category or "").strip()

        if self._db_list_mode and is_file_db_configured():
            append_docman_file(
                file_path,
                path_segments=self._path_segments,
                category=category,
                work_condition=self._default_work_condition,
                remark="",
                facility_code=self._facility_code,
            )
            return

        if is_file_db_configured():
            row_index = len(self._records) + 1
            result = replace_docman_file(
                file_path,
                path_segments=self._path_segments,
                row_index=row_index,
                category=category,
                work_condition=self._default_work_condition,
                remark="",
                facility_code=self._facility_code,
            )
            self._records.append(self._record_from_upload_result(result, file_path, category))
            return

        target_path = self._copy_local_upload(file_path)
        self._records.append(self._record_from_local_upload(target_path, item, category))

    def _copy_local_upload(self, file_path: str) -> str:
        target_dir = self._storage_dir_getter(self._path_segments)
        os.makedirs(target_dir, exist_ok=True)
        filename = os.path.basename(file_path)
        target_path = os.path.join(target_dir, filename)
        root, ext = os.path.splitext(target_path)
        suffix = 1
        while os.path.exists(target_path):
            target_path = f"{root} ({suffix}){ext}"
            suffix += 1
        shutil.copy2(file_path, target_path)
        try:
            os.utime(target_path, None)
        except OSError:
            pass
        return target_path

    def _record_from_upload_result(self, result: dict, file_path: str, category: str) -> dict:
        dt = result.get("uploaded_at") or result.get("source_modified_at") or result.get("updated_at")
        rec = {
            "index": len(self._records) + 1,
            "checked": False,
            "category": result.get("category_name") or category,
            "work_condition": result.get("work_condition") or self._default_work_condition,
            "fmt": (result.get("file_ext") or self._format_label_from_path(file_path)).upper(),
            "filename": result.get("original_name") or os.path.basename(file_path),
            "mtime": dt.strftime("%Y/%m/%d %H:%M") if dt else QDateTime.currentDateTime().toString("yyyy/M/d HH:mm"),
            "path": resolve_storage_path(result),
            "remark": result.get("remark") or "",
            "record_id": result.get("id"),
            "logical_path": result.get("logical_path") or "",
        }
        for key in (
            "document_code",
            "document_title",
            "design_stage_name",
            "discipline_name",
            "file_class_name",
            "recognition_status",
            "recognition_message",
        ):
            rec[key] = result.get(key) or ""
        return rec

    def _record_from_local_upload(self, target_path: str, item: dict, category: str) -> dict:
        meta = item.get("meta") or {}
        return {
            "index": len(self._records) + 1,
            "checked": False,
            "category": category,
            "work_condition": self._default_work_condition,
            "fmt": self._format_label_from_path(target_path),
            "filename": os.path.basename(target_path),
            "mtime": QDateTime.currentDateTime().toString("yyyy/M/d HH:mm"),
            "path": target_path,
            "remark": "",
            "logical_path": "",
            "document_code": meta.get("document_code") or "",
            "document_title": meta.get("document_title") or "",
            "design_stage_name": meta.get("design_stage_name") or "",
            "discipline_name": meta.get("discipline_name") or "",
            "file_class_name": meta.get("file_class_name") or "",
            "recognition_status": meta.get("recognition_status") or "",
            "recognition_message": meta.get("recognition_message") or "",
        }

    def _update_pagination_controls(self, total_rows: int, total_pages: int) -> None:
        if not hasattr(self, "page_label"):
            return
        self.page_label.setText(f"第 {self._current_page + 1} / {total_pages} 页，共 {total_rows} 条")
        self.btn_prev_page.setEnabled(self._current_page > 0)
        self.btn_next_page.setEnabled(self._current_page < total_pages - 1)

    def _go_prev_page(self) -> None:
        if self._current_page <= 0:
            return
        self._current_page -= 1
        self.refresh()

    def _go_next_page(self) -> None:
        self._current_page += 1
        self.refresh()

    def _delete_checked_rows(self):
        checked_records = [rec for rec in self._records if rec.get("checked")]
        if not checked_records:
            QMessageBox.information(self, "提示", "请先勾选要删除的文件。")
            return

        if self._custom_delete_handler is not None:
            self._custom_delete_handler(checked_records, self._records)
            self._normalize_records()
            self.refresh()
            return

        failures: list[str] = []
        failed_ids: set[int] = set()
        if is_file_db_configured():
            for rec in checked_records:
                record_id = rec.get("record_id")
                if record_id is None:
                    continue
                try:
                    hard_delete_record(int(record_id))
                except FileBackendError as exc:
                    failures.append(str(exc))
                    failed_ids.add(int(record_id))

        kept = []
        for rec in self._records:
            if not rec.get("checked"):
                kept.append(rec)
                continue
            if rec.get("record_id") is None:
                if self._hide_empty_templates and not self._record_has_content(rec):
                    rec["checked"] = False
                    rec["_force_visible"] = False
                    kept.append(rec)
                continue
            if int(rec.get("record_id")) in failed_ids:
                rec["checked"] = False
                kept.append(rec)

        self._records[:] = kept
        self._normalize_records()
        self.refresh()
        if failures:
            QMessageBox.warning(self, "警告", failures[0])

    def _upload_or_modify(self, row: int):
        record_index = self._record_index_for_row(row)
        if record_index is None:
            return

        rec = self._records[record_index]
        raw_category = str(rec.get("category", "")).strip()
        default_category = self._default_category()
        current_category = raw_category or default_category
        allow_auto_category = self._display_profile in {"design", "rebuild"}
        if not current_category and not allow_auto_category:
            QMessageBox.warning(self, "提示", "请先填写类别，再上传文件。")
            return
        if self._custom_upload_handler is not None:
            self._custom_upload_handler(record_index, rec, self._records)
            self._normalize_records()
            self.refresh()
            return

        upload_category = "" if allow_auto_category and not raw_category else current_category
        title = f"选择上传文件 - {current_category}" if current_category else "选择上传文件"
        file_path, _ = QFileDialog.getOpenFileName(self, title, "", "所有文件 (*.*)")
        if not file_path:
            return

        if self._db_list_mode and is_file_db_configured():
            try:
                record_id = rec.get("record_id")
                logical_path = rec.get("logical_path") or ""
                if record_id and logical_path:
                    replace_docman_list_file(
                        file_path,
                        logical_path=logical_path,
                        record_id=int(record_id),
                        category=upload_category,
                        work_condition=rec.get("work_condition", "") or self._default_work_condition,
                        remark=rec.get("remark", ""),
                        facility_code=self._facility_code,
                    )
                else:
                    append_docman_file(
                        file_path,
                        path_segments=self._path_segments,
                        category=upload_category,
                        work_condition=rec.get("work_condition", "") or self._default_work_condition,
                        remark=rec.get("remark", ""),
                        facility_code=self._facility_code,
                    )
                self._load_record_list_from_db()
                self._normalize_records()
                self.refresh()
                QMessageBox.information(self, "上传成功", "上传成功")
                return
            except FileBackendError as exc:
                QMessageBox.warning(self, "上传失败", str(exc))
                return

        if is_file_db_configured():
            try:
                result = replace_docman_file(
                    file_path,
                    path_segments=self._path_segments,
                        row_index=record_index + 1,
                        category=upload_category,
                        work_condition=rec.get("work_condition", "") or self._default_work_condition,
                        remark=rec.get("remark", ""),
                    facility_code=self._facility_code,
                )
                rec["record_id"] = result.get("id")
                rec["path"] = resolve_storage_path(result)
                rec["fmt"] = (result.get("file_ext") or "").upper()
                rec["filename"] = result.get("original_name") or os.path.basename(file_path)
                rec["category"] = result.get("category_name") or upload_category or current_category
                rec["work_condition"] = result.get("work_condition") or rec.get("work_condition", "")
                rec["logical_path"] = result.get("logical_path") or rec.get("logical_path", "")
                for key in (
                    "document_code",
                    "document_title",
                    "design_stage_name",
                    "discipline_name",
                    "file_class_name",
                    "recognition_status",
                    "recognition_message",
                ):
                    rec[key] = result.get(key) or rec.get(key, "")
                dt = result.get("uploaded_at") or result.get("source_modified_at") or result.get("updated_at")
                rec["mtime"] = dt.strftime("%Y/%m/%d %H:%M") if dt else QDateTime.currentDateTime().toString("yyyy/M/d HH:mm")
                self.refresh()
                QMessageBox.information(self, "上传成功", "上传成功")
                return
            except FileBackendError as exc:
                QMessageBox.warning(self, "错误", str(exc))
                return

        target_dir = self._storage_dir_getter(self._path_segments)
        os.makedirs(target_dir, exist_ok=True)
        filename = os.path.basename(file_path)
        target_path = os.path.join(target_dir, filename)
        root, ext = os.path.splitext(target_path)
        suffix = 1
        while os.path.exists(target_path):
            target_path = f"{root} ({suffix}){ext}"
            suffix += 1

        try:
            shutil.copy2(file_path, target_path)
        except Exception as exc:
            QMessageBox.warning(self, "错误", f"复制文件失败：{exc}")
            return
        try:
            os.utime(target_path, None)
        except OSError:
            pass

        rec["path"] = target_path
        rec["fmt"] = self._format_label_from_path(target_path)
        rec["filename"] = filename
        rec["mtime"] = QDateTime.currentDateTime().toString("yyyy/M/d HH:mm")
        self.refresh()
        QMessageBox.information(self, "上传成功", "上传成功")

    @staticmethod
    def _format_label_from_path(file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lstrip(".").upper()
        return ext or ""

    def _on_item_changed(self, item: Optional[QTableWidgetItem]):
        if item is None:
            return
        record_index = self._record_index_for_row(item.row())
        if record_index is None:
            return

        record = self._records[record_index]
        record_id = record.get("record_id")
        if item.column() == self.COL_CATEGORY:
            category = item.text().strip()
            record["category"] = category
            if record_id is not None and is_file_db_configured():
                try:
                    updated = update_file_record(
                        int(record_id),
                        category_name=category,
                        expected_updated_at=record.get("_lock_updated_at"),
                    )
                    record["_lock_updated_at"] = updated.get("lock_updated_at")
                except FileBackendError as exc:
                    QMessageBox.warning(self, "保存失败", str(exc))
            return

        if item.column() == self.COL_WORK_CONDITION:
            work_condition = item.text().strip()
            record["work_condition"] = work_condition
            if record_id is not None and is_file_db_configured():
                try:
                    updated = update_file_record(
                        int(record_id),
                        work_condition=work_condition,
                        expected_updated_at=record.get("_lock_updated_at"),
                    )
                    record["_lock_updated_at"] = updated.get("lock_updated_at")
                except FileBackendError as exc:
                    QMessageBox.warning(self, "保存失败", str(exc))
            return
        if item.column() != self.COL_REMARK:
            return

        remark = item.text().strip()
        record["remark"] = remark
        if record_id is not None and is_file_db_configured():
            try:
                updated = update_file_record(
                    int(record_id),
                    remark=remark,
                    expected_updated_at=record.get("_lock_updated_at"),
                )
                record["_lock_updated_at"] = updated.get("lock_updated_at")
            except FileBackendError as exc:
                QMessageBox.warning(self, "保存失败", str(exc))

    def _download_checked_rows(self):
        selected = [rec for rec in self._records if rec.get("checked")]
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选需要下载的文件。")
            return

        if self._custom_download_handler is not None:
            self._custom_download_handler(selected, self._records)
            return

        available: list[tuple[str, str]] = []
        missing = 0
        for rec in selected:
            path = rec.get("path") or ""
            if path and os.path.exists(path):
                available.append((path, rec.get("filename") or os.path.basename(path)))
            else:
                missing += 1

        if not available:
            QMessageBox.information(self, "提示", "未找到可下载的文件。")
            return

        if len(available) == 1:
            src_path, default_name = available[0]
            safe_default_name = sanitize_download_filename(default_name, fallback=os.path.basename(src_path))
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存文件",
                safe_default_name,
                "",
            )
            if not save_path:
                return
            save_path = normalize_download_save_path(save_path, fallback_name=safe_default_name)
            try:
                shutil.copy2(src_path, save_path)
            except Exception as exc:
                QMessageBox.warning(self, "下载失败", str(exc))
                return
            message = "已下载 1 个文件。"
            if missing:
                message += f"\n另有 {missing} 个文件不存在。"
            QMessageBox.information(self, "下载完成", message)
            return

        target_dir = QFileDialog.getExistingDirectory(self, "选择下载文件夹")
        if not target_dir:
            return

        downloaded = 0
        for src_path, filename in available:
            target_path = unique_download_target_path(target_dir, filename)
            try:
                shutil.copy2(src_path, target_path)
                downloaded += 1
            except Exception:
                continue

        message = f"已下载 {downloaded} 个文件到：\n{target_dir}"
        if missing:
            message += f"\n另有 {missing} 个文件不存在。"
        QMessageBox.information(self, "下载完成", message)

    def _open_row_file(self, row: int, col: int) -> None:
        if col in {self.COL_CHECK, self.COL_INDEX, self.COL_STAGE, self.COL_CATEGORY, self.COL_REMARK}:
            return
        record_index = self._record_index_for_row(row)
        if record_index is None:
            return
        rec = self._records[record_index]
        path = str(rec.get("path") or "").strip()
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "提示", "当前行没有可打开的文件。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))
