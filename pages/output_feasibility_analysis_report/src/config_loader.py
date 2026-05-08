from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


DEFAULT_DOC_RENDERER_CONFIG: dict[str, Any] = {
    "table_headers": {
        "analysis_summary": [
            "校核内容",
            "位置",
            "最大UC值/ 最小安全系数",
            "对应工况",
            "是否满足",
        ],
        "pile_capacity": [
            [
                "桩头ID",
                "桩基承载能力(kN)",
                "桩基承载能力(kN)",
                "桩自重 （kN）",
                "设计载荷",
                "设计载荷",
                "设计载荷",
                "设计载荷",
                "安全系数",
                "安全系数",
            ],
            [
                "桩头ID",
                "抗压",
                "抗拔",
                "桩自重 （kN）",
                "工况",
                "压力(kN)",
                "工况",
                "拉力(kN)",
                "抗压",
                "抗拔",
            ],
        ],
        "basic_case_desc": ["序号", "名称", "描述"],
        "basic_case_loads": [
            "工况 名称",
            "FX （kN）",
            "FY （kN）",
            "FZ （kN）",
            "MX （kN.m）",
            "MY （kN.m）",
            "MZ （kN.m）",
            "固定载荷 （kN）",
            "海生物方法浮力 （kN）",
        ],
        "combo_case_desc": ["序号", "名称", "类别", "描述"],
        "combo_case_loads": [
            "序号",
            "工况 名称",
            "FX （kN）",
            "FY （kN）",
            "FZ （kN）",
            "MX （kN.m）",
            "MY （kN.m）",
            "MZ （kN.m）",
        ],
        # 1.2 节“平台历次改造清单如下：”下方表格的表头。
        "retrofit_history_list": ["序号", "改造项目", "年份"],
        "environment_water_level": ["元素", "元素", "相对海图基准面"],
        "environment_wave": [
            ["元素", "元素", "回归周期 (年)", "回归周期 (年)", "回归周期 (年)", "回归周期 (年)", "回归周期 (年)"],
            ["元素", "元素", "1", "10", "25", "50", "100"],
        ],
        "environment_current": [
            ["海流速度（cm/s）", "海流速度（cm/s）", "海流速度（cm/s）", "海流速度（cm/s）", "海流速度（cm/s）", "海流速度（cm/s）", "海流速度（cm/s）"],
            ["元素", "元素", "回归周期 (年)", "回归周期 (年)", "回归周期 (年)", "回归周期 (年)", "回归周期 (年)"],
            ["元素", "元素", "1", "10", "25", "50", "100"],
        ],
        "environment_wind": [
            ["风速 @10m (m/s)", "风速 @10m (m/s)", "风速 @10m (m/s)", "风速 @10m (m/s)", "风速 @10m (m/s)", "风速 @10m (m/s)", "风速 @10m (m/s)"],
            ["元素", "元素", "回归周期 (年)", "回归周期 (年)", "回归周期 (年)", "回归周期 (年)", "回归周期 (年)"],
            ["元素", "元素", "1", "10", "25", "50", "100"],
        ],
        "environment_marine_growth": [
            ["层数", "层数", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
            ["高度区域", "上限(m)", "0", "-15", "-30", "-50", "-60", "-70", "-80", "-95", "-110"],
            ["高度区域", "下限(m)", "-15", "-30", "-50", "-60", "-70", "-80", "-95", "-110", "-122"],
            ["海生物", "厚度（cm)", "10", "10", "10", "4.5", "4.5", "4.5", "4", "4", "4"],
            ["海生物密度(t/m3)", "海生物密度(t/m3)", "1.4", "1.4", "1.4", "1.4", "1.4", "1.4", "1.4", "1.4", "1.4"],
        ],
        "environment_splash_zone": ["飞溅区上限(m)", "飞溅区下限(m)", "腐蚀余量(mm/y)"],
    },
    "paragraph_anchors": {
        "member_summary_title": "构件名义应力校核",
        "joint_summary_title": "节点冲剪应力校核",
        "pile_summary_title": "桩基承载力及桩应力校核",
        "raw_block_placeholder": "（以下内容来自结果文件读取）",
        "pile_extreme_label": "极端风暴工况：",
        "pile_operation_label": "操作工况：",
        "pile_capacity_conclusion_prefix": "从以上结果可知：",
        "pile_stress_prefix": "桩应力UC",
        "pile_raw_block_prefix": "* * P I L E",
    },
    "chapter_paragraphs": {
        "platform_overview": {
            "title": "平台概况",
            "body_mode": "replace_region",
            "end_title": "改造历史",
            "replace_anchor_prefix": "例子：",
        },
        "retrofit_history": {
            "title": "改造历史",
            "body_mode": "replace_region",
            "end_title": "平台的评估结论",
            "replace_anchor_prefix": "例子：",
        },
        "platform_evaluation_conclusion": {
            "title": "平台的评估结论",
            "body_mode": "replace_region",
            "end_title": "基础数据",
            "replace_anchor_prefix": "例子：",
        },
        "basis_data": {
            "title": "基础数据",
            "body_mode": "replace_region",
            "end_title": "载荷变化",
        },
        "load_information": {
            "title": "载荷变化",
            "body_mode": "replace_region",
            "end_title": "环境条件",
        },
        "environment_conditions": {
            "title": "环境条件",
            "body_mode": "replace_region",
            "end_title": "分析模型",
        },
        "analysis_model": {
            "title": "分析模型",
            "body_mode": "replace_region",
            "end_title": "构件名义应力校核",
        },
    },
    "styles": {
        "raw_block_font_size_pt": 7,
    },
    "render_plans": {
        "analysis_summary_doc": ["analysis_summary_table"],
        "section_45_3_doc": [
            "analysis_summary_table",
            "pile_capacity_tables",
            "summary_paragraphs_45",
        ],
        "report_doc": [
            "chapters_1_3",
            "retrofit_history_list_table",
            "load_information_table",
            "environment_conditions_tables",
            "tables_43",
            "tables_44",
            "analysis_summary_table",
            "pile_capacity_tables",
            "summary_paragraphs_45",
            "raw_blocks_45",
        ],
    },
}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _config_path() -> Path:
    return _project_root() / "config" / "doc_renderer.xml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
            continue
        merged[key] = value
    return merged


@lru_cache(maxsize=1)
def load_doc_renderer_config() -> dict[str, Any]:
    config = deepcopy(DEFAULT_DOC_RENDERER_CONFIG)
    path = _config_path()
    if not path.exists():
        return config

    tree = ET.parse(path)
    root = tree.getroot()
    loaded = {
        "table_headers": _parse_table_headers(root.find("table_headers")),
        "paragraph_anchors": _parse_key_value_section(root.find("paragraph_anchors")),
        "chapter_paragraphs": _parse_nested_key_value_section(root.find("chapter_paragraphs")),
        "styles": _parse_styles(root.find("styles")),
        "render_plans": _parse_render_plans(root.find("render_plans")),
    }

    return _deep_merge(config, loaded)


def _parse_table_headers(element: ET.Element | None) -> dict[str, Any]:
    if element is None:
        return {}

    parsed: dict[str, Any] = {}
    for child in element:
        rows = child.findall("row")
        if rows:
            parsed[child.tag] = [[item.text or "" for item in row.findall("item")] for row in rows]
            continue
        parsed[child.tag] = [item.text or "" for item in child.findall("item")]
    return parsed


def _parse_key_value_section(element: ET.Element | None) -> dict[str, str]:
    if element is None:
        return {}
    return {child.tag: child.text or "" for child in element}


def _parse_styles(element: ET.Element | None) -> dict[str, Any]:
    raw_styles = _parse_key_value_section(element)
    parsed: dict[str, Any] = {}
    for key, value in raw_styles.items():
        if value.isdigit():
            parsed[key] = int(value)
            continue
        parsed[key] = value
    return parsed


def _parse_nested_key_value_section(element: ET.Element | None) -> dict[str, dict[str, str]]:
    if element is None:
        return {}

    parsed: dict[str, dict[str, str]] = {}
    for child in element:
        parsed[child.tag] = {grandchild.tag: grandchild.text or "" for grandchild in child}
    return parsed


def _parse_render_plans(element: ET.Element | None) -> dict[str, list[str]]:
    if element is None:
        return {}

    plans: dict[str, list[str]] = {}
    for child in element:
        plans[child.tag] = [item.text or "" for item in child.findall("section")]
    return plans
