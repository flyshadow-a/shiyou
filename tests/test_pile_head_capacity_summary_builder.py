from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_SRC_ROOT = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
if str(REPORT_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(REPORT_SRC_ROOT))

from src.parsers.pile_head_capacity_summary_builder import build_pile_head_capacity_summary
from src.parsers.pile_axial_capacity_summary_builder import build_pile_axial_capacity_summary


class PileHeadCapacitySummaryBuilderTests(unittest.TestCase):
    def test_negative_axial_force_outputs_dash_for_tension(self) -> None:
        pile_head_forces = {
            "rows": [
                {
                    "load_case": "OP1",
                    "pile_head_id": "P101",
                    "batter_joint_id": "P111",
                    "axial_force_kn": -80.0,
                },
                {
                    "load_case": "OP2",
                    "pile_head_id": "P201",
                    "batter_joint_id": "P211",
                    "axial_force_kn": 160.0,
                },
            ]
        }
        axial_summary = {
            "rows": [
                {
                    "pile_head_id": "P101",
                    "comp_capacity_kn": -1000.0,
                    "tens_capacity_kn": 800.0,
                    "pile_weight_kn": 100.0,
                },
                {
                    "pile_head_id": "P201",
                    "comp_capacity_kn": -1000.0,
                    "tens_capacity_kn": 900.0,
                    "pile_weight_kn": 100.0,
                },
            ]
        }

        built = build_pile_head_capacity_summary(
            pile_head_forces,
            axial_summary,
            case_type_map={"OP1": "operation", "OP2": "operation"},
        )

        self.assertEqual("-", built["operation_table_rows"][0]["tension_sf"])
        self.assertEqual("", built["operation_table_rows"][0]["tension_load_kn"])
        self.assertEqual("", built["operation_table_rows"][0]["tension_case"])
        expected_tension_sf = 900.0 / (160.0 - 100.0)
        self.assertEqual("15", built["operation_table_rows"][1]["tension_sf"])
        self.assertEqual("P201", built["operation_tension"]["pile_head_id"])
        self.assertEqual("满足", built["operation_tension"]["is_pass_text"])
        self.assertAlmostEqual(expected_tension_sf, built["operation_tension"]["min_sf"])

    def test_all_negative_axial_forces_do_not_show_negative_tension_load(self) -> None:
        pile_head_forces = {
            "rows": [
                {
                    "load_case": "OP1",
                    "pile_head_id": "P101",
                    "batter_joint_id": "P111",
                    "axial_force_kn": -80.0,
                },
                {
                    "load_case": "OP2",
                    "pile_head_id": "P101",
                    "batter_joint_id": "P111",
                    "axial_force_kn": -40.0,
                },
            ]
        }
        axial_summary = {
            "rows": [
                {
                    "pile_head_id": "P101",
                    "comp_capacity_kn": -1000.0,
                    "tens_capacity_kn": 800.0,
                    "pile_weight_kn": 100.0,
                },
            ]
        }

        built = build_pile_head_capacity_summary(
            pile_head_forces,
            axial_summary,
            case_type_map={"OP1": "operation", "OP2": "operation"},
        )

        self.assertEqual("80", built["operation_table_rows"][0]["compression_load_kn"])
        self.assertEqual("", built["operation_table_rows"][0]["tension_load_kn"])
        self.assertEqual("-", built["operation_table_rows"][0]["tension_sf"])
        self.assertEqual("无数据", built["operation_tension"]["is_pass_text"])

    def test_tension_less_than_weight_outputs_dash(self) -> None:
        pile_head_forces = {
            "rows": [
                {
                    "load_case": "OP1",
                    "pile_head_id": "P101",
                    "batter_joint_id": "P111",
                    "axial_force_kn": 80.0,
                },
            ]
        }
        axial_summary = {
            "rows": [
                {
                    "pile_head_id": "P101",
                    "comp_capacity_kn": -1000.0,
                    "tens_capacity_kn": 800.0,
                    "pile_weight_kn": 100.0,
                },
            ]
        }

        built = build_pile_head_capacity_summary(
            pile_head_forces,
            axial_summary,
            case_type_map={"OP1": "operation"},
        )

        self.assertEqual("-", built["operation_table_rows"][0]["tension_sf"])
        self.assertEqual("无数据", built["operation_tension"]["is_pass_text"])

    def test_client_safety_factor_formula_uses_capacity_over_demand(self) -> None:
        pile_head_forces = {
            "rows": [
                {
                    "load_case": "OP1",
                    "pile_head_id": "P101",
                    "batter_joint_id": "P111",
                    "axial_force_kn": -80.0,
                },
                {
                    "load_case": "OP2",
                    "pile_head_id": "P101",
                    "batter_joint_id": "P111",
                    "axial_force_kn": 1200.0,
                },
            ]
        }
        axial_summary = {
            "rows": [
                {
                    "pile_head_id": "P101",
                    "comp_capacity_kn": -1000.0,
                    "tens_capacity_kn": 800.0,
                    "pile_weight_kn": 100.0,
                },
            ]
        }

        built = build_pile_head_capacity_summary(
            pile_head_forces,
            axial_summary,
            case_type_map={"OP1": "operation", "OP2": "operation"},
        )

        expected_compression_sf = 1000.0 / (80.0 + 100.0)
        expected_tension_sf = 800.0 / (1200.0 - 100.0)
        self.assertEqual("5.556", built["operation_table_rows"][0]["compression_sf"])
        self.assertEqual("0.727", built["operation_table_rows"][0]["tension_sf"])
        self.assertAlmostEqual(expected_compression_sf, built["operation_compression"]["min_sf"])
        self.assertAlmostEqual(expected_tension_sf, built["operation_tension"]["min_sf"])
        self.assertEqual("满足", built["operation_compression"]["is_pass_text"])
        self.assertEqual("不满足", built["operation_tension"]["is_pass_text"])

    def test_client_formula_uses_smallest_safety_factor_as_control(self) -> None:
        pile_head_forces = {
            "rows": [
                {
                    "load_case": "OP1",
                    "pile_head_id": "P101",
                    "batter_joint_id": "P111",
                    "axial_force_kn": -80.0,
                },
                {
                    "load_case": "OP2",
                    "pile_head_id": "P201",
                    "batter_joint_id": "P211",
                    "axial_force_kn": -500.0,
                },
            ]
        }
        axial_summary = {
            "rows": [
                {
                    "pile_head_id": "P101",
                    "comp_capacity_kn": -1000.0,
                    "tens_capacity_kn": 800.0,
                    "pile_weight_kn": 100.0,
                },
                {
                    "pile_head_id": "P201",
                    "comp_capacity_kn": -1000.0,
                    "tens_capacity_kn": 800.0,
                    "pile_weight_kn": 100.0,
                },
            ]
        }

        built = build_pile_head_capacity_summary(
            pile_head_forces,
            axial_summary,
            case_type_map={"OP1": "operation", "OP2": "operation"},
        )

        self.assertEqual("P201", built["operation_compression"]["pile_head_id"])
        self.assertLess(
            built["operation_compression"]["min_sf"],
            float(built["operation_table_rows"][0]["compression_sf"]),
        )

    def test_fallback_axial_summary_recalculates_client_formula(self) -> None:
        axial_summary = {
            "rows": [
                {
                    "pile_head_id": "P101",
                    "group_id": "PA",
                    "pile_weight_kn": 100.0,
                    "comp_capacity_kn": -1000.0,
                    "comp_max_load_kn": -80.0,
                    "comp_critical_load_kn": -80.0,
                    "comp_case": "OP1",
                    "comp_sf": 12.25,
                    "tens_capacity_kn": 800.0,
                    "tens_max_load_kn": 1200.0,
                    "tens_critical_load_kn": 1200.0,
                    "tens_case": "OP2",
                    "tens_sf": 6.53,
                    "max_unity_check": 0.5,
                }
            ]
        }

        built = build_pile_axial_capacity_summary(
            axial_summary,
            case_type_map={"OP1": "operation", "OP2": "operation"},
        )

        self.assertEqual("5.556", built["operation_table_rows"][0]["compression_sf"])
        self.assertEqual("0.727", built["operation_table_rows"][0]["tension_sf"])
        self.assertAlmostEqual(
            1000.0 / (80.0 + 100.0),
            built["operation_compression"]["min_sf"],
        )
        self.assertAlmostEqual(
            800.0 / (1200.0 - 100.0),
            built["operation_tension"]["min_sf"],
        )

    def test_template_threshold_requires_safety_factor_not_less_than_1_5(self) -> None:
        pile_head_forces = {
            "rows": [
                {
                    "load_case": "OP1",
                    "pile_head_id": "P101",
                    "batter_joint_id": "P111",
                    "axial_force_kn": -400.0,
                },
            ]
        }
        axial_summary = {
            "rows": [
                {
                    "pile_head_id": "P101",
                    "group_id": "PA",
                    "pile_weight_kn": 100.0,
                    "comp_capacity_kn": -600.0,
                    "comp_max_load_kn": -400.0,
                    "comp_critical_load_kn": -400.0,
                    "comp_case": "OP1",
                    "comp_sf": 9.99,
                    "tens_capacity_kn": 1000.0,
                    "tens_max_load_kn": 0.0,
                    "tens_critical_load_kn": 0.0,
                    "tens_case": "",
                    "tens_sf": 0.0,
                    "max_unity_check": 0.5,
                }
            ]
        }

        head_built = build_pile_head_capacity_summary(
            pile_head_forces,
            axial_summary,
            case_type_map={"OP1": "operation"},
        )
        axial_built = build_pile_axial_capacity_summary(
            axial_summary,
            case_type_map={"OP1": "operation"},
        )

        self.assertEqual("1.2", head_built["operation_table_rows"][0]["compression_sf"])
        self.assertFalse(head_built["operation_compression"]["is_pass"])
        self.assertEqual("1.2", axial_built["operation_table_rows"][0]["compression_sf"])
        self.assertFalse(axial_built["operation_compression"]["is_pass"])


if __name__ == "__main__":
    unittest.main()
