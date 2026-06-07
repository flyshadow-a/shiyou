# -*- coding: utf-8 -*-
import os
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

import pages.platform_load_information_page as platform_load_page  # noqa: E402
import services.platform_load_preheat as platform_load_preheat  # noqa: E402
from pages.file_management_platforms import default_platform  # noqa: E402
from pages.platform_load_information_page import (  # noqa: E402
    PlatformLoadDataWorker,
    PlatformLoadInformationPage,
)
from services.platform_load_preheat import (  # noqa: E402
    clear_platform_load_data_cache,
    get_platform_load_data_cache,
    preheat_platform_load_data,
)


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class PlatformLoadInformationAsyncLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _ensure_app()

    def setUp(self) -> None:
        clear_platform_load_data_cache()

    def tearDown(self) -> None:
        clear_platform_load_data_cache()

    def test_preheat_platform_load_data_caches_default_payload(self) -> None:
        with patch.object(
            platform_load_preheat,
            "load_facility_profile",
            return_value={
                "facility_code": default_platform()["facility_code"],
                "facility_name": "PreheatPlatform",
            },
        ), patch.object(
            platform_load_preheat,
            "load_platform_load_information_items",
            return_value=[{"seq_no": "0", "project_name": "PreheatProject"}],
        ), patch.object(
            platform_load_preheat,
            "list_rebuild_directories",
            return_value=[{"project_name": "PreheatRebuild"}],
        ):
            self.assertTrue(preheat_platform_load_data())

        cached = get_platform_load_data_cache(default_platform()["facility_code"])
        self.assertIsNotNone(cached)
        self.assertEqual(default_platform()["facility_code"], cached["facility_code"])
        self.assertEqual("PreheatPlatform", cached["profile"]["facility_name"])
        self.assertEqual([{"seq_no": "0", "project_name": "PreheatProject"}], cached["rows"])
        self.assertEqual([{"project_name": "PreheatRebuild"}], cached["rebuild_projects"])

    def test_page_construction_uses_preheated_default_payload_without_starting_worker(self) -> None:
        facility_code = default_platform()["facility_code"]
        with patch.object(
            platform_load_preheat,
            "load_facility_profile",
            return_value={"facility_code": facility_code},
        ), patch.object(
            platform_load_preheat,
            "load_platform_load_information_items",
            return_value=[
                {
                    "seq_no": "0",
                    "project_name": "CachedProject",
                    "rebuild_time": "2026",
                    "rebuild_content": "CachedContent",
                }
            ],
        ), patch.object(
            platform_load_preheat,
            "list_rebuild_directories",
            return_value=[],
        ):
            self.assertTrue(preheat_platform_load_data())

        with patch.object(
            PlatformLoadInformationPage,
            "_start_platform_load_worker",
            side_effect=AssertionError("cache hit should not start async worker"),
        ):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)

        self.assertFalse(page._is_platform_data_loading)
        self.assertEqual("CachedProject", page.table.item(page.DATA_START_ROW, 1).text())
        self.assertEqual("2026", page.table.item(page.DATA_START_ROW, 2).text())
        self.assertEqual("CachedContent", page.table.item(page.DATA_START_ROW, 3).text())

    def test_page_construction_starts_async_load_without_sync_database_reads(self) -> None:
        started = []

        def fail_sync_load(*_args, **_kwargs):
            raise AssertionError("page construction should not run sync DB load")

        def fake_start_async(self):
            started.append(self._get_top_value("设施编码"))

        with patch.object(
            PlatformLoadInformationPage,
            "_load_current_platform_data",
            fail_sync_load,
        ), patch.object(
            platform_load_page,
            "load_facility_profile",
            side_effect=AssertionError("page construction should not load profile synchronously"),
        ), patch.object(
            platform_load_preheat,
            "load_facility_profile",
            side_effect=AssertionError("page construction should not load profile synchronously"),
        ), patch.object(
            PlatformLoadInformationPage,
            "_start_async_current_platform_load",
            fake_start_async,
            create=True,
        ):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)

        self.assertEqual([default_platform()["facility_code"]], started)

    def test_legacy_load_current_platform_data_delegates_to_async_worker(self) -> None:
        started = []

        def fake_start_async(self):
            started.append(self._get_top_value("璁炬柦缂栫爜"))

        with patch.object(PlatformLoadInformationPage, "_start_async_current_platform_load", lambda self: None):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)

        with patch.object(
            platform_load_page,
            "load_platform_load_information_items",
            side_effect=AssertionError("_load_current_platform_data should not read DB on UI thread"),
        ), patch.object(
            platform_load_page,
            "list_rebuild_directories",
            side_effect=AssertionError("_load_current_platform_data should not read files on UI thread"),
        ), patch.object(
            PlatformLoadInformationPage,
            "_start_async_current_platform_load",
            fake_start_async,
        ):
            page._load_current_platform_data()

        self.assertEqual(1, len(started))

    def test_worker_emits_platform_load_payload(self) -> None:
        emitted = []
        failed = []
        worker = PlatformLoadDataWorker("WC19-1D", {"facility_code": "WC19-1D"})
        worker.finished.connect(emitted.append)
        worker.failed.connect(lambda code, error: failed.append((code, error)))

        with patch.object(
            platform_load_preheat,
            "load_facility_profile",
            return_value={"facility_code": "WC19-1D", "facility_name": "PlatformA"},
        ), patch.object(
            platform_load_preheat,
            "load_platform_load_information_items",
            return_value=[{"seq_no": "0", "project_name": "OriginalDesign"}],
        ), patch.object(
            platform_load_preheat,
            "list_rebuild_directories",
            return_value=[{"project_name": "RebuildA"}],
        ):
            worker.run()

        self.assertEqual([], failed)
        self.assertEqual("WC19-1D", emitted[0]["facility_code"])
        self.assertEqual({"facility_code": "WC19-1D", "facility_name": "PlatformA"}, emitted[0]["profile"])
        self.assertEqual([{"seq_no": "0", "project_name": "OriginalDesign"}], emitted[0]["rows"])
        self.assertEqual([{"project_name": "RebuildA"}], emitted[0]["rebuild_projects"])
        self.assertEqual("", emitted[0]["rebuild_error"])

    def test_worker_keeps_load_rows_when_rebuild_directory_load_fails(self) -> None:
        emitted = []
        failed = []
        worker = PlatformLoadDataWorker("WC19-1D", {"facility_code": "WC19-1D"})
        worker.finished.connect(emitted.append)
        worker.failed.connect(lambda code, error: failed.append((code, error)))

        with patch.object(
            platform_load_preheat,
            "load_facility_profile",
            return_value={"facility_code": "WC19-1D"},
        ), patch.object(
            platform_load_preheat,
            "load_platform_load_information_items",
            return_value=[{"seq_no": "0", "project_name": "OriginalDesign"}],
        ), patch.object(
            platform_load_preheat,
            "list_rebuild_directories",
            side_effect=RuntimeError("rebuild load failed"),
        ):
            worker.run()

        self.assertEqual([], failed)
        self.assertEqual([{"seq_no": "0", "project_name": "OriginalDesign"}], emitted[0]["rows"])
        self.assertEqual([], emitted[0]["rebuild_projects"])
        self.assertIn("rebuild load failed", emitted[0]["rebuild_error"])

    def test_loaded_payload_updates_visible_table_cells(self) -> None:
        with patch.object(PlatformLoadInformationPage, "_start_async_current_platform_load", lambda self: None):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)

        page._on_async_current_platform_loaded(
            {
                "facility_code": page._get_top_value("设施编码"),
                "profile": {"facility_code": page._get_top_value("设施编码")},
                "rows": [
                    {
                        "seq_no": "0",
                        "project_name": "OriginalDesign",
                        "rebuild_time": "2024",
                        "rebuild_content": "TestContent",
                    }
                ],
                "rebuild_projects": [],
                "rebuild_error": "",
            }
        )

        self.assertEqual("OriginalDesign", page.table.item(page.DATA_START_ROW, 1).text())
        self.assertEqual("2024", page.table.item(page.DATA_START_ROW, 2).text())
        self.assertEqual("TestContent", page.table.item(page.DATA_START_ROW, 3).text())

    def test_page_construction_auto_load_updates_visible_table_cells(self) -> None:
        with patch.object(
            platform_load_preheat,
            "load_facility_profile",
            return_value={"facility_code": default_platform()["facility_code"]},
        ), patch.object(
            platform_load_preheat,
            "load_platform_load_information_items",
            return_value=[
                {
                    "seq_no": "0",
                    "project_name": "AutoProject",
                    "rebuild_time": "2026",
                    "rebuild_content": "AutoContent",
                }
            ],
        ), patch.object(
            platform_load_preheat,
            "list_rebuild_directories",
            return_value=[],
        ):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)
            for _ in range(80):
                self._app.processEvents()
                if page._platform_load_thread is None and not page._is_platform_data_loading:
                    break
                time.sleep(0.01)

        self.assertIsNone(page._platform_load_thread)
        self.assertEqual("AutoProject", page.table.item(page.DATA_START_ROW, 1).text())
        self.assertEqual("2026", page.table.item(page.DATA_START_ROW, 2).text())
        self.assertEqual("AutoContent", page.table.item(page.DATA_START_ROW, 3).text())

    def test_initial_async_load_failure_shows_error_row(self) -> None:
        with patch.object(PlatformLoadInformationPage, "_start_async_current_platform_load", lambda self: None):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)

        page._show_platform_data_loading_placeholder()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
            page._on_async_current_platform_failed(page._get_top_value("设施编码"), "connect failed")

        self.assertIn("加载失败", page.table.item(page.DATA_START_ROW, 1).text())
        self.assertIn("connect failed", page.table.item(page.DATA_START_ROW, 3).text())

    def test_async_load_failure_preserves_existing_table_rows(self) -> None:
        with patch.object(PlatformLoadInformationPage, "_start_async_current_platform_load", lambda self: None):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)

        page._apply_data([page._blank_table_row()])
        page.table.item(page.DATA_START_ROW, 1).setText("ExistingData")
        page.table.item(page.DATA_START_ROW, 2).setText("2024")
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
            page._on_async_current_platform_failed(page._get_top_value("设施编码"), "connect failed")

        self.assertEqual("ExistingData", page.table.item(page.DATA_START_ROW, 1).text())
        self.assertEqual("2024", page.table.item(page.DATA_START_ROW, 2).text())

    def test_successful_empty_load_shows_no_data_message(self) -> None:
        with patch.object(PlatformLoadInformationPage, "_start_async_current_platform_load", lambda self: None):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)

        facility_code = page._get_top_value("设施编码")
        page._on_async_current_platform_loaded(
            {
                "facility_code": facility_code,
                "profile": {"facility_code": facility_code},
                "rows": [],
                "rebuild_projects": [],
                "rebuild_error": "",
            }
        )

        self.assertIn("暂无数据", page.table.item(page.DATA_START_ROW, 1).text())
        self.assertIn(facility_code, page.table.item(page.DATA_START_ROW, 3).text())

    def test_loaded_rows_clear_previous_explanation_row_spans(self) -> None:
        with patch.object(PlatformLoadInformationPage, "_start_async_current_platform_load", lambda self: None):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)

        page._show_platform_data_loading_placeholder()
        rows = []
        for index in range(6):
            row = page._blank_table_row()
            row[1] = f"Project{index}"
            row[2] = f"202{index}"
            row[3] = f"Content{index}"
            rows.append(row)

        page._apply_data(rows)

        second_data_row = page.DATA_START_ROW + 1
        self.assertEqual(1, page.table.columnSpan(second_data_row, 0))
        self.assertEqual("Project1", page.table.item(second_data_row, 1).text())
        self.assertEqual("2021", page.table.item(second_data_row, 2).text())
        self.assertEqual("Content1", page.table.item(second_data_row, 3).text())

    def test_empty_reload_clears_old_data_row_widgets_from_explanation_rows(self) -> None:
        with patch.object(PlatformLoadInformationPage, "_start_async_current_platform_load", lambda self: None):
            page = PlatformLoadInformationPage()
            self.addCleanup(page.deleteLater)

        rows = []
        for index in range(6):
            row = page._blank_table_row()
            row[1] = f"Project{index}"
            row[page.OVERALL_ASSESSMENT_COL if hasattr(page, "OVERALL_ASSESSMENT_COL") else 25] = "是"
            rows.append(row)
        page._apply_data(rows)

        empty_row = page._blank_table_row()
        empty_row[1] = "暂无数据"
        page._apply_data([empty_row])

        explain_start = page.DATA_START_ROW + 1
        explain_end = page.table.rowCount()
        for row in range(explain_start, explain_end):
            for col in range(page.table.columnCount()):
                self.assertIsNone(page.table.cellWidget(row, col))
            self.assertEqual(page.table.columnCount(), page.table.columnSpan(row, 0))


if __name__ == "__main__":
    unittest.main()
