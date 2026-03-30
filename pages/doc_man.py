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


class DocManWidget(QFrame):
    def __init__(self, storage_dir_getter: Callable[[List[str]], str], parent=None):
        super().__init__(parent)
        self._storage_dir_getter = storage_dir_getter
        self._path_segments: List[str] = []
        self._records: List[dict] = []
        self._category_options: List[str] = []
        self._build_ui()

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

    def set_context(self, path_segments: List[str], records: List[dict], category_options: List[str]):
        self._path_segments = list(path_segments)
        self._records = records
        self._category_options = list(category_options)
        self._normalize_records()
        self.refresh()

    def _normalize_records(self):
        default_category = self._category_options[0] if self._category_options else ""
        for index, rec in enumerate(self._records, start=1):
            rec["index"] = index
            rec.setdefault("checked", False)
            rec.setdefault("category", default_category)
            rec.setdefault("fmt", "")
            rec.setdefault("filename", "")
            rec.setdefault("mtime", "")
            rec.setdefault("path", "")
            rec.setdefault("remark", "")
            if not rec.get("filename") and rec.get("path"):
                rec["filename"] = os.path.basename(rec["path"])

    def refresh(self):
        self.table.clearContents()
        self.table.setRowCount(len(self._records))

        for row, rec in enumerate(self._records):
            self._set_checkbox_index_cell(row, rec)
            self._set_category_cell(row, rec)
            self._set_readonly_item(row, 2, rec.get("filename", ""), Qt.AlignVCenter | Qt.AlignLeft)
            self._set_readonly_item(row, 3, rec.get("fmt", ""), Qt.AlignCenter)
            self._set_readonly_item(row, 4, rec.get("mtime", ""), Qt.AlignCenter)
            self._set_upload_button(row)
            self._set_remark_item(row, rec.get("remark", ""))

    def _set_checkbox_index_cell(self, row: int, rec: dict):
        box = QCheckBox(self.table)
        box.setChecked(bool(rec.get("checked", False)))
        box.stateChanged.connect(lambda state, r=row: self._on_checked_changed(r, state))

        index_label = QPushButton(str(rec.get("index", row + 1)), self.table)
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
        combo.addItems(self._category_options)
        category = rec.get("category", "")
        if category:
            idx = combo.findText(category)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            elif category not in self._category_options:
                combo.addItem(category)
                combo.setCurrentText(category)
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
        if 0 <= row < len(self._records):
            self._records[row]["checked"] = state == Qt.Checked

    def _on_category_changed(self, row: int, text: str):
        if 0 <= row < len(self._records):
            self._records[row]["category"] = text

    def _add_row(self):
        default_category = self._category_options[0] if self._category_options else ""
        self._records.append(
            {
                "index": len(self._records) + 1,
                "checked": False,
                "category": default_category,
                "fmt": "",
                "filename": "",
                "mtime": "",
                "path": "",
                "remark": "",
            }
        )
        self.refresh()
        if self._records:
            self.table.scrollToBottom()

    def _delete_checked_rows(self):
        kept = [rec for rec in self._records if not rec.get("checked")]
        if len(kept) == len(self._records):
            QMessageBox.information(self, "提示", "请先勾选要删除的文件。")
            return

        self._records[:] = kept
        self._normalize_records()
        self.refresh()

    def _download_checked_rows(self):
        selected = [rec for rec in self._records if rec.get("checked")]
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要下载的文件。")
            return

        downloaded = 0
        missing = 0
        for rec in selected:
            path = rec.get("path") or ""
            if path and os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                downloaded += 1
            else:
                missing += 1

        QMessageBox.information(
            self,
            "提示",
            f"已处理 {downloaded} 个文件下载请求。"
            + (f"\n另有 {missing} 个勾选项尚未上传文件。" if missing else ""),
        )

    def _upload_or_modify(self, row: int):
        if row < 0 or row >= len(self._records):
            return

        current_category = self._records[row].get("category", "")
        title = f"选择上传文件 - {current_category}" if current_category else "选择上传文件"
        file_path, _ = QFileDialog.getOpenFileName(self, title, "", "所有文件 (*.*)")
        if not file_path:
            return

        target_dir = self._storage_dir_getter(self._path_segments)
        os.makedirs(target_dir, exist_ok=True)
        filename = os.path.basename(file_path)
        target_path = os.path.join(target_dir, filename)

        try:
            shutil.copy2(file_path, target_path)
        except Exception as exc:
            QMessageBox.warning(self, "错误", f"复制文件失败：{exc}")
            return

        rec = self._records[row]
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
        row = item.row()
        if 0 <= row < len(self._records):
            self._records[row]["remark"] = item.text().strip()
