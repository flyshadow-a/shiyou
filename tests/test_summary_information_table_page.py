# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from pages.summary_information_table_page import SummaryInformationTablePage


class SummaryInformationTablePageTest(unittest.TestCase):
    def test_profiles_from_saved_platform_summary_snapshot_without_facility_list_fallback(self) -> None:
        page = SummaryInformationTablePage.__new__(SummaryInformationTablePage)

        snapshot = {
            "columns": ["分公司", "作业公司", "设施编码", "设施名称", "投产时间", "设计年限"],
            "rows": [
                ["湛江分公司", "文昌作业公司", "WC19-1D", "WC19-1D平台", "2013-07-15", "15"],
            ],
        }

        with patch(
            "pages.summary_information_table_page.load_platform_summary_snapshot",
            return_value=snapshot,
        ), patch(
            "pages.summary_information_table_page.list_facility_profiles",
            side_effect=AssertionError("should not read full facility profile list"),
            create=True,
        ):
            profiles = page._profiles_from_saved_platform_summary_snapshot()

        self.assertEqual(
            [
                {
                    "branch": "湛江分公司",
                    "op_company": "文昌作业公司",
                    "oilfield": "",
                    "facility_code": "WC19-1D",
                    "facility_name": "WC19-1D平台",
                    "facility_type": "",
                    "category": "",
                    "start_time": "2013-07-15",
                    "design_life": "15",
                }
            ],
            profiles,
        )


if __name__ == "__main__":
    unittest.main()
