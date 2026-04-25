from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pages.feasibility_assessment_results_page import FeasibilityAssessmentResultsPage


class FeasibilityAssessmentResultsPageTests(unittest.TestCase):
    def test_format_basis_data_file_paragraph_formats_names(self) -> None:
        result = FeasibilityAssessmentResultsPage._format_basis_data_file_paragraph(
            ["完工文件A.pdf", "完工文件B.docx"]
        )
        self.assertEqual("（1）完工文件A.pdf；（2）完工文件B.docx。", result)

    def test_format_basis_data_file_paragraph_handles_empty(self) -> None:
        result = FeasibilityAssessmentResultsPage._format_basis_data_file_paragraph([])
        self.assertEqual("暂无文件。", result)

    def test_list_basis_data_files_supports_alias_prefixes_and_deduplicates(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.facility_code = "WC19-1D"

        returned_rows = {
            "历史改造信息": [
                {"original_name": "历史改造文件A.pdf"},
                {"original_name": "重复文件.docx"},
            ],
            "WC19-1D/历史改造信息": [
                {"original_name": "重复文件.docx"},
                {"original_name": "历史改造文件B.pdf"},
            ],
            "历史改造文件": [
                {"original_name": "历史改造文件C.pdf"},
            ],
            "WC19-1D/历史改造文件": [],
        }

        def fake_list_files_by_prefix(**kwargs):
            return returned_rows.get(kwargs.get("logical_path_prefix"), [])

        with patch(
            "pages.feasibility_assessment_results_page.list_files_by_prefix",
            side_effect=fake_list_files_by_prefix,
        ):
            result = page._list_basis_data_files([["历史改造信息"], ["历史改造文件"]])

        self.assertEqual(
            ["历史改造文件A.pdf", "重复文件.docx", "历史改造文件B.pdf", "历史改造文件C.pdf"],
            result,
        )

    def test_build_basis_data_section_includes_inspection_alias_prefixes(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.facility_code = "WC19-1D"

        with patch.object(
            page,
            "_list_basis_data_files",
            side_effect=[
                ["完工文件A.pdf"],
                ["改造文件A.pdf"],
                ["定期检测A.pdf", "特殊事件检测B.pdf"],
            ],
        ) as mocked_list_files:
            result = page._build_basis_data_section()

        self.assertEqual("replace_region", result["mode"])
        self.assertEqual("（1）完工文件A.pdf。", result["blocks"][0]["text"])
        self.assertEqual("（1）改造文件A.pdf。", result["blocks"][1]["text"])
        self.assertEqual("（1）定期检测A.pdf；（2）特殊事件检测B.pdf。", result["blocks"][2]["text"])

        self.assertEqual(
            [
                [["详细设计"], ["完工文件"], ["安装文件"]],
                [["历史改造信息"], ["历史改造文件"]],
                [["定期检测"], ["定期检测1-N"], ["特殊事件检测"], ["特殊事件检测（台风、碰撞等）"]],
            ],
            [call.args[0] for call in mocked_list_files.call_args_list],
        )

    def test_build_load_information_section_uses_platform_load_rows(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.facility_code = "WC19-1D"

        facility_profile = {
            "branch": "湛江分公司",
            "op_company": "文昌油田群作业公司",
            "oilfield": "WC19-1油田",
            "facility_name": "WC19-1D平台",
            "start_time": "2013-07-15",
            "design_life": "15",
        }
        load_rows = [
            {
                "seq_no": "0",
                "project_name": "原设计",
                "rebuild_time": "2013年",
                "fx_kn": "100",
                "safety_op": "2.4",
                "assessment_org": "机构A",
            }
        ]

        with patch(
            "pages.feasibility_assessment_results_page.load_platform_load_information_items",
            return_value=load_rows,
        ):
            result = page._build_load_information_section(facility_profile)

        self.assertEqual("replace_region", result["mode"])
        self.assertEqual("湛江分公司", result["load_information_meta"]["branch"])
        self.assertEqual("WC19-1D平台", result["load_information_meta"]["facility_name"])
        self.assertEqual(
            {
                "seq_no": "0",
                "project_name": "原设计",
                "rebuild_time": "2013年",
                "rebuild_content": "",
                "total_weight_mt": "",
                "weight_limit_mt": "",
                "weight_delta_mt": "",
                "center_xyz": "",
                "center_radius_m": "",
                "fx_kn": "100",
                "fy_kn": "",
                "fz_kn": "",
                "mx_kn_m": "",
                "my_kn_m": "",
                "mz_kn_m": "",
                "safety_op": "2.4",
                "safety_extreme": "",
                "overall_assessment": "",
                "assessment_org": "机构A",
            },
            result["load_information_rows"][0],
        )


if __name__ == "__main__":
    unittest.main()
