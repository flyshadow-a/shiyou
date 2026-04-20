from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.special_strategy_runtime import resolve_current_model_inputs


class SpecialStrategyRuntimeInputTests(unittest.TestCase):
    def test_current_model_inputs_only_use_runtime_supported_files_and_sort_by_work_condition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = {
                "model": base / "sacinp.demo",
                "clplog": base / "clplog",
                "clplst": base / "clplst",
                "ftglst_a": base / "ftglst_a",
                "ftglst_b": base / "ftglst_b",
                "wvrinp": base / "wvrinp",
                "ftginp_a": base / "ftginp_a.demo",
                "ftginp_b": base / "ftginp_b.demo",
            }
            for path in files.values():
                path.write_text("demo", encoding="utf-8")

            rows = [
                {
                    "logical_path": "WC19-1D/当前模型/结构模型/用户上传/结构模型文件",
                    "original_name": "sacinp.demo",
                    "storage_path": str(files["model"]),
                    "work_condition": "",
                },
                {
                    "logical_path": "WC19-1D/当前模型/倒塌分析/结果/用户上传/倒塌分析结果文件",
                    "original_name": "clplst",
                    "storage_path": str(files["clplst"]),
                    "work_condition": "忽略",
                },
                {
                    "logical_path": "WC19-1D/当前模型/倒塌分析/结果/用户上传/倒塌分析日志文件",
                    "original_name": "clplog",
                    "storage_path": str(files["clplog"]),
                    "work_condition": "操作工况",
                },
                {
                    "logical_path": "WC19-1D/当前模型/疲劳分析/结果/用户上传/疲劳分析结果文件",
                    "original_name": "wvrinp",
                    "storage_path": str(files["wvrinp"]),
                    "work_condition": "4-3WJT",
                },
                {
                    "logical_path": "WC19-1D/当前模型/疲劳分析/结果/用户上传/疲劳分析结果文件",
                    "original_name": "ftglst",
                    "storage_path": str(files["ftglst_b"]),
                    "work_condition": "4-2WJT",
                },
                {
                    "logical_path": "WC19-1D/当前模型/疲劳分析/结果/用户上传/疲劳分析结果文件",
                    "original_name": "ftglst",
                    "storage_path": str(files["ftglst_a"]),
                    "work_condition": "4-1WJT",
                },
                {
                    "logical_path": "WC19-1D/当前模型/疲劳分析/输入/用户上传/疲劳分析模型文件",
                    "original_name": "ftginp.demo",
                    "storage_path": str(files["ftginp_b"]),
                    "work_condition": "4-2WJT",
                },
                {
                    "logical_path": "WC19-1D/当前模型/疲劳分析/输入/用户上传/疲劳分析模型文件",
                    "original_name": "ftginp.demo",
                    "storage_path": str(files["ftginp_a"]),
                    "work_condition": "4-1WJT",
                },
            ]

            def fake_resolve_storage_path(row):
                return str(row["storage_path"])

            with patch("services.special_strategy_runtime.is_file_db_configured", return_value=True), patch(
                "services.special_strategy_runtime.list_files_by_prefix",
                return_value=rows,
            ), patch(
                "services.special_strategy_runtime.resolve_storage_path",
                side_effect=fake_resolve_storage_path,
            ):
                resolved = resolve_current_model_inputs(
                    "WC19-1D",
                    {
                        "model": "",
                        "clplog": [],
                        "ftglst": [],
                        "ftginp": [],
                    },
                )

            self.assertEqual(resolved["model"], str(files["model"]))
            self.assertEqual(resolved["clplog"], [str(files["clplog"])])
            self.assertEqual(
                resolved["ftglst"],
                [str(files["ftglst_a"]), str(files["ftglst_b"])],
            )
            self.assertEqual(
                resolved["ftginp"],
                [str(files["ftginp_a"]), str(files["ftginp_b"])],
            )


if __name__ == "__main__":
    unittest.main()
