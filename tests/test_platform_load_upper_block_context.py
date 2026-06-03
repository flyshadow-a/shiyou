# -*- coding: utf-8 -*-
import unittest

from pages.platform_load_information_page import _upper_block_context_menu_columns
from pages.upper_block_subproject_calculation_table_page import (
    _main_center_writeback_column,
    _upper_block_writeback_values,
    build_row_scoped_phases,
)


class PlatformLoadUpperBlockContextTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
