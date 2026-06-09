from __future__ import annotations

from typing import Any

from services.inspection_business_db_adapter import (
    list_inspection_findings,
    list_inspection_projects,
)

"""
特检策略“查看历史”点位叠加数据服务。

最新需求：
- 不再写死“第一次检测 / 第二次检测”的节点；
- 直接根据“检测记录文件”中的数据库记录绘制；
- 数据来源包含：
    1. 定期检测（periodic）
    2. 特殊事件检测（special_event）
- 每个检测项目使用一种独立颜色；
- 图例要明确说明“颜色 -> 对应哪次/哪类检测”；
- 轮廓图保持原样，彩色圆点仅用于标识检测节点。
"""


ROUND_COLOR_PALETTE = [
    "#E74C3C",  # 红
    "#2D9CDB",  # 蓝
    "#27AE60",  # 绿
    "#F2994A",  # 橙
    "#9B51E0",  # 紫
    "#00A896",  # 青绿
    "#D35400",  # 深橙
    "#34495E",  # 深灰蓝
    "#E91E63",  # 洋红
    "#1ABC9C",  # 绿松石
    "#8E44AD",  # 深紫
    "#16A085",  # 蓝绿
    "#C0392B",  # 深红
    "#2980B9",  # 深蓝
    "#F1C40F",  # 黄
    "#7F8C8D",  # 灰
]

PROJECT_TYPE_LABELS = {
    "periodic": "定期检测",
    "special_event": "特殊事件检测",
}


