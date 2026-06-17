from __future__ import annotations

import datetime
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from pages.history_events_inspection_page import HistoryEventsInspectionPage  # noqa: E402
from pages.history_inspection_summary_page import HistoryInspectionSummaryPage  # noqa: E402
from pages.important_history_rebuild_info_page import ImportantHistoryDetailWidget  # noqa: E402
from pages.doc_man import DocManWidget  # noqa: E402
from pages.model_files_page import ModelFilesDocsWidget, ModelFilesPage  # noqa: E402
from pages.new_special_inspection_page import NewSpecialInspectionPage  # noqa: E402


class _FakeTableIndex:
    def __init__(self, row: int):
        self._row = row

    def row(self) -> int:
        return self._row


class _FakeSelectionModel:
    def __init__(self, rows: list[int]):
        self._rows = rows

    def selectedRows(self) -> list[_FakeTableIndex]:
        return [_FakeTableIndex(row) for row in self._rows]


class _FakeFilesTable:
    def __init__(self, rows: list[int]):
        self._selection_model = _FakeSelectionModel(rows)

    def selectionModel(self) -> _FakeSelectionModel:
        return self._selection_model


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class GuiSmokeBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _ensure_app()


class HistoryEventsInspectionPageSmokeTests(GuiSmokeBase):
    def test_outer_platform_sync_updates_inspection_subpage_facility_code(self) -> None:
        page = HistoryEventsInspectionPage()
        self.addCleanup(page.deleteLater)

        page.dropdown_bar.set_options("facility_code", ["WC19-1D", "WC9-7"], "WC9-7")
        page.dropdown_bar.set_options("facility_name", ["WC19-1D平台", "WC9-7平台"], "WC9-7平台")
        page._sync_platform_ui(changed_key="facility_code")

        self.assertEqual("WC9-7", page.home_widget.facility_code)
        self.assertEqual("WC9-7", page.page_inspection.facility_code)


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
                    page.files_table.item(1, columns["工况"]).text(),
                    "",
                )
                self.assertEqual(
                    page.files_table.item(1, columns["文件名"]).text(),
                    "sacinp.demo",
                )
                self.assertEqual(
                    page.files_table.item(3, columns["工况"]).text(),
                    "极端工况",
                )
                self.assertEqual(
                    page.files_table.item(3, columns["文件名"]).text(),
                    "clplog",
                )
                self.assertEqual(
                    page.files_table.item(5, columns["工况"]).text(),
                    "4-1WJT",
                )
                self.assertEqual(
                    page.files_table.item(7, columns["文件名"]).text(),
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

    def test_collect_runtime_input_overrides_accepts_local_upload_temp_names(self) -> None:
        page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
        page._file_meta_by_path = {}
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model_path = base / "20260611_101010_sacinp.demo"
            collapse_path = base / "20260611_101011_clplog"
            ftglst_path = base / "20260611_101012_ftglst"
            ftginp_path = base / "20260611_101013_ftginp.demo"
            for path in (model_path, collapse_path, ftglst_path, ftginp_path):
                path.write_text("demo", encoding="utf-8")

            page._remember_file_meta(str(model_path), original_name="sacinp.demo")
            page._remember_file_meta(str(collapse_path), original_name="clplog")
            page._remember_file_meta(str(ftglst_path), original_name="ftglst")
            page._remember_file_meta(str(ftginp_path), original_name="ftginp.demo")
            page.model_files = [str(model_path)]
            page.collapse_files = [str(collapse_path)]
            page.fatigue_result_files = [str(ftglst_path)]
            page.fatigue_input_files = [str(ftginp_path)]

            overrides = page._collect_runtime_input_overrides()

        self.assertEqual(overrides["model"], str(model_path))
        self.assertEqual(overrides["clplog"], [str(collapse_path)])
        self.assertEqual(overrides["ftglst"], [str(ftglst_path)])
        self.assertEqual(overrides["ftginp"], [str(ftginp_path)])

    def test_delete_model_row_only_removes_current_selection_not_db_record(self) -> None:
        page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
        page.files_table = _FakeFilesTable([0])
        page._model_row_map = {0: 0}
        page.model_files = [r"D:\server\sacinp.demo"]
        page.model_file_rows = [{"storage_path": r"D:\server\sacinp.demo"}]
        page._db_delete_file = lambda *_args, **_kwargs: self.fail("should not delete database file record")
        page._refresh_files_table = lambda: None
        page._refresh_model_preview = lambda: None
        page._invalidate_rule_preview_cache = lambda: None
        messages = []

        with patch.object(
            QMessageBox,
            "information",
            side_effect=lambda _parent, title, text: messages.append((title, text)) or QMessageBox.Ok,
        ):
            page._on_del_model()

        self.assertEqual(page.model_files, [])
        self.assertEqual(page.model_file_rows, [])
        self.assertEqual(messages, [("移除成功", "已从当前计算文件列表移除。")])

    def test_delete_collapse_row_only_removes_current_selection_not_db_record(self) -> None:
        page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
        page.files_table = _FakeFilesTable([0])
        page._collapse_row_map = {0: 0}
        page.collapse_files = [r"D:\server\clplog"]
        page.collapse_file_rows = [{"storage_path": r"D:\server\clplog"}]
        page._db_delete_file = lambda *_args, **_kwargs: self.fail("should not delete database file record")
        page._refresh_files_table = lambda: None
        messages = []

        with patch.object(
            QMessageBox,
            "information",
            side_effect=lambda _parent, title, text: messages.append((title, text)) or QMessageBox.Ok,
        ):
            page._on_del_collapse()

        self.assertEqual(page.collapse_files, [])
        self.assertEqual(page.collapse_file_rows, [])
        self.assertEqual(messages, [("移除成功", "已从当前计算文件列表移除。")])

    def test_delete_fatigue_row_only_removes_current_selection_not_db_record(self) -> None:
        page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
        page.files_table = _FakeFilesTable([0])
        page._fatigue_result_row_map = {0: 0}
        page._fatigue_input_row_map = {}
        page.fatigue_result_files = [r"D:\server\ftglst"]
        page.fatigue_input_files = []
        page.fatigue_result_file_rows = [{"storage_path": r"D:\server\ftglst"}]
        page.fatigue_input_file_rows = []
        page._db_delete_file = lambda *_args, **_kwargs: self.fail("should not delete database file record")
        page._refresh_files_table = lambda: None
        messages = []

        with patch.object(
            QMessageBox,
            "information",
            side_effect=lambda _parent, title, text: messages.append((title, text)) or QMessageBox.Ok,
        ):
            page._on_del_fatigue("result")

        self.assertEqual(page.fatigue_result_files, [])
        self.assertEqual(page.fatigue_result_file_rows, [])
        self.assertEqual(messages, [("移除成功", "已从当前计算文件列表移除。")])

    def test_runtime_file_selection_requires_current_model_file(self) -> None:
        page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
        page._file_meta_by_path = {}
        page.model_files = []
        page.collapse_files = [r"D:\server\clplog"]
        page.fatigue_result_files = [r"D:\server\ftglst"]
        page.fatigue_input_files = [r"D:\server\ftginp.demo"]
        for path, original_name in (
            (page.collapse_files[0], "clplog"),
            (page.fatigue_result_files[0], "ftglst"),
            (page.fatigue_input_files[0], "ftginp.demo"),
        ):
            page._remember_file_meta(path, original_name=original_name)

        with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok) as warning:
            self.assertFalse(page._validate_runtime_file_selection())

        warning.assert_called_once()
        self.assertIn("结构模型文件", warning.call_args.args[2])

    def test_add_model_local_accepts_multiple_files(self) -> None:
        page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
        page._file_meta_by_path = {}
        page.model_files = []
        page.model_file_rows = []
        page.facility_code = "WC19-1D"
        page._scan_model_signature = lambda _path: True
        page._db_store_local_file = lambda path, _category, _branch=None: path
        page._invalidate_rule_preview_cache = lambda: None
        page._start_rule_preview_preload = lambda: None
        page._refresh_model_files_table = lambda: None
        page._refresh_model_preview = lambda: None

        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "sacinp.first"
            second = Path(tmp) / "sacinp.second"
            first.write_text("JOINT\nMEMBER\n", encoding="utf-8")
            second.write_text("JOINT\nMEMBER\n", encoding="utf-8")

            with patch(
                "pages.new_special_inspection_page.QFileDialog.getOpenFileNames",
                return_value=([str(first), str(second)], ""),
            ), patch(
                "pages.new_special_inspection_page.QFileDialog.getOpenFileName",
                side_effect=AssertionError("must use multi-select file dialog"),
            ), patch.object(QMessageBox, "information", return_value=QMessageBox.Ok):
                page._on_add_model_local()

        self.assertEqual(page.model_files, [str(first), str(second)])

    def test_add_collapse_local_accepts_multiple_files(self) -> None:
        page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
        page._file_meta_by_path = {}
        page.collapse_files = []
        page.collapse_file_rows = []
        page.facility_code = "WC19-1D"
        page._db_store_local_file = lambda path, _category, _branch=None: path
        page._refresh_files_table = lambda: None

        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "clplog.first"
            second = Path(tmp) / "clplog.second"
            first.write_text("demo", encoding="utf-8")
            second.write_text("demo", encoding="utf-8")

            with patch(
                "pages.new_special_inspection_page.QFileDialog.getOpenFileNames",
                return_value=([str(first), str(second)], ""),
            ), patch(
                "pages.new_special_inspection_page.QFileDialog.getOpenFileName",
                side_effect=AssertionError("must use multi-select file dialog"),
            ), patch.object(QMessageBox, "information", return_value=QMessageBox.Ok):
                page._on_add_collapse_local()

        self.assertEqual(page.collapse_files, [str(first), str(second)])

    def test_add_fatigue_local_accepts_multiple_files(self) -> None:
        page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
        page._file_meta_by_path = {}
        page.fatigue_result_files = []
        page.fatigue_input_files = []
        page.fatigue_result_file_rows = []
        page.fatigue_input_file_rows = []
        page.facility_code = "WC19-1D"
        page._db_store_local_file = lambda path, _category, _branch=None: path
        page._refresh_files_table = lambda: None

        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "ftglst.first"
            second = Path(tmp) / "ftglst.second"
            first.write_text("demo", encoding="utf-8")
            second.write_text("demo", encoding="utf-8")

            with patch(
                "pages.new_special_inspection_page.QFileDialog.getOpenFileNames",
                return_value=([str(first), str(second)], ""),
            ), patch(
                "pages.new_special_inspection_page.QFileDialog.getOpenFileName",
                side_effect=AssertionError("must use multi-select file dialog"),
            ), patch.object(QMessageBox, "information", return_value=QMessageBox.Ok):
                page._on_add_fatigue_local("result")

        self.assertEqual(page.fatigue_result_files, [str(first), str(second)])

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

    def test_new_upload_category_dialog_exec_error_shows_message(self) -> None:
        widget = ModelFilesDocsWidget()
        self.addCleanup(widget.deleteLater)
        widget.current_leaf_key = "当前模型/静力"
        widget.doc_man_configs = {widget.current_leaf_key: ["结构模型文件"]}
        messages = []

        with patch(
            "pages.model_files_page.QDialog.exec_",
            side_effect=TypeError("exec_(self): first argument of unbound method must have type 'QDialog'"),
        ), patch(
            "pages.model_files_page.QMessageBox.critical",
            side_effect=lambda _parent, title, text: messages.append((title, text)),
        ):
            widget._handle_model_doc_new_upload([])

        self.assertTrue(messages)
        self.assertIn("选择文件类别窗口打开失败", messages[0][1])

    def test_model_doc_context_enables_category_header_filter(self) -> None:
        widget = ModelFilesDocsWidget()
        self.addCleanup(widget.deleteLater)

        widget._apply_model_doc_context(
            path_segments=["当前模型", "静力"],
            records=[
                {"category": "结构模型文件", "filename": "sacinp"},
                {"category": "静力分析结果文件", "filename": "psilst"},
            ],
            categories=["结构模型文件"],
            path_hint="",
            use_handlers=True,
        )

        doc_widget = widget.doc_man_widget
        self.assertEqual("模型类别 ▼", doc_widget.table.horizontalHeaderItem(DocManWidget.COL_CATEGORY).text())
        self.assertIn("静力分析结果文件", doc_widget._category_filter_options)

    def test_single_model_row_upload_confirms_overwrite(self) -> None:
        widget = ModelFilesDocsWidget()
        self.addCleanup(widget.deleteLater)
        widget.current_leaf_key = "当前模型/静力"
        tasks = []

        with patch("pages.model_files_page.QFileDialog.getOpenFileName", return_value=(r"D:\demo\sacinp", "")), patch.object(
            widget,
            "_confirm_overwrite_single_model_file",
            return_value=True,
        ) as confirm, patch.object(widget, "_start_model_upload_worker", side_effect=tasks.append):
            widget._handle_model_doc_upload(
                0,
                {"category": "结构模型文件", "record_id": 12, "logical_path": "WC19-1D/当前模型/结构模型"},
                [{"category": "结构模型文件", "record_id": 12}],
            )

        confirm.assert_called_once_with("结构模型文件")
        self.assertEqual(1, len(tasks))
        self.assertEqual(12, tasks[0]["delete_record_id"])

    def test_single_model_row_upload_cancel_skips_upload(self) -> None:
        widget = ModelFilesDocsWidget()
        self.addCleanup(widget.deleteLater)
        widget.current_leaf_key = "当前模型/静力"
        tasks = []

        with patch("pages.model_files_page.QFileDialog.getOpenFileName", return_value=(r"D:\demo\sacinp", "")), patch.object(
            widget,
            "_confirm_overwrite_single_model_file",
            return_value=False,
        ), patch.object(widget, "_start_model_upload_worker", side_effect=tasks.append):
            widget._handle_model_doc_upload(
                0,
                {"category": "结构模型文件", "record_id": 12, "logical_path": "WC19-1D/当前模型/结构模型"},
                [{"category": "结构模型文件", "record_id": 12}],
            )

        self.assertEqual([], tasks)

    def test_single_model_new_upload_confirms_existing_category(self) -> None:
        widget = ModelFilesDocsWidget()
        self.addCleanup(widget.deleteLater)
        widget.current_leaf_key = "当前模型/静力"
        widget.facility_code = "WC19-1D"
        widget.doc_man_configs = {widget.current_leaf_key: ["结构模型文件"]}
        tasks = []

        with patch("pages.model_files_page.QDialog.exec_", return_value=QDialog.Accepted), patch(
            "pages.model_files_page.QFileDialog.getOpenFileName",
            return_value=(r"D:\demo\sacinp", ""),
        ), patch.object(
            widget,
            "_confirm_overwrite_single_model_file",
            return_value=True,
        ) as confirm, patch.object(widget, "_start_model_upload_worker", side_effect=tasks.append):
            widget._handle_model_doc_new_upload([{"category": "结构模型文件", "record_id": 12}])

        confirm.assert_called_once_with("结构模型文件")
        self.assertEqual(1, len(tasks))
        self.assertEqual(12, tasks[0]["delete_record_id"])

    def test_multi_model_category_upload_does_not_confirm_overwrite(self) -> None:
        widget = ModelFilesDocsWidget()
        self.addCleanup(widget.deleteLater)
        widget.current_leaf_key = "当前模型/疲劳"
        tasks = []

        with patch("pages.model_files_page.QFileDialog.getOpenFileName", return_value=(r"D:\demo\ftglst", "")), patch.object(
            widget,
            "_confirm_overwrite_single_model_file",
        ) as confirm, patch.object(widget, "_start_model_upload_worker", side_effect=tasks.append):
            widget._handle_model_doc_upload(
                0,
                {"category": "疲劳分析结果文件", "record_id": 12, "logical_path": "WC19-1D/当前模型/疲劳分析/结果"},
                [{"category": "疲劳分析结果文件", "record_id": 12}],
            )

        confirm.assert_not_called()
        self.assertEqual(1, len(tasks))
        self.assertIsNone(tasks[0]["delete_record_id"])


