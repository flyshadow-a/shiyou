from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from src.chapter_1_3_builder import build_chapter_1_3_context
from src.parsers.basic_case_desc_parser import parse_basic_case_desc
from src.parsers.basic_case_loads_parser import (
    parse_basic_case_loads,
    validate_basic_case_loads_against_desc,
)
from src.parsers.combo_case_desc_parser import parse_combo_case_desc
from src.parsers.combo_case_loads_parser import (
    parse_combo_case_loads,
    validate_combo_case_loads_against_desc,
)
from src.parsers.joint_can_summary_builder import build_joint_can_summary
from src.parsers.joint_can_summary_parser import parse_joint_can_summary
from src.parsers.load_case_status_parser import parse_load_case_status
from src.parsers.member_group_summary_parser import parse_member_group_summary
from src.parsers.member_summary_builder import build_member_summary
from src.parsers.pile_axial_capacity_summary_builder import build_pile_axial_capacity_summary
from src.parsers.pile_axial_capacity_summary_parser import parse_pile_axial_capacity_summary
from src.parsers.pile_head_capacity_summary_builder import build_pile_head_capacity_summary
from src.parsers.pile_head_force_parser import parse_pile_head_forces
from src.parsers.pile_group_summary_builder import build_pile_group_summary
from src.parsers.pile_group_summary_parser import parse_pile_group_summary
from src.parsers.psilst_reader import read_lines, read_ui_analysis_lines
from src.path_config_loader import get_report_defaults
from src.parsers.summary_builder import build_analysis_summary
from src.pdf_converter import convert_docx_to_pdf
from src.renderers.doc_renderer import render_report_doc


def _build_docx_output_path(output_path: str | Path) -> Path:
    output = Path(output_path)
    if output.suffix.lower() == ".pdf":
        return output.with_suffix(".docx")
    return output


def _build_pdf_output_path(output_path: str | Path) -> Path:
    return Path(output_path).with_suffix(".pdf")


def _format_platform_evaluation_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    text = f"{number:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _extract_platform_evaluation_conclusion_text(
    section_source: Mapping[str, Any] | str | None,
    *,
    member_summary: Mapping[str, Any],
    joint_summary: Mapping[str, Any],
    pile_axial_capacity_summary: Mapping[str, Any],
) -> str:
    if not isinstance(section_source, Mapping):
        return str(section_source or "").strip()

    existing_text = str(section_source.get("text", "")).strip()
    if existing_text:
        return existing_text

    blocks = section_source.get("blocks")
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, Mapping):
                block_text = str(block.get("text", "")).strip()
                if block_text:
                    return block_text

    well_slot_count = int(section_source.get("well_slot_count", 0) or 0)
    riser_count = int(section_source.get("riser_count", 0) or 0)
    topside_weight_sum_t = float(section_source.get("topside_weight_sum_t", 0.0) or 0.0)

    prefix = (
        f"本次改造新增井槽{well_slot_count}根，"
        f"立管和电缆{riser_count}条，"
        f"上部组块增加重量{_format_platform_evaluation_number(topside_weight_sum_t)}t。"
    )

    member_max_uc = float(member_summary.get("max_uc", 0.0) or 0.0)
    joint_max_uc = float(joint_summary.get("max_uc", 0.0) or 0.0)
    member_ok = str(member_summary.get("is_pass_text", "")) == "满足" and member_max_uc < 1.0
    joint_ok = str(joint_summary.get("is_pass_text", "")) == "满足" and joint_max_uc < 1.0

    pile_items = [
        pile_axial_capacity_summary.get("operation_compression", {}),
        pile_axial_capacity_summary.get("operation_tension", {}),
        pile_axial_capacity_summary.get("extreme_compression", {}),
        pile_axial_capacity_summary.get("extreme_tension", {}),
    ]
    valid_pile_items = [
        item for item in pile_items if str(item.get("is_pass_text", "")) != "无数据"
    ]
    pile_min_sf = min(
        (float(item.get("min_sf", 0.0) or 0.0) for item in valid_pile_items),
        default=0.0,
    )
    pile_ok = bool(valid_pile_items) and pile_min_sf >= 1.5

    uc_text = "小于1.0" if member_ok and joint_ok else "大于1.0"
    pile_text = "大于1.5" if pile_ok else "小于1.5"

    if member_ok and joint_ok and pile_ok:
        suffix = (
            f"对平台改造后的整体结构进行设计水平强度分析，结果显示所有杆件和节点UC值{uc_text}，"
            f"桩基承载力安全系数{pile_text}，满足规范要求。综合以上结果，认为本次改造可行。"
        )
    else:
        suffix = (
            f"对平台改造后的整体结构进行设计水平强度分析，结果显示所有杆件和节点UC值{uc_text}，"
            f"桩基承载力安全系数{pile_text}，不满足规范要求。综合以上结果，认为本次改造不可行。"
        )
    return prefix + suffix


