from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.special_strategy_runtime import _prune_runtime_artifacts, load_base_config, run_artifact_paths


REPO_ROOT = Path(__file__).resolve().parents[1]


class SpecialStrategyRuntimeConfigCleanupTests(unittest.TestCase):
    def test_run_configs_do_not_embed_local_output_special_strategy_paths(self) -> None:
        targets = [
            REPO_ROOT / "pages" / "output_special_strategy" / "wc19_1d_run_config.json",
            REPO_ROOT / "pages" / "output_special_strategy" / "wc19_1d_run_config.preview.json",
            REPO_ROOT / "pages" / "output_special_strategy" / "wc19_1d_run_config.example.json",
            REPO_ROOT / "pages" / "output_special_strategy" / "wc9_7_run_config.json",
            REPO_ROOT / "pages" / "output_special_strategy" / "wc9_7_run_config.example.json",
        ]
        bad_snippets = (
            "pages/output_special_strategy/",
            "d:/pyproject/shiyou/pages/output_special_strategy",
            "c:/path/to/",
            "d:/desk/",
        )
        for path in targets:
            text = path.read_text(encoding="utf-8-sig").lower()
            for snippet in bad_snippets:
                with self.subTest(path=path.name, snippet=snippet):
                    self.assertNotIn(snippet, text)

    def test_load_base_config_routes_output_artifacts_to_runtime_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("services.special_strategy_runtime.shared_storage_dir", return_value=tmp):
                cfg = load_base_config("WC19-1D")

            runtime_root = (Path(tmp) / "WC19-1D").resolve()
            self.assertEqual(
                cfg["output_report"],
                str((runtime_root / "special_strategy.docx").resolve()),
            )
            self.assertEqual(
                cfg["intermediate_workbook"],
                str((runtime_root / "special_strategy.pipeline.xlsx").resolve()),
            )

    def test_prune_runtime_artifacts_keeps_latest_three_sets(self) -> None:
        stamps = [
            "20260421_090000_000001",
            "20260421_090000_000002",
            "20260421_090000_000003",
            "20260421_090000_000004",
        ]
        suffixes = [
            ".params.json",
            ".pipeline.xlsx",
            ".docx",
            ".report_metadata.json",
            ".state.json",
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "WC19-1D"
            root.mkdir(parents=True, exist_ok=True)
            for stamp in stamps:
                run_root = root / f"special_strategy_run_{stamp}"
                run_root.mkdir(parents=True, exist_ok=True)
                for suffix in suffixes:
                    name = {
                        ".params.json": "runtime_params.json",
                        ".pipeline.xlsx": "special_strategy.pipeline.xlsx",
                        ".docx": "special_strategy.docx",
                        ".report_metadata.json": "report_metadata.json",
                        ".state.json": "runtime_state.json",
                    }[suffix]
                    (run_root / name).write_text("demo", encoding="utf-8")
            (root / "runtime_state.json").write_text("{}", encoding="utf-8")

            with patch("services.special_strategy_runtime.shared_storage_dir", return_value=tmp):
                _prune_runtime_artifacts("WC19-1D", keep_latest=3)

            remaining = sorted(path.name for path in root.iterdir())
            remaining_dirs = sorted(path.name for path in root.iterdir() if path.is_dir())
            self.assertNotIn(f"special_strategy_run_{stamps[0]}", remaining_dirs)
            for stamp in stamps[1:]:
                self.assertIn(f"special_strategy_run_{stamp}", remaining_dirs)
            self.assertIn("runtime_state.json", remaining)

    def test_run_artifact_paths_groups_each_run_into_its_own_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("services.special_strategy_runtime.shared_storage_dir", return_value=tmp):
                paths = run_artifact_paths("WC19-1D", "20260421_090000_000001")

        run_root = (Path(tmp) / "WC19-1D" / "special_strategy_run_20260421_090000_000001").resolve()
        self.assertEqual(paths["root"], run_root)
        self.assertEqual(paths["params_json"], run_root / "runtime_params.json")
        self.assertEqual(paths["intermediate_workbook"], run_root / "special_strategy.pipeline.xlsx")
        self.assertEqual(paths["output_report"], run_root / "special_strategy.docx")
        self.assertEqual(paths["report_metadata_json"], run_root / "report_metadata.json")
        self.assertEqual(paths["state_json"], run_root / "runtime_state.json")


if __name__ == "__main__":
    unittest.main()