class ImportantHistoryDetailWidgetSmokeTests(GuiSmokeBase):
    def test_rebuild_doc_context_enables_category_and_discipline_filters(self) -> None:
        with patch("pages.important_history_rebuild_info_page.list_rebuild_directories", return_value=[]), patch(
            "pages.important_history_rebuild_info_page.list_inspection_projects",
            return_value=[],
        ):
            widget = ImportantHistoryDetailWidget()
        self.addCleanup(widget.deleteLater)

        widget._refresh_doc_man(
            {
                "id": 1,
                "name": "改造项目",
                "year": "2024",
                "conclusion": "",
            }
        )

        doc_widget = widget.doc_man_widget
        self.assertEqual("专业 ▼", doc_widget.table.horizontalHeaderItem(DocManWidget.COL_MTIME).text())
        self.assertEqual("类别 ▼", doc_widget.table.horizontalHeaderItem(DocManWidget.COL_CATEGORY).text())


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

    def test_top_tables_include_description_column(self) -> None:
        with patch(
            "pages.history_inspection_summary_page.list_inspection_projects",
            return_value=[
                {
                    "id": 1,
                    "project_name": "2025年定期检测",
                    "project_year": "2025",
                    "summary_text": "北侧平台复核",
                }
            ],
        ), patch("pages.history_inspection_summary_page.list_inspection_findings", return_value=[]):
            page = HistoryInspectionSummaryPage()
            self.addCleanup(page.deleteLater)

            self.assertEqual(page.periodic_overview_table.columnCount(), 4)
            self.assertEqual(page.periodic_overview_table.horizontalHeaderItem(2).text(), "描述")
            self.assertEqual(page.periodic_overview_table.item(0, 2).text(), "北侧平台复核")

            self.assertEqual(page.special_event_overview_table.columnCount(), 4)
            self.assertEqual(page.special_event_overview_table.horizontalHeaderItem(2).text(), "描述")


if __name__ == "__main__":
    unittest.main()
