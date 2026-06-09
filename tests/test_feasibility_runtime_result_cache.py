from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.feasibility_runtime import load_feasibility_result_bundle


class FeasibilityRuntimeResultTests(unittest.TestCase):
    def test_load_result_bundle_reads_result_file_each_time_without_cache_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            factor_path = work_dir / "psilst.factor"
            factor_path.write_text("factor data", encoding="utf-8")

            calls = []

            def fake_build_analysis_results_for_ui(path, pile_capacity_input_rows=None):
                calls.append((path, pile_capacity_input_rows))
                return {
                    "analysis_summary": {"items": [{"check_item": "member"}]},
                    "call_count": len(calls),
                }

            fake_report_service = types.SimpleNamespace(
                build_analysis_results_for_ui=fake_build_analysis_results_for_ui
            )

            with patch(
                "services.feasibility_runtime._latest_state_result_file",
                return_value=(str(factor_path), str(work_dir), {}),
            ), patch.dict(
                sys.modules,
                {"report_service": fake_report_service},
            ):
                first = load_feasibility_result_bundle(facility_code="WC19-1D")
                second = load_feasibility_result_bundle(facility_code="WC19-1D")

        self.assertEqual(2, len(calls))
        self.assertEqual((str(factor_path), []), calls[0])
        self.assertEqual((str(factor_path), []), calls[1])
        self.assertEqual(1, first["results"]["call_count"])
        self.assertEqual(2, second["results"]["call_count"])
        self.assertNotIn("cache_hit", first)
        self.assertNotIn("cache_hit", second)


if __name__ == "__main__":
    unittest.main()
