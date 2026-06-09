# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QAbstractItemView

from core.table_clipboard import TableClipboardController
from pages.feasibility_assessment_page import FeasibilityAssessmentPage


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class FeasibilityAssessmentTableClipboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _ensure_app()

    def setUp(self) -> None:
        QApplication.clipboard().clear()

    def _page(self) -> FeasibilityAssessmentPage:
        page = FeasibilityAssessmentPage(
            main_window=None,
            facility_code="TEST-FACILITY",
            elevations=[36, 31, 27],
        )
        self.addCleanup(page.deleteLater)
        return page

    def test_three_input_tables_install_excel_clipboard_controller(self) -> None:
        page = self._page()

        for table in (page.tbl1, page.tbl2, page.tbl3):
            self.assertIsInstance(table._table_clipboard, TableClipboardController)
            self.assertEqual(QAbstractItemView.ExtendedSelection, table.selectionMode())
            self.assertEqual(QAbstractItemView.SelectItems, table.selectionBehavior())

    def test_clipboard_policy_skips_headers_row_numbers_and_combo_cells(self) -> None:
        page = self._page()

        self.assertFalse(page._can_paste_input_table_cell(page.tbl1, 0, 1, 2))
        self.assertFalse(page._can_paste_input_table_cell(page.tbl1, 2, 0, 2))
        self.assertTrue(page._can_paste_input_table_cell(page.tbl1, 2, 1, 2))
        self.assertFalse(page._can_paste_input_table_cell(page.tbl1, 2, 8, 2))

        self.assertFalse(page._can_paste_input_table_cell(page.tbl2, 1, 1, 2))
        self.assertFalse(page._can_paste_input_table_cell(page.tbl2, 2, 0, 2))
        self.assertTrue(page._can_paste_input_table_cell(page.tbl2, 2, 1, 2))
        self.assertFalse(page._can_paste_input_table_cell(page.tbl2, 2, 9, 2))

        self.assertFalse(page._can_paste_input_table_cell(page.tbl3, 0, 1, 2))
        self.assertFalse(page._can_paste_input_table_cell(page.tbl3, 2, 0, 2))
        self.assertTrue(page._can_paste_input_table_cell(page.tbl3, 2, 1, 2))

    def test_paste_updates_editable_cells_in_top_block_weight_table(self) -> None:
        page = self._page()

        QApplication.clipboard().setText("1\t2\t3")
        page.tbl3.setCurrentCell(2, 1)
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(page.tbl3, event)

        self.assertEqual("1", page.tbl3.item(2, 1).text())
        self.assertEqual("2", page.tbl3.item(2, 2).text())
        self.assertEqual("3", page.tbl3.item(2, 3).text())
        self.assertEqual("", page.tbl3.item(2, 4).text())


if __name__ == "__main__":
    unittest.main()
