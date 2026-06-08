# -*- coding: utf-8 -*-
# pages/platform_summary_page.py

import datetime
import os
import re
import shutil
from typing import List, Optional

from PyQt5.QtCore import QEvent, QPoint, QTimer, Qt
from PyQt5.QtGui import QColor, QPixmap, QResizeEvent
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.base_page import BasePage
from core.message_boxes import ask_yes_no
from services.inspection_business_db_adapter import (
    save_facility_profile,
    save_platform_summary_snapshot,
)
from services.platform_summary_source import load_platform_summary_source
from pages.file_management_platforms import refresh_platform_profiles_cache

try:
    import pandas as pd
except ImportError:
    pd = None


PLATFORM_DETAIL_FIELD_ROWS: List[tuple[str, str, str, str]] = [
    ("分公司", "设计气处理能力", "是否有生活楼", "上部组块工作甲板尺寸长×宽(m×m)"),
    ("作业公司", "设计水处理能力", "生活楼层数", "上部组块下下甲板尺寸长×宽(m×m)"),
    ("油气田", "导管架腿数", "上部组块生活楼吊装重量(t)", "飞机甲板承重能力(t)"),
    ("设施编码", "水深", "生活楼尺寸长×宽×高(m×m×m)", "飞机甲板尺寸(m×m)"),
    ("设施名称", "井槽数量", "主体最大尺度(m3)", "最大储油能力(m3)"),
    ("设施类型", "桩数量", "系泊能力(t)", "柴油存储能力(m3)"),
    ("分类", "供电形式", "设计抗风能力", "供热能力(KW)"),
    ("投产时间", "最大供电容量", "导管架自重(t)", "淡水存储量(m3)"),
    ("设计年限", "设计注水压力", "设计最大桩基承载力(t)", "压缩空气设计供应能力(Sm3/h)"),
    ("服役到期时间", "钻修机", "上部组块安装重量(t)", "消防水设计供应能力(m3/h)"),
    ("设施原值", "地理信息编码", "生活楼吊重(t)", "海水设计供应能力(m3/h)"),
    ("经度", "单体区域编码", "组块层数(层)", "设计注入水处理能力(m3/d)"),
    ("纬度", "导管架工作点间距(m)", "上部组块操作重量(t)", "上部组块结构用钢量(t)"),
    ("生产厂家", "导管架水平层层数(层)", "上部组块上层甲板尺寸长×宽(m×m)", "第三方发证机构"),
    ("型号", "主桩桩径(mm)", "上部组块中层甲板尺寸长×宽(m×m)", "所属阶段名称"),
    ("设计油处理能力", "生活楼床位数(定员)(人)", "上部组块下层甲板尺寸长×宽(m×m)", "备注"),
]

PLATFORM_DETAIL_FIELDS: List[str] = [
    field
    for row_fields in PLATFORM_DETAIL_FIELD_ROWS
    for field in row_fields
]

