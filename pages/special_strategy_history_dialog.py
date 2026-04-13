# -*- coding: utf-8 -*-

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from special_strategy_services import SpecialStrategyResultService


class SpecialStrategyHistoryDialog(QDialog):
    def __init__(
        self,
        facility_code: str,
        parent=None,
        *,
        result_service: SpecialStrategyResultService | None = None,
    ):
        super().__init__(parent)
        self.facility_code = facility_code
        self.selected_run_id: int | None = None
        self.selected_action = "summary"
        self._result_service = result_service or SpecialStrategyResultService()
        self.setWindowTitle(f"{facility_code}特检策略历史记录")
        self.resize(760, 420)
        self._build_ui()
        self._load_rows()

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background: #e6eef7;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QTableWidget {
                background: #ffffff;
                gridline-color: #d0d0d0;
                border: 1px solid #d0d0d0;
            }
            QHeaderView::section {
                background: #f3f6fb;
                color: #000000;
                border: 1px solid #e6e6e6;
                padding: 4px 6px;
                font-weight: normal;
            }
            QPushButton {
                background: #efefef;
                border: 1px solid #666;
                min-height: 32px;
                padding: 4px 12px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hint = QLabel(f"当前仅显示平台 {self.facility_code} 的历史计算记录")
        layout.addWidget(hint)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["记录ID", "平台编码", "计算时间", "报告时间", "状态"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemDoubleClicked.connect(self._accept_result_view)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_refresh = QPushButton("刷新")
        self.btn_load_summary = QPushButton("加载到主页")
        self.btn_view_result = QPushButton("查看结果")
        self.btn_close = QPushButton("关闭")

        self.btn_refresh.clicked.connect(self._load_rows)
        self.btn_load_summary.clicked.connect(self._accept_summary_view)
        self.btn_view_result.clicked.connect(self._accept_result_view)
        self.btn_close.clicked.connect(self.reject)

        for button in (self.btn_refresh, self.btn_load_summary, self.btn_view_result, self.btn_close):
            btn_row.addWidget(button)
        layout.addLayout(btn_row)

    def _load_rows(self) -> None:
        rows = self._result_service.list_history(self.facility_code, limit=100)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                str(row.run_id),
                row.facility_code,
                row.updated_at,
                row.report_generated_at,
                row.status,
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                if col_index == 0:
                    item.setData(Qt.UserRole, row.run_id)
                self.table.setItem(row_index, col_index, item)
        if rows:
            self.table.selectRow(0)

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.UserRole)
        try:
            return int(value)
        except Exception:
            return None

    def _accept_summary_view(self, *_args) -> None:
        run_id = self._selected_id()
        if run_id is None:
            QMessageBox.information(self, "提示", "请先选择一条历史记录。")
            return
        self.selected_run_id = run_id
        self.selected_action = "summary"
        self.accept()

    def _accept_result_view(self, *_args) -> None:
        run_id = self._selected_id()
        if run_id is None:
            QMessageBox.information(self, "提示", "请先选择一条历史记录。")
            return
        self.selected_run_id = run_id
        self.selected_action = "result"
        self.accept()
