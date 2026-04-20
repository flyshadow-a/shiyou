from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.special_strategy_runtime import generate_special_strategy_report, list_result_run_history, load_result_bundle


@dataclass(frozen=True)
class StrategyRunHistoryItem:
    run_id: int
    facility_code: str
    updated_at: str
    report_generated_at: str
    status: str


class NodeYearLabelMapper:
    def __init__(self) -> None:
        self._display_to_context = {
            "当前": "当前",
            "+5年": "第5年",
            "+10年": "第10年",
            "+15年": "第15年",
            "+20年": "第20年",
            "+25年": "第25年",
        }
        self._context_to_display = {value: key for key, value in self._display_to_context.items()}

    def display_labels(self) -> list[str]:
        return list(self._display_to_context.keys())

    def default_display_label(self) -> str:
        return self.display_labels()[0]

    def to_context_label(self, display_label: str) -> str:
        return self._display_to_context.get(display_label, display_label)

    def to_display_label(self, context_label: str) -> str | None:
        return self._context_to_display.get(context_label)


class SpecialStrategySummaryBuilder:
    RISK_LEVELS = ["一", "二", "三", "四", "五"]

    def __init__(self, year_mapper: NodeYearLabelMapper | None = None) -> None:
        self._year_mapper = year_mapper or NodeYearLabelMapper()

    @staticmethod
    def display_cell(value: object) -> str:
        if value in ("", None):
            return "-"
        return str(value)

    def build_component_inspection_rows(self, context: dict[str, Any]) -> list[tuple[str, str, str, str]]:
        summary_map = {
            str(row.get("risk_level", "")): row
            for row in context.get("member_inspection_summary", [])
        }
        rows: list[tuple[str, str, str, str]] = []
        for risk in self.RISK_LEVELS:
            row = summary_map.get(risk, {})
            rows.append(
                (
                    self.display_cell(row.get("count")),
                    self.display_cell(row.get("II")),
                    self.display_cell(row.get("III")),
                    self.display_cell(row.get("IV")),
                )
            )
        rows.append(
            (
                self.display_cell(context.get("member_inspection_total")),
                self.display_cell(context.get("member_inspection_total_II")),
                self.display_cell(context.get("member_inspection_total_III")),
                self.display_cell(context.get("member_inspection_total_IV")),
            )
        )
        return rows

    def build_node_inspection_rows(self, context: dict[str, Any], display_year: str) -> list[tuple[str, str, str, str]]:
        context_year = self._year_mapper.to_context_label(display_year)
        risk_block = next(
            (item for item in context.get("node_summary_blocks", []) if str(item.get("time_node", "")) == context_year),
            None,
        )
        inspect_block = next(
            (item for item in context.get("node_inspection_blocks", []) if str(item.get("time_node", "")) == context_year),
            None,
        )
        if risk_block is None:
            return [("-", "-", "-", "-") for _ in range(6)]

        risk_counts = dict(risk_block.get("counts", {}) or {})
        inspection_summary_map = {
            str(row.get("risk_level", "")): row
            for row in (inspect_block or {}).get("summary_rows", [])
        }
        rows: list[tuple[str, str, str, str]] = []
        for risk in self.RISK_LEVELS:
            inspect_row = inspection_summary_map.get(risk, {})
            rows.append(
                (
                    self.display_cell(risk_counts.get(risk)),
                    self.display_cell(inspect_row.get("II")),
                    self.display_cell(inspect_row.get("III")),
                    self.display_cell(inspect_row.get("IV")),
                )
            )
        rows.append(
            (
                self.display_cell(risk_block.get("total", risk_block.get("total_count"))),
                self.display_cell((inspect_block or {}).get("total_II")),
                self.display_cell((inspect_block or {}).get("total_III")),
                self.display_cell((inspect_block or {}).get("total_IV")),
            )
        )
        return rows

    def iter_node_summary_blocks(self, context: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for block in context.get("node_summary_blocks", []):
            context_label = str(block.get("time_node", "")).strip()
            display_label = self._year_mapper.to_display_label(context_label)
            if not display_label:
                continue
            items.append(
                (
                    display_label,
                    dict(block.get("counts", {}) or {}),
                    dict(block.get("ratios", {}) or {}),
                )
            )
        return items


class SpecialStrategyResultService:
    def __init__(self, year_mapper: NodeYearLabelMapper | None = None) -> None:
        self.year_mapper = year_mapper or NodeYearLabelMapper()

    @staticmethod
    def _format_timestamp(value: object) -> str:
        if value is None:
            return ""
        if hasattr(value, "strftime"):
            try:
                return value.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return str(value)
        return str(value)

    def load_result_bundle(self, facility_code: str, run_id: int | None = None) -> dict[str, Any] | None:
        return load_result_bundle(facility_code, run_id)

    def list_history(self, facility_code: str, limit: int = 100) -> list[StrategyRunHistoryItem]:
        rows = list_result_run_history(facility_code, limit=limit)
        items: list[StrategyRunHistoryItem] = []
        for row in rows:
            run_id = row.get("id")
            try:
                normalized_run_id = int(run_id)
            except Exception:
                continue
            items.append(
                StrategyRunHistoryItem(
                    run_id=normalized_run_id,
                    facility_code=str(row.get("facility_code", "")),
                    updated_at=self._format_timestamp(row.get("updated_at")),
                    report_generated_at=self._format_timestamp(row.get("report_generated_at")),
                    status=str(row.get("status", "")),
                )
            )
        return items

    def generate_report(
        self,
        facility_code: str,
        *,
        run_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        return generate_special_strategy_report(facility_code, run_id=run_id, metadata=metadata)
