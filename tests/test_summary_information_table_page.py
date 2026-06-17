# -*- coding: utf-8 -*-
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtGui import QColor, QKeyEvent  # noqa: E402
from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetSelectionRange  # noqa: E402

from pages.summary_information_table_page import SummaryInformationTablePage


_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


class SummaryInformationTablePageTest(unittest.TestCase):
    def test_profiles_from_saved_platform_summary_source(self) -> None:
        page = SummaryInformationTablePage.__new__(SummaryInformationTablePage)

        source_profiles = [
            {
                "facility_code": "WC19-1D",
                "facility_name": "WC19-1D平台",
                "branch": "湛江分公司",
                "op_company": "文昌作业公司",
                "oilfield": "文昌油田",
                "facility_type": "导管架平台",
                "category": "有人平台",
                "start_time": "2013-07-15",
                "design_life": "15",
            }
        ]

        with patch(
            "pages.summary_information_table_page.load_platform_summary_source",
            return_value=SimpleNamespace(profiles=source_profiles),
        ):
            profiles = page._profiles_from_saved_platform_summary_snapshot()

        self.assertEqual(source_profiles, profiles)

    def test_apply_data_does_not_render_first_data_row_green(self) -> None:
        _ensure_app()
        page = SummaryInformationTablePage.__new__(SummaryInformationTablePage)
        page.table = QTableWidget(2, 15)

        page._apply_data([["1", "branch"], ["2", "other"]])

        first_data_item = page.table.item(2, 0)
        self.assertIsNotNone(first_data_item)
        self.assertNotEqual(QColor(0, 170, 0), first_data_item.foreground().color())

    def test_apply_data_makes_only_data_cells_after_first_six_columns_editable(self) -> None:
        _ensure_app()
        page = SummaryInformationTablePage.__new__(SummaryInformationTablePage)
        page.table = page._build_table_skeleton()

        page._apply_data(
            [[
                "1",
                "branch",
                "company",
                "facility",
                "2020",
                "15",
                "100",
                "200",
                "3.5",
                "400",
                "10.2",
                "5.8",
                "0.95",
                "1.05",
                "8",
            ]]
        )

        self.assertFalse(bool(page.table.item(0, 6).flags() & Qt.ItemIsEditable))
        self.assertFalse(bool(page.table.item(2, 5).flags() & Qt.ItemIsEditable))
        self.assertTrue(bool(page.table.item(2, 6).flags() & Qt.ItemIsEditable))
        self.assertTrue(bool(page.table.item(2, 14).flags() & Qt.ItemIsEditable))

    def test_summary_table_clipboard_paste_skips_headers_and_first_six_columns(self) -> None:
        _ensure_app()
        QApplication.clipboard().clear()
        page = SummaryInformationTablePage.__new__(SummaryInformationTablePage)
        page.table = page._build_table_skeleton()
        page._apply_data([["1", "branch", "company", "facility", "2020", "15", "", ""]])
        try:
            table = page.table
            table.setRangeSelected(QTableWidgetSelectionRange(2, 5, 2, 7), True)
            table.setCurrentCell(2, 5)
            QApplication.clipboard().setText("a\tb\tc")

            paste_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
            QApplication.sendEvent(table, paste_event)

            self.assertEqual("15", table.item(2, 5).text())
            self.assertEqual("b", table.item(2, 6).text())
            self.assertEqual("c", table.item(2, 7).text())
        finally:
            table.deleteLater()
            QApplication.instance().processEvents()

    def test_summary_apply_data_keeps_center_text_as_provided(self) -> None:
        _ensure_app()
        page = SummaryInformationTablePage.__new__(SummaryInformationTablePage)
        page.table = page._build_table_skeleton()
        page._apply_data([["1", "B", "O", "N", "2024", "15", "100", "10", "10%", "400", "1，2，3", "5", "0.95", "1.05", "8"]])

        self.assertEqual("1，2，3", page.table.item(2, 10).text())


if __name__ == "__main__":
    unittest.main()
