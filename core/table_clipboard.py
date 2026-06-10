# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import QObject, QEvent, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem


CanPasteCell = Callable[[int, int], bool]
PasteRowsIgnoredCallback = Callable[[int], None]
PasteCellsSkippedCallback = Callable[[int], None]


class TableClipboardController(QObject):
    """Excel-compatible copy/cut/paste support for QTableWidget."""

    def __init__(
        self,
        table: QTableWidget,
        *,
        can_paste_cell: CanPasteCell | None = None,
        on_paste_rows_ignored: PasteRowsIgnoredCallback | None = None,
        on_paste_cells_skipped: PasteCellsSkippedCallback | None = None,
    ) -> None:
        super().__init__(table)
        self._table = table
        self._can_paste_cell = can_paste_cell
        self._on_paste_rows_ignored = on_paste_rows_ignored
        self._on_paste_cells_skipped = on_paste_cells_skipped
        table.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._table and event.type() == QEvent.KeyPress:
            key_event = event
            if isinstance(key_event, QKeyEvent):
                if key_event.modifiers() & Qt.ControlModifier:
                    if key_event.key() == Qt.Key_C:
                        self.copy_selection()
                        return True
                    if key_event.key() == Qt.Key_X:
                        self.cut_selection()
                        return True
                    if key_event.key() == Qt.Key_V:
                        self.paste_from_clipboard()
                        return True
                if key_event.modifiers() == Qt.NoModifier and key_event.key() in (
                    Qt.Key_Delete,
                    Qt.Key_Backspace,
                ):
                    self.clear_selection()
                    return True
        return super().eventFilter(obj, event)

    def copy_selection(self) -> None:
        indexes = self._table.selectedIndexes()
        rows = sorted({index.row() for index in indexes})
        cols = sorted({index.column() for index in indexes})
        if not rows or not cols:
            return

        selected = {(index.row(), index.column()) for index in indexes}
        lines: list[str] = []
        for row in rows:
            values: list[str] = []
            for col in cols:
                values.append(self._cell_text(row, col) if (row, col) in selected else "")
            lines.append("\t".join(values))
        QApplication.clipboard().setText("\n".join(lines))

    def cut_selection(self) -> None:
        self.copy_selection()
        self.clear_selection()

    def clear_selection(self) -> None:
        for index in self._table.selectedIndexes():
            row = index.row()
            col = index.column()
            if self._is_writable_cell(row, col):
                self._ensure_item(row, col).setText("")

    def paste_from_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return

        start_row, start_col = self._paste_start_cell()
        ignored_rows = 0
        skipped_cells = 0
        lines = text.splitlines()
        paste_lines = self._target_paste_lines(lines)
        for row_offset, line in enumerate(paste_lines):
            row = start_row + row_offset
            if row >= self._table.rowCount():
                ignored_rows += len(paste_lines) - row_offset
                break
            row_written = False
            for col_offset, value in enumerate(line.split("\t")):
                col = start_col + col_offset
                if col >= self._table.columnCount():
                    break
                if self._is_writable_cell(row, col):
                    self._ensure_item(row, col).setText(value)
                    row_written = True
                else:
                    skipped_cells += 1
            if not row_written:
                ignored_rows += 1
        if ignored_rows and self._on_paste_rows_ignored is not None:
            self._on_paste_rows_ignored(ignored_rows)
        if skipped_cells and self._on_paste_cells_skipped is not None:
            self._on_paste_cells_skipped(skipped_cells)

    def _paste_start_cell(self) -> tuple[int, int]:
        indexes = self._table.selectedIndexes()
        current = (max(0, self._table.currentRow()), max(0, self._table.currentColumn()))
        if indexes:
            selected = {(index.row(), index.column()) for index in indexes}
            if len(selected) <= 1 or current not in selected:
                return current
            return (
                min(index.row() for index in indexes),
                min(index.column() for index in indexes),
            )
        return current

    def _target_paste_lines(self, lines: list[str]) -> list[str]:
        if len(lines) != 1:
            return lines

        selected_rows = {index.row() for index in self._table.selectedIndexes()}
        if len(selected_rows) <= 1:
            return lines

        return lines * len(selected_rows)

    def _cell_text(self, row: int, col: int) -> str:
        widget = self._table.cellWidget(row, col)
        if widget is not None:
            current_text = getattr(widget, "currentText", None)
            return str(current_text()) if callable(current_text) else ""
        item = self._table.item(row, col)
        return item.text() if item is not None else ""

    def _is_writable_cell(self, row: int, col: int) -> bool:
        if self._can_paste_cell is not None and not self._can_paste_cell(row, col):
            return False
        if self._table.cellWidget(row, col) is not None:
            return False
        item = self._table.item(row, col)
        if item is None:
            return True
        return bool(item.flags() & Qt.ItemIsEditable)

    def _ensure_item(self, row: int, col: int) -> QTableWidgetItem:
        item = self._table.item(row, col)
        if item is None:
            item = QTableWidgetItem("")
            self._table.setItem(row, col, item)
        return item
