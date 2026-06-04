# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from feasibility_analysis_services.oilfield_env_service import (
    get_env_profile_id,
    replace_platform_strength_marine_items,
    replace_platform_strength_splash_items,
)
from pages.sacs_import_service import import_model_bundle_to_db
from services.platform_strength_db import save_structure_model_info


def run_quick_assessment_preparation(payload: dict[str, Any]) -> dict[str, Any]:
    """Prepare the strength quick-assessment job without touching Qt widgets."""
    mysql_url = str(payload.get("mysql_url") or "").strip()
    facility_code = str(payload.get("facility_code") or "").strip()
    branch = str(payload.get("branch") or "").strip()
    op_company = str(payload.get("op_company") or "").strip()
    oilfield = str(payload.get("oilfield") or "").strip()
    model_path = str(payload.get("model_path") or "").strip()
    sea_file = str(payload.get("sea_file") or "").strip()
    workpoint = payload.get("workpoint")
    workpoint_m = payload.get("workpoint_m")
    mud_level = payload.get("mud_level")
    level_threshold = int(payload.get("level_threshold") or 40)

    if not mysql_url:
        raise ValueError("数据库连接未配置，无法准备快速评估。")
    if not facility_code:
        raise ValueError("缺少设施编码，无法准备快速评估。")
    if not (branch and op_company and oilfield):
        raise ValueError("缺少分公司/作业公司/油气田信息，无法保存结构强度环境数据。")
    if not model_path:
        raise ValueError("未找到当前设施对应的 sacinp 模型文件，无法打开评估页。")

    profile_id = get_env_profile_id(
        branch=branch,
        op_company=op_company,
        oilfield=oilfield,
        create_if_missing=True,
    )
    if not profile_id:
        raise ValueError("未能创建或获取环境主表记录。")

    replace_platform_strength_splash_items(
        int(profile_id),
        facility_code,
        list(payload.get("splash_items") or []),
        mysql_url=mysql_url,
    )
    replace_platform_strength_marine_items(
        int(profile_id),
        facility_code,
        list(payload.get("marine_items") or []),
        mysql_url=mysql_url,
    )
    save_structure_model_info(
        mysql_url,
        profile_id=int(profile_id),
        facility_code=facility_code,
        mud_level_m=mud_level,
        workpoint_m=workpoint_m,
        level_threshold=level_threshold,
    )

    import_result = import_model_bundle_to_db(
        mysql_url=mysql_url,
        job_name=facility_code,
        model_file=model_path,
        sea_file=sea_file or None,
        workpoint=workpoint,
        level_threshold=level_threshold,
        overwrite_job=True,
    )

    return {
        "job_name": str(import_result.get("job_name") or facility_code),
        "import_result": import_result,
    }