PLATFORM_SUMMARY_COLUMNS: List[str] = [
    "分公司",
    "作业公司",
    "油气田",
    "设施编码",
    "设施名称",
    "设施类型",
    "分类",
    "投产时间",
    "设计年限",
    "服役到期时间",
    "设施原值",
    "经度",
    "纬度",
    "生产厂家",
    "型号",
    "设计油处理能力",
    "设计气处理能力",
    "设计水处理能力",
    "导管架腿数",
    "水深",
    "井槽数量",
    "桩数量",
    "供电形式",
    "最大供电容量",
    "设计注水压力",
    "钻修机",
    "地理信息编码",
    "单体区域编码",
    "导管架工作点间距(m)",
    "导管架水平层层数(层)",
    "主桩桩径(mm)",
    "生活楼床位数(定员)(人)",
    "是否有生活楼",
    "生活楼层数",
    "上部组块生活楼吊装重量(t)",
    "生活楼尺寸长×宽×高(m×m×m)",
    "主体最大尺度(m3)",
    "系泊能力(t)",
    "设计抗风能力",
    "导管架自重(t)",
    "设计最大桩基承载力(t)",
    "上部组块安装重量(t)",
    "生活楼吊重(t)",
    "组块层数(层)",
    "上部组块操作重量(t)",
    "上部组块上层甲板尺寸长×宽(m×m)",
    "上部组块中层甲板尺寸长×宽(m×m)",
    "上部组块下层甲板尺寸长×宽(m×m)",
    "上部组块工作甲板尺寸长×宽(m×m)",
    "上部组块下下甲板尺寸长×宽(m×m)",
    "飞机甲板承重能力(t)",
    "飞机甲板尺寸(m×m)",
    "最大储油能力(m3)",
    "柴油存储能力(m3)",
    "供热能力(KW)",
    "淡水存储量(m3)",
    "压缩空气设计供应能力(Sm3/h)",
    "消防水设计供应能力(m3/h)",
    "海水设计供应能力(m3/h)",
    "设计注入水处理能力(m3/d)",
    "上部组块结构用钢量(t)",
    "第三方发证机构",
    "所属阶段名称",
    "备注",
]

PLATFORM_FIELD_ALIASES: dict[str, List[str]] = {
    "设施编码": ["设施编码", "设施编号", "平台编码", "平台编号", "编码"],
    "设施名称": ["设施名称", "平台名称"],
    "分公司": ["分公司", "所属分公司"],
    "作业公司": ["作业公司", "所属作业单元", "所属作业公司", "作业单元", "作业单位"],
    "油气田": ["油气田", "所属油（气）田", "所属油气田", "油田"],
    "设施类型": ["设施类型", "平台类型"],
    "分类": ["分类", "平台分类"],
    "投产时间": ["投产时间", "投产日期", "投产年月"],
    "设计年限": ["设计年限", "设计寿命"],
    "上部组块下下甲板尺寸长×宽(m×m)": ["上部组块下甲板尺寸长×宽(m×m)"],
}


