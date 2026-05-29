from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_SRC_ROOT = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
if str(REPORT_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(REPORT_SRC_ROOT))

from src.parsers.pile_head_capacity_summary_builder import build_pile_head_capacity_summary


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
        self.assertEqual("P201", built["operation_tension"]["pile_head_id"])
        self.assertAlmostEqual(15.0, built["operation_tension"]["min_sf"])

    def test_tension_less_than_weight_is_still_calculated(self) -> None:
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

        self.assertEqual("-40", built["operation_table_rows"][0]["tension_sf"])
        self.assertAlmostEqual(-40.0, built["operation_tension"]["min_sf"])


if __name__ == "__main__":
    unittest.main()
