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

    def test_psvdb_lock_does_not_block_analysis_precheck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            psvdb = work_dir / "psvdb.M1"
            psvdb.write_text("locked", encoding="utf-8")

            with patch(
                "services.feasibility_runtime._can_rename_for_lock_check",
                return_value=False,
            ):
                feasibility_runtime.assert_analysis_outputs_ready_before_analysis(str(work_dir))

    def test_locked_psilst_blocks_analysis_precheck(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            psilst = work_dir / "psilst.M1"
            psilst.write_text("locked", encoding="utf-8")

            with patch(
                "services.feasibility_runtime._can_rename_for_lock_check",
                return_value=False,
            ):
                with self.assertRaisesRegex(RuntimeError, "上一轮 SACS 关键计算结果文件仍被占用"):
                    feasibility_runtime.assert_analysis_outputs_ready_before_analysis(str(work_dir))

    def test_cleanup_skips_locked_psvdb_but_blocks_locked_psilst(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            psvdb = work_dir / "psvdb.M1"
            psilst = work_dir / "psilst.M1"
            psvdb.write_text("locked", encoding="utf-8")
            psilst.write_text("locked", encoding="utf-8")

            def fake_remove(path: str) -> None:
                raise RuntimeError(f"locked: {Path(path).name}")

            with patch("services.feasibility_runtime._remove_analysis_output_with_retry", fake_remove):
                with self.assertRaisesRegex(RuntimeError, "locked: psilst.M1") as caught:
                    feasibility_runtime._cleanup_previous_analysis_outputs(str(work_dir))

        self.assertNotIn("locked: psvdb.M1", str(caught.exception))

    def test_run_route_returns_409_when_key_outputs_locked(self) -> None:
        with patch(
            "server.routers.feasibility.assert_sacs_not_running_before_analysis",
        ), patch(
            "server.routers.feasibility.get_feasibility_local_work_dir",
            return_value=r"C:\Users\tester\AppData\Local\shiyou\sacs_runtime\feasibility_assessment_runtime\WC19-1D\current",
        ), patch(
            "server.routers.feasibility.assert_analysis_outputs_ready_before_analysis",
            side_effect=RuntimeError("上一轮 SACS 关键计算结果文件仍被占用"),
        ), patch("server.routers.feasibility.submit_task_if_no_active") as submit_task:
            with self.assertRaises(feasibility_router.HTTPException) as caught:
                feasibility_router.run_feasibility(
                    FeasibilityRunRequest(facility_code="WC19-1D", analysis_mode="auto")
                )

        self.assertEqual(409, caught.exception.status_code)
        self.assertIn("上一轮 SACS 关键计算结果文件仍被占用", str(caught.exception.detail))
        submit_task.assert_not_called()

    def test_local_work_dir_uses_configured_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "services.feasibility_runtime.get_sacs_local_runtime_root",
            return_value=str(Path(tmp_dir) / "runtime_root"),
        ):
            work_dir = feasibility_runtime.get_feasibility_local_work_dir("WC19-1D")

        self.assertTrue(work_dir.endswith(r"feasibility_assessment_runtime\WC19-1D\current"))
        self.assertIn("runtime_root", work_dir)

    def test_sync_analysis_outputs_to_shared_copies_result_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            local_dir = root / "local"
            shared_dir = root / "shared"
            local_dir.mkdir()
            shared_dir.mkdir()
            result_file = local_dir / "psilst.M1"
            result_file.write_text("result", encoding="utf-8")
            (local_dir / "analysis_summary.log").write_text("summary", encoding="utf-8")
            (local_dir / "analysis_exitcode.txt").write_text("0", encoding="utf-8")

            shared_result, warnings = feasibility_runtime._sync_analysis_outputs_to_shared(
                local_work_dir=str(local_dir),
                shared_work_dir=str(shared_dir),
                result_file=str(result_file),
            )

            self.assertEqual(str(shared_dir / "psilst.M1"), shared_result)
            self.assertEqual([], warnings)
            self.assertEqual("result", (shared_dir / "psilst.M1").read_text(encoding="utf-8"))
            self.assertEqual("summary", (shared_dir / "analysis_summary.log").read_text(encoding="utf-8"))
            self.assertEqual("0", (shared_dir / "analysis_exitcode.txt").read_text(encoding="utf-8"))

    def test_run_feasibility_analysis_uses_local_work_dir_and_syncs_shared_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            shared_dir = root / "shared_runtime" / "WC19-1D"
            local_root = root / "local_runtime"
            shared_dir.mkdir(parents=True)

            for name, text in {
                "sacinp.M1": "model",
                "seainp.M1": "sea",
                "psiinp.M1": "psi",
                "Jcninp.M1": "jcn",
                "psiM1.runx": "sacinp.JKnew seainp.JKnew FACTOR psiinp Jcninp psilst.factor",
            }.items():
                (shared_dir / name).write_text(text, encoding="utf-8")

            expected_local_dir = local_root / "feasibility_assessment_runtime" / "WC19-1D" / "current"

            def fake_ensure_analysis_bat(*, work_dir, runx_path, psiinp_path, jcninp_path):
                self.assertEqual(str(expected_local_dir), work_dir)
                self.assertEqual(str(expected_local_dir / "psiM1.runx"), runx_path)
                self.assertEqual(str(expected_local_dir / "psiinp.M1"), psiinp_path)
                self.assertEqual(str(expected_local_dir / "Jcninp.M1"), jcninp_path)
                bat = expected_local_dir / "Autorun.bat"
                bat.write_text("@echo off", encoding="utf-8")
                return str(bat)

            def fake_subprocess_run(*_args, **_kwargs):
                self.assertEqual(str(expected_local_dir), _kwargs.get("cwd"))
                (expected_local_dir / "psilst.M1").write_text("local result", encoding="utf-8")
                (expected_local_dir / "analysis_summary.log").write_text("ExitCode=0", encoding="utf-8")
                (expected_local_dir / "analysis_exitcode.txt").write_text("0", encoding="utf-8")
                return types.SimpleNamespace(returncode=0)

            with patch("services.feasibility_runtime.get_sacs_local_runtime_root", return_value=str(local_root)), patch(
                "services.feasibility_runtime._assert_sacs_not_running_before_analysis"
            ), patch(
                "services.feasibility_runtime.assert_analysis_outputs_ready_before_analysis"
            ), patch(
                "services.feasibility_runtime.get_mysql_url",
                return_value="mysql://test",
            ), patch(
                "services.feasibility_runtime.prepare_latest_rebuild_runtime_for_analysis",
                return_value={
                    "model_dir": str(shared_dir),
                    "new_model_file": str(shared_dir / "sacinp.M1"),
                    "new_sea_file": str(shared_dir / "seainp.M1"),
                },
            ), patch(
                "services.feasibility_runtime.stage_support_files_for_job",
                return_value={
                    "runx": str(shared_dir / "psiM1.runx"),
                    "psiinp": str(shared_dir / "psiinp.M1"),
                    "jcninp": str(shared_dir / "Jcninp.M1"),
                },
            ), patch(
                "services.feasibility_runtime.get_job_new_model_file",
                return_value=str(shared_dir / "sacinp.M1"),
            ), patch(
                "services.feasibility_runtime.get_job_new_sea_file",
                return_value=str(shared_dir / "seainp.M1"),
            ), patch(
                "services.feasibility_runtime.ensure_analysis_bat",
                side_effect=fake_ensure_analysis_bat,
            ), patch(
                "services.feasibility_runtime.subprocess.run",
                side_effect=fake_subprocess_run,
            ), patch(
                "services.feasibility_runtime._wait_for_fresh_result_file",
                return_value=(str(expected_local_dir / "psilst.M1"), ""),
            ), patch(
                "services.feasibility_runtime._analysis_output_has_error",
                return_value="",
            ), patch(
                "services.feasibility_runtime._wait_for_analysis_outputs_released",
            ):
                state = feasibility_runtime.run_feasibility_analysis(facility_code="WC19-1D")

            self.assertEqual(str(expected_local_dir), state["work_dir"])
            self.assertEqual(str(expected_local_dir), state["local_work_dir"])
            self.assertEqual(str(shared_dir), state["shared_work_dir"])
            self.assertEqual(str(expected_local_dir / "psilst.M1"), state["result_file"])
            self.assertEqual(str(shared_dir / "psilst.M1"), state["shared_result_file"])
            self.assertEqual("local result", (shared_dir / "psilst.M1").read_text(encoding="utf-8"))
            self.assertTrue((expected_local_dir / "feasibility_analysis_state.json").is_file())
            self.assertTrue((shared_dir / "feasibility_analysis_state.json").is_file())


if __name__ == "__main__":
    unittest.main()
