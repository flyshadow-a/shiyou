# -*- coding: utf-8 -*-
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QColor  # noqa: E402
from PyQt5.QtWidgets import QApplication, QTableWidget  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