class PlatformDetailDialog(QDialog):
    """单个平台详情弹窗。"""

    DROPDOWN_PLACEHOLDER = "▼"
    YES_NO_OPTIONS = ("是", "否")

    def __init__(self, values: dict[str, str] | None = None, parent=None, *, is_new: bool = False):
        super().__init__(parent)
        self.values = dict(values or {})
        self.is_new = is_new
        self.table: QTableWidget | None = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("新增平台" if self.is_new else "平台详情")
        self.resize(1520, 760)
        self.setModal(True)
        self.setStyleSheet(
            """
            QDialog {
                background: #eef3f8;
            }
            QFrame#DetailCard {
                background: #ffffff;
                border: 1px solid #cfd8e3;
                border-radius: 6px;
            }
            QLabel#DetailTitle {
                color: #172b3a;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#SectionTitle {
                color: #172b3a;
                font-size: 14px;
                font-weight: 700;
                padding: 6px 0;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #222222;
                gridline-color: #222222;
                selection-background-color: #dbe9ff;
                selection-color: #111111;
            }
            QTableWidget::item {
                padding: 2px 6px;
            }
            QPushButton {
                min-height: 32px;
                min-width: 96px;
                padding: 5px 16px;
                border-radius: 4px;
                border: 1px solid #b9c8d8;
                background: #ffffff;
            }
            QPushButton:hover {
                background: #edf5ff;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        card = QFrame()
        card.setObjectName("DetailCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 14)
        card_layout.setSpacing(8)

        title = QLabel("平台所有信息")
        title.setObjectName("DetailTitle")
        section_title = QLabel("基本信息")
        section_title.setObjectName("SectionTitle")

        self.table = QTableWidget(len(PLATFORM_DETAIL_FIELD_ROWS), 8)
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setDefaultSectionSize(30)

        for col in range(8):
            if col % 2 == 0:
                self.table.setColumnWidth(col, 210)
            else:
                self.table.setColumnWidth(col, 135)

        for row, row_fields in enumerate(PLATFORM_DETAIL_FIELD_ROWS):
            self.table.setRowHeight(row, 30)
            for pair_idx, field in enumerate(row_fields):
                label_col = pair_idx * 2
                value_col = label_col + 1
                label_item = QTableWidgetItem(field)
                label_item.setTextAlignment(Qt.AlignCenter)
                label_item.setFlags(Qt.ItemIsEnabled)
                label_item.setBackground(QColor("#e7ebf3"))
                self.table.setItem(row, label_col, label_item)

                value = str(self.values.get(field, "") or "")
                if field.startswith("是否"):
                    value_item = QTableWidgetItem(self._dropdown_cell_text(value))
                    value_item.setData(Qt.UserRole, value if value in self.YES_NO_OPTIONS else "")
                    value_item.setTextAlignment(Qt.AlignCenter)
                    value_item.setToolTip("点击选择")
                    value_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row, value_col, value_item)
                else:
                    value_item = QTableWidgetItem(value)
                    value_item.setTextAlignment(Qt.AlignCenter)
                    value_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
                    self.table.setItem(row, value_col, value_item)

        self.table.cellClicked.connect(self._on_detail_table_cell_clicked)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("保存")
        button_box.button(QDialogButtonBox.Cancel).setText("取消")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        card_layout.addWidget(title)
        card_layout.addWidget(section_title)
        card_layout.addWidget(self.table, 1)
        card_layout.addWidget(button_box)
        root.addWidget(card)

    def get_values(self) -> dict[str, str]:
        if self.table is None:
            return {}
        values: dict[str, str] = {}
        for row, row_fields in enumerate(PLATFORM_DETAIL_FIELD_ROWS):
            for pair_idx, field in enumerate(row_fields):
                value_col = pair_idx * 2 + 1
                item = self.table.item(row, value_col)
                if field.startswith("是否"):
                    values[field] = str(item.data(Qt.UserRole) or "").strip() if item is not None else ""
                    continue
                values[field] = item.text().strip() if item is not None else ""
        return values

    def _dropdown_cell_text(self, value: str) -> str:
        value_text = str(value or "").strip()
        if not value_text:
            return self.DROPDOWN_PLACEHOLDER
        return f"{value_text}  {self.DROPDOWN_PLACEHOLDER}"

    @staticmethod
    def _dropdown_menu_qss() -> str:
        return """
            QMenu {
                background-color: #ffffff;
                color: #1d2b3a;
                border: 1px solid #cfd8e3;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 18px;
                background-color: transparent;
                color: #1d2b3a;
            }
            QMenu::item:selected {
                background-color: #dbe9ff;
                color: #1d2b3a;
            }
        """

    def _on_detail_table_cell_clicked(self, row: int, column: int) -> None:
        if self.table is None or column % 2 == 0:
            return
        field_idx = column // 2
        if not (0 <= row < len(PLATFORM_DETAIL_FIELD_ROWS)):
            return
        row_fields = PLATFORM_DETAIL_FIELD_ROWS[row]
        if not (0 <= field_idx < len(row_fields)):
            return
        if not row_fields[field_idx].startswith("是否"):
            return
        self._open_yes_no_menu(row, column)

    def _open_yes_no_menu(self, row: int, column: int) -> None:
        if self.table is None:
            return
        item = self.table.item(row, column)
        if item is None:
            return

        menu = QMenu(self.table)
        menu.setStyleSheet(self._dropdown_menu_qss())
        for option in self.YES_NO_OPTIONS:
            menu.addAction(option)

        rect = self.table.visualItemRect(item)
        menu_width = menu.sizeHint().width()
        local_x = max(0, rect.right() - menu_width + 1)
        local_y = rect.bottom() + 1
        action = menu.exec_(self.table.viewport().mapToGlobal(QPoint(local_x, local_y)))
        if action is None:
            return

        value = action.text().strip()
        item.setText(self._dropdown_cell_text(value))
        item.setData(Qt.UserRole, value)


class PlatformSummaryPage(BasePage):
    """平台汇总信息页面。"""
    DEFAULT_HEADER_ROW = 0

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
        self._summary_refresh_timer: QTimer | None = None

        self.columns = list(PLATFORM_SUMMARY_COLUMNS)

        self._build_ui()
        self._load_profiles_from_database()

    def _store_session_profiles_cache(self):
        mw = self.window()
        if mw is None:
            return
        try:
            setattr(mw, "platform_summary_profiles_cache", self.current_facility_profiles())
        except Exception:
            pass

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
            QLabel#TableHint {
                color: #5c6f84;
                background: transparent;
                padding: 0 2px 4px 2px;
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

        table_hint = QLabel("双击任意平台行查看/编辑平台全部信息；新增平台会打开同样的详情窗口。")
        table_hint.setObjectName("TableHint")
        table_layout.addWidget(table_hint)

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
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.cellDoubleClicked.connect(self.open_detail_dialog_for_row)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table_layout.addWidget(self.table, 1)

        self._summary_refresh_timer = QTimer(self)
        self._summary_refresh_timer.setSingleShot(True)
        self._summary_refresh_timer.setInterval(200)
        self._summary_refresh_timer.timeout.connect(self._notify_summary_pages_refresh)

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
        self._update_table_columns()

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
        if self._platform_column_match_score(df.columns) <= 0:
            # 兼容旧样表：第一行是标题，第二行才是真正表头。
            fallback_df = pd.read_excel(file_path, header=1, engine=engine)
            fallback_df = fallback_df.dropna(axis=0, how="all")
            fallback_df.columns = self._normalize_columns(fallback_df.columns)
            if self._platform_column_match_score(fallback_df.columns) > self._platform_column_match_score(df.columns):
                df = fallback_df
        return df

    def _platform_column_match_score(self, columns) -> int:
        known = {self._normalize_header_name(col) for col in PLATFORM_SUMMARY_COLUMNS}
        for field, aliases in PLATFORM_FIELD_ALIASES.items():
            known.add(self._normalize_header_name(field))
            for alias in aliases:
                known.add(self._normalize_header_name(alias))
        return sum(1 for col in columns if self._normalize_header_name(col) in known)

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

    def _column_index(self, names: List[str]) -> int | None:
        normalized = {
            self._normalize_header_name(name): index
            for index, name in enumerate(self.columns)
        }
        for name in names:
            index = normalized.get(self._normalize_header_name(name))
            if index is not None:
                return index

        requested = [self._normalize_header_name(name) for name in names if self._normalize_header_name(name)]
        for index, candidate in enumerate(self.columns):
            candidate_norm = self._normalize_header_name(candidate)
            if not candidate_norm:
                continue
            for target in requested:
                if target in candidate_norm or candidate_norm in target:
                    return index
        return None

    @staticmethod
    def _normalize_header_name(value: object) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            return ""
        text = re.sub(r"\s+", "", text)
        text = re.sub(r"[()（）\[\]【】,:：/\\._，；;\-]", "", text)
        return text.lower()

    def _aliases_for_field(self, field: str) -> List[str]:
        aliases = PLATFORM_FIELD_ALIASES.get(field, [])
        return [field, *[alias for alias in aliases if alias != field]]

    def _value_from_mapping(self, mapping: dict, field: str) -> str:
        if not mapping:
            return ""
        normalized = {
            self._normalize_header_name(key): value
            for key, value in mapping.items()
        }
        for alias in self._aliases_for_field(field):
            norm = self._normalize_header_name(alias)
            if norm in normalized:
                return self._display_text(normalized[norm])
        return ""

    def _row_value(self, row: int, names: List[str]) -> str:
        if self.table is None:
            return ""
        index = self._column_index(names)
        if index is None:
            return ""
        item = self.table.item(row, index)
        return item.text().strip() if item is not None else ""

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

        signals_blocked = self.table.blockSignals(True)
        try:
            self._set_table_columns(list(PLATFORM_SUMMARY_COLUMNS))
            self.table.setRowCount(0)
            self.table.clearContents()

            for _, row_data in df.iterrows():
                row = self.table.rowCount()
                self.table.insertRow(row)
                source = {str(col or ""): row_data.get(col, "") for col in df.columns}
                for col, col_name in enumerate(self.columns):
                    value = self._value_from_mapping(source, col_name)
                    self.table.setItem(row, col, QTableWidgetItem(value))

            self._update_table_columns()
        finally:
            self.table.blockSignals(signals_blocked)
        self._store_session_profiles_cache()

    def _load_profiles_from_database(self):
        if self.table is None:
            return
        try:
            summary_source = load_platform_summary_source(snapshot_key="latest")
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", f"读取平台历史汇总信息失败：\n{exc}")
            return

        if summary_source.snapshot and summary_source.snapshot.get("columns"):
            self._apply_snapshot_to_table(summary_source.snapshot)
            self._schedule_summary_pages_refresh()
            return

        profiles = summary_source.profiles
        if not profiles:
            return

        signals_blocked = self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            self.table.clearContents()
            for profile in profiles:
                row = self.table.rowCount()
                self.table.insertRow(row)
                source = {
                    "分公司": profile.get("branch") or "",
                    "作业公司": profile.get("op_company") or "",
                    "油气田": profile.get("oilfield") or "",
                    "设施编码": profile.get("facility_code") or "",
                    "设施名称": profile.get("facility_name") or "",
                    "设施类型": profile.get("facility_type") or "",
                    "分类": profile.get("category") or "",
                    "投产时间": profile.get("start_time") or "",
                    "设计年限": profile.get("design_life") or "",
                }
                for col, col_name in enumerate(self.columns):
                    self.table.setItem(row, col, QTableWidgetItem(str(source.get(col_name, ""))))
            self._update_table_columns()
        finally:
            self.table.blockSignals(signals_blocked)
        self._store_session_profiles_cache()
        self._schedule_summary_pages_refresh()

    def _apply_snapshot_to_table(self, snapshot: dict):
        if self.table is None:
            return
        columns = [str(col or "") for col in (snapshot.get("columns") or [])]
        rows = snapshot.get("rows") or []
        if not columns:
            return

        signals_blocked = self.table.blockSignals(True)
        try:
            self._set_table_columns(list(PLATFORM_SUMMARY_COLUMNS))
            self.table.setRowCount(0)
            self.table.clearContents()
            for row_data in rows:
                row = self.table.rowCount()
                self.table.insertRow(row)
                values = list(row_data) if isinstance(row_data, list) else []
                source = {
                    columns[index]: values[index]
                    for index in range(min(len(columns), len(values)))
                }
                for col, col_name in enumerate(self.columns):
                    value = self._value_from_mapping(source, col_name)
                    self.table.setItem(row, col, QTableWidgetItem(value))
            self._update_table_columns()
        finally:
            self.table.blockSignals(signals_blocked)
        self._store_session_profiles_cache()

    def _collect_snapshot_rows(self) -> List[List[str]]:
        if self.table is None:
            return []
        rows: List[List[str]] = []
        for row in range(self.table.rowCount()):
            values: List[str] = []
            has_content = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                text = item.text() if item is not None else ""
                if text.strip():
                    has_content = True
                values.append(text)
            if has_content:
                rows.append(values)
        return rows

    def _sync_profiles_to_database(self, silent: bool = False) -> tuple[int, int, List[str]]:
        if self.table is None:
            return 0, 0, []

        saved = 0
        skipped = 0
        errors: List[str] = []
        for row in range(self.table.rowCount()):
            facility_code = self._row_value(row, ["设施编码", "设施编号", "平台编码", "平台编号", "编码"])
            if not facility_code:
                skipped += 1
                continue
            payload = {
                "facility_name": self._row_value(row, ["设施名称", "平台名称"]),
                "branch": self._row_value(row, ["分公司", "所属分公司"]),
                "op_company": self._row_value(row, ["作业公司", "所属作业单元", "所属作业公司", "作业单元", "作业单位"]),
                "oilfield": self._row_value(row, ["油气田", "所属油（气）田", "所属油气田"]),
                "facility_type": self._row_value(row, ["设施类型", "平台类型"]),
                "category": self._row_value(row, ["分类", "平台分类"]),
                "start_time": self._row_value(row, ["投产时间", "投产日期", "投产年月"]),
                "design_life": self._row_value(row, ["设计年限", "设计寿命"]),
            }
            try:
                save_facility_profile(facility_code, payload)
                saved += 1
            except Exception as exc:
                errors.append(f"第 {row + 1} 行 {facility_code}：{exc}")

        if errors and not silent:
            QMessageBox.warning(self, "保存失败", "部分平台档案同步失败：\n" + "\n".join(errors[:5]))
        return saved, skipped, errors

    def current_facility_profiles(self) -> List[dict]:
        """Return profiles represented by the current table, including unsaved edits."""
        if self.table is None:
            return []

        profiles: List[dict] = []
        for row in range(self.table.rowCount()):
            profile = {
                "facility_code": self._row_value(row, ["设施编码", "设施编号", "平台编码", "平台编号", "编码"]),
                "facility_name": self._row_value(row, ["设施名称", "平台名称"]),
                "branch": self._row_value(row, ["分公司", "所属分公司"]),
                "op_company": self._row_value(row, ["作业公司", "所属作业单元", "所属作业公司", "作业单元", "作业单位"]),
                "oilfield": self._row_value(row, ["油气田", "所属油（气）田", "所属油气田"]),
                "facility_type": self._row_value(row, ["设施类型", "平台类型"]),
                "category": self._row_value(row, ["分类", "平台分类"]),
                "start_time": self._row_value(row, ["投产时间", "投产日期", "投产年月"]),
                "design_life": self._row_value(row, ["设计年限", "设计寿命"]),
            }
            if not any(str(value or "").strip() for value in profile.values()):
                continue
            profiles.append(profile)
        return profiles

    def _update_table_columns(self):
        if self.table is None:
            return
        header = self.table.horizontalHeader()
        self.table.resizeColumnsToContents()
        for col in range(self.table.columnCount()):
            self.table.setColumnHidden(col, False)
            header.setSectionResizeMode(col, QHeaderView.Interactive)
            width = self.table.columnWidth(col)
            self.table.setColumnWidth(col, min(max(width + 18, 96), 240))
        header.setStretchLastSection(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

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

    def _on_table_item_changed(self, _item: QTableWidgetItem):
        self._store_session_profiles_cache()
        self._schedule_summary_pages_refresh()

    def _schedule_summary_pages_refresh(self):
        if self._summary_refresh_timer is None:
            self._notify_summary_pages_refresh()
            return
        self._summary_refresh_timer.start()

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
        dialog = PlatformDetailDialog({}, self, is_new=True)
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.get_values()
        if not any(str(value or "").strip() for value in values.values()):
            QMessageBox.information(self, "提示", "未录入任何平台数据。")
            return

        if self.table is None:
            return

        row = self.table.rowCount()
        self.table.insertRow(row)
        self._write_row_values(row, values)

        self._update_table_columns()
        self._store_session_profiles_cache()
        self._schedule_summary_pages_refresh()
        QMessageBox.information(self, "新增完成", "已新增 1 条平台记录。")

    def open_detail_dialog_for_row(self, row: int, _col: int = 0):
        if self.table is None or row < 0 or row >= self.table.rowCount():
            return
        values = self._row_values_dict(row)
        dialog = PlatformDetailDialog(values, self, is_new=False)
        if dialog.exec_() != QDialog.Accepted:
            return
        self._write_row_values(row, dialog.get_values())
        self._update_table_columns()
        self._store_session_profiles_cache()
        self._schedule_summary_pages_refresh()

    def _row_values_dict(self, row: int) -> dict[str, str]:
        if self.table is None:
            return {}
        values: dict[str, str] = {}
        for col, col_name in enumerate(self.columns):
            item = self.table.item(row, col)
            values[col_name] = item.text().strip() if item is not None else ""
        return values

    def _write_row_values(self, row: int, values: dict[str, str]):
        if self.table is None:
            return
        signals_blocked = self.table.blockSignals(True)
        try:
            for col, col_name in enumerate(self.columns):
                text = str(values.get(col_name, "") or "")
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    self.table.setItem(row, col, item)
                item.setText(text)
        finally:
            self.table.blockSignals(signals_blocked)

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
        if not ask_yes_no(
            self,
            "删除选中平台",
            f"确认删除选中的 {count} 个平台吗？",
        ):
            return

        for row in rows:
            self.table.removeRow(row)
        self._store_session_profiles_cache()
        self._schedule_summary_pages_refresh()

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
        self._store_session_profiles_cache()
        self._notify_summary_pages_refresh()

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
        if self.table is None:
            return

        preferred_facility_code = self._preferred_new_facility_code_for_refresh()
        try:
            save_platform_summary_snapshot(
                self.columns,
                self._collect_snapshot_rows(),
                snapshot_key="latest",
                snapshot_name="平台汇总信息",
            )
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"保存平台汇总完整表失败：\n{exc}")
            return

        saved, skipped, errors = self._sync_profiles_to_database()
        refresh_platform_profiles_cache()
        self._store_session_profiles_cache()
        self._notify_summary_pages_refresh(preferred_facility_code=preferred_facility_code)
        msg = f"已保存 {saved} 条平台档案到数据库。"
        if skipped:
            msg += f"\n跳过 {skipped} 条未识别到设施编码的记录。"
        if errors:
            msg += "\n\n失败记录：\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "保存", msg)

    def _preferred_new_facility_code_for_refresh(self) -> str:
        try:
            existing_profiles = load_platform_summary_source(snapshot_key="latest").profiles
        except Exception:
            existing_profiles = []

        existing_codes = {
            str(profile.get("facility_code") or "").strip().lower()
            for profile in existing_profiles
            if str(profile.get("facility_code") or "").strip()
        }
        for profile in reversed(self.current_facility_profiles()):
            code = str(profile.get("facility_code") or "").strip()
            if code and code.lower() not in existing_codes:
                return code
        return ""

    def _notify_summary_pages_refresh(self, preferred_facility_code: str | None = None):
        mw = self.window()
        tab_widget = getattr(mw, "tab_widget", None)
        if tab_widget is None:
            return
        preferred_code = str(preferred_facility_code or "").strip()
        for index in range(tab_widget.count()):
            page = tab_widget.widget(index)
            refresh = getattr(page, "refresh_from_database", None)
            if callable(refresh):
                refresh()
            refresh_platform_options = getattr(page, "refresh_platform_options", None)
            if callable(refresh_platform_options):
                refresh_platform_options()
                continue
            sync_platform_ui = getattr(page, "_sync_platform_ui", None)
            if callable(sync_platform_ui):
                changed_key = None
                if preferred_code and PlatformSummaryPage._set_preferred_facility_code(page, preferred_code):
                    changed_key = "facility_code"
                if changed_key:
                    try:
                        sync_platform_ui(changed_key=changed_key)
                    except TypeError:
                        sync_platform_ui()
                else:
                    sync_platform_ui()

    @staticmethod
    def _set_preferred_facility_code(page, facility_code: str) -> bool:
        dropdown_bar = getattr(page, "dropdown_bar", None)
        if dropdown_bar is None:
            return False
        try:
            dropdown_bar.set_options("facility_code", [facility_code], facility_code)
            return True
        except Exception:
            return False

