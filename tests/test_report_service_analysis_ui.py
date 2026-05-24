from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_MODULE_ROOT = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
if str(REPORT_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(REPORT_MODULE_ROOT))

from src.report_service import build_analysis_results_for_ui


class ReportServiceAnalysisUiTests(unittest.TestCase):
    def test_build_analysis_results_for_ui_reuses_report_builders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            factor_path = Path(tmp_dir) / "psilst.factor"
            factor_path.write_text("fake factor", encoding="utf-8")

            with patch("src.report_service.read_ui_analysis_lines", return_value=["line"]), patch(
                "src.report_service.parse_member_group_summary",
                return_value={"rows": ["member-row"]},
            ), patch(
                "src.report_service.build_member_summary",
                return_value={"summary_table_row": {"check_item": "构件"}},
            ), patch(
                "src.report_service.parse_joint_can_summary",
                return_value={"rows": ["joint-row"]},
            ), patch(
                "src.report_service.build_joint_can_summary",
                return_value={"summary_table_row": {"check_item": "节点冲剪"}},
            ), patch(
                "src.report_service.parse_pile_group_summary",
                return_value={"rows": ["pile-row"]},
            ), patch(
                "src.report_service.build_pile_group_summary",
                return_value={"summary_table_row": {"check_item": "桩应力"}},
            ), patch(
                "src.report_service.parse_load_case_status",
                return_value={"case_type_map": {"OL1": "operation"}},
            ), patch(
                "src.report_service.parse_pile_head_forces",
                return_value={"rows": ["force-row"]},
            ), patch(
                "src.report_service.parse_pile_axial_capacity_summary",
                return_value={"rows": ["capacity-row"]},
            ), patch(
                "src.report_service.build_pile_head_capacity_summary",
                return_value={
                    "operation_table_rows": [{"pile_head_id": "P108"}],
                    "extreme_table_rows": [{"pile_head_id": "P201"}],
                    "operation_compression": {"summary_table_row": {"check_item": "操作工况桩基抗压"}},
                    "operation_tension": {"summary_table_row": {"check_item": "操作工况桩基抗拔"}},
                    "extreme_compression": {"summary_table_row": {"check_item": "极端工况桩基抗压"}},
                    "extreme_tension": {"summary_table_row": {"check_item": "极端工况桩基抗拔"}},
                },
            ) as build_head_capacity:
                result = build_analysis_results_for_ui(str(factor_path))

        build_head_capacity.assert_called_once()
        self.assertIn("analysis_summary", result)
        self.assertEqual(["member-row"], result["member_group_summary"]["rows"])
        self.assertEqual([{"pile_head_id": "P108"}], result["pile_axial_capacity_summary"]["operation_table_rows"])


if __name__ == "__main__":
    unittest.main()
