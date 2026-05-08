"""
当 pile_axial_capacity_summary_parser 数据提取后，在此装配 4.5.3 桩基承载力摘要。

说明：
1. 工况分类优先使用 `LOAD CASE STATUS REPORT` 解析得到的真实映射。
2. 仅当状态报告缺失或未命中时，才回退到历史前缀规则：
   - `OP`/`OL` -> 操作工况
   - `EH`/`EL`/`LTH`/`LTL` -> 极端工况
3. 这样可以与原 VBA 的 `AMOD FACTOR = 1.33` 判定逻辑保持一致。
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, TypedDict


ConditionType = Literal["operation", "extreme"]
ResistanceType = Literal["compression", "tension"]

OPERATION_CASE_PREFIXES = ("OP", "OL")
EXTREME_CASE_PREFIXES = ("EH", "EL", "LTH", "LTL")


class PileAxialCapacityControlSummary(TypedDict):
    key: str
    check_item: str
    condition_type: ConditionType
    resistance_type: ResistanceType
    min_sf: float
    pile_head_id: str
    group_id: str
    case: str
    capacity_kn: float
    design_load_kn: float
    critical_load_kn: float
    max_unity_check: float
    is_pass: bool
    is_pass_text: str
    summary_text: str
    summary_table_row: dict


class PileAxialCapacitySummaryBuilt(TypedDict):
    operation_rows: list[dict]
    extreme_rows: list[dict]
    operation_table_rows: list[dict]
    extreme_table_rows: list[dict]
    operation_compression: PileAxialCapacityControlSummary
    operation_tension: PileAxialCapacityControlSummary
    extreme_compression: PileAxialCapacityControlSummary
    extreme_tension: PileAxialCapacityControlSummary
    summary_items: list[PileAxialCapacityControlSummary]


def _match_condition(
    case_name: str,
    case_type_map: Mapping[str, ConditionType] | None = None,
) -> ConditionType | None:
    upper_name = case_name.upper()

    if case_type_map:
        mapped = case_type_map.get(upper_name) or case_type_map.get(case_name)
        if mapped in {"operation", "extreme"}:
            return mapped

    if upper_name.startswith(OPERATION_CASE_PREFIXES):
        return "operation"
    if upper_name.startswith(EXTREME_CASE_PREFIXES):
        return "extreme"
    return None


def _format_number(value: float | None) -> str:
    if value is None:
        return ""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text


def _format_positive(value: float | None) -> str:
    if value is None:
        return ""
    return _format_number(abs(value))


def _build_condition_table_rows(
    rows: list[dict],
    condition_type: ConditionType,
    case_type_map: Mapping[str, ConditionType] | None = None,
) -> list[dict]:
    ordered_rows: list[dict] = []

    for row in rows:
        pile_head_id = str(row.get("pile_head_id", "")).strip()
        comp_case = str(row.get("comp_case", "")).strip()
        tens_case = str(row.get("tens_case", "")).strip()

        comp_matches = _match_condition(comp_case, case_type_map) == condition_type
        tens_matches = _match_condition(tens_case, case_type_map) == condition_type

        ordered_rows.append(
            {
                "pile_head_id": pile_head_id,
                "compression_capacity_kn": _format_positive(row.get("comp_capacity_kn")),
                "tension_capacity_kn": _format_positive(row.get("tens_capacity_kn")),
                "pile_weight_kn": _format_number(float(row.get("pile_weight_kn", 0.0))),
                "compression_case": comp_case if comp_matches else "",
                "compression_load_kn": _format_positive(
                    row.get("comp_max_load_kn") if comp_matches else None
                ),
                "tension_case": tens_case if tens_matches else "",
                "tension_load_kn": _format_positive(
                    row.get("tens_max_load_kn") if tens_matches else None
                ),
                "compression_sf": _format_number(
                    float(row["comp_sf"]) if comp_matches else None
                ),
                "tension_sf": _format_number(
                    float(row["tens_sf"]) if tens_matches else None
                ),
            }
        )

    return ordered_rows


def _build_control_summary(
    row: Mapping[str, Any] | None,
    *,
    key: str,
    check_item: str,
    condition_type: ConditionType,
    resistance_type: ResistanceType,
    sf_field: str,
    case_field: str,
    capacity_field: str,
    max_load_field: str,
    critical_load_field: str,
    pass_threshold: float,
) -> PileAxialCapacityControlSummary:
    if row is None:
        return {
            "key": key,
            "check_item": check_item,
            "condition_type": condition_type,
            "resistance_type": resistance_type,
            "min_sf": 0.0,
            "pile_head_id": "",
            "group_id": "",
            "case": "",
            "capacity_kn": 0.0,
            "design_load_kn": 0.0,
            "critical_load_kn": 0.0,
            "max_unity_check": 0.0,
            "is_pass": False,
            "is_pass_text": "无数据",
            "summary_text": f"未读取到{check_item}结果，无法生成摘要。",
            "summary_table_row": {
                "check_item": check_item,
                "position": "",
                "value": "",
                "case": "",
                "is_pass": "无数据",
            },
        }

    min_sf = float(row[sf_field])
    is_pass = min_sf >= pass_threshold
    is_pass_text = "满足" if is_pass else "不满足"
    case_name = str(row[case_field]).strip()
    pile_head_id = str(row["pile_head_id"]).strip()
    group_id = str(row["group_id"]).strip()
    capacity_kn = float(row[capacity_field])
    design_load_kn = float(row[max_load_field])
    critical_load_kn = float(row[critical_load_field])
    max_unity_check = float(row["max_unity_check"])

    summary_text = (
        f"{check_item}最小安全系数为{min_sf:.2f}，"
        f"对应桩头为{pile_head_id}，"
        f"控制工况为{case_name}，{is_pass_text}安全系数不小于{pass_threshold:.2f}的要求。"
    )

    return {
        "key": key,
        "check_item": check_item,
        "condition_type": condition_type,
        "resistance_type": resistance_type,
        "min_sf": min_sf,
        "pile_head_id": pile_head_id,
        "group_id": group_id,
        "case": case_name,
        "capacity_kn": capacity_kn,
        "design_load_kn": design_load_kn,
        "critical_load_kn": critical_load_kn,
        "max_unity_check": max_unity_check,
        "is_pass": is_pass,
        "is_pass_text": is_pass_text,
        "summary_text": summary_text,
        "summary_table_row": {
            "check_item": check_item,
            "position": pile_head_id,
            "value": f"{min_sf:.2f}",
            "case": case_name,
            "is_pass": is_pass_text,
        },
    }


def build_pile_axial_capacity_summary(
    pile_axial_capacity_summary: Mapping[str, Any],
    *,
    operation_pass_threshold: float = 1.5,
    extreme_pass_threshold: float = 1.5,
    case_type_map: Mapping[str, ConditionType] | None = None,
) -> PileAxialCapacitySummaryBuilt:
    rows = pile_axial_capacity_summary.get("rows", [])

    operation_rows: list[dict] = []
    extreme_rows: list[dict] = []

    for row in rows:
        comp_condition = _match_condition(str(row.get("comp_case", "")), case_type_map)
        tens_condition = _match_condition(str(row.get("tens_case", "")), case_type_map)

        if comp_condition == "operation" or tens_condition == "operation":
            operation_rows.append(row)
        if comp_condition == "extreme" or tens_condition == "extreme":
            extreme_rows.append(row)

    operation_comp_row = min(
        (
            row
            for row in rows
            if _match_condition(str(row.get("comp_case", "")), case_type_map) == "operation"
        ),
        key=lambda item: item["comp_sf"],
        default=None,
    )
    operation_tens_row = min(
        (
            row
            for row in rows
            if _match_condition(str(row.get("tens_case", "")), case_type_map) == "operation"
        ),
        key=lambda item: item["tens_sf"],
        default=None,
    )
    extreme_comp_row = min(
        (
            row
            for row in rows
            if _match_condition(str(row.get("comp_case", "")), case_type_map) == "extreme"
        ),
        key=lambda item: item["comp_sf"],
        default=None,
    )
    extreme_tens_row = min(
        (
            row
            for row in rows
            if _match_condition(str(row.get("tens_case", "")), case_type_map) == "extreme"
        ),
        key=lambda item: item["tens_sf"],
        default=None,
    )

    operation_compression = _build_control_summary(
        operation_comp_row,
        key="pile_comp_op",
        check_item="操作工况桩基抗压",
        condition_type="operation",
        resistance_type="compression",
        sf_field="comp_sf",
        case_field="comp_case",
        capacity_field="comp_capacity_kn",
        max_load_field="comp_max_load_kn",
        critical_load_field="comp_critical_load_kn",
        pass_threshold=operation_pass_threshold,
    )
    operation_tension = _build_control_summary(
        operation_tens_row,
        key="pile_tens_op",
        check_item="操作工况桩基抗拔",
        condition_type="operation",
        resistance_type="tension",
        sf_field="tens_sf",
        case_field="tens_case",
        capacity_field="tens_capacity_kn",
        max_load_field="tens_max_load_kn",
        critical_load_field="tens_critical_load_kn",
        pass_threshold=operation_pass_threshold,
    )
    extreme_compression = _build_control_summary(
        extreme_comp_row,
        key="pile_comp_ext",
        check_item="极端工况桩基抗压",
        condition_type="extreme",
        resistance_type="compression",
        sf_field="comp_sf",
        case_field="comp_case",
        capacity_field="comp_capacity_kn",
        max_load_field="comp_max_load_kn",
        critical_load_field="comp_critical_load_kn",
        pass_threshold=extreme_pass_threshold,
    )
    extreme_tension = _build_control_summary(
        extreme_tens_row,
        key="pile_tens_ext",
        check_item="极端工况桩基抗拔",
        condition_type="extreme",
        resistance_type="tension",
        sf_field="tens_sf",
        case_field="tens_case",
        capacity_field="tens_capacity_kn",
        max_load_field="tens_max_load_kn",
        critical_load_field="tens_critical_load_kn",
        pass_threshold=extreme_pass_threshold,
    )

    operation_table_rows = _build_condition_table_rows(rows, "operation", case_type_map)
    extreme_table_rows = _build_condition_table_rows(rows, "extreme", case_type_map)

    return {
        "operation_rows": operation_rows,
        "extreme_rows": extreme_rows,
        "operation_table_rows": operation_table_rows,
        "extreme_table_rows": extreme_table_rows,
        "operation_compression": operation_compression,
        "operation_tension": operation_tension,
        "extreme_compression": extreme_compression,
        "extreme_tension": extreme_tension,
        "summary_items": [
            operation_compression,
            operation_tension,
            extreme_compression,
            extreme_tension,
        ],
    }
