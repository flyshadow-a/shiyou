from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

from pages.history_inspection_summary_page import HistoryInspectionSummaryPage  # noqa: E402
from pages.model_files_page import ModelFilesPage  # noqa: E402
from pages.new_special_inspection_page import NewSpecialInspectionPage  # noqa: E402


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class GuiSmokeBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _ensure_app()


class NewSpecialInspectionPageSmokeTests(GuiSmokeBase):
    def test_page_constructs_and_splits_fatigue_groups(self) -> None:
        fatigue_records = [
            r"D:\demo\fatigue\4-1\ftglst",
            r"D:\demo\fatigue\4-1\ftginp.demo",
            r"D:\demo\fatigue\4-2\ftglst",
            r"D:\demo\fatigue\4-2\ftginp.demo",
        ]

        def fake_fetch(self, category: str, branch: str | None = None):
            if category == self.CATEGORY_MODEL:
                return []
            if category == self.CATEGORY_COLLAPSE:
                return []
            if category == self.CATEGORY_FATIGUE:
                if branch == "result":
                    return [p for p in fatigue_records if "ftglst" in p.lower()]
                if branch == "input":
                    return [p for p in fatigue_records if "ftginp" in p.lower()]
                return list(fatigue_records)
            return []

        with patch.object(NewSpecialInspectionPage, "_db_fetch_file_records", fake_fetch), patch.object(
            NewSpecialInspectionPage,
            "_refresh_model_preview",
            lambda self: None,
        ):
            page = NewSpecialInspectionPage("WC19-1D")
            self.addCleanup(page.deleteLater)
            self.assertEqual(len(page.fatigue_result_files), 2)
            self.assertEqual(len(page.fatigue_input_files), 2)
            self.assertGreater(page.files_table.rowCount(), 0)

    def test_collect_runtime_input_overrides_requires_complete_fatigue_groups(self) -> None:
        with patch.object(NewSpecialInspectionPage, "_db_fetch_file_records", lambda *args, **kwargs: []), patch.object(
            NewSpecialInspectionPage,
            "_refresh_model_preview",
            lambda self: None,
        ):
            page = NewSpecialInspectionPage("WC19-1D")
            self.addCleanup(page.deleteLater)
            with tempfile.TemporaryDirectory() as tmp:
                model_path = Path(tmp) / "sacinp.demo"
                collapse_path = Path(tmp) / "clplog"
                ftglst_path = Path(tmp) / "ftglst"
                ftginp_path = Path(tmp) / "ftginp.demo"
                for path in (model_path, collapse_path, ftglst_path, ftginp_path):
                    path.write_text("demo", encoding="utf-8")

                page.model_files = [str(model_path)]
                page.collapse_files = [str(collapse_path)]
                page.fatigue_result_files = [str(ftglst_path)]
                page.fatigue_input_files = []
                overrides = page._collect_runtime_input_overrides()
                self.assertIn("model", overrides)
                self.assertIn("clplog", overrides)
                self.assertNotIn("ftglst", overrides)
                self.assertNotIn("ftginp", overrides)

                page.fatigue_input_files = [str(ftginp_path)]
                overrides = page._collect_runtime_input_overrides()
                self.assertEqual(overrides["ftglst"], [str(ftglst_path)])
                self.assertEqual(overrides["ftginp"], [str(ftginp_path)])

    def test_validate_fatigue_groups_blocks_incomplete_group(self) -> None:
        with patch.object(NewSpecialInspectionPage, "_db_fetch_file_records", lambda *args, **kwargs: []), patch.object(
            NewSpecialInspectionPage,
            "_refresh_model_preview",
            lambda self: None,
        ):
            page = NewSpecialInspectionPage("WC19-1D")
            self.addCleanup(page.deleteLater)
            with tempfile.TemporaryDirectory() as tmp:
                ftglst_path = Path(tmp) / "ftglst"
                ftglst_path.write_text("demo", encoding="utf-8")
                page.fatigue_result_files = [str(ftglst_path)]
                page.fatigue_input_files = []
                with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok) as warning:
                    self.assertFalse(page._validate_fatigue_groups())
                    warning.assert_called()


class ModelFilesPageSmokeTests(GuiSmokeBase):
    def test_page_syncs_facility_code_to_docs_widget(self) -> None:
        page = ModelFilesPage()
        self.addCleanup(page.deleteLater)
        self.assertTrue(page.docs_widget.facility_code)
        page.dropdown_bar.set_value("facility_code", "WC9-7")
        page._sync_platform_ui(changed_key="facility_code")
        self.assertEqual(page.docs_widget.facility_code, "WC9-7")


class HistoryInspectionSummaryPageSmokeTests(GuiSmokeBase):
    def test_page_constructs_and_switches_facility(self) -> None:
        with patch("pages.history_inspection_summary_page.list_inspection_projects", return_value=[]), patch(
            "pages.history_inspection_summary_page.list_inspection_findings",
            return_value=[],
        ):
            page = HistoryInspectionSummaryPage()
            self.addCleanup(page.deleteLater)
            page.set_facility_code("WC9-7")
            self.assertEqual(page.facility_code, "WC9-7")
            self.assertEqual(page._project_file_key("periodic", {"id": 12}, 0), "periodic_project_12")
            self.assertEqual(page._project_file_key("special_event", None, 3), "special_event_row_3")


if __name__ == "__main__":
    unittest.main()
