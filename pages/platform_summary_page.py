# -*- coding: utf-8 -*-
# pages/platform_summary_page.py

import datetime
import os
import shutil
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import QEvent, QTimer, Qt
from PyQt5.QtGui import QPixmap, QResizeEvent
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from base_page import BasePage

try:
    import pandas as pd
except ImportError:
    pd = None


class PlatformBatchAddDialog(QDialog):
    """批量新增平台弹窗。"""

    def __init__(self, columns: List[str], parent=None, initial_rows: int = 5):
        super().__init__(parent)
        self.columns = columns
        self.initial_rows = max(1, initial_rows)
        self.table: QTableWidget | None = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("新增平台")
        self.resize(1500, 820)
        self.setModal(True)

        self.setStyleSheet(
            """
            QDialog {
                background: #f5f8fc;
            }
            QFrame#DialogCard {
                background: #ffffff;
                border: 1px solid #d9e4f0;
                border-radius: 14px;
            }
            QLabel#DialogTitle {
                color: #1f3b57;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel#DialogHint {
                color: #5f7185;
                font-size: 12px;
            }
            QPushButton {
                min-height: 32px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #c9d5e2;
                background: #ffffff;
            }
            QPushButton:hover {
                background: #eef5ff;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #d9e4f0;
                gridline-color: #e4ebf3;
                selection-background-color: #d9ebff;
                selection-color: #102a43;
            }
            QHeaderView::section {
                background: #edf4fb;
                color: #23415f;
                padding: 6px 8px;
                border: none;
                border-right: 1px solid #d9e4f0;
                border-bottom: 1px solid #d9e4f0;
                font-weight: bold;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        card = QFrame()
        card.setObjectName("DialogCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        title = QLabel("批量新增平台")
        title.setObjectName("DialogTitle")
        hint = QLabel("每列对应一个字段。可直接录入多行，空行不会写入主表。")
        hint.setObjectName("DialogHint")

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)

        btn_add = QPushButton("新增一行")
        btn_delete = QPushButton("删除选中行")
        btn_add.clicked.connect(self._append_empty_row)
        btn_delete.clicked.connect(self._remove_selected_rows)

        top_bar.addWidget(btn_add)
        top_bar.addWidget(btn_delete)
        top_bar.addStretch()

        self.table = QTableWidget(self.initial_rows, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)

        for col in range(len(self.columns)):
            self.table.setColumnWidth(col, 150)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("写入主表")
        button_box.button(QDialogButtonBox.Cancel).setText("取消")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        card_layout.addWidget(title)
        card_layout.addWidget(hint)
        card_layout.addLayout(top_bar)
        card_layout.addWidget(self.table, 1)
        card_layout.addWidget(button_box)

        root.addWidget(card)

    def _append_empty_row(self):
        if self.table is None:
            return
        self.table.insertRow(self.table.rowCount())

    def _remove_selected_rows(self):
        if self.table is None:
            return
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        for index in sorted((it.row() for it in selected), reverse=True):
            self.table.removeRow(index)
        if self.table.rowCount() == 0:
            self.table.insertRow(0)

    def get_rows(self) -> List[List[str]]:
        if self.table is None:
            return []

        rows: List[List[str]] = []
        for row in range(self.table.rowCount()):
            values: List[str] = []
            has_content = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                text = item.text().strip() if item is not None else ""
                if text:
                    has_content = True
                values.append(text)
            if has_content:
                rows.append(values)
        return rows


class PlatformSummaryPage(BasePage):
    """平台汇总信息页面。"""

    DEFAULT_SAMPLE_FILE = Path(r"d:\desk\横向\平台汇总信息样表 (1).xls")
    DEFAULT_HEADER_ROW = 1

    def __init__(self, parent: QWidget = None):
        super().__init__("平台汇总信息", parent)

        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.map_image_path = os.path.join(self.project_root, "pict", "youtianfenbu.png")
        self._original_map_pixmap: QPixmap | None = None

        self.columns: List[str] = []
        self.source_excel_path: Optional[str] = None
        self.table: QTableWidget | None = None
        self.map_frame: QFrame | None = None
        self.map_canvas: QFrame | None = None
        self.map_label: QLabel | None = None

        bootstrap_df = self._load_default_dataframe()
        if bootstrap_df is not None:
            self.columns = list(bootstrap_df.columns)
        else:
            self.columns = ["分公司", "作业公司", "油气田", "设施编码", "设施名称"]

        self._build_ui()

        if bootstrap_df is not None:
            self._apply_dataframe_to_table(bootstrap_df)
        else:
            self._load_fallback_rows()

    def _build_ui(self):
        root = QFrame()
        root.setObjectName("PlatformSummaryRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        self.setStyleSheet(
            """
            QFrame#PlatformSummaryRoot {
                background: #f4f7fb;
            }
            QFrame#TablePanel, QFrame#RightPanel {
                background: #ffffff;
                border-radius: 16px;
                border: 1px solid #dce6f2;
            }
            QFrame#MapFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f8fbff,
                    stop:0.52 #eef5fd,
                    stop:1 #e8f0fa
                );
                border-radius: 24px;
                border: 1px solid #d7e4f2;
            }
            QFrame#MapCanvas {
                background: qradialgradient(
                    cx:0.25, cy:0.18, radius:1.1,
                    fx:0.25, fy:0.18,
                    stop:0 rgba(255,255,255,0.95),
                    stop:0.35 rgba(236,244,252,0.92),
                    stop:1 rgba(221,233,246,0.98)
                );
                border-radius: 18px;
                border: none;
            }
            QLabel#MapLabel {
                background: transparent;
            }
            QTableWidget {
                background: #ffffff;
                border: none;
                gridline-color: #e5ebf2;
                alternate-background-color: #f8fbff;
                selection-background-color: #d6e9ff;
                selection-color: #102a43;
            }
            QHeaderView::section {
                background: #edf4fb;
                color: #213a57;
                padding: 6px 8px;
                border: none;
                border-right: 1px solid #d8e3ef;
                border-bottom: 1px solid #d8e3ef;
                font-weight: bold;
            }
            QPushButton {
                min-height: 30px;
                padding: 6px 14px;
                border-radius: 8px;
                border: 1px solid #c9d5e2;
                background: #ffffff;
                color: #1e344b;
            }
            QPushButton:hover {
                background: #edf5ff;
            }
            QPushButton.PrimaryButton {
                background: #0090d0;
                border-color: #0090d0;
                color: #ffffff;
            }
            QPushButton.PrimaryButton:hover {
                background: #00a4f2;
            }
            """
        )

        table_panel = QFrame()
        table_panel.setObjectName("TablePanel")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(10)

        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table_layout.addWidget(self.table, 1)

        table_btn_layout = QHBoxLayout()
        table_btn_layout.setContentsMargins(0, 0, 0, 0)
        table_btn_layout.setSpacing(8)

        self.btn_add_row = QPushButton("新增平台")
        self.btn_del_row = QPushButton("删除选中平台")
        self.btn_add_row.clicked.connect(self.open_batch_add_dialog)
        self.btn_del_row.clicked.connect(self.remove_selected_rows)

        table_btn_layout.addWidget(self.btn_add_row)
        table_btn_layout.addWidget(self.btn_del_row)
        table_btn_layout.addStretch()
        table_layout.addLayout(table_btn_layout)

        right_panel = QFrame()
        right_panel.setObjectName("RightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 0, 0, 0)
        btn_bar.setSpacing(8)

        self.btn_save = QPushButton("保存")
        self.btn_save.setProperty("class", "PrimaryButton")
        self.btn_import = QPushButton("导入Excel")
        self.btn_export = QPushButton("导出数据")
        self.btn_export_tpl = QPushButton("导出模板")

        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_import.clicked.connect(self.on_import_clicked)
        self.btn_export.clicked.connect(self.on_export_clicked)
        self.btn_export_tpl.clicked.connect(self.on_export_template_clicked)

        btn_bar.addWidget(self.btn_save)
        btn_bar.addSpacing(8)
        btn_bar.addWidget(self.btn_import)
        btn_bar.addWidget(self.btn_export)
        btn_bar.addWidget(self.btn_export_tpl)
        btn_bar.addStretch()
        right_layout.addLayout(btn_bar)

        self.map_frame = QFrame()
        self.map_frame.setObjectName("MapFrame")
        self.map_frame.installEventFilter(self)
        map_frame_layout = QVBoxLayout(self.map_frame)
        map_frame_layout.setContentsMargins(16, 16, 16, 16)
        map_frame_layout.setSpacing(10)

        map_title = QLabel("平台分布示意")
        map_title.setObjectName("MapTitle")
        map_hint = QLabel("去除旧边框后，底纹改为浅蓝灰渐变背景。")
        map_hint.setObjectName("MapHint")

        self.map_canvas = QFrame()
        self.map_canvas.setObjectName("MapCanvas")
        map_canvas_layout = QVBoxLayout(self.map_canvas)
        map_canvas_layout.setContentsMargins(14, 14, 14, 14)

        self.map_label = QLabel()
        self.map_label.setObjectName("MapLabel")
        self.map_label.setAlignment(Qt.AlignCenter)
        self.map_label.setScaledContents(False)
        self.map_label.setMinimumSize(0, 0)
        self.map_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        map_canvas_layout.addWidget(self.map_label)

        map_frame_layout.addWidget(self.map_canvas, 1)
        right_layout.addWidget(self.map_frame, 1)

        QTimer.singleShot(0, self._load_map_image)

        table_scroll = QScrollArea()
        table_scroll.setWidgetResizable(True)
        table_scroll.setFrameShape(QFrame.NoFrame)
        table_scroll.setWidget(table_panel)
        table_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        root_layout.addWidget(table_scroll)
        root_layout.addWidget(right_panel)
        root_layout.setStretch(0, 7)
        root_layout.setStretch(1, 3)

        self.main_layout.addWidget(root)

    def eventFilter(self, obj, event):
        if obj is self.map_frame and event.type() == QEvent.Resize:
            self._update_map_display()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_map_display()

    def _get_upload_root(self) -> str:
        root = os.path.join(self.project_root, "upload", "platform_summary")
        os.makedirs(root, exist_ok=True)
        return root

    def _default_excel_candidates(self) -> List[Path]:
        candidates = [self.DEFAULT_SAMPLE_FILE]

        desk_dir = Path(r"d:\desk\横向")
        if desk_dir.exists():
            candidates.extend(
                sorted(
                    desk_dir.glob("*.xls"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            )

        candidates.extend(
            [
                Path(self.project_root) / "data" / "platform_total.xls",
                Path.cwd() / "data" / "platform_total.xls",
            ]
        )
        return candidates

    def _load_default_dataframe(self):
        for candidate in self._default_excel_candidates():
            if candidate.exists():
                try:
                    df = self._read_excel_dataframe(str(candidate))
                    self.source_excel_path = str(candidate)
                    return df
                except Exception:
                    continue
        return None

    def _ensure_excel_support(self) -> bool:
        if pd is None:
            QMessageBox.warning(
                self,
                "缺少依赖",
                "当前读取 Excel 需要安装 pandas、openpyxl、xlrd。",
            )
            return False
        return True

    def _normalize_columns(self, columns) -> List[str]:
        normalized: List[str] = []
        for idx, col in enumerate(columns):
            text = "" if col is None else str(col).strip()
            if not text or text.lower().startswith("unnamed:"):
                text = f"未命名列{idx + 1}"
            normalized.append(text)
        return normalized

    def _read_excel_dataframe(self, file_path: str):
        if not self._ensure_excel_support():
            raise RuntimeError("Excel 依赖未安装")

        ext = os.path.splitext(file_path)[1].lower()
        engine = "xlrd" if ext == ".xls" else "openpyxl"
        df = pd.read_excel(file_path, header=self.DEFAULT_HEADER_ROW, engine=engine)
        df = df.dropna(axis=0, how="all")
        df.columns = self._normalize_columns(df.columns)
        return df

    def _display_text(self, value) -> str:
        if pd is not None:
            try:
                if pd.isna(value):
                    return ""
            except Exception:
                pass

        if value is None:
            return ""

        if hasattr(value, "strftime"):
            try:
                return value.strftime("%Y-%m-%d")
            except Exception:
                pass

        text = str(value).strip()
        return "" if text == "nan" else text

    def _set_table_columns(self, columns: List[str]):
        self.columns = list(columns)
        if self.table is None:
            return
        self.table.clear()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)

    def _apply_dataframe_to_table(self, df):
        if self.table is None:
            return

        self._set_table_columns(list(df.columns))
        self.table.setRowCount(0)
        self.table.clearContents()

        for _, row_data in df.iterrows():
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, col_name in enumerate(self.columns):
                value = self._display_text(row_data.get(col_name, ""))
                self.table.setItem(row, col, QTableWidgetItem(value))

        self._update_table_columns()

    def _update_table_columns(self):
        if self.table is None:
            return
        header = self.table.horizontalHeader()
        self.table.resizeColumnsToContents()
        for col in range(self.table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            width = self.table.columnWidth(col)
            self.table.setColumnWidth(col, min(max(width + 18, 120), 260))
        header.setStretchLastSection(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def _load_fallback_rows(self):
        fallback_rows = [
            ["湛江分公司", "文昌油田群作业公司", "文昌19-1油田", "WC19-1WHPC", "文昌19-1WHPC井口平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲12-1油田", "WZ12-1WHPB", "涠洲12-1WHPB井口平台"],
        ]
        if self.table is None:
            return
        self.table.setRowCount(0)
        for row_data in fallback_rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, value in enumerate(row_data):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self._update_table_columns()

    def _load_map_image(self):
        if self.map_label is None:
            return

        if os.path.exists(self.map_image_path):
            pix = QPixmap(self.map_image_path)
            if not pix.isNull():
                self._original_map_pixmap = pix
                self._update_map_display()
                return

        self.map_label.setText("找不到图片：youtianfenbu.png")

        self.map_label.clear()

    def _update_map_display(self):
        if self._original_map_pixmap is None or self.map_label is None:
            return

        target = self.map_label.size()
        if target.width() <= 1 or target.height() <= 1:
            return

        scaled = self._original_map_pixmap.scaled(
            target,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.map_label.setPixmap(scaled)

    def open_batch_add_dialog(self):
        dialog = PlatformBatchAddDialog(self.columns, self, initial_rows=5)
        if dialog.exec_() != QDialog.Accepted:
            return

        rows = dialog.get_rows()
        if not rows:
            QMessageBox.information(self, "提示", "未录入任何平台数据。")
            return

        if self.table is None:
            return

        for row_values in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, value in enumerate(row_values):
                self.table.setItem(row, col, QTableWidgetItem(value))

        self._update_table_columns()
        QMessageBox.information(self, "新增完成", f"已新增 {len(rows)} 条平台记录。")

    def _generate_initial_data(self) -> List[List[str]]:
        initial_rows = [
            ["湛江分公司", "文昌油田群作业公司", "文昌19-1油田", "WC19-1WHPB", "文昌19-1WHPB井口平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲6-12油田", "WZ6-12WHP", "涠洲6-12WHP井口平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲12-1油田", "WZ12-1WHPB", "涠洲12-1WHPB井口平台"],
            ["湛江分公司", "洞洲作业公司", "洞洲11-4油田", "WZ11-4WHPC", "洞洲11-4WHPC井口平台"],
            ["湛江分公司", "洞洲作业公司", "洞洲11-4油田", "WZ11-4CEPA", "洞洲11-4CEPA中心平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲12-1油田", "WZ12-2WHPB", "涠洲12-2WHPB井口平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲12-1油田", "WZ12-1WWHPA", "涠洲12-1WWHPA井口平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲11-2油田", "WZ11-2WHPB", "涠洲11-2WHPB井口平台"],
            ["湛江分公司", "洞洲作业公司", "洞洲11-4油田", "WZ11-4DWHPA", "洞洲11-4DWHPA井口平台"],
            ["湛江分公司", "洞洲作业公司", "洞洲11-4N油田", "WZ11-1NWHPA", "洞洲11-1NWHPA井口平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲12-1油田", "WZ12-1PUQBCEP", "涠洲12-1PUQBCEP中心平台"],
            ["湛江分公司", "文昌油田群作业公司", "文昌19-1油田", "WC19-1WHPC", "文昌19-1WHPC井口平台"],
            ["湛江分公司", "文昌油田群作业公司", "文昌8-3油田", "WC8-3WHPB", "文昌8-3WHPB井口平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲12-1油田", "WZ12-1WHPC", "涠洲12-1WHPC井口平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲11-1油田", "WZ11-1WHPA", "涠洲11-1WHPA井口平台"],
            ["湛江分公司", "文昌油田群作业公司", "文昌14-3油田", "WC14-3WHPA", "文昌14-3WHPA井口平台"],
            ["湛江分公司", "洞洲作业公司", "洞洲11-4油田", "WZ11-4WHPB", "洞洲11-4WHPB井口平台"],
            ["湛江分公司", "文昌油田群作业公司", "文昌13-2油田", "WC13-2WHPA", "文昌13-2WHPA井口平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲11-2油田", "WZ11-2WHPC", "涠洲11-2WHPC井口平台"],
            ["湛江分公司", "文昌油田群作业公司", "文昌13-6油田", "WC13-6WHPA", "文昌13-6WHPA井口平台"],
            ["湛江分公司", "文昌油田群作业公司", "文昌23-5油田", "WS23-5WHPA", "文昌23-5WHPA井口平台"],
            ["湛江分公司", "洞洲作业公司", "洞洲11-4N油田", "WZ11-4NWHPC", "洞洲11-4NWHPC井口平台"],
            ["湛江分公司", "文昌油田群作业公司", "文昌9-2气田", "WC9-2/9-3CEP", "文昌9-2/9-3CEP中心平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲12-1油田", "WZ12-1CEPA", "涠洲12-1CEPA中心平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲11-1油田", "WZ11-1RP", "涠洲11-1RP立管平台"],
            ["湛江分公司", "涠洲作业公司", "涠洲6-8油田", "WZ6-8WHPA", "涠洲6-8WHPA井口平台"],
        ]
        return initial_rows

    # ------------------------------------------------------------------ #
    # 表格增删行
    # ------------------------------------------------------------------ #
    def add_empty_row(self):
        """在表格末尾新增一空行."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        # 默认每个单元格给一个 QTableWidgetItem，方便直接编辑
        for col in range(self.table.columnCount()):
            item = QTableWidgetItem("")
            self.table.setItem(row, col, item)


    def remove_selected_rows(self):
        if self.table is None:
            return

        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择要删除的平台。")
            return

        rows = sorted((idx.row() for idx in selected), reverse=True)
        count = len(rows)
        reply = QMessageBox.question(
            self,
            "删除选中平台",
            f"确认删除选中的 {count} 个平台吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        for row in rows:
            self.table.removeRow(row)

    def _copy_import_file(self, file_path: str) -> Optional[str]:
        try:
            upload_root = self._get_upload_root()
            date_str = datetime.date.today().strftime("%Y%m%d")
            target_dir = os.path.join(upload_root, date_str)
            os.makedirs(target_dir, exist_ok=True)

            basename = os.path.basename(file_path)
            time_str = datetime.datetime.now().strftime("%H%M%S")
            saved_path = os.path.join(target_dir, f"{time_str}_{basename}")
            shutil.copy2(file_path, saved_path)
            return saved_path
        except Exception as exc:
            QMessageBox.warning(self, "提示", f"样表复制到 upload 目录失败：\n{exc}")
            return None

    def on_import_clicked(self):
        if not self._ensure_excel_support():
            return

        default_dir = os.path.dirname(self.source_excel_path) if self.source_excel_path else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要导入的 Excel 文件",
            default_dir,
            "Excel 文件 (*.xls *.xlsx *.xlsm)",
        )
        if not file_path:
            return

        try:
            df = self._read_excel_dataframe(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "导入失败", f"读取 Excel 失败：\n{exc}")
            return

        saved_path = self._copy_import_file(file_path)
        self.source_excel_path = file_path
        self._apply_dataframe_to_table(df)

        message = f"已导入 {len(df)} 条平台记录。"
        if saved_path:
            message += f"\n\n源文件已复制到：\n{saved_path}"
        QMessageBox.information(self, "导入完成", message)

    def on_export_clicked(self):
        if not self._ensure_excel_support() or self.table is None:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Excel 文件",
            "平台汇总信息.xlsx",
            "Excel 文件 (*.xlsx)",
        )
        if not file_path:
            return

        data = {col: [] for col in self.columns}
        for row in range(self.table.rowCount()):
            for col, col_name in enumerate(self.columns):
                item = self.table.item(row, col)
                data[col_name].append(item.text() if item is not None else "")

        try:
            pd.DataFrame(data).to_excel(file_path, index=False)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"写入 Excel 失败：\n{exc}")
            return

        QMessageBox.information(
            self,
            "导出完成",
            f"已导出 {self.table.rowCount()} 条平台记录到：\n{file_path}",
        )

    def on_export_template_clicked(self):
        if not self._ensure_excel_support():
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Excel 模板",
            "平台汇总信息模板.xlsx",
            "Excel 文件 (*.xlsx)",
        )
        if not file_path:
            return

        try:
            pd.DataFrame(columns=self.columns).to_excel(file_path, index=False)
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"写入 Excel 失败：\n{exc}")
            return

        QMessageBox.information(self, "导出完成", f"模板已导出到：\n{file_path}")

    def on_save_clicked(self):
        rows = self.table.rowCount() if self.table is not None else 0
        QMessageBox.information(
            self,
            "保存",
            f"当前共有 {rows} 条平台记录。\n\n后续可以在 on_save_clicked 中接入后端接口或数据库。",
        )
