from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _class_method_duplicates(relative_path: str, class_name: str) -> dict[str, list[tuple[int, int]]]:
    source_path = REPO_ROOT / relative_path
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            seen: dict[str, list[tuple[int, int]]] = {}
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    seen.setdefault(item.name, []).append((item.lineno, item.end_lineno or item.lineno))
            return {name: spans for name, spans in seen.items() if len(spans) > 1}
    raise AssertionError(f"class not found: {class_name} in {relative_path}")


class UploadLogicRegressionTests(unittest.TestCase):
    def test_upload_related_classes_have_no_shadowed_methods(self) -> None:
        targets = [
            ("pages/new_special_inspection_page.py", "NewSpecialInspectionPage"),
            ("pages/model_files_page.py", "ModelFilesPage"),
            ("pages/model_files_page.py", "ModelFilesDocsWidget"),
            ("pages/construction_docs_widget.py", "ConstructionDocsWidget"),
            ("pages/doc_man.py", "DocManWidget"),
            ("pages/history_inspection_summary_page.py", "HistoryInspectionSummaryPage"),
            ("pages/important_history_rebuild_info_page.py", "ImportantHistoryDetailWidget"),
        ]
        for relative_path, class_name in targets:
            with self.subTest(relative_path=relative_path, class_name=class_name):
                self.assertEqual(
                    _class_method_duplicates(relative_path, class_name),
                    {},
                    msg=f"duplicate methods found in {class_name}",
                )

    def test_special_inspection_upload_paths_use_runtime_branches(self) -> None:
        text = (REPO_ROOT / "pages/new_special_inspection_page.py").read_text(encoding="utf-8")
        for snippet in (
            'self.CATEGORY_MODEL: "当前模型/结构模型/用户上传"',
            'self.CATEGORY_COLLAPSE: "当前模型/倒塌分析/结果/用户上传"',
            "self.CATEGORY_FATIGUE: f\"当前模型/疲劳分析/{'输入' if branch == 'input' else '结果'}/用户上传\"",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

    def test_runtime_scans_current_model_branches(self) -> None:
        text = (REPO_ROOT / "special_strategy_runtime.py").read_text(encoding="utf-8")
        for snippet in (
            'logical_path_prefix=f"{normalize_facility_code(facility_code)}/当前模型"',
            '_logical_has_segment(logical_path, "当前模型/结构模型")',
            '_logical_has_segment(logical_path, "当前模型/倒塌分析")',
            '_logical_has_segment(logical_path, "当前模型/疲劳分析")',
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

    def test_model_files_uploads_keep_user_upload_suffix(self) -> None:
        text = (REPO_ROOT / "pages/model_files_page.py").read_text(encoding="utf-8")
        for snippet in (
            'return f"{base}/结构模型/用户上传"',
            'return f"{base}/疲劳分析/{branch}/用户上传"',
            'return f"{base}/倒塌分析/{branch}/用户上传"',
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

    def test_runtime_only_overrides_complete_fatigue_groups(self) -> None:
        text = (REPO_ROOT / "special_strategy_runtime.py").read_text(encoding="utf-8")
        for snippet in (
            "def _should_override_fatigue_groups(",
            "if result_count <= 0 or input_count <= 0:",
            'if _should_override_fatigue_groups(resolved["ftglst"], resolved["ftginp"], ftglst_rows, ftginp_rows):',
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)


if __name__ == "__main__":
    unittest.main()
