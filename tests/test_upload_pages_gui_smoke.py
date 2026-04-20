from __future__ import annotations

import datetime
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

from pages.history_inspection_summary_page import HistoryInspectionSummaryPage  # noqa: E402
from pages.doc_man import DocManWidget  # noqa: E402
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
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fatigue_records = [
                str((base / "4-1" / "ftglst")),
                str((base / "4-1" / "ftginp.demo")),
                str((base / "4-2" / "ftglst")),
                str((base / "4-2" / "ftginp.demo")),
            ]
            for raw in fatigue_records:
                path = Path(raw)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("demo", encoding="utf-8")

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

    def test_page_shows_current_model_file_metadata_in_upload_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model_path = base / "sacinp.demo"
            collapse_path = base / "clplog"
            ftglst_path = base / "ftglst"
            ftginp_path = base / "ftginp.demo"
            for path in (model_path, collapse_path, ftglst_path, ftginp_path):
                path.write_text("demo", encoding="utf-8")

            modified_at = datetime.datetime(2026, 4, 20, 12, 0, 0)

            def fake_rows(self, category: str, branch: str | None = None):
                if category == self.CATEGORY_MODEL:
                    return [
                        {
                            "storage_path": str(model_path),
                            "display_path": str(model_path),
                            "original_name": "sacinp.demo",
                            "logical_path": "WC19-1D/当前模型/结构模型/用户上传/结构模型文件",
                            "category_name": "结构模型文件",
                            "work_condition": "",
                            "remark": "模型备注",
                            "source_modified_at": modified_at,
                        }
                    ]
                if category == self.CATEGORY_COLLAPSE:
                    return [
                        {
                            "storage_path": str(collapse_path),
                            "display_path": str(collapse_path),
                            "original_name": "clplog",
                            "logical_path": "WC19-1D/当前模型/倒塌分析/结果/用户上传/倒塌分析日志文件",
                            "category_name": "倒塌分析日志文件",
                            "work_condition": "极端工况",
                            "remark": "倒塌备注",
                            "source_modified_at": modified_at,
                        }
                    ]
                if category == self.CATEGORY_FATIGUE:
                    rows = [
                        {
                            "storage_path": str(ftglst_path),
                            "display_path": str(ftglst_path),
                            "original_name": "ftglst",
                            "logical_path": "WC19-1D/当前模型/疲劳分析/结果/用户上传/疲劳分析结果文件",
                            "category_name": "疲劳分析结果文件",
                            "work_condition": "4-1WJT",
                            "remark": "结果备注",
                            "source_modified_at": modified_at,
                        },
                        {
                            "storage_path": str(ftginp_path),
                            "display_path": str(ftginp_path),
                            "original_name": "ftginp.demo",
                            "logical_path": "WC19-1D/当前模型/疲劳分析/输入/用户上传/疲劳分析模型文件",
                            "category_name": "疲劳分析模型文件",
                            "work_condition": "4-1WJT",
                            "remark": "输入备注",
                            "source_modified_at": modified_at,
                        },
                    ]
                    if branch == "result":
                        return rows[:1]
                    if branch == "input":
                        return rows[1:]
                    return rows
                return []

            with patch.object(NewSpecialInspectionPage, "_db_fetch_file_rows", fake_rows), patch.object(
                NewSpecialInspectionPage,
                "_refresh_model_preview",
                lambda self: None,
            ):
                page = NewSpecialInspectionPage("WC19-1D")
                self.addCleanup(page.deleteLater)
                columns = {
                    name: NewSpecialInspectionPage.FILE_TABLE_HEADERS.index(name)
                    for name in ("文件类别", "工况", "文件名", "文件格式", "修改时间", "备注")
                }

                self.assertEqual(
                    page.model_files_table.item(1, columns["文件类别"]).text(),
                    "结构模型文件",
                )
                self.assertEqual(
                    page.model_files_table.item(1, columns["文件名"]).text(),
                    "sacinp.demo",
                )
                self.assertEqual(
                    page.files_table.item(1, columns["工况"]).text(),
                    "极端工况",
                )
                self.assertEqual(
                    page.files_table.item(1, columns["文件名"]).text(),
                    "clplog",
                )
                self.assertEqual(
                    page.files_table.item(3, columns["工况"]).text(),
                    "4-1WJT",
                )
                self.assertEqual(
                    page.files_table.item(5, columns["文件名"]).text(),
                    "ftginp.demo",
                )

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

    def test_work_condition_column_only_shows_for_fatigue_and_collapse(self) -> None:
        with patch("pages.model_files_page.list_files_by_prefix", return_value=[]):
            page = ModelFilesPage()
            self.addCleanup(page.deleteLater)

            page.docs_widget.current_path = ["当前模型", "疲劳"]
            page.docs_widget._show_files_for_current_leaf()
            self.assertFalse(
                page.docs_widget.doc_man_widget.table.isColumnHidden(DocManWidget.COL_WORK_CONDITION)
            )

            page.docs_widget.current_path = ["当前模型", "静力"]
            page.docs_widget._show_files_for_current_leaf()
            self.assertTrue(
                page.docs_widget.doc_man_widget.table.isColumnHidden(DocManWidget.COL_WORK_CONDITION)
            )

    def test_current_model_records_keep_work_condition_from_db(self) -> None:
        db_rows = [
            {
                "id": 12,
                "category_name": "疲劳分析结果文件",
                "work_condition": "4-1WJT",
                "original_name": "ftglst",
                "logical_path": "WC19-1D/当前模型/疲劳分析/结果/用户上传/疲劳分析结果文件",
                "remark": "demo",
                "source_modified_at": None,
                "uploaded_at": None,
            }
        ]
        with patch("pages.model_files_page.list_files_by_prefix", return_value=db_rows), patch(
            "pages.model_files_page.resolve_storage_path",
            return_value=r"D:\demo\ftglst",
        ):
            page = ModelFilesPage()
            self.addCleanup(page.deleteLater)
            records = page.docs_widget._build_model_file_doc_records("当前模型/疲劳")
            self.assertEqual(records[0]["work_condition"], "4-1WJT")


class DocManWidgetSmokeTests(GuiSmokeBase):
    def test_edit_work_condition_updates_db_record(self) -> None:
        widget = DocManWidget(lambda _segments: tempfile.gettempdir())
        self.addCleanup(widget.deleteLater)
        widget.set_context(
            ["当前模型", "疲劳"],
            [
                {
                    "index": 1,
                    "checked": False,
                    "category": "疲劳分析结果文件",
                    "work_condition": "WJT",
                    "fmt": "FTGLST",
                    "filename": "ftglst",
                    "mtime": "",
                    "path": "",
                    "remark": "",
                    "record_id": 12,
                    "logical_path": "当前模型/疲劳/row_1",
                }
            ],
            ["疲劳分析结果文件"],
            overlay_from_db=False,
            show_work_condition=True,
        )
        item = widget.table.item(0, DocManWidget.COL_WORK_CONDITION)
        self.assertIsNotNone(item)

        with patch("pages.doc_man.is_file_db_configured", return_value=True), patch(
            "pages.doc_man.update_file_record"
        ) as update_record:
            item.setText("WJ1")
            self._app.processEvents()
            update_record.assert_called_once_with(12, work_condition="WJ1")


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
