from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services import feasibility_runtime
from server.routers import feasibility as feasibility_router
from server.schemas import FeasibilityRunRequest


class FeasibilitySacsProcessDetectionTests(unittest.TestCase):
    def test_detects_configured_analysis_engine_name(self) -> None:
        with patch(
            "services.feasibility_runtime.get_sacs_analysis_engine_exe",
            return_value=r"D:\SACS\CustomEngine.exe",
        ):
            self.assertTrue(feasibility_runtime._is_sacs_process_name("CustomEngine.exe"))

    def test_detects_sacw_and_sacs_process_names(self) -> None:
        self.assertTrue(feasibility_runtime._is_sacs_process_name("sacwpsi.exe"))
        self.assertTrue(feasibility_runtime._is_sacs_process_name("SACSWorker.exe"))
        self.assertFalse(feasibility_runtime._is_sacs_process_name("notepad.exe"))

    def test_detects_cmd_running_current_work_dir_analysis(self) -> None:
        work_dir = r"\\10.177.19.121\shiyou_file_storage\feasibility_assessment_runtime\WC19-1D"
        command_line = (
            r"cmd.exe /c "
            r"\\10.177.19.121\shiyou_file_storage\feasibility_assessment_runtime\WC19-1D\Autorun.bat"
        )

        self.assertTrue(
            feasibility_runtime._is_sacs_command_line(
                "cmd.exe",
                command_line,
                work_dir=work_dir,
            )
        )
        self.assertFalse(
            feasibility_runtime._is_sacs_command_line(
                "cmd.exe",
                command_line,
                work_dir=r"D:\other_platform",
            )
        )

    def test_assert_blocks_running_sacs_process(self) -> None:
        with patch(
            "services.feasibility_runtime._read_tasklist_process_names",
            return_value=["sacwdb.exe"],
        ), patch(
            "services.feasibility_runtime._read_windows_process_details",
            return_value=[],
        ):
            with self.assertRaisesRegex(RuntimeError, "当前服务端已有 SACS 计算任务正在运行"):
                feasibility_runtime.assert_sacs_not_running_before_analysis()

    def test_run_route_returns_409_before_submitting_when_sacs_busy(self) -> None:
        with patch(
            "server.routers.feasibility.assert_sacs_not_running_before_analysis",
            side_effect=RuntimeError("当前服务端已有 SACS 计算任务正在运行"),
        ), patch("server.routers.feasibility.submit_task_if_no_active") as submit_task:
            with self.assertRaises(feasibility_router.HTTPException) as caught:
                feasibility_router.run_feasibility(
                    FeasibilityRunRequest(facility_code="WC19-1D", analysis_mode="auto")
                )

        self.assertEqual(409, caught.exception.status_code)
        self.assertIn("当前服务端已有 SACS 计算任务正在运行", str(caught.exception.detail))
        submit_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
