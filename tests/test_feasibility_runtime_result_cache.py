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


class FeasibilityRuntimeResultCacheTests(unittest.TestCase):
    def test_load_result_bundle_reuses_cache_for_same_factor_and_pile_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            factor_path = work_dir / "psilst.factor"
            factor_path.write_text("factor data", encoding="utf-8")

            calls = []

            def fake_build_analysis_results_for_ui(path, pile_capacity_input_rows=None):
                calls.append((path, pile_capacity_input_rows))
                return {
                    "analysis_summary": {"items": [{"check_item": "member"}]},
                    "pile_axial_capacity_summary": {
                        "operation_table_rows": list(pile_capacity_input_rows or [])
                    },
                }

            fake_report_service = types.SimpleNamespace(
                build_analysis_results_for_ui=fake_build_analysis_results_for_ui
            )

            with patch(
                "services.feasibility_runtime.get_job_runtime_dir",
                return_value=str(work_dir),
            ), patch(
                "services.feasibility_runtime.find_result_file",
                return_value=str(factor_path),
            ), patch.dict(
                sys.modules,
                {"report_service": fake_report_service},
            ):
                first = load_feasibility_result_bundle(
                    facility_code="WC19-1D",
                    pile_capacity_input_rows=[{"pile_head_id": "P1"}],
                )
                second = load_feasibility_result_bundle(
                    facility_code="WC19-1D",
                    pile_capacity_input_rows=[{"pile_head_id": "P1"}],
                )

        self.assertEqual(1, len(calls))
        self.assertEqual(
            [{"pile_head_id": "P1"}],
            first["results"]["pile_axial_capacity_summary"]["operation_table_rows"],
        )
        self.assertEqual(first["results"], second["results"])
        self.assertEqual(True, second["cache_hit"])

    def test_preheat_starts_without_blocking_analysis_return(self) -> None:
        from services import feasibility_runtime

        started = []

        class FakeThread:
            def __init__(self, *, target, args, name, daemon):
                started.append(
                    {
                        "target": target,
                        "args": args,
                        "name": name,
                        "daemon": daemon,
                    }
                )

            def start(self):
                started[-1]["started"] = True

        with patch.object(feasibility_runtime.threading, "Thread", FakeThread):
            feasibility_runtime._start_feasibility_result_cache_preheat("WC19-1D")

        self.assertEqual(("WC19-1D",), started[0]["args"])
        self.assertEqual(True, started[0]["daemon"])
        self.assertEqual(True, started[0]["started"])


if __name__ == "__main__":
    unittest.main()