def _build_platform_evaluation_conclusion_section(
    section_source: Mapping[str, Any] | str | None,
    *,
    member_summary: Mapping[str, Any],
    joint_summary: Mapping[str, Any],
    pile_axial_capacity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    existing_section = dict(section_source) if isinstance(section_source, Mapping) else {}
    conclusion_text = _extract_platform_evaluation_conclusion_text(
        section_source,
        member_summary=member_summary,
        joint_summary=joint_summary,
        pile_axial_capacity_summary=pile_axial_capacity_summary,
    )
    if not conclusion_text:
        return existing_section

    existing_section["mode"] = str(existing_section.get("mode", "replace_region")).strip() or "replace_region"
    existing_section["text"] = conclusion_text
    existing_section["blocks"] = [
        {
            "text": conclusion_text,
            "anchor_prefix": "例子：",
            "anchor_occurrence": 1,
            "preserve_anchor_style": True,
        }
    ]
    return existing_section


def build_analysis_results_for_ui(factor_path: str) -> dict[str, Any]:
    factor_file = Path(factor_path)
    if not factor_file.exists():
        raise FileNotFoundError(
            f"无法读取文件: {factor_file} (exists={factor_file.exists()}, absolute={factor_file.resolve(strict=False)})"
        )

    lines = read_ui_analysis_lines(factor_path)

    member_group_summary = parse_member_group_summary(lines)
    member_summary = build_member_summary(member_group_summary)

    joint_can_summary = parse_joint_can_summary(lines)
    joint_summary = build_joint_can_summary(joint_can_summary)

    pile_group_summary = parse_pile_group_summary(lines)
    pile_summary = build_pile_group_summary(pile_group_summary)

    load_case_status = parse_load_case_status(lines)
    pile_head_forces = parse_pile_head_forces(lines)
    pile_axial_capacity = parse_pile_axial_capacity_summary(lines)
    if pile_head_forces.get("rows"):
        pile_axial_capacity_summary = build_pile_head_capacity_summary(
            pile_head_forces,
            pile_axial_capacity,
            case_type_map=load_case_status.get("case_type_map", {}),
        )
    else:
        pile_axial_capacity_summary = build_pile_axial_capacity_summary(
            pile_axial_capacity,
            case_type_map=load_case_status.get("case_type_map", {}),
        )

    analysis_summary = build_analysis_summary(
        member_summary=member_summary,
        joint_can_summary=joint_summary,
        pile_stress_summary=pile_summary,
        pile_axial_capacity_summary=pile_axial_capacity_summary,
    )

    return {
        "analysis_summary": analysis_summary,
        "member_group_summary": member_group_summary,
        "member_summary": member_summary,
        "joint_can_summary": joint_can_summary,
        "joint_summary": joint_summary,
        "pile_group_summary": pile_group_summary,
        "pile_summary": pile_summary,
        "pile_axial_capacity_summary": pile_axial_capacity_summary,
    }


def generate_report(
    *,
    factor_path: str,
    template_path: str,
    output_path: str,
    chapter_1_3_sources: Mapping[str, Mapping[str, Any] | str] | None = None,
) -> str:
    # 报告联调阶段优先给出更明确的 factor_path 诊断信息，
    # 便于区分“前端传参错误”和“后端进程看不到该文件”两类问题。
    factor_file = Path(factor_path)
    if not factor_file.exists():
        raise FileNotFoundError(
            f"无法读取文件: {factor_file} (exists={factor_file.exists()}, absolute={factor_file.resolve(strict=False)})"
        )

    lines = read_lines(factor_path)

    validate_basic_case_loads_against_desc(lines)
    validate_combo_case_loads_against_desc(lines)

    basic_case_desc_rows = parse_basic_case_desc(lines)
    basic_case_load_rows = parse_basic_case_loads(lines)
    combo_case_desc_rows = parse_combo_case_desc(lines)
    combo_case_load_rows = parse_combo_case_loads(lines)

    analysis_results = build_analysis_results_for_ui(factor_path)
    analysis_summary = analysis_results["analysis_summary"]
    member_group_summary = analysis_results["member_group_summary"]
    member_summary = analysis_results["member_summary"]
    joint_can_summary = analysis_results["joint_can_summary"]
    joint_summary = analysis_results["joint_summary"]
    pile_group_summary = analysis_results["pile_group_summary"]
    pile_summary = analysis_results["pile_summary"]
    pile_axial_capacity_summary = analysis_results["pile_axial_capacity_summary"]

    chapter_1_3_sources_dict = deepcopy(dict(chapter_1_3_sources or {}))
    cover_meta = chapter_1_3_sources_dict.get("cover_meta", {})
    cover_platform_name = ""
    if isinstance(cover_meta, Mapping):
        cover_platform_name = str(cover_meta.get("platform_name") or "").strip()
    try:
        report_date_text = datetime.now().strftime("%Y年%-m月%-d日")
    except ValueError:
        report_date_text = f"{datetime.now().year}年{datetime.now().month}月{datetime.now().day}日"
    platform_evaluation_conclusion_source = chapter_1_3_sources_dict.get("platform_evaluation_conclusion", {})
    platform_evaluation_conclusion_section = _build_platform_evaluation_conclusion_section(
        platform_evaluation_conclusion_source,
        member_summary=member_summary,
        joint_summary=joint_summary,
        pile_axial_capacity_summary=pile_axial_capacity_summary,
    )
    if platform_evaluation_conclusion_section:
        chapter_1_3_sources_dict["platform_evaluation_conclusion"] = platform_evaluation_conclusion_section

    chapter_1_3_context = build_chapter_1_3_context(chapter_1_3_sources_dict)

    docx_output_path = _build_docx_output_path(output_path)
    pdf_output_path = _build_pdf_output_path(output_path)

    rendered_docx_path = render_report_doc(
        template_path=template_path,
        output_path=str(docx_output_path),
        cover_platform_name=cover_platform_name,
        report_date_text=report_date_text,
        analysis_summary=analysis_summary,
        pile_axial_capacity_summary=pile_axial_capacity_summary,
        basic_case_desc_rows=basic_case_desc_rows,
        basic_case_load_rows=basic_case_load_rows,
        combo_case_desc_rows=combo_case_desc_rows,
        combo_case_load_rows=combo_case_load_rows,
        chapter_1_3_context=chapter_1_3_context,
        member_summary=member_summary,
        joint_summary=joint_summary,
        pile_stress_summary=pile_summary,
        member_group_summary=member_group_summary,
        joint_can_summary_result=joint_can_summary,
        pile_group_summary_result=pile_group_summary,
    )
    return convert_docx_to_pdf(rendered_docx_path, pdf_output_path)


def generate_report_with_project_defaults(
    *,
    project_root: str | Path,
    chapter_1_3_sources: Mapping[str, Mapping[str, Any] | str] | None = None,
    factor_path: str | None = None,
    template_path: str | None = None,
    output_path: str | None = None,
) -> str:
    defaults = get_report_defaults()
    if not factor_path:
        raise ValueError("必须传入 factor_path；迁移后的报告模块不再提供 data/psilst.factor 兜底路径。")
    if not output_path:
        raise ValueError("必须传入 output_path；请由用户选择报告保存目录后再生成。")
    return generate_report(
        factor_path=str(factor_path),
        template_path=str(template_path or defaults["template_path"]),
        output_path=str(output_path),
        chapter_1_3_sources=chapter_1_3_sources,
    )
