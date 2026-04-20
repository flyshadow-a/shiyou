from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class SpecialStrategyHistoryRegressionTests(unittest.TestCase):
    def test_runtime_exposes_history_loading_by_run(self) -> None:
        text = (REPO_ROOT / "services" / "special_strategy_runtime.py").read_text(encoding="utf-8")
        for snippet in (
            "def load_result_bundle(facility_code: str, run_id: int | None = None)",
            "if run_id and run_payload is None:",
            "load_strategy_result_snapshot_by_run(run_id)",
            "def list_result_run_history(facility_code: str, limit: int = 50)",
            "def generate_special_strategy_report(",
            'paths["root"] / f"special_strategy_run_{int(run_id)}.docx"',
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

    def test_state_db_has_history_queries_and_run_index(self) -> None:
        text = (REPO_ROOT / "services" / "special_strategy_state_db.py").read_text(encoding="utf-8")
        for snippet in (
            "ix_special_strategy_result_run_id",
            "def load_strategy_run_by_id(run_id: int",
            "def list_strategy_runs(",
            "def load_strategy_result_snapshot_by_run(",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

    def test_oop_service_module_exists(self) -> None:
        text = (REPO_ROOT / "services" / "special_strategy_services.py").read_text(encoding="utf-8")
        for snippet in (
            "class StrategyRunHistoryItem:",
            "class NodeYearLabelMapper:",
            "class SpecialStrategySummaryBuilder:",
            "class SpecialStrategyResultService:",
            "def display_labels(self) -> list[str]:",
            "def build_component_inspection_rows(self, context: dict[str, Any])",
            "def build_node_inspection_rows(self, context: dict[str, Any], display_year: str)",
            "def list_history(self, facility_code: str, limit: int = 100)",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

    def test_special_strategy_page_uses_dialog_and_service_objects(self) -> None:
        text = (REPO_ROOT / "pages/special_inspection_strategy.py").read_text(encoding="utf-8")
        for snippet in (
            "from pages.special_strategy_history_dialog import SpecialStrategyHistoryDialog as SpecialStrategyHistoryDialogView",
            "from services.special_strategy_services import (",
            "self._result_service = SpecialStrategyResultService()",
            "self._year_mapper = NodeYearLabelMapper()",
            "self._summary_builder = SpecialStrategySummaryBuilder(self._year_mapper)",
            "years = self._year_mapper.display_labels()",
            "bundle = self._result_service.load_result_bundle(facility_code, run_id)",
            "self._summary_builder.build_component_inspection_rows(context)",
            "self._summary_builder.build_node_inspection_rows(context, year)",
            "dialog = SpecialStrategyHistoryDialogView(",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

    def test_history_dialog_uses_service(self) -> None:
        text = (REPO_ROOT / "pages/special_strategy_history_dialog.py").read_text(encoding="utf-8")
        for snippet in (
            "from services.special_strategy_services import SpecialStrategyResultService",
            "result_service: SpecialStrategyResultService | None = None",
            "self._result_service = result_service or SpecialStrategyResultService()",
            "rows = self._result_service.list_history(self.facility_code, limit=100)",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

    def test_result_page_uses_service_and_mapper(self) -> None:
        text = (REPO_ROOT / "pages/upgrade_special_inspection_result_page.py").read_text(encoding="utf-8")
        for snippet in (
            "from services.special_strategy_services import NodeYearLabelMapper, SpecialStrategyResultService",
            "self._result_service = SpecialStrategyResultService()",
            "self._year_mapper = NodeYearLabelMapper()",
            "self.summary_node = self._make_summary_table(self._year_mapper.display_labels())",
            "bundle = self._result_service.load_result_bundle(self.facility_code, self.run_id)",
            "display_label = self._year_mapper.to_display_label(context_label)",
            "report_path = self._result_service.generate_report(self.facility_code, run_id=self.run_id)",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, text)

    def test_new_page_and_main_window_wire_summary_refresh(self) -> None:
        new_page_text = (REPO_ROOT / "pages/new_special_inspection_page.py").read_text(encoding="utf-8")
        main_text = (REPO_ROOT / "main.py").read_text(encoding="utf-8")
        for snippet in (
            "strategy_calculated = pyqtSignal(str, object)",
            "self.strategy_calculated.emit(self.facility_code, self._latest_run_id)",
            "open_upgrade_special_inspection_result_tab(self.facility_code, run_id=self._latest_run_id)",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, new_page_text)
        for snippet in (
            "page.strategy_calculated.connect(self._on_special_strategy_calculated)",
            "def _on_special_strategy_calculated(self, facility_code: str, run_id: object = None):",
            "refresh(facility_code=facility_code, run_id=run_id, sync_dropdown=True)",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, main_text)


if __name__ == "__main__":
    unittest.main()
