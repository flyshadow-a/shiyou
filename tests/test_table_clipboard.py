# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QItemSelectionModel, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QTableWidgetSelectionRange,
)

from core.table_clipboard import TableClipboardController


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _item(text: str, *, editable: bool = True) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    flags = item.flags()
    if editable:
        flags |= Qt.ItemIsEditable
    else:
        flags &= ~Qt.ItemIsEditable
    item.setFlags(flags)
    return item


class TableClipboardControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _ensure_app()

    def setUp(self) -> None:
        QApplication.clipboard().clear()

    def _table(self) -> QTableWidget:
        table = QTableWidget(3, 3)
        self.addCleanup(table.deleteLater)
        for row in range(3):
            for col in range(3):
                table.setItem(row, col, _item(f"r{row}c{col}"))
        return table

    def test_copy_selection_writes_excel_compatible_tsv(self) -> None:
        table = self._table()
        TableClipboardController(table)
        table.setRangeSelected(QTableWidgetSelectionRange(0, 1, 1, 2), True)

        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_C, Qt.ControlModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("r0c1\tr0c2\nr1c1\tr1c2", QApplication.clipboard().text())

    def test_paste_skips_read_only_widget_and_callback_disallowed_cells(self) -> None:
        table = self._table()
        table.setItem(0, 1, _item("readonly", editable=False))
        table.setCellWidget(1, 0, QComboBox(table))
        TableClipboardController(table, can_paste_cell=lambda row, col: col != 2)

        QApplication.clipboard().setText("a\tb\tc\nd\te\tf")
        table.setCurrentCell(0, 0)
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("a", table.item(0, 0).text())
        self.assertEqual("readonly", table.item(0, 1).text())
        self.assertEqual("r0c2", table.item(0, 2).text())
        self.assertEqual("r1c0", table.item(1, 0).text())
        self.assertEqual("e", table.item(1, 1).text())
        self.assertEqual("r1c2", table.item(1, 2).text())

    def test_paste_reports_skipped_protected_cells(self) -> None:
        table = self._table()
        skipped_counts = []
        table.setItem(0, 1, _item("readonly", editable=False))
        table.setCellWidget(1, 0, QComboBox(table))
        TableClipboardController(
            table,
            can_paste_cell=lambda row, col: col != 2,
            on_paste_cells_skipped=skipped_counts.append,
        )

        QApplication.clipboard().setText("a\tb\tc\nd\te\tf")
        table.setCurrentCell(0, 0)
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("a", table.item(0, 0).text())
        self.assertEqual("readonly", table.item(0, 1).text())
        self.assertEqual("r0c2", table.item(0, 2).text())
        self.assertEqual("r1c0", table.item(1, 0).text())
        self.assertEqual("e", table.item(1, 1).text())
        self.assertEqual("r1c2", table.item(1, 2).text())
        self.assertEqual([4], skipped_counts)

    def test_paste_does_not_report_protected_cells_for_rows_past_table_bottom(self) -> None:
        table = self._table()
        overflow_counts = []
        skipped_counts = []
        TableClipboardController(
            table,
            on_paste_rows_ignored=overflow_counts.append,
            on_paste_cells_skipped=skipped_counts.append,
        )

        QApplication.clipboard().setText("a\tb\nc\td")
        table.setCurrentCell(2, 0)
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual([1], overflow_counts)
        self.assertEqual([], skipped_counts)

    def test_paste_starts_at_top_left_of_selected_range_not_current_cell(self) -> None:
        table = self._table()
        TableClipboardController(table)
        table.setRangeSelected(QTableWidgetSelectionRange(1, 0, 1, 2), True)
        table.selectionModel().setCurrentIndex(
            table.model().index(1, 2),
            QItemSelectionModel.NoUpdate,
        )

        QApplication.clipboard().setText("a\tb\tc")
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("a", table.item(1, 0).text())
        self.assertEqual("b", table.item(1, 1).text())
        self.assertEqual("c", table.item(1, 2).text())

    def test_paste_repeats_single_clipboard_row_across_selected_rows(self) -> None:
        table = self._table()
        TableClipboardController(table)
        table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 2, 1), True)

        QApplication.clipboard().setText("a\tb")
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("a", table.item(0, 0).text())
        self.assertEqual("b", table.item(0, 1).text())
        self.assertEqual("a", table.item(1, 0).text())
        self.assertEqual("b", table.item(1, 1).text())
        self.assertEqual("a", table.item(2, 0).text())
        self.assertEqual("b", table.item(2, 1).text())

    def test_paste_reports_rows_beyond_table_bottom(self) -> None:
        table = self._table()
        overflow_counts = []
        TableClipboardController(table, on_paste_rows_ignored=overflow_counts.append)

        QApplication.clipboard().setText("a\nb\nc")
        table.setCurrentCell(2, 0)
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("a", table.item(2, 0).text())
        self.assertEqual([2], overflow_counts)

    def test_paste_reports_rows_with_no_writable_targets(self) -> None:
        table = self._table()
        overflow_counts = []
        TableClipboardController(
            table,
            can_paste_cell=lambda row, col: row == 0,
            on_paste_rows_ignored=overflow_counts.append,
        )

        QApplication.clipboard().setText("a\nb\nc")
        table.setCurrentCell(0, 0)
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("a", table.item(0, 0).text())
        self.assertEqual("r1c0", table.item(1, 0).text())
        self.assertEqual("r2c0", table.item(2, 0).text())
        self.assertEqual([2], overflow_counts)

    def test_cut_copies_then_clears_only_editable_allowed_cells(self) -> None:
        table = self._table()
        table.setItem(0, 1, _item("readonly", editable=False))
        TableClipboardController(
            table,
            can_paste_cell=lambda row, col: not (row == 1 and col == 1),
        )
        table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 1), True)

        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_X, Qt.ControlModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("r0c0\treadonly\nr1c0\tr1c1", QApplication.clipboard().text())
        self.assertEqual("", table.item(0, 0).text())
        self.assertEqual("readonly", table.item(0, 1).text())
        self.assertEqual("", table.item(1, 0).text())
        self.assertEqual("r1c1", table.item(1, 1).text())

    def test_delete_clears_selected_editable_allowed_cells(self) -> None:
        table = self._table()
        table.setItem(0, 1, _item("readonly", editable=False))
        TableClipboardController(
            table,
            can_paste_cell=lambda row, col: not (row == 1 and col == 1),
        )
        table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 1), True)

        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("", table.item(0, 0).text())
        self.assertEqual("readonly", table.item(0, 1).text())
        self.assertEqual("", table.item(1, 0).text())
        self.assertEqual("r1c1", table.item(1, 1).text())

    def test_backspace_clears_selected_editable_allowed_cells(self) -> None:
        table = self._table()
        table.setItem(0, 1, _item("readonly", editable=False))
        TableClipboardController(table)
        table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 0, 1), True)

        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
        QApplication.sendEvent(table, event)

        self.assertEqual("", table.item(0, 0).text())
        self.assertEqual("readonly", table.item(0, 1).text())


if __name__ == "__main__":
    unittest.main()
