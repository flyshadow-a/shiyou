from __future__ import annotations

from typing import Any


"""
特检策略“查看历史”点位叠加数据服务。

当前需求：
- 不再从检测记录表/历史项目表中读取点位；
- 直接按照用户指定的第 N 次检测节点清单，在同一张原模型轮廓图上叠加显示；
- 不同检测次数使用不同颜色；
- 轮廓图本身仍保持黑色，彩色圆点只用于标识指定检测节点。

如果后续需要新增第三次、第四次检测，只需要继续在 HISTORY_DETECTION_ROUNDS
中追加一组配置即可。
"""


ROUND_COLOR_PALETTE = [
    "#E74C3C",  # 第一次：红色
    "#2D9CDB",  # 第二次：蓝色
    "#27AE60",  # 第三次：绿色
    "#F2994A",  # 第四次：橙色
    "#9B51E0",  # 第五次：紫色
    "#00A896",  # 第六次：青绿色
    "#D35400",  # 第七次：深橙色
    "#34495E",  # 第八次：深灰蓝
]


HISTORY_DETECTION_ROUNDS: list[dict[str, Any]] = [
    {
        "round_label": "第一次检测",
        "color": ROUND_COLOR_PALETTE[0],
        "points": [
            {"joint_id": "301L", "inspect_level": "II", "conclusion": "正常无损伤"},
            {"joint_id": "411X", "inspect_level": "III", "conclusion": "正常无损伤"},
            {"joint_id": "208L", "inspect_level": "II", "conclusion": "正常无损伤"},
            {"joint_id": "507L", "inspect_level": "II", "conclusion": "正常无损伤"},
            {"joint_id": "331X", "inspect_level": "III", "conclusion": "正常无损伤"},
            {"joint_id": "504L", "inspect_level": "II", "conclusion": "正常无损伤"},
        ],
    },
    {
        "round_label": "第二次检测",
        "color": ROUND_COLOR_PALETTE[1],
        "points": [
            {"joint_id": "305L", "inspect_level": "II", "conclusion": "正常无损伤"},
            {"joint_id": "202L", "inspect_level": "III", "conclusion": "正常无损伤"},
            {"joint_id": "112X", "inspect_level": "II", "conclusion": "正常无损伤"},
            {"joint_id": "308L", "inspect_level": "II", "conclusion": "正常无损伤"},
            {"joint_id": "541X", "inspect_level": "III", "conclusion": "正常无损伤"},
            {"joint_id": "401L", "inspect_level": "II", "conclusion": "正常无损伤"},
        ],
    },
]


def _txt(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_level(value: Any) -> str:
    return _txt(value).upper().replace("Ⅱ", "II").replace("Ⅲ", "III").replace("Ⅳ", "IV")


def load_history_detection_overlay(
    facility_code: str,
    *,
    run_id: int | None = None,
    include_special_event: bool = False,  # 兼容旧调用参数，本功能不使用
) -> dict[str, Any]:
    """返回“查看历史”所需的固定检测点叠加数据。

    返回结构与 SacsElevationRiskView.set_history_overlay 保持一致：
    - items: 所有需要标注的节点点位；
    - legend: 图例，说明颜色对应第几次检测；
    - debug: 调试信息。

    注意：这里仅提供“要标注哪些节点”。真正能否在当前立面/平面中显示，
    取决于当前轮廓图的可见节点集合。例如某个节点如果不在当前 XY 层面，
    它不会出现在这张 XY 图上；切换到包含该节点的立面/平面后即可显示。
    """
    code = _txt(facility_code)

    items: list[dict[str, Any]] = []
    legend: list[dict[str, Any]] = []

    for round_index, round_cfg in enumerate(HISTORY_DETECTION_ROUNDS, start=1):
        round_label = _txt(round_cfg.get("round_label")) or f"第{round_index}次检测"
        color = _txt(round_cfg.get("color")) or ROUND_COLOR_PALETTE[(round_index - 1) % len(ROUND_COLOR_PALETTE)]
        points = list(round_cfg.get("points") or [])

        legend.append({
            "round_index": round_index,
            "round_label": round_label,
            "round_color": color,
            "count": len(points),
        })

        for offset_index, point in enumerate(points):
            joint_id = _txt(point.get("joint_id") or point.get("节点号"))
            if not joint_id:
                continue

            items.append({
                "round_index": round_index,
                "round_label": round_label,
                "round_color": color,
                "joint_id": joint_id,
                "inspect_level": _normalize_level(point.get("inspect_level") or point.get("检验等级")),
                "conclusion": _txt(point.get("conclusion") or point.get("检验结论")),
                "offset_index": offset_index,
            })

    debug = {
        "source": "hardcoded_points",
        "facility_code": code,
        "run_id": run_id,
        "round_count": len(legend),
        "item_count": len(items),
        "round_labels": [entry.get("round_label") for entry in legend],
    }

    print(
        "[HistoryOverlay] source=hardcoded_points",
        "facility=", code,
        "rounds=", len(legend),
        "items=", len(items),
    )

    return {
        "facility_code": code,
        "run_id": run_id,
        "source": "hardcoded_points",
        "items": items,
        "legend": legend,
        "debug": debug,
    }