def _txt(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_level(value: Any) -> str:
    return (
        _txt(value)
        .upper()
        .replace("Ⅰ", "I")
        .replace("Ⅱ", "II")
        .replace("Ⅲ", "III")
        .replace("Ⅳ", "IV")
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        text = _txt(value)
        return int(text) if text else default
    except Exception:
        return default


def _normalize_joint_id(value: Any) -> str:
    """
    将检测记录中的节点号规范化。

    说明：
    - 检测记录表中“节点号”通常就是 item_code；
    - 有些用户可能会输入额外空格，这里统一去掉前后空白；
    - SACS 节点号大小写通常不敏感，这里统一转大写；
    """
    return _txt(value).replace("　", " ").strip().upper()


def _project_sort_key(project: dict[str, Any]) -> tuple[int, int, int, int]:
    """
    排序规则：
    1. 先按检测类别：定期检测 -> 特殊事件检测
    2. 再按 sort_order
    3. 再按年份
    4. 最后按 id

    这样可与左侧“检测记录文件”的分类习惯保持一致。
    """
    project_type = _txt(project.get("project_type"))
    type_order = 0 if project_type == "periodic" else 1
    sort_order = _safe_int(project.get("sort_order"), 0)
    year_value = _safe_int(project.get("project_year"), 0)
    project_id = _safe_int(project.get("id"), 0)
    return type_order, sort_order, year_value, project_id


def _build_round_label(project: dict[str, Any]) -> str:
    """
    图例显示文本。
    例如：
    - 定期检测：第五年检测（2021）
    - 特殊事件检测：1111（2025）
    """
    project_type = _txt(project.get("project_type"))
    type_label = PROJECT_TYPE_LABELS.get(project_type, project_type or "检测")
    project_name = _txt(project.get("project_name")) or "未命名检测"
    project_year = _txt(project.get("project_year"))

    if project_year:
        return f"{type_label}：{project_name}（{project_year}）"
    return f"{type_label}：{project_name}"


def _empty_result(code: str, *, run_id: int | None = None, source: str = "inspection_db") -> dict[str, Any]:
    return {
        "facility_code": code,
        "run_id": run_id,
        "source": source,
        "items": [],
        "legend": [],
        "debug": {
            "source": source,
            "facility_code": code,
            "run_id": run_id,
            "round_count": 0,
            "item_count": 0,
            "project_count": 0,
        },
    }


def load_history_detection_overlay(
    facility_code: str,
    *,
    run_id: int | None = None,
    include_special_event: bool = True,  # 为兼容旧调用保留；当前默认同时加载两类检测
) -> dict[str, Any]:
    """
    从“检测记录文件”的数据库中读取检测项目及检测节点，生成右侧模型预览所需的叠加数据。

    返回结构与 SpecialInspectionModelPreviewPanel / SpecialInspectionSacsView 的使用方式保持一致：
    - items: 需要叠加到模型上的所有检测节点
    - legend: 图例，说明每种颜色对应哪次检测
    - debug: 调试信息
    """
    code = _txt(facility_code)
    if not code:
        return _empty_result(code, run_id=run_id, source="inspection_db_empty")

    project_types = ["periodic"]
    if include_special_event:
        project_types.append("special_event")

    all_projects: list[dict[str, Any]] = []
    for project_type in project_types:
        try:
            rows = list_inspection_projects(
                facility_code=code,
                project_type=project_type,
            ) or []
        except Exception as exc:
            print(
                "[HistoryOverlay] list_inspection_projects failed:",
                f"facility={code}",
                f"type={project_type}",
                f"error={exc}",
            )
            rows = []
        all_projects.extend(rows)

    if not all_projects:
        print("[HistoryOverlay] no inspection projects found:", code)
        return _empty_result(code, run_id=run_id, source="inspection_db_empty")

    all_projects = sorted(all_projects, key=_project_sort_key)

    items: list[dict[str, Any]] = []
    legend: list[dict[str, Any]] = []
    skipped_projects: list[dict[str, Any]] = []

    round_index = 0
    for project in all_projects:
        project_id = _safe_int(project.get("id"), 0)
        if project_id <= 0:
            skipped_projects.append({
                "project": project,
                "reason": "invalid_project_id",
            })
            continue

        try:
            findings = list_inspection_findings(project_id) or []
        except Exception as exc:
            print(
                "[HistoryOverlay] list_inspection_findings failed:",
                f"facility={code}",
                f"project_id={project_id}",
                f"error={exc}",
            )
            skipped_projects.append({
                "project_id": project_id,
                "reason": f"findings_load_failed: {exc}",
            })
            continue

        # 只保留真正有节点号的数据
        valid_rows: list[dict[str, Any]] = []
        seen_joint_ids: set[str] = set()
        for row in findings:
            joint_id = _normalize_joint_id(
                row.get("item_code")
                or row.get("joint_id")
                or row.get("节点号")
                or row.get("node")
            )
            if not joint_id:
                continue

            # 同一个检测项目内，如果同一节点重复出现，只保留一次
            if joint_id in seen_joint_ids:
                continue
            seen_joint_ids.add(joint_id)

            valid_rows.append(row)

        if not valid_rows:
            skipped_projects.append({
                "project_id": project_id,
                "reason": "no_valid_joint_ids",
            })
            continue

        round_index += 1
        color = ROUND_COLOR_PALETTE[(round_index - 1) % len(ROUND_COLOR_PALETTE)]
        round_label = _build_round_label(project)

        legend.append({
            "round_index": round_index,
            "project_id": project_id,
            "project_type": _txt(project.get("project_type")),
            "project_name": _txt(project.get("project_name")),
            "project_year": _txt(project.get("project_year")),
            "round_label": round_label,
            "round_color": color,
            "count": len(valid_rows),
        })

        for offset_index, row in enumerate(valid_rows):
            joint_id = _normalize_joint_id(
                row.get("item_code")
                or row.get("joint_id")
                or row.get("节点号")
                or row.get("node")
            )
            if not joint_id:
                continue

            items.append({
                "round_index": round_index,
                "project_id": project_id,
                "project_type": _txt(project.get("project_type")),
                "project_name": _txt(project.get("project_name")),
                "project_year": _txt(project.get("project_year")),
                "round_label": round_label,
                "round_color": color,
                "joint_id": joint_id,
                "inspect_level": _normalize_level(
                    row.get("risk_level")
                    or row.get("inspect_level")
                    or row.get("检验等级")
                ),
                "conclusion": _txt(
                    row.get("conclusion")
                    or row.get("检验结论")
                ),
                "offset_index": offset_index,
            })

    debug = {
        "source": "inspection_db",
        "facility_code": code,
        "run_id": run_id,
        "project_count": len(all_projects),
        "round_count": len(legend),
        "item_count": len(items),
        "round_labels": [entry.get("round_label") for entry in legend],
        "skipped_projects": skipped_projects,
    }

    print(
        "[HistoryOverlay] source=inspection_db",
        f"facility={code}",
        f"projects={len(all_projects)}",
        f"rounds={len(legend)}",
        f"items={len(items)}",
    )

    return {
        "facility_code": code,
        "run_id": run_id,
        "source": "inspection_db",
        "items": items,
        "legend": legend,
        "debug": debug,
    }