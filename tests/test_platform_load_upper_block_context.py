# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QPushButton, QTabWidget, QWidget

from pages.platform_load_information_page import _upper_block_context_menu_columns
from pages.upper_block_subproject_calculation_table_page import (
    UpperBlockSubprojectCalculationTablePage,
    _main_center_writeback_column,
    _upper_block_writeback_values,
    build_row_scoped_phases,
)


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class PlatformLoadUpperBlockContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _ensure_app()

    def test_dry_and_operation_center_columns_open_upper_block_context(self) -> None:
        self.assertEqual({8, 9}, _upper_block_context_menu_columns())

    def test_upper_block_save_targets_source_center_column(self) -> None:
        self.assertEqual(8, _main_center_writeback_column(8))
        self.assertEqual(9, _main_center_writeback_column(9))
        self.assertEqual(9, _main_center_writeback_column(None))

    def test_source_row_zero_uses_original_design_phase_only(self) -> None:
        phases = build_row_scoped_phases(2, {1: "原设计"}, data_start_row=2)

        self.assertEqual(["build"], [phase.key for phase in phases])
        self.assertEqual("原设计\n(详细设计或称重)", phases[0].label)

    def test_rebuild_source_row_uses_current_project_phase_only(self) -> None:
        phases = build_row_scoped_phases(4, {1: "新增生活楼"}, data_start_row=2)

        self.assertEqual(["rebuild_2"], [phase.key for phase in phases])
        self.assertEqual("新增生活楼", phases[0].label)

    def test_rebuild_source_row_falls_back_to_rebuild_number(self) -> None:
        phases = build_row_scoped_phases(3, {1: ""}, data_start_row=2)

        self.assertEqual(["rebuild_1"], [phase.key for phase in phases])
        self.assertEqual("改造1", phases[0].label)

    def test_dry_center_entry_writes_back_dry_weight_and_center_only(self) -> None:
        values = _upper_block_writeback_values(
            source_col=8,
            op_weight="101.000",
            op_center="1.000,2.000,3.000",
        )

        self.assertEqual({4: "101.000", 8: "1.000,2.000,3.000"}, values)

    def test_operation_center_entry_writes_back_operation_weight_and_center_only(self) -> None:
        values = _upper_block_writeback_values(
            source_col=9,
            op_weight="202.000",
            op_center="4.000,5.000,6.000",
        )

        self.assertEqual({5: "202.000", 9: "4.000,5.000,6.000"}, values)

    def test_back_button_switches_to_platform_load_tab_without_saving(self) -> None:
        main_window = QWidget()
        self.addCleanup(main_window.deleteLater)
        main_window.tab_widget = QTabWidget(main_window)
        platform_page = QWidget()
        self.addCleanup(platform_page.deleteLater)
        calc_page = UpperBlockSubprojectCalculationTablePage(main_window=main_window, parent=main_window)
        self.addCleanup(calc_page.deleteLater)
        saved_payloads = []
        calc_page.saved.connect(saved_payloads.append)

        platform_index = main_window.tab_widget.addTab(platform_page, "平台载荷信息")
        calc_index = main_window.tab_widget.addTab(calc_page, "上部组块分项目计算表")
        main_window.tab_widget.setCurrentIndex(calc_index)

        calc_page._on_back()

        self.assertEqual(platform_index, main_window.tab_widget.currentIndex())
        self.assertEqual([], saved_payloads)

    def test_action_buttons_match_platform_load_save_style_and_order(self) -> None:
        page = UpperBlockSubprojectCalculationTablePage()
        self.addCleanup(page.deleteLater)

        button_layout = page.main_layout.itemAt(0).layout()
        buttons = []
        for index in range(button_layout.count()):
            widget = button_layout.itemAt(index).widget()
            if isinstance(widget, QPushButton):
                buttons.append(widget)

        self.assertEqual([page.btn_save, page.btn_back], buttons)
        self.assertIn("background: #2563eb", page.btn_save.styleSheet())
        self.assertIn("border: 1px solid #1d4ed8", page.btn_save.styleSheet())
        self.assertEqual(page.btn_save.styleSheet(), page.btn_back.styleSheet())


if __name__ == "__main__":
    unittest.main()
