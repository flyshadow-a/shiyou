# -*- coding: utf-8 -*-

import os
import shutil
from typing import Callable, List, Optional

from PyQt5.QtCore import QDateTime, Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from file_db_adapter import (
    append_docman_file,
    FileBackendError,
    is_file_db_configured,
    load_docman_records,
    load_docman_record_list,
    replace_docman_list_file,
    replace_docman_file,
    soft_delete_record,
)


class DocManWidget(QFrame):
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
        self._custom_upload_handler = None
        self._custom_delete_handler = None
        self._custom_download_handler = None
        self._build_ui()

    def set_action_handlers(self, *, upload_handler=None, delete_handler=None, download_handler=None):
        self._custom_upload_handler = upload_handler
        self._custom_delete_handler = delete_handler
        self._custom_download_handler = download_handler

    def _build_ui(self):
        self.setObjectName("DocManWidget")
        self.setStyleSheet(
            """
            QFrame#DocManWidget {
                background-color: #ffffff;
            }
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
                font-weight: 600;
                font-size: 12pt;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #93a4b7;
                background: #ffffff;
            }
            QCheckBox::indicator:checked {
                background: #1677c5;
                border: 1px solid #1677c5;
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
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels(["序号", "文件类别", "文件名", "文件格式", "修改时间", "上传/修改", "备注"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table_font = self.table.font()
        table_font.setPointSize(12)
        self.table.setFont(table_font)
        self.table.itemChanged.connect(self._on_item_changed)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.Fixed)
        header.setSectionResizeMode(1, header.Stretch)
        header.setSectionResizeMode(2, header.Stretch)
        header.setSectionResizeMode(3, header.Fixed)
        header.setSectionResizeMode(4, header.Fixed)
        header.setSectionResizeMode(5, header.Fixed)
        header.setSectionResizeMode(6, header.Stretch)
        self.table.setColumnWidth(0, 88)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 150)
        self.table.setColumnWidth(5, 120)
        self.table.verticalHeader().setDefaultSectionSize(40)
        layout.addWidget(self.table, 1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.addStretch()

        self.btn_add = QPushButton("新增", self)
        self.btn_add.setProperty("class", "DocManBlueButton")
        self.btn_add.clicked.connect(self._add_row)
        action_row.addWidget(self.btn_add)

        self.btn_delete = QPushButton("删除", self)
        self.btn_delete.setProperty("class", "DocManBlueButton")
        self.btn_delete.clicked.connect(self._delete_checked_rows)
        action_row.addWidget(self.btn_delete)

        self.btn_download = QPushButton("下载", self)
        self.btn_download.setProperty("class", "DocManBlueButton")
        self.btn_download.clicked.connect(self._download_checked_rows)
        action_row.addWidget(self.btn_download)

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
    ):
        self._path_segments = list(path_segments)
        self._db_list_mode = bool(db_list_mode)
        self._records = [dict(rec) for rec in records] if not self._db_list_mode else [
            dict(rec) for rec in records if self._record_has_content(rec)
        ]
        self._category_options = list(category_options)
        self._facility_code = (facility_code or "").strip() or None
        self._hide_empty_templates = bool(hide_empty_templates)
        if self._db_list_mode:
            self._load_record_list_from_db()
        elif overlay_from_db:
            self._overlay_records_from_db()
        self._normalize_records()
        self.refresh()

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
            rec.setdefault("fmt", "")
            rec.setdefault("filename", "")
            rec.setdefault("mtime", "")
            rec.setdefault("path", "")
            rec.setdefault("remark", "")
            rec.setdefault("logical_path", "")
            if not rec.get("filename") and rec.get("path"):
                rec["filename"] = os.path.basename(rec["path"])

    @staticmethod
    def _record_has_content(rec: dict) -> bool:
        return any(
            bool(rec.get(key))
            for key in ("filename", "path", "mtime", "record_id", "remark")
        )

    def _record_index_for_row(self, row: int) -> int | None:
        if 0 <= row < len(self._visible_row_indices):
            return self._visible_row_indices[row]
        return None

    def refresh(self):
        self._visible_row_indices = []
        for idx, rec in enumerate(self._records):
            if not self._hide_empty_templates or self._record_has_content(rec) or rec.get("_force_visible"):
                self._visible_row_indices.append(idx)

        self.table.clearContents()
        self.table.setRowCount(len(self._visible_row_indices))

        for row, record_index in enumerate(self._visible_row_indices):
            rec = self._records[record_index]
            self._set_checkbox_index_cell(row, rec, row + 1)
            self._set_category_cell(row, rec)
            self._set_readonly_item(row, 2, rec.get("filename", ""), Qt.AlignVCenter | Qt.AlignLeft)
            self._set_readonly_item(row, 3, rec.get("fmt", ""), Qt.AlignCenter)
            self._set_readonly_item(row, 4, rec.get("mtime", ""), Qt.AlignCenter)
            self._set_upload_button(row)
            self._set_remark_item(row, rec.get("remark", ""))

    def _set_checkbox_index_cell(self, row: int, rec: dict, display_index: int):
        box = QCheckBox(self.table)
        box.setChecked(bool(rec.get("checked", False)))
        box.stateChanged.connect(lambda state, r=row: self._on_checked_changed(r, state))

        index_label = QPushButton(str(display_index), self.table)
        index_label.setFlat(True)
        index_label.setEnabled(False)
        index_label.setStyleSheet(
            "QPushButton { border: none; background: transparent; color: #12344d; font-size: 12pt; }"
        )

        wrapper = QWidget(self.table)
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(box)
        layout.addWidget(index_label)
        self.table.setCellWidget(row, 0, wrapper)

    def _set_category_cell(self, row: int, rec: dict):
        combo = QComboBox(self.table)
        combo.addItem("")
        for option in self._category_options:
            if option and combo.findText(option) < 0:
                combo.addItem(option)
        category = rec.get("category", "")
        if category:
            idx = combo.findText(category)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            elif category not in self._category_options:
                combo.addItem(category)
                combo.setCurrentText(category)
        else:
            combo.setCurrentIndex(0)
        combo.currentTextChanged.connect(lambda text, r=row: self._on_category_changed(r, text))
        self.table.setCellWidget(row, 1, combo)

    def _set_upload_button(self, row: int):
        btn = QPushButton("上传/修改", self.table)
        btn.setProperty("class", "DocManCellButton")
        btn.clicked.connect(lambda _=False, r=row: self._upload_or_modify(r))
        self.table.setCellWidget(row, 5, btn)

    def _set_remark_item(self, row: int, text: str):
        item = QTableWidgetItem(text)
        item.setTextAlignment(int(Qt.AlignVCenter | Qt.AlignLeft))
        self.table.setItem(row, 6, item)

    def _set_readonly_item(self, row: int, col: int, text: str, align: Qt.AlignmentFlag):
        item = QTableWidgetItem(text)
        item.setTextAlignment(int(align))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, col, item)

    def _on_checked_changed(self, row: int, state: int):
        record_index = self._record_index_for_row(row)
        if record_index is not None:
            self._records[record_index]["checked"] = state == Qt.Checked

    def _on_category_changed(self, row: int, text: str):
        record_index = self._record_index_for_row(row)
        if record_index is not None:
            self._records[record_index]["category"] = text

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
                "fmt": "",
                "filename": "",
                "mtime": "",
                "path": "",
                "remark": "",
                "logical_path": "",
                "_force_visible": True,
            }
        )
        self.refresh()
        if self._records:
            self.table.scrollToBottom()

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
                    soft_delete_record(int(record_id))
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
        current_category = str(rec.get("category", "")).strip()
        if not current_category:
            QMessageBox.warning(self, "提示", "请先选择文件类别，再上传文件。")
            return
        if self._custom_upload_handler is not None:
            self._custom_upload_handler(record_index, rec, self._records)
            self._normalize_records()
            self.refresh()
            return

        current_category = rec.get("category", "")
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
                        category=current_category,
                        remark=rec.get("remark", ""),
                        facility_code=self._facility_code,
                    )
                else:
                    append_docman_file(
                        file_path,
                        path_segments=self._path_segments,
                        category=current_category,
                        remark=rec.get("remark", ""),
                        facility_code=self._facility_code,
                    )
                self._load_record_list_from_db()
                self._normalize_records()
                self.refresh()
                return
            except FileBackendError as exc:
                QMessageBox.warning(self, "上传失败", str(exc))
                return

        if is_file_db_configured():
            try:
                result = replace_docman_file(
                    file_path,
                    path_segments=self._path_segments,
                    row_index=row + 1,
                    category=current_category,
                    remark=rec.get("remark", ""),
                    facility_code=self._facility_code,
                )
                rec["record_id"] = result.get("id")
                rec["path"] = result.get("storage_path") or ""
                rec["fmt"] = (result.get("file_ext") or "").upper()
                rec["filename"] = result.get("original_name") or os.path.basename(file_path)
                dt = result.get("source_modified_at") or result.get("uploaded_at")
                rec["mtime"] = dt.strftime("%Y/%m/%d %H:%M") if dt else QDateTime.currentDateTime().toString("yyyy/M/d HH:mm")
                self.refresh()
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

        rec["path"] = target_path
        rec["fmt"] = self._format_label_from_path(target_path)
        rec["filename"] = filename
        rec["mtime"] = QDateTime.currentDateTime().toString("yyyy/M/d HH:mm")
        self.refresh()

    @staticmethod
    def _format_label_from_path(file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lstrip(".").upper()
        return ext or ""

    def _on_item_changed(self, item: Optional[QTableWidgetItem]):
        if item is None or item.column() != 6:
            return
        record_index = self._record_index_for_row(item.row())
        if record_index is not None:
            self._records[record_index]["remark"] = item.text().strip()

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
            save_path, _ = QFileDialog.getSaveFileName(self, "保存文件", default_name, "所有文件 (*.*)")
            if not save_path:
                return
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
            target_path = os.path.join(target_dir, filename)
            root, ext = os.path.splitext(target_path)
            suffix = 1
            while os.path.exists(target_path):
                target_path = f"{root} ({suffix}){ext}"
                suffix += 1
            try:
                shutil.copy2(src_path, target_path)
                downloaded += 1
            except Exception:
                continue

        message = f"已下载 {downloaded} 个文件到：\n{target_dir}"
        if missing:
            message += f"\n另有 {missing} 个文件不存在。"
        QMessageBox.information(self, "下载完成", message)
