from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


CHAPTER_1_3_KEYS = (
    "platform_overview",
    "retrofit_history",
    "platform_evaluation_conclusion",
    "basis_data",
    "load_information",
    "environment_conditions",
    "analysis_model",
)


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_numeric_text(value: Any) -> str:
    text = _to_text(value)
    if not text:
        return ""

    try:
        decimal_value = Decimal(text)
    except (InvalidOperation, ValueError):
        return text

    normalized = format(decimal_value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    if normalized in {"-0", "+0", ""}:
        return "0"
    return normalized


def _build_blocks_from_text(text: str) -> list[dict[str, str]]:
    # 1～3 章改为块级渲染后，这里把原始文本按空段拆成多个正文块，
    # 供渲染层按章节范围逐段写入，而不是只覆盖标题后的单个段落。
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = []
    for paragraph in normalized.split("\n\n"):
        paragraph_text = paragraph.strip()
        if not paragraph_text:
            continue
        blocks.append({"kind": "generated_paragraph", "text": paragraph_text})
    return blocks


def _normalize_section_source(source: Mapping[str, Any] | str) -> dict[str, Any]:
    # 兼容两类输入：
    # 1) 旧格式纯字符串/带 text 的简单对象
    # 2) 新格式结构化 section（mode + blocks）
    if isinstance(source, Mapping):
        mode = _to_text(source.get("mode")) or "replace_region"
        table_rows = source.get("table_rows")
        normalized_table_rows = []
        if isinstance(table_rows, list):
            # 1.2 节表格填充使用结构化 table_rows，供渲染层直接写入模板表格。
            for row in table_rows:
                if not isinstance(row, Mapping):
                    continue
                normalized_table_rows.append(
                    {
                        "index": _to_text(row.get("index")),
                        "name": _to_text(row.get("name")),
                        "year": _to_text(row.get("year")),
                    }
                )
        environment_table_keys = (
            "water_level_rows",
            "wind_rows",
            "wave_rows",
            "current_rows",
            "marine_growth_rows",
            "splash_zone_rows",
        )
        load_information_row_keys = (
            "seq_no",
            "project_name",
            "rebuild_time",
            "rebuild_content",
            "total_weight_mt",
            "weight_limit_mt",
            "weight_delta_mt",
            "center_xyz",
            "center_radius_m",
            "fx_kn",
            "fy_kn",
            "fz_kn",
            "mx_kn_m",
            "my_kn_m",
            "mz_kn_m",
            "safety_op",
            "safety_extreme",
            "overall_assessment",
            "assessment_org",
        )
        normalized_load_information_meta = {}
        raw_load_information_meta = source.get("load_information_meta")
        if isinstance(raw_load_information_meta, Mapping):
            normalized_load_information_meta = {
                "branch": _to_text(raw_load_information_meta.get("branch")),
                "op_company": _to_text(raw_load_information_meta.get("op_company")),
                "oilfield": _to_text(raw_load_information_meta.get("oilfield")),
                "facility_name": _to_text(raw_load_information_meta.get("facility_name")),
                "start_time": _to_text(raw_load_information_meta.get("start_time")),
                "design_life": _to_text(raw_load_information_meta.get("design_life")),
            }
        normalized_load_information_rows = []
        raw_load_information_rows = source.get("load_information_rows")
        if isinstance(raw_load_information_rows, list):
            for row in raw_load_information_rows:
                if not isinstance(row, Mapping):
                    continue
                normalized_row = {}
                for field in load_information_row_keys:
                    normalized_row[field] = _normalize_numeric_text(row.get(field))
                normalized_load_information_rows.append(normalized_row)
        platform_evaluation_table_fields = {
            "well_slot_rows": (
                "slot_no",
                "x",
                "y",
                "conductor_od",
                "conductor_wt",
                "support_od",
                "support_wt",
                "top_load_fz",
            ),
            "riser_rows": (
                "riser_no",
                "x",
                "y",
                "riser_od",
                "riser_wt",
                "support_od",
                "support_wt",
                "batter_x",
                "batter_y",
            ),
            "topside_weight_rows": (
                "weight_no",
                "x",
                "y",
                "z",
                "weight_t",
            ),
        }
        normalized_platform_evaluation_tables: dict[str, list[dict[str, str]]] = {}
        for table_key, fields in platform_evaluation_table_fields.items():
            raw_rows = source.get(table_key)
            normalized_rows = []
            if isinstance(raw_rows, list):
                for row in raw_rows:
                    if not isinstance(row, Mapping):
                        continue
                    normalized_rows.append(
                        {field: _normalize_numeric_text(row.get(field)) for field in fields}
                    )
            normalized_platform_evaluation_tables[table_key] = normalized_rows
        normalized_environment_tables: dict[str, list[dict[str, str]]] = {}
        for table_key in environment_table_keys:
            raw_rows = source.get(table_key)
            normalized_rows = []
            if isinstance(raw_rows, list):
                for row in raw_rows:
                    if not isinstance(row, Mapping):
                        continue
                    normalized_rows.append(
                        {
                            "group_name": _to_text(row.get("group_name")),
                            "item_name": _to_text(row.get("item_name")),
                            "return_period": _to_text(row.get("return_period")),
                            "value": _normalize_numeric_text(row.get("value")),
                            "unit": _to_text(row.get("unit")),
                            "layer_no": _to_text(row.get("layer_no")),
                            "upper_limit_m": _normalize_numeric_text(row.get("upper_limit_m")),
                            "lower_limit_m": _normalize_numeric_text(row.get("lower_limit_m")),
                            "thickness_mm": _normalize_numeric_text(row.get("thickness_mm")),
                            "density_t_per_m3": _normalize_numeric_text(row.get("density_t_per_m3")),
                            "corrosion_allowance_mm_per_y": _normalize_numeric_text(row.get("corrosion_allowance_mm_per_y")),
                        }
                    )
            normalized_environment_tables[table_key] = normalized_rows
        blocks = source.get("blocks")
        overall_model_image_path = _to_text(source.get("overall_model_image_path"))
        coordinate_system_image_path = _to_text(source.get("coordinate_system_image_path"))
        if isinstance(blocks, list):
            normalized_blocks = []
            for block in blocks:
                if not isinstance(block, Mapping):
                    continue
                text = _to_text(block.get("text"))
                if not text:
                    continue
                normalized_blocks.append(
                    {
                        # 保留章节内定点替换所需的锚点元数据，
                        # 否则从 API 传进来的第几个例子/说明后下一段等信息会在这里丢失。
                        "kind": _to_text(block.get("kind")) or "generated_paragraph",
                        "text": text,
                        "anchor_prefix": _to_text(block.get("anchor_prefix")),
                        "anchor_occurrence": int(block.get("anchor_occurrence", 1) or 1),
                        "preserve_anchor_style": bool(block.get("preserve_anchor_style", False)),
                        "replace_next_paragraph": bool(block.get("replace_next_paragraph", False)),
                        "keep_anchor_paragraph": bool(block.get("keep_anchor_paragraph", False)),
                    }
                )
            if (
                normalized_blocks
                or normalized_table_rows
                or any(normalized_environment_tables.values())
                or normalized_load_information_meta
                or normalized_load_information_rows
                or any(normalized_platform_evaluation_tables.values())
                or overall_model_image_path
                or coordinate_system_image_path
            ):
                return {
                    "mode": mode,
                    "blocks": normalized_blocks,
                    "table_rows": normalized_table_rows,
                    "overall_model_image_path": overall_model_image_path,
                    "coordinate_system_image_path": coordinate_system_image_path,
                    "load_information_meta": normalized_load_information_meta,
                    "load_information_rows": normalized_load_information_rows,
                    **normalized_platform_evaluation_tables,
                    **normalized_environment_tables,
                }

        text = _to_text(source.get("text", ""))
        return {
            "mode": mode,
            "blocks": _build_blocks_from_text(text),
            "table_rows": normalized_table_rows,
            "overall_model_image_path": overall_model_image_path,
            "coordinate_system_image_path": coordinate_system_image_path,
            "load_information_meta": normalized_load_information_meta,
            "load_information_rows": normalized_load_information_rows,
            **normalized_platform_evaluation_tables,
            **normalized_environment_tables,
        }

    return {"mode": "replace_region", "blocks": _build_blocks_from_text(_to_text(source))}


def build_chapter_1_3_context(
    section_sources: Mapping[str, Mapping[str, Any] | str] | None = None,
) -> dict[str, dict[str, Any]]:
    sources = section_sources or {}
    context: dict[str, dict[str, Any]] = {}

    for key in CHAPTER_1_3_KEYS:
        # 统一归一化为 section 对象，便于后续支持 replace_region / hybrid 等模式。
        context[key] = _normalize_section_source(sources.get(key, ""))

    return context
