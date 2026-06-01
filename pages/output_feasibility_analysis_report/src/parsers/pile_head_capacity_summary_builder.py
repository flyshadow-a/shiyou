"""
装配 4.5.3 桩基承载力结果。

说明：
1. 操作/极端工况来源于 `LOAD CASE STATUS REPORT` 的真实分类。
2. 压力/拉力来源于 `PILE HEAD COORDINATES` 下的轴向力极值，而不是直接抄
   `SOIL MAXIMUM AXIAL CAPACITY SUMMARY` 的控制工况。
3. 承载力和桩身重量仍复用 `SOIL MAXIMUM AXIAL CAPACITY SUMMARY` 中每个桩头的能力参数。
4. 安全系数公式：
   - 受压: compression_capacity / (abs(compression_load) + weight)
   - 受拉: tension_capacity / (abs(tension_load) - weight)
     若受拉分母小于等于 0，则显示为 "-"，不参与控制值判断。
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, TypedDict


ConditionType = Literal["operation", "extreme"]
ResistanceType = Literal["compression", "tension"]

OPERATION_CASE_PREFIXES = ("OP", "OL")
EXTREME_CASE_PREFIXES = ("EH", "EL", "LTH", "LTL")


class PileHeadConditionRow(TypedDict):
    pile_head_id: str
    pile_weight_kn: float
    compression_capacity_kn: float
    tension_capacity_kn: float
    compression_case: str
    compression_load_kn: float | None
    compression_sf: float | None
    tension_case: str
    tension_load_kn: float | None
    tension_sf: float | str | None


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


class PileHeadCapacitySummaryBuilt(TypedDict):
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
    case_type_map: Mapping[str, ConditionType] | None,
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


def _format_number(value: float | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _build_empty_summary(
    *,
    key: str,
    check_item: str,
    condition_type: ConditionType,
    resistance_type: ResistanceType,
) -> PileAxialCapacityControlSummary:
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


def _build_control_summary(
    row: Mapping[str, Any] | None,
    *,
    key: str,
    check_item: str,
    condition_type: ConditionType,
    resistance_type: ResistanceType,
    pass_threshold: float,
) -> PileAxialCapacityControlSummary:
    if row is None:
        return _build_empty_summary(
            key=key,
            check_item=check_item,
            condition_type=condition_type,
            resistance_type=resistance_type,
        )

    sf_field = f"{resistance_type}_sf"
    load_field = f"{resistance_type}_load_kn"
    case_field = f"{resistance_type}_case"
    capacity_field = f"{resistance_type}_capacity_kn"
    min_sf = float(row[sf_field])
    is_pass = min_sf >= pass_threshold
    is_pass_text = "满足" if is_pass else "不满足"
    case_name = str(row[case_field]).strip()
    pile_head_id = str(row["pile_head_id"]).strip()
    capacity_kn = float(row[capacity_field])
    design_load_kn = float(row[load_field])

    return {
        "key": key,
        "check_item": check_item,
        "condition_type": condition_type,
        "resistance_type": resistance_type,
        "min_sf": min_sf,
        "pile_head_id": pile_head_id,
        "group_id": "",
        "case": case_name,
        "capacity_kn": capacity_kn,
        "design_load_kn": design_load_kn,
        "critical_load_kn": design_load_kn,
        "max_unity_check": 0.0,
        "is_pass": is_pass,
        "is_pass_text": is_pass_text,
        "summary_text": (
            f"{check_item}最小安全系数为{min_sf:.2f}，"
            f"对应桩头为{pile_head_id}，"
            f"控制工况为{case_name}，{is_pass_text}安全系数不小于{pass_threshold:.2f}的要求。"
        ),
        "summary_table_row": {
            "check_item": check_item,
            "position": pile_head_id,
            "value": f"{min_sf:.2f}",
            "case": case_name,
            "is_pass": is_pass_text,
        },
    }


def _to_table_row(row: PileHeadConditionRow) -> dict:
    return {
        "pile_head_id": row["pile_head_id"],
        "compression_capacity_kn": _format_number(row["compression_capacity_kn"]),
        "tension_capacity_kn": _format_number(row["tension_capacity_kn"]),
        "pile_weight_kn": _format_number(row["pile_weight_kn"]),
        "compression_case": row["compression_case"],
        "compression_load_kn": _format_number(row["compression_load_kn"]),
        "tension_case": row["tension_case"],
        "tension_load_kn": _format_number(row["tension_load_kn"]),
        "compression_sf": _format_number(row["compression_sf"]),
        "tension_sf": _format_number(row["tension_sf"]),
    }


def build_pile_head_capacity_summary(
    pile_head_force_result: Mapping[str, Any],
    pile_axial_capacity_summary: Mapping[str, Any],
    *,
    case_type_map: Mapping[str, ConditionType] | None = None,
    operation_pass_threshold: float = 1.5,
    extreme_pass_threshold: float = 1.5,
) -> PileHeadCapacitySummaryBuilt:
    capacity_map: dict[str, dict[str, float]] = {}
    for row in pile_axial_capacity_summary.get("rows", []):
        pile_head_id = str(row.get("pile_head_id", "")).strip()
        if not pile_head_id:
            continue
        capacity_map[pile_head_id] = {
            "compression_capacity_kn": abs(float(row.get("comp_capacity_kn", 0.0))),
            "tension_capacity_kn": abs(float(row.get("tens_capacity_kn", 0.0))),
            "pile_weight_kn": float(row.get("pile_weight_kn", 0.0)),
        }

    grouped: dict[tuple[str, ConditionType], dict[str, Any]] = {}
    for row in pile_head_force_result.get("rows", []):
        load_case = str(row.get("load_case", "")).strip()
        condition_type = _match_condition(load_case, case_type_map)
        pile_head_id = str(row.get("pile_head_id", "")).strip()
        if condition_type is None or not pile_head_id or pile_head_id not in capacity_map:
            continue

        record = grouped.setdefault(
            (pile_head_id, condition_type),
            {
                "pile_head_id": pile_head_id,
                "compression_case": "",
                "compression_load_kn": None,
                "tension_case": "",
                "tension_load_kn": None,
            },
        )
        axial_force_kn = float(row.get("axial_force_kn", 0.0))

        current_compression = record["compression_load_kn"]
        if current_compression is None or axial_force_kn < current_compression:
            record["compression_load_kn"] = axial_force_kn
            record["compression_case"] = load_case

        current_tension = record["tension_load_kn"]
        if axial_force_kn > 0 and (current_tension is None or axial_force_kn > current_tension):
            record["tension_load_kn"] = axial_force_kn
            record["tension_case"] = load_case

    condition_rows: dict[ConditionType, list[PileHeadConditionRow]] = {
        "operation": [],
        "extreme": [],
    }
    ordered_pile_head_ids = list(capacity_map.keys())

    for condition_type in ("operation", "extreme"):
        for pile_head_id in ordered_pile_head_ids:
            capacity = capacity_map[pile_head_id]
            record = grouped.get((pile_head_id, condition_type), {})
            compression_load_kn = record.get("compression_load_kn")
            tension_load_kn = record.get("tension_load_kn")
            pile_weight_kn = capacity["pile_weight_kn"]
            compression_capacity_kn = capacity["compression_capacity_kn"]
            tension_capacity_kn = capacity["tension_capacity_kn"]

            compression_sf = None
            if compression_load_kn is not None:
                compression_load_kn = abs(compression_load_kn)
                denominator = compression_load_kn + pile_weight_kn
                if denominator > 0:
                    compression_sf = compression_capacity_kn / denominator

            tension_sf: float | str | None = "-"
            if tension_load_kn is not None:
                tension_load_kn = abs(tension_load_kn)
                denominator = tension_load_kn - pile_weight_kn
                if denominator > 0:
                    tension_sf = tension_capacity_kn / denominator

            condition_rows[condition_type].append(
                {
                    "pile_head_id": pile_head_id,
                    "pile_weight_kn": pile_weight_kn,
                    "compression_capacity_kn": compression_capacity_kn,
                    "tension_capacity_kn": tension_capacity_kn,
                    "compression_case": str(record.get("compression_case", "")),
                    "compression_load_kn": compression_load_kn,
                    "compression_sf": compression_sf,
                    "tension_case": str(record.get("tension_case", "")),
                    "tension_load_kn": tension_load_kn,
                    "tension_sf": tension_sf,
                }
            )

    operation_rows = condition_rows["operation"]
    extreme_rows = condition_rows["extreme"]
    operation_table_rows = [_to_table_row(row) for row in operation_rows]
    extreme_table_rows = [_to_table_row(row) for row in extreme_rows]

    operation_compression = _build_control_summary(
        min((row for row in operation_rows if row["compression_sf"] is not None), key=lambda row: row["compression_sf"], default=None),
        key="pile_comp_op",
        check_item="操作工况桩基抗压",
        condition_type="operation",
        resistance_type="compression",
        pass_threshold=operation_pass_threshold,
    )
    operation_tension = _build_control_summary(
        min((row for row in operation_rows if isinstance(row["tension_sf"], float)), key=lambda row: row["tension_sf"], default=None),
        key="pile_tens_op",
        check_item="操作工况桩基抗拔",
        condition_type="operation",
        resistance_type="tension",
        pass_threshold=operation_pass_threshold,
    )
    extreme_compression = _build_control_summary(
        min((row for row in extreme_rows if row["compression_sf"] is not None), key=lambda row: row["compression_sf"], default=None),
        key="pile_comp_ext",
        check_item="极端工况桩基抗压",
        condition_type="extreme",
        resistance_type="compression",
        pass_threshold=extreme_pass_threshold,
    )
    extreme_tension = _build_control_summary(
        min((row for row in extreme_rows if isinstance(row["tension_sf"], float)), key=lambda row: row["tension_sf"], default=None),
        key="pile_tens_ext",
        check_item="极端工况桩基抗拔",
        condition_type="extreme",
        resistance_type="tension",
        pass_threshold=extreme_pass_threshold,
    )

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
