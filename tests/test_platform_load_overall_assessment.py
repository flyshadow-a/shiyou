# -*- coding: utf-8 -*-
import unittest

from pages.platform_load_information_page import (
    OVERALL_ASSESSMENT_COL,
    _normalise_overall_assessment_value,
    _overall_assessment_options,
)


class PlatformLoadOverallAssessmentTests(unittest.TestCase):
    def test_overall_assessment_column_index_matches_table_schema(self) -> None:
        self.assertEqual(25, OVERALL_ASSESSMENT_COL)

    def test_overall_assessment_options_only_keep_yes_no(self) -> None:
        self.assertEqual(["是", "否"], _overall_assessment_options())

    def test_overall_assessment_value_only_accepts_yes_or_no(self) -> None:
        self.assertEqual("是", _normalise_overall_assessment_value("是"))
        self.assertEqual("否", _normalise_overall_assessment_value("否"))
        self.assertEqual("否", _normalise_overall_assessment_value(""))
        self.assertEqual("否", _normalise_overall_assessment_value("其他"))


if __name__ == "__main__":
    unittest.main()
