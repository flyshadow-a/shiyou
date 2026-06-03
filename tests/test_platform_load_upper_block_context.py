# -*- coding: utf-8 -*-
import unittest

from pages.platform_load_information_page import _upper_block_context_menu_columns
from pages.upper_block_subproject_calculation_table_page import _main_center_writeback_column


class PlatformLoadUpperBlockContextTests(unittest.TestCase):
    def test_dry_and_operation_center_columns_open_upper_block_context(self) -> None:
        self.assertEqual({8, 9}, _upper_block_context_menu_columns())

    def test_upper_block_save_targets_source_center_column(self) -> None:
        self.assertEqual(8, _main_center_writeback_column(8))
        self.assertEqual(9, _main_center_writeback_column(9))
        self.assertEqual(9, _main_center_writeback_column(None))


if __name__ == "__main__":
    unittest.main()
