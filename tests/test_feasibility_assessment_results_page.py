from __future__ import annotations

import sys
import tempfile
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image
from PyQt5.QtWidgets import QApplication, QMessageBox, QTableWidget


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pages.feasibility_assessment_results_page import FeasibilityAssessmentResultsPage
from src.path_config_loader import get_coordinate_system_config, get_overall_model_config, get_report_defaults, load_path_config


_QT_APP = QApplication.instance() or QApplication([])


class FeasibilityAssessmentResultsPageTests(unittest.TestCase):
    def test_format_basis_data_file_paragraph_formats_names(self) -> None:
        result = FeasibilityAssessmentResultsPage._format_basis_data_file_paragraph(
            ["完工文件A.pdf", "完工文件B.docx"]
        )
        self.assertEqual("（1）完工文件A.pdf\n（2）完工文件B.docx", result)

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
        self.assertEqual("（1）完工文件A.pdf", result["blocks"][0]["text"])
        self.assertEqual("（1）改造文件A.pdf", result["blocks"][1]["text"])
        self.assertEqual("（1）定期检测A.pdf\n（2）特殊事件检测B.pdf", result["blocks"][2]["text"])

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
                "dry_weight_mt": "1000",
                "dry_center_xyz": "1,2,3",
                "op_fx_kn": "90",
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
                "dry_weight_mt": "1000",
                "total_weight_mt": "",
                "weight_limit_mt": "",
                "weight_delta_mt": "",
                "dry_center_xyz": "1,2,3",
                "center_xyz": "",
                "center_radius_m": "",
                "op_fx_kn": "90",
                "op_fy_kn": "",
                "op_fz_kn": "",
                "op_mx_kn_m": "",
                "op_my_kn_m": "",
                "op_mz_kn_m": "",
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

    def test_extract_chart_water_depth_text_from_seainp_reads_ldopt_water_depth_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sea_file = Path(tmpdir) / "seainp.JKnew FACTOR"
            sea_file.write_text(
                "LDOPT SF    NF+Z   1.025   7.850 -122.20  123.40GLOBMN          CMB\n",
                encoding="utf-8",
            )

            result = FeasibilityAssessmentResultsPage._extract_chart_water_depth_text_from_seainp(
                str(sea_file)
            )

        self.assertEqual("123.40", result)

    def test_extract_environment_load_directions_from_seainp_reads_fixed_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sea_file = Path(tmpdir) / "seainp.JKnew FACTOR"
            sea_file.write_text(
                "WAVE1.00STRN  12.5124.88  11.8                    D  -90.0    5.  72MM10 1 1 3\n"
                "WAVE1.00STRN  12.5124.88  11.8         51.09      D  -90.0    5.  72MM10 1 1 3\n"
                "WAVE1.00STRN  12.5124.88  11.8         90.00      D  -90.0    5.  72MM10 1 1 3\n"
                "WAVE0.95STRN  21.9125.16  14.9         51.09      D  -90.0    5.  72MM10 1 1 3\n",
                encoding="utf-8",
            )

            result = FeasibilityAssessmentResultsPage._extract_environment_load_directions_from_seainp(
                str(sea_file)
            )

        self.assertEqual(["0", "51.09", "90.00"], result)

    def test_build_analysis_model_section_uses_seainp_directions(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.facility_code = "WC19-1D"

        with patch.object(page, "_resolve_overall_model_image", return_value="Y:/special_strategy_images/WC19-1D/latest/platform_strength_page/overall_model/当前/3d.png"), patch.object(
            page,
            "_build_coordinate_system_image",
            return_value="Y:/shiyou_file_storage/image/WC19-1D/coordinate_system.png",
        ), patch.object(
            page,
            "_resolve_current_sea_file",
            return_value="sea-file",
        ), patch.object(
            page,
            "_extract_environment_load_directions_from_seainp",
            return_value=["0", "51.09", "90.00"],
        ):
            result = page._build_analysis_model_section()

        self.assertEqual("Y:/special_strategy_images/WC19-1D/latest/platform_strength_page/overall_model/当前/3d.png", result["overall_model_image_path"])
        self.assertEqual("Y:/shiyou_file_storage/image/WC19-1D/coordinate_system.png", result["coordinate_system_image_path"])
        self.assertEqual(
            "环境荷载计算3个方向，分别为 0°，51.09°，90.00°。波浪理论采用STOKS V。",
            result["blocks"][0]["text"],
        )
        self.assertEqual("环境荷载计算", result["blocks"][0]["anchor_prefix"])

    def test_resolve_overall_model_image_reads_fixed_platform_strength_directory(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.facility_code = "WC19-1D"

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_dir = root / "special_strategy_images" / "WC19-1D" / "latest" / "platform_strength_page" / "overall_model" / "当前"
            source_dir.mkdir(parents=True)
            expected = source_dir / "3d.png"
            Image.new("RGB", (20, 10), "white").save(expected)

            with patch(
                "pages.feasibility_assessment_results_page.get_overall_model_config",
                return_value={
                    "directory": source_dir,
                    "preferred_file": "3d.png",
                    "fallback_extensions": (".png", ".jpg", ".jpeg"),
                },
            ):
                result = page._resolve_overall_model_image()

        self.assertEqual(str(expected), result)

    def test_path_config_loader_resolves_analysis_model_paths(self) -> None:
        load_path_config.cache_clear()
        overall_config = get_overall_model_config("WC19-1D")
        coordinate_config = get_coordinate_system_config("WC19-1D")
        report_defaults = get_report_defaults()

        self.assertEqual(
            Path(
                r"\\10.177.19.121\shiyou_file_storage\special_strategy_images\WC19-1D\latest\platform_strength_page\overall_model\Current"
            ),
            overall_config["directory"],
        )
        self.assertEqual("3d.png", overall_config["preferred_file"])
        self.assertEqual(
            Path(
                r"\\10.177.19.121\shiyou_file_storage\special_strategy_images\WC19-1D\latest\feasibility_assessment_results_page\elevation_outline_rebuilt"
            ),
            coordinate_config["directory"],
        )
        self.assertEqual("XY_-14.png", coordinate_config["xy_file"])
        self.assertEqual("YZ_Left.png", coordinate_config["yz_file"])
        self.assertEqual(
            Path(r"\\10.177.19.121\shiyou_file_storage\image\WC19-1D\coordinate_system.png"),
            coordinate_config["output_path"],
        )
        self.assertEqual(PROJECT_ROOT / "pages" / "output_feasibility_analysis_report" / "xxx平台改建可行性评估报告纯净版.docx", report_defaults["template_path"])
        self.assertNotIn("appendix_a_reference_path", report_defaults)
        self.assertNotIn("factor_path", report_defaults)
        self.assertNotIn("output_path", report_defaults)

    def test_build_coordinate_system_image_combines_xy_and_yz_left(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.facility_code = "WC19-1D"

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_dir = root / "special_strategy_images" / "WC19-1D" / "latest" / "feasibility_assessment_results_page" / "elevation_outline_rebuilt"
            source_dir.mkdir(parents=True)
            Image.new("RGB", (20, 10), "white").save(source_dir / "XY_-14.png")
            Image.new("RGB", (30, 12), "white").save(source_dir / "YZ_Left.png")

            with patch(
                "pages.feasibility_assessment_results_page.get_coordinate_system_config",
                return_value={
                    "directory": source_dir,
                    "xy_file": "XY_-14.png",
                    "yz_file": "YZ_Left.png",
                    "output_path": root / "shiyou_file_storage" / "image" / "WC19-1D" / "coordinate_system.png",
                },
            ):
                result = page._build_coordinate_system_image()

            self.assertTrue(result.endswith("coordinate_system.png"))
            self.assertTrue(Path(result).exists())

    def test_generate_report_uses_local_report_service(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        output_path = r"C:\reports\WC19-1D_report.pdf"

        with patch.object(
            page,
            "_generate_report_locally",
            return_value={"message": "report generated (local)", "output_path": output_path},
        ) as generate_local, patch("pages.feasibility_assessment_results_page.ApiClient") as api_cls:
            result = page._generate_report({"chapter_1_3": {}, "output_path": output_path})

        self.assertEqual("report generated (local)", result["message"])
        self.assertEqual(output_path, result["output_path"])
        generate_local.assert_called_once()
        api_cls.assert_not_called()

    def test_generate_report_requires_output_path_before_local_generation(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)

        with patch.object(page, "_generate_report_locally") as generate_local:
            with self.assertRaises(ValueError):
                page._generate_report({"chapter_1_3": {}})

        generate_local.assert_not_called()

    def test_build_report_payload_reuses_loaded_analysis_factor_path(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page._analysis_results = {"_factor_path": r"C:\client_cache\psilst.M1"}
        page.facility_code = "WC19-1D"
        page.mysql_url = "mysql://example"
        page.env_branch = ""
        page.env_op_company = ""
        page.env_oilfield = ""
        page.inspection_record_summary_text = ""

        with patch("pages.feasibility_assessment_results_page.os.path.isfile", return_value=True), patch.object(
            page,
            "_get_current_job_factor_path",
            side_effect=AssertionError("loaded factor path should be reused"),
        ), patch(
            "pages.feasibility_assessment_results_page.load_facility_profile",
            return_value={"description_text": "platform"},
        ), patch(
            "pages.feasibility_assessment_results_page.build_history_rebuild_summary",
            return_value="",
        ), patch(
            "pages.feasibility_assessment_results_page.get_history_rebuild_projects",
            return_value=[],
        ), patch.object(
            page,
            "_build_latest_inspection_record_summary",
            return_value="",
        ), patch.object(
            page,
            "_build_cover_platform_name",
            return_value="WC19-1D",
        ), patch.object(
            page,
            "_build_platform_evaluation_conclusion_section",
            return_value={},
        ), patch.object(
            page,
            "_build_basis_data_section",
            return_value={},
        ), patch.object(
            page,
            "_build_load_information_section",
            return_value={},
        ), patch.object(
            page,
            "_build_environment_conditions_section",
            return_value={},
        ), patch.object(
            page,
            "_build_analysis_model_section",
            return_value={},
        ), patch.object(
            page,
            "_load_pile_capacity_input_rows",
            return_value=[],
        ):
            payload = page._build_report_payload()

        self.assertEqual(r"C:\client_cache\psilst.M1", payload["factor_path"])

    def test_fill_summary_table_from_analysis_uses_report_summary_items(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.tbl_summary = QTableWidget(3, 5)
        page.HDR_BG = FeasibilityAssessmentResultsPage.HDR_BG
        page.INDEX_BG = FeasibilityAssessmentResultsPage.INDEX_BG

        page._fill_summary_table_from_analysis(
            {
                "items": [
                    {
                        "check_item": "构件",
                        "position": "L541-L542",
                        "value": "0.92",
                        "case": "OL12",
                        "is_pass": "满足",
                    }
                ]
            }
        )

        self.assertEqual("构件", page.tbl_summary.item(2, 0).text())
        self.assertEqual("L541-L542", page.tbl_summary.item(2, 1).text())
        self.assertEqual("0.92", page.tbl_summary.item(2, 2).text())
        self.assertEqual("OL12", page.tbl_summary.item(2, 3).text())
        self.assertEqual("满足", page.tbl_summary.item(2, 4).text())

    def test_result_tables_display_dash_for_empty_cells(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.HDR_BG = FeasibilityAssessmentResultsPage.HDR_BG
        page.INDEX_BG = FeasibilityAssessmentResultsPage.INDEX_BG
        page.cb_row_limit = type("FakeCombo", (), {"currentText": lambda self: "全部"})()
        page._detail_table_rows = {}

        page.tbl_summary = QTableWidget(3, 5)
        page._fill_summary_table_from_analysis(
            {
                "items": [
                    {
                        "check_item": "构件",
                        "position": "",
                        "value": None,
                        "case": " ",
                        "is_pass": "",
                    }
                ]
            }
        )
        self.assertEqual("-", page.tbl_summary.item(2, 1).text())
        self.assertEqual("-", page.tbl_summary.item(2, 2).text())
        self.assertEqual("-", page.tbl_summary.item(2, 3).text())
        self.assertEqual("-", page.tbl_summary.item(2, 4).text())

        standard_table = QTableWidget(2, 5)
        standard_table.setProperty("header_rows", 2)
        page.detail_tables = {"构件": standard_table}
        page._fill_standard_detail_table("构件", [["1", "", None]])
        self.assertEqual("-", standard_table.item(2, 1).text())
        self.assertEqual("-", standard_table.item(2, 2).text())
        self.assertEqual("-", standard_table.item(2, 3).text())
        self.assertEqual("-", standard_table.item(2, 4).text())

    def test_fill_detail_tables_from_analysis_uses_report_pile_capacity_rows(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.HDR_BG = FeasibilityAssessmentResultsPage.HDR_BG
        page.INDEX_BG = FeasibilityAssessmentResultsPage.INDEX_BG
        page._detail_table_rows = {}
        page.cb_row_limit = type("FakeCombo", (), {"currentText": lambda self: "全部"})()
        table = QTableWidget(3, 10)
        table.setProperty("header_rows", 3)
        page.detail_tables = {"操作工况桩基承载力": table}

        page._fill_pile_capacity_detail_table(
            "操作工况桩基承载力",
            [
                {
                    "pile_head_id": "P108",
                    "compression_capacity_kn": "110887",
                    "tension_capacity_kn": "117019",
                    "pile_weight_kn": "6864.3",
                    "compression_case": "OL12",
                    "compression_load_kn": "38993",
                    "tension_case": "OL18",
                    "tension_load_kn": "47123",
                    "compression_sf": "2.42",
                    "tension_sf": "2.91",
                }
            ],
        )

        self.assertEqual(4, table.rowCount())
        self.assertEqual("P108", table.item(3, 0).text())
        self.assertEqual("OL12", table.item(3, 4).text())
        self.assertEqual("2.42", table.item(3, 8).text())

    def test_fill_detail_tables_from_analysis_defers_non_current_tabs(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        tab_names = list(FeasibilityAssessmentResultsPage.DETAIL_HEADERS.keys())
        page.current_tab = tab_names[0]
        page._pile_capacity_input_warning_shown = False

        rendered = []
        deferred = []

        def record_standard(tab_name, rows):
            rendered.append(("standard", tab_name, rows))

        def record_pile(tab_name, rows):
            rendered.append(("pile", tab_name, rows))

        page._fill_standard_detail_table = record_standard
        page._fill_pile_capacity_detail_table = record_pile
        page._sync_pile_capacity_head_column_width = lambda: rendered.append(("sync",))

        results = {
            "member_group_summary": {
                "rows": [{"member": "M1", "unity_check": 0.8, "cond": "OL1"}],
            },
            "joint_can_summary": {
                "rows": [{"joint": "J1", "orig_load_uc": 0.7, "orig_strn_uc": 0.9, "load_case": "OL2"}],
            },
            "pile_group_summary": {
                "rows": [{"pile_head_id": "P1", "distance_from_pilehead": 1.2, "maximum_unity_check": 0.6, "critical_load_case": "OL3"}],
            },
            "pile_axial_capacity_summary": {
                "operation_table_rows": [{"pile_head_id": "P1"}],
                "extreme_table_rows": [{"pile_head_id": "P2"}],
            },
        }

        with patch(
            "pages.feasibility_assessment_results_page.QTimer.singleShot",
            side_effect=lambda _delay, callback: deferred.append(callback),
        ):
            page._fill_detail_tables_from_analysis(results)

        self.assertEqual([("standard", tab_names[0], rendered[0][2])], rendered)
        self.assertEqual(4, len(deferred))

        for callback in deferred:
            callback()

        rendered_tabs = [item[1] for item in rendered if item[0] in {"standard", "pile"}]
        self.assertEqual(tab_names, rendered_tabs)
        self.assertEqual(("sync",), rendered[-1])

    def test_pile_capacity_empty_cells_display_dash_and_export_dash(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.HDR_BG = FeasibilityAssessmentResultsPage.HDR_BG
        page.INDEX_BG = FeasibilityAssessmentResultsPage.INDEX_BG
        page._detail_table_rows = {}
        page.cb_row_limit = type("FakeCombo", (), {"currentText": lambda self: "全部"})()
        table = QTableWidget(3, 10)
        table.setProperty("header_rows", 3)
        tab_name = "操作工况桩基承载力"
        page.detail_tables = {tab_name: table}

        page._fill_pile_capacity_detail_table(
            tab_name,
            [
                {
                    "pile_head_id": "P108",
                    "compression_capacity_kn": "110887",
                    "tension_capacity_kn": "117019",
                    "pile_weight_kn": "6864.3",
                    "compression_case": "OL12",
                    "compression_load_kn": "38993",
                    "tension_case": "",
                    "tension_load_kn": "",
                    "compression_sf": "2.42",
                    "tension_sf": "",
                }
            ],
        )

        self.assertEqual("-", table.item(3, 6).text())
        self.assertEqual("-", table.item(3, 7).text())
        self.assertEqual("-", table.item(3, 9).text())
        self.assertEqual("-", page._detail_rows_for_export(tab_name)[0][6])

    def test_detail_table_row_limit_applies_to_loaded_rows(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.HDR_BG = FeasibilityAssessmentResultsPage.HDR_BG
        page.INDEX_BG = FeasibilityAssessmentResultsPage.INDEX_BG
        page.current_tab = "构件"
        page.cb_row_limit = type("FakeCombo", (), {"currentText": lambda self: "10"})()
        table = QTableWidget(2, 5)
        table.setProperty("header_rows", 2)
        page.table_stack = type(
            "FakeStack",
            (),
            {
                "currentIndex": lambda self: 0,
                "widget": lambda self, index: table,
            },
        )()
        page._detail_table_rows = {
            "构件": [[str(index), f"M{index}", "0.9", "OL1", "满足"] for index in range(1, 13)]
        }

        page._update_current_table_rows()

        self.assertEqual(12, table.rowCount())
        self.assertEqual("M10", table.item(11, 1).text())

    def test_start_analysis_results_loading_uses_background_thread(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page._analysis_thread = None
        page._analysis_worker = None
        page._analysis_results = {}
        page.facility_code = "WC19-1D"
        page.job_name = "WC19-1D"
        page.mysql_url = "mysql://example"
        page.analysis_mode = "rebuild"
        page.server_result_file = ""
        page.server_work_dir = ""
        page._remote_model_cache_dir = Path(tempfile.gettempdir()) / "feasibility-analysis-cache"
        page._get_current_job_factor_path = lambda: (_ for _ in ()).throw(
            AssertionError("factor path resolution must not run synchronously")
        )
        page._get_wordtemplate_project_root = lambda: PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
        page._load_pile_capacity_input_rows_for_analysis = lambda: ([{"pile_head_id": "P1"}], "")

        with patch("pages.feasibility_assessment_results_page.QThread") as thread_cls, patch(
            "pages.feasibility_assessment_results_page.AnalysisResultsWorker"
        ) as worker_cls:
            thread = thread_cls.return_value
            worker = worker_cls.return_value
            page.start_analysis_results_loading()

        worker_cls.assert_called_once()
        args = worker_cls.call_args.args
        self.assertEqual(PROJECT_ROOT / "pages" / "output_feasibility_analysis_report", args[0])
        self.assertEqual("", args[1])
        self.assertEqual([{"pile_head_id": "P1"}], args[2])
        self.assertEqual("", args[3])
        self.assertEqual("WC19-1D", args[4]["facility_code"])
        self.assertEqual("mysql://example", args[4]["mysql_url"])
        worker.moveToThread.assert_called_once_with(thread)
        thread.start.assert_called_once()

    def test_analysis_worker_reads_client_factor_file_directly(self) -> None:
        from pages import feasibility_assessment_results_page as results_page

        emitted = []
        worker = results_page.AnalysisResultsWorker(
            PROJECT_ROOT / "pages" / "output_feasibility_analysis_report",
            "",
            [],
            "",
            {"facility_code": "WC19-1D"},
        )
        worker.finished.connect(emitted.append)

        with patch(
            "pages.feasibility_assessment_results_page._get_current_job_factor_path_for_results",
            return_value="factor-path",
        ), patch(
            "src.report_service.build_analysis_results_for_ui",
            return_value={"source": "local"},
        ) as build_results:
            worker.run()

        build_results.assert_called_once_with("factor-path", pile_capacity_input_rows=[])
        self.assertEqual([{"source": "local", "_factor_path": "factor-path"}], emitted)

    def test_analysis_worker_prefers_latest_state_result_file(self) -> None:
        from pages import feasibility_assessment_results_page as results_page

        with tempfile.TemporaryDirectory() as tmp_dir:
            runtime_dir = Path(tmp_dir)
            result_file = runtime_dir / "analysis_runs" / "run_1" / "psilst.M1"
            result_file.parent.mkdir(parents=True)
            result_file.write_text("result", encoding="utf-8")
            (runtime_dir / "feasibility_analysis_state.json").write_text(
                json.dumps({"result_file": str(result_file), "work_dir": str(result_file.parent)}),
                encoding="utf-8",
            )

            emitted = []
            worker = results_page.AnalysisResultsWorker(
                PROJECT_ROOT / "pages" / "output_feasibility_analysis_report",
                "",
                [],
                "",
                {"facility_code": "WC19-1D", "job_name": "WC19-1D"},
            )
            worker.finished.connect(emitted.append)

            with patch(
                "pages.feasibility_assessment_results_page.get_job_runtime_dir",
                return_value=str(runtime_dir),
            ), patch(
                "pages.feasibility_assessment_results_page._download_feasibility_outputs_for_results",
                side_effect=AssertionError("result loading must not use exported cache"),
            ), patch(
                "src.report_service.build_analysis_results_for_ui",
                return_value={"source": "local-state"},
            ) as build_results:
                worker.run()

        build_results.assert_called_once_with(str(result_file), pile_capacity_input_rows=[])
        self.assertEqual("local-state", emitted[0]["source"])
        self.assertEqual(str(result_file), emitted[0]["_factor_path"])

    def test_result_path_lookup_ignores_non_psilst_lst_files(self) -> None:
        from pages import feasibility_assessment_results_page as results_page

        with tempfile.TemporaryDirectory() as tmp_dir:
            runtime_dir = Path(tmp_dir)
            fatigue_file = runtime_dir / "ftglst.lst"
            fatigue_file.write_text("fatigue", encoding="utf-8")
            generic_file = runtime_dir / "analysis.lst"
            generic_file.write_text("generic", encoding="utf-8")

            found = results_page._find_result_file_in_dir_for_results(str(runtime_dir))

        self.assertEqual("", found)

    def test_result_path_lookup_rejects_non_psilst_state_result(self) -> None:
        from pages import feasibility_assessment_results_page as results_page

        with tempfile.TemporaryDirectory() as tmp_dir:
            runtime_dir = Path(tmp_dir)
            fatigue_file = runtime_dir / "ftglst.lst"
            fatigue_file.write_text("fatigue", encoding="utf-8")
            state = {"result_file": str(fatigue_file), "work_dir": str(runtime_dir)}

            found = results_page._pick_result_from_state_for_results(state)

        self.assertEqual("", found)

    def test_analysis_worker_downloads_raw_result_then_parses_locally(self) -> None:
        from pages import feasibility_assessment_results_page as results_page

        with tempfile.TemporaryDirectory() as tmp_dir:
            runtime_dir = Path(tmp_dir) / "runtime"
            runtime_dir.mkdir()
            downloaded_result = Path(tmp_dir) / "download" / "psilst.M1"
            downloaded_result.parent.mkdir()
            downloaded_result.write_text("result", encoding="utf-8")

            emitted = []
            worker = results_page.AnalysisResultsWorker(
                PROJECT_ROOT / "pages" / "output_feasibility_analysis_report",
                "",
                [],
                "",
                {"facility_code": "WC19-1D", "job_name": "WC19-1D", "cache_root": str(Path(tmp_dir) / "cache")},
            )
            worker.finished.connect(emitted.append)

            with patch(
                "pages.feasibility_assessment_results_page.get_job_runtime_dir",
                return_value=str(runtime_dir),
            ), patch(
                "pages.feasibility_assessment_results_page.ApiClient"
            ) as api_client_cls, patch(
                "src.report_service.build_analysis_results_for_ui",
                return_value={"source": "downloaded-raw"},
            ) as build_results:
                api_client_cls.return_value.export_feasibility_files_and_extract.return_value = [str(downloaded_result)]
                worker.run()

        api_client_cls.return_value.export_feasibility_files_and_extract.assert_called_once()
        build_results.assert_called_once_with(str(downloaded_result), pile_capacity_input_rows=[])
        self.assertEqual("downloaded-raw", emitted[0]["source"])
        self.assertEqual(str(downloaded_result), emitted[0]["_factor_path"])

    def test_analysis_worker_uses_explicit_factor_path_without_payload_lookup(self) -> None:
        from pages import feasibility_assessment_results_page as results_page

        emitted = []
        worker = results_page.AnalysisResultsWorker(
            PROJECT_ROOT / "pages" / "output_feasibility_analysis_report",
            "explicit-factor",
            [{"pile_head_id": "P1"}],
            "",
            {"facility_code": "WC19-1D"},
        )
        worker.finished.connect(emitted.append)

        with patch(
            "pages.feasibility_assessment_results_page._get_current_job_factor_path_for_results",
            side_effect=AssertionError("payload path lookup must not run when explicit factor path exists"),
        ), patch(
            "src.report_service.build_analysis_results_for_ui",
            return_value={"analysis_summary": {"items": []}},
        ) as build_results:
            worker.run()

        build_results.assert_called_once_with(
            "explicit-factor",
            pile_capacity_input_rows=[{"pile_head_id": "P1"}],
        )
        self.assertEqual([{"analysis_summary": {"items": []}, "_factor_path": "explicit-factor"}], emitted)

    def test_analysis_results_loaded_does_not_start_model_load_again(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page._analysis_results = {}
        page._fill_summary_table_from_analysis = unittest.mock.Mock()
        page._fill_detail_tables_from_analysis = unittest.mock.Mock()
        page._set_result_file_path_label = unittest.mock.Mock()

        scheduled = []
        with patch(
            "pages.feasibility_assessment_results_page.QTimer.singleShot",
            side_effect=lambda delay, callback: scheduled.append((delay, callback)),
        ):
            page._on_analysis_results_loaded(
                {"analysis_summary": {"items": []}, "_factor_path": r"C:\cache\psilst.M1"}
            )

        page._fill_summary_table_from_analysis.assert_called_once_with({"items": []})
        page._fill_detail_tables_from_analysis.assert_called_once()
        page._set_result_file_path_label.assert_called_once_with(r"C:\cache\psilst.M1")
        self.assertEqual([], scheduled)

    def test_initial_load_starts_model_and_analysis_loading_independently(self) -> None:
        calls = []
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page._build_ui = lambda: calls.append("build_ui")
        page._show_analysis_status_in_tables = lambda message: calls.append(("status", message))
        page.reload_model_view = lambda: calls.append("reload_model_view")
        page.start_analysis_results_loading = lambda: calls.append("start_analysis_results_loading")

        page._start_initial_loading()

        self.assertEqual(
            [
                ("status", "正在解析数据..."),
                "reload_model_view",
                "start_analysis_results_loading",
            ],
            calls,
        )

    def test_reload_model_view_starts_background_worker(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page._model_load_thread = None
        page._model_load_worker = None
        page._model_load_seq = 0
        page.facility_code = "WC19-1D"
        page.job_name = "WC19-1D"
        page.mysql_url = "mysql://example"
        page.analysis_mode = "rebuild"
        page.server_result_file = ""
        page.server_work_dir = ""
        page._remote_model_cache_dir = Path(tempfile.gettempdir()) / "feasibility-test-cache"

        page._fetch_model_paths = lambda: (_ for _ in ()).throw(
            AssertionError("model path resolution must not run synchronously in reload_model_view")
        )
        page._client_cache_dir = lambda *parts: page._remote_model_cache_dir / "_".join(parts or ["default"])

        model_panel = unittest.mock.Mock()
        page.model_panel = model_panel

        with patch("pages.feasibility_assessment_results_page.QThread") as thread_cls, patch(
            "pages.feasibility_assessment_results_page.ModelViewLoadWorker"
        ) as worker_cls:
            thread = thread_cls.return_value
            worker = worker_cls.return_value
            page.reload_model_view()

        worker_cls.assert_called_once()
        self.assertTrue(worker_cls.call_args.args[0]["reuse_cached_outputs"])
        worker.moveToThread.assert_called_once_with(thread)
        thread.start.assert_called_once()
        model_panel.load_files.assert_not_called()

    def test_open_report_output_directory_selects_generated_file(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "pages.feasibility_assessment_results_page.QProcess.startDetached",
            return_value=True,
        ) as start_detached, patch(
            "pages.feasibility_assessment_results_page.os.startfile"
        ) as startfile:
            output_path = Path(tmp_dir) / "WC19-1D_可行性评估报告.pdf"
            output_path.write_text("report", encoding="utf-8")

            result = page._open_report_output_directory(str(output_path))

        self.assertTrue(result)
        start_detached.assert_called_once_with("explorer", ["/select,", str(output_path.resolve())])
        startfile.assert_not_called()

    def test_open_report_output_directory_falls_back_to_parent_directory(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "pages.feasibility_assessment_results_page.QProcess.startDetached",
            return_value=False,
        ) as start_detached, patch(
            "pages.feasibility_assessment_results_page.os.startfile"
        ) as startfile:
            output_path = Path(tmp_dir) / "WC19-1D_可行性评估报告.pdf"
            output_path.write_text("report", encoding="utf-8")

            result = page._open_report_output_directory(str(output_path))

        self.assertTrue(result)
        start_detached.assert_called_once()
        startfile.assert_called_once_with(str(Path(tmp_dir).resolve()))

    def test_on_generate_report_starts_background_worker(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page._report_thread = None
        output_path = r"C:\reports\WC19-1D_可行性评估报告.pdf"
        page._pending_report_payload_after_outline = {
            "output_filename": "WC19-1D_可行性评估报告.pdf",
            "output_path": output_path,
        }

        with patch.object(page, "_start_report_generation_worker") as start_worker, patch.object(
            page,
            "_set_report_button_busy",
        ), patch.object(page, "_show_report_progress"):
            page._do_generate_report_after_outline_export()

        start_worker.assert_called_once()
        payload = start_worker.call_args.args[0]
        self.assertEqual(output_path, payload["output_path"])

    def test_report_generation_finished_opens_selected_output_file(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page._report_progress = None
        page._report_button = None
        page._report_thread = None
        page._report_worker = None
        output_path = r"C:\reports\WC19-1D_可行性评估报告.pdf"

        with patch.object(page, "_open_report_output_directory", return_value=True) as open_directory, patch(
            "pages.feasibility_assessment_results_page.QMessageBox.information"
        ) as information, patch("pages.feasibility_assessment_results_page.QMessageBox.warning") as warning:
            page._on_report_generation_finished({"output_path": output_path})

        open_directory.assert_called_once_with(output_path)
        information.assert_called_once()
        warning.assert_not_called()

    def test_get_wordtemplate_project_root_points_to_embedded_report_module(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)

        result = page._get_wordtemplate_project_root()

        self.assertEqual(PROJECT_ROOT / "pages" / "output_feasibility_analysis_report", result)

    def test_select_report_output_path_returns_selected_directory_file(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)

        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "pages.feasibility_assessment_results_page.QFileDialog.getExistingDirectory",
            return_value=tmp_dir,
        ), patch("pages.feasibility_assessment_results_page.ask_yes_no") as ask_yes_no:
            result = page._select_report_output_path("WC19-1D_可行性评估报告.pdf")

        self.assertEqual(str(Path(tmp_dir) / "WC19-1D_可行性评估报告.pdf"), result)
        ask_yes_no.assert_not_called()

    def test_select_report_output_path_returns_empty_when_existing_file_not_replaced(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "WC19-1D_可行性评估报告.pdf"
            output_path.write_text("existing", encoding="utf-8")
            with patch(
                "pages.feasibility_assessment_results_page.QFileDialog.getExistingDirectory",
                return_value=tmp_dir,
            ), patch(
                "pages.feasibility_assessment_results_page.ask_yes_no",
                return_value=False,
            ):
                result = page._select_report_output_path(output_path.name)

        self.assertEqual("", result)

    def test_select_report_output_path_returns_existing_file_when_replaced(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "WC19-1D_可行性评估报告.pdf"
            output_path.write_text("existing", encoding="utf-8")
            with patch(
                "pages.feasibility_assessment_results_page.QFileDialog.getExistingDirectory",
                return_value=tmp_dir,
            ), patch(
                "pages.feasibility_assessment_results_page.ask_yes_no",
                return_value=True,
            ):
                result = page._select_report_output_path(output_path.name)

        self.assertEqual(str(output_path), result)

    def test_build_environment_conditions_reads_seainp_by_facility_code(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.facility_code = "WC19-1D"
        page.job_name = "analysis-job-001"
        page.mysql_url = "mysql://example"
        page.env_branch = "湛江分公司"
        page.env_op_company = "文昌油田群作业公司"
        page.env_oilfield = "WC19-1油田"

        with patch("pages.feasibility_assessment_results_page.get_env_profile_id", return_value=1), patch(
            "pages.feasibility_assessment_results_page.load_water_level_items",
            return_value=[{"item_name": "海图基准面 (CD)", "value": "0.00"}],
        ), patch("pages.feasibility_assessment_results_page.load_metric_items", return_value=[]), patch(
            "pages.feasibility_assessment_results_page.load_platform_strength_marine_items", return_value=[]
        ), patch(
            "pages.feasibility_assessment_results_page.load_platform_strength_pile_items", return_value=[]
        ), patch(
            "pages.feasibility_assessment_results_page.load_platform_strength_splash_items", return_value=[]
        ), patch.object(
            page, "_resolve_current_sea_file", return_value="platform-sea-file"
        ) as mocked_resolve_sea_file, patch.object(
            page, "_extract_chart_water_depth_text_from_seainp", return_value="123.40"
        ) as mocked_extract_depth:
            result = page._build_environment_conditions_section()

        mocked_resolve_sea_file.assert_called_once_with("WC19-1D")
        mocked_extract_depth.assert_called_once_with("platform-sea-file")
        self.assertEqual("海图水深为123.40 m，计算中使用的水位（m）如下所示。", result["blocks"][0]["text"])

    def test_build_platform_evaluation_conclusion_includes_detail_rows(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)

        with patch.object(
            page,
            "_load_platform_evaluation_statistics",
            return_value={
                "well_slot_count": 1,
                "riser_count": 2,
                "topside_weight_sum_t": 3.5,
                "well_slot_rows": [{"slot_no": 1, "x": 10}],
                "riser_rows": [{"riser_no": 2, "batter_y": 0.2}],
                "topside_weight_rows": [{"weight_no": 3, "weight_t": 4.5}],
            },
        ):
            result = page._build_platform_evaluation_conclusion_section()

        self.assertEqual(1, result["well_slot_count"])
        self.assertEqual([{"slot_no": 1, "x": 10}], result["well_slot_rows"])
        self.assertEqual([{"riser_no": 2, "batter_y": 0.2}], result["riser_rows"])
        self.assertEqual([{"weight_no": 3, "weight_t": 4.5}], result["topside_weight_rows"])

    def test_load_platform_evaluation_statistics_falls_back_to_facility_code(self) -> None:
        page = FeasibilityAssessmentResultsPage.__new__(FeasibilityAssessmentResultsPage)
        page.mysql_url = "mysql://example"
        page.job_name = "runtime-job"
        page.facility_code = "WC19-1D"

        empty_statistics = {
            "well_slot_count": 0,
            "riser_count": 0,
            "topside_weight_sum_t": 0.0,
            "well_slot_rows": [],
            "riser_rows": [],
            "topside_weight_rows": [],
        }
        facility_statistics = {
            "well_slot_count": 1,
            "riser_count": 1,
            "topside_weight_sum_t": 2.5,
            "well_slot_rows": [{"slot_no": 1}],
            "riser_rows": [{"riser_no": 1}],
            "topside_weight_rows": [{"weight_no": 1}],
        }

        with patch(
            "pages.feasibility_assessment_results_page.load_platform_evaluation_statistics",
            side_effect=[empty_statistics, facility_statistics],
        ) as mocked_load:
            result = page._load_platform_evaluation_statistics()

        self.assertEqual(facility_statistics, result)
        self.assertEqual(
            ["runtime-job", "WC19-1D"],
            [call.kwargs["job_name"] for call in mocked_load.call_args_list],
        )


if __name__ == "__main__":
    unittest.main()
