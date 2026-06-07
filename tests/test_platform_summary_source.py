# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from services.platform_summary_source import load_platform_summary_source


class PlatformSummarySourceTest(unittest.TestCase):
    def test_snapshot_source_wins_without_reading_facility_profiles(self) -> None:
        snapshot = {
            "columns": ["分公司", "作业公司", "设施编码", "设施名称", "投产时间", "设计年限"],
            "rows": [
                ["湛江分公司", "文昌作业公司", "WC19-1D", "WC19-1D平台", "2013-07-15", "15"],
            ],
        }

        with patch(
            "services.platform_summary_source.load_platform_summary_snapshot",
            return_value=snapshot,
        ), patch(
            "services.platform_summary_source.list_facility_profiles",
            side_effect=AssertionError("facility profile list should not be read when snapshot has data"),
        ):
            source = load_platform_summary_source()

        self.assertEqual("snapshot", source.source)
        self.assertEqual(snapshot, source.snapshot)
        self.assertEqual(
            [
                {
                    "facility_code": "WC19-1D",
                    "facility_name": "WC19-1D平台",
                    "branch": "湛江分公司",
                    "op_company": "文昌作业公司",
                    "oilfield": "",
                    "facility_type": "",
                    "category": "",
                    "start_time": "2013-07-15",
                    "design_life": "15",
                }
            ],
            source.profiles,
        )

    def test_empty_snapshot_falls_back_to_facility_profiles(self) -> None:
        facility_profiles = [
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
            "services.platform_summary_source.load_platform_summary_snapshot",
            return_value={"columns": [], "rows": []},
        ), patch(
            "services.platform_summary_source.list_facility_profiles",
            return_value=facility_profiles,
        ):
            source = load_platform_summary_source()

        self.assertEqual("facility_profiles", source.source)
        self.assertIsNone(source.snapshot)
        self.assertEqual(facility_profiles, source.profiles)


if __name__ == "__main__":
    unittest.main()
