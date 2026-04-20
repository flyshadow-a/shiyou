from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from shiyou_db.runtime_db import get_mysql_url


def _default_mysql_url() -> str:
    return get_mysql_url().strip()


def _create_mysql_engine(mysql_url: str | None = None):
    raw_url = (mysql_url or _default_mysql_url()).strip()
    if not raw_url:
        raise ValueError("sea_env 数据库连接未配置")
    return create_engine(raw_url, future=True, pool_pre_ping=True)


def ensure_oilfield_env_schema(mysql_url: str | None = None) -> None:
    engine = _create_mysql_engine(mysql_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS oilfield_env_profile (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    branch VARCHAR(100) NOT NULL,
                    op_company VARCHAR(100) NOT NULL,
                    oilfield VARCHAR(100) NOT NULL,
                    version_no INT NOT NULL DEFAULT 1,
                    remark VARCHAR(255) DEFAULT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_oilfield_env_profile (branch, op_company, oilfield, version_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS oilfield_water_level_item (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    profile_id BIGINT NOT NULL,
                    group_name VARCHAR(50) DEFAULT NULL,
                    item_name VARCHAR(100) NOT NULL,
                    value DECIMAL(10, 3) NOT NULL,
                    unit VARCHAR(20) NOT NULL DEFAULT 'm',
                    sort_order INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_water_level_profile (profile_id),
                    KEY idx_water_level_sort (profile_id, sort_order),
                    KEY idx_water_level_group (profile_id, group_name),
                    CONSTRAINT fk_water_level_profile
                        FOREIGN KEY (profile_id) REFERENCES oilfield_env_profile(id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS oilfield_wind_param_item (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    profile_id BIGINT NOT NULL,
                    group_name VARCHAR(100) NOT NULL,
                    item_name VARCHAR(50) NOT NULL,
                    return_period INT NOT NULL,
                    value DECIMAL(10, 3) NOT NULL,
                    unit VARCHAR(20) NOT NULL DEFAULT 'm/s',
                    sort_order INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_wind_profile (profile_id),
                    KEY idx_wind_sort (profile_id, sort_order),
                    KEY idx_wind_group (profile_id, group_name),
                    KEY idx_wind_period (profile_id, return_period),
                    CONSTRAINT fk_wind_param_profile
                        FOREIGN KEY (profile_id) REFERENCES oilfield_env_profile(id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS oilfield_wave_param_item (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    profile_id BIGINT NOT NULL,
                    group_name VARCHAR(100) NOT NULL,
                    item_name VARCHAR(100) NOT NULL,
                    return_period INT NOT NULL,
                    value DECIMAL(10, 3) NOT NULL,
                    unit VARCHAR(20) NOT NULL,
                    sort_order INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_wave_profile (profile_id),
                    KEY idx_wave_sort (profile_id, sort_order),
                    KEY idx_wave_group (profile_id, group_name),
                    KEY idx_wave_period (profile_id, return_period),
                    CONSTRAINT fk_wave_param_profile
                        FOREIGN KEY (profile_id) REFERENCES oilfield_env_profile(id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS oilfield_current_param_item (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    profile_id BIGINT NOT NULL,
                    group_name VARCHAR(100) NOT NULL,
                    item_name VARCHAR(100) NOT NULL,
                    return_period INT NOT NULL,
                    value DECIMAL(10, 3) NOT NULL,
                    unit VARCHAR(20) NOT NULL DEFAULT 'm/s',
                    sort_order INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY idx_current_profile (profile_id),
                    KEY idx_current_sort (profile_id, sort_order),
                    KEY idx_current_group (profile_id, group_name),
                    KEY idx_current_period (profile_id, return_period),
                    CONSTRAINT fk_current_param_profile
                        FOREIGN KEY (profile_id) REFERENCES oilfield_env_profile(id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text_value = str(value).strip()
    if (not text_value) or (text_value.lower() == "nan"):
        return ""
    if text_value.endswith(".0") and text_value[:-2].isdigit():
        return text_value[:-2]
    return text_value


def sync_env_profiles_from_records(
    records: list[dict[str, str]],
    mysql_url: str | None = None,
    version_no: int = 1,
) -> int:
    ensure_oilfield_env_schema(mysql_url)
    cleaned_records: list[dict[str, str]] = []
    seen = set()
    for record in records:
        branch = _normalize_text(record.get("分公司", ""))
        op_company = _normalize_text(record.get("作业公司", ""))
        oilfield = _normalize_text(record.get("油气田", ""))
        if not (branch and op_company and oilfield):
            continue
        signature = (branch, op_company, oilfield, int(version_no))
        if signature in seen:
            continue
        seen.add(signature)
        cleaned_records.append({
            "branch": branch,
            "op_company": op_company,
            "oilfield": oilfield,
            "version_no": int(version_no),
            "remark": "由海洋环境页面顶部下拉数据同步",
        })

    if not cleaned_records:
        return 0

    engine = _create_mysql_engine(mysql_url)
    sql = text(
        """
        INSERT INTO oilfield_env_profile (
            branch, op_company, oilfield, version_no, remark
        ) VALUES (
            :branch, :op_company, :oilfield, :version_no, :remark
        )
        ON DUPLICATE KEY UPDATE
            remark = COALESCE(VALUES(remark), remark),
            updated_at = CURRENT_TIMESTAMP
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, cleaned_records)
    return len(cleaned_records)


def load_env_profiles(mysql_url: str | None = None, version_no: int = 1) -> list[dict[str, str]]:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    sql = text(
        """
        SELECT branch, op_company, oilfield
        FROM oilfield_env_profile
        WHERE version_no = :version_no
        ORDER BY branch, op_company, oilfield
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"version_no": int(version_no)}).mappings().all()
    return [
        {
            "分公司": _normalize_text(row.get("branch", "")),
            "作业公司": _normalize_text(row.get("op_company", "")),
            "油气田": _normalize_text(row.get("oilfield", "")),
        }
        for row in rows
    ]


def upsert_env_profile(
    branch: str,
    op_company: str,
    oilfield: str,
    mysql_url: str | None = None,
    version_no: int = 1,
) -> bool:
    payload = [{
        "分公司": branch,
        "作业公司": op_company,
        "油气田": oilfield,
    }]
    return sync_env_profiles_from_records(payload, mysql_url=mysql_url, version_no=version_no) > 0


def get_env_profile_id(
    branch: str,
    op_company: str,
    oilfield: str,
    mysql_url: str | None = None,
    version_no: int = 1,
    create_if_missing: bool = False,
) -> int | None:
    ensure_oilfield_env_schema(mysql_url)
    norm_branch = _normalize_text(branch)
    norm_op_company = _normalize_text(op_company)
    norm_oilfield = _normalize_text(oilfield)
    if not (norm_branch and norm_op_company and norm_oilfield):
        return None

    if create_if_missing:
        upsert_env_profile(
            branch=norm_branch,
            op_company=norm_op_company,
            oilfield=norm_oilfield,
            mysql_url=mysql_url,
            version_no=version_no,
        )

    engine = _create_mysql_engine(mysql_url)
    sql = text(
        """
        SELECT id
        FROM oilfield_env_profile
        WHERE branch = :branch
          AND op_company = :op_company
          AND oilfield = :oilfield
          AND version_no = :version_no
        LIMIT 1
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "branch": norm_branch,
                "op_company": norm_op_company,
                "oilfield": norm_oilfield,
                "version_no": int(version_no),
            },
        ).first()
    return int(row[0]) if row else None


def load_water_level_items(profile_id: int, mysql_url: str | None = None) -> list[dict[str, Any]]:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    sql = text(
        """
        SELECT group_name, item_name, value, unit, sort_order
        FROM oilfield_water_level_item
        WHERE profile_id = :profile_id
        ORDER BY sort_order, id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"profile_id": int(profile_id)}).mappings().all()
    return [dict(row) for row in rows]


def replace_water_level_items(
    profile_id: int,
    items: list[dict[str, Any]],
    mysql_url: str | None = None,
) -> None:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    delete_sql = text("DELETE FROM oilfield_water_level_item WHERE profile_id = :profile_id")
    insert_sql = text(
        """
        INSERT INTO oilfield_water_level_item (
            profile_id, group_name, item_name, value, unit, sort_order
        ) VALUES (
            :profile_id, :group_name, :item_name, :value, :unit, :sort_order
        )
        """
    )
    payload = []
    for item in items:
        payload.append(
            {
                "profile_id": int(profile_id),
                "group_name": _normalize_text(item.get("group_name", "")) or None,
                "item_name": _normalize_text(item.get("item_name", "")),
                "value": item.get("value"),
                "unit": _normalize_text(item.get("unit", "m")) or "m",
                "sort_order": int(item.get("sort_order", 0) or 0),
            }
        )
    with engine.begin() as conn:
        conn.execute(delete_sql, {"profile_id": int(profile_id)})
        if payload:
            conn.execute(insert_sql, payload)


def load_metric_items(table_name: str, profile_id: int, mysql_url: str | None = None) -> list[dict[str, Any]]:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    sql = text(
        f"""
        SELECT group_name, item_name, return_period, value, unit, sort_order
        FROM {table_name}
        WHERE profile_id = :profile_id
        ORDER BY sort_order, id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(sql, {"profile_id": int(profile_id)}).mappings().all()
    return [dict(row) for row in rows]


def replace_metric_items(
    table_name: str,
    profile_id: int,
    items: list[dict[str, Any]],
    mysql_url: str | None = None,
) -> None:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    delete_sql = text(f"DELETE FROM {table_name} WHERE profile_id = :profile_id")
    insert_sql = text(
        f"""
        INSERT INTO {table_name} (
            profile_id, group_name, item_name, return_period, value, unit, sort_order
        ) VALUES (
            :profile_id, :group_name, :item_name, :return_period, :value, :unit, :sort_order
        )
        """
    )
    payload = []
    for item in items:
        payload.append(
            {
                "profile_id": int(profile_id),
                "group_name": _normalize_text(item.get("group_name", "")),
                "item_name": _normalize_text(item.get("item_name", "")),
                "return_period": int(item.get("return_period", 0) or 0),
                "value": item.get("value"),
                "unit": _normalize_text(item.get("unit", "")),
                "sort_order": int(item.get("sort_order", 0) or 0),
            }
        )
    with engine.begin() as conn:
        conn.execute(delete_sql, {"profile_id": int(profile_id)})
        if payload:
            conn.execute(insert_sql, payload)


def _normalize_facility_code(value: Any) -> str:
    return _normalize_text(value)


def load_platform_strength_splash_items(
    profile_id: int,
    facility_code: str,
    mysql_url: str | None = None,
) -> list[dict[str, Any]]:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    sql = text(
        """
        SELECT upper_limit_m, lower_limit_m, corrosion_allowance_mm_per_y, sort_order
        FROM platform_strength_splash_zone_item
        WHERE profile_id = :profile_id AND facility_code = :facility_code
        ORDER BY sort_order, id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(
            sql,
            {
                "profile_id": int(profile_id),
                "facility_code": _normalize_facility_code(facility_code),
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def replace_platform_strength_splash_items(
    profile_id: int,
    facility_code: str,
    items: list[dict[str, Any]],
    mysql_url: str | None = None,
) -> None:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    delete_sql = text(
        """
        DELETE FROM platform_strength_splash_zone_item
        WHERE profile_id = :profile_id AND facility_code = :facility_code
        """
    )
    insert_sql = text(
        """
        INSERT INTO platform_strength_splash_zone_item (
            profile_id, facility_code, upper_limit_m, lower_limit_m,
            corrosion_allowance_mm_per_y, sort_order
        ) VALUES (
            :profile_id, :facility_code, :upper_limit_m, :lower_limit_m,
            :corrosion_allowance_mm_per_y, :sort_order
        )
        """
    )
    normalized_facility_code = _normalize_facility_code(facility_code)
    payload = [
        {
            "profile_id": int(profile_id),
            "facility_code": normalized_facility_code,
            "upper_limit_m": item.get("upper_limit_m"),
            "lower_limit_m": item.get("lower_limit_m"),
            "corrosion_allowance_mm_per_y": item.get("corrosion_allowance_mm_per_y"),
            "sort_order": int(item.get("sort_order", 0) or 0),
        }
        for item in items
    ]
    with engine.begin() as conn:
        conn.execute(
            delete_sql,
            {"profile_id": int(profile_id), "facility_code": normalized_facility_code},
        )
        if payload:
            conn.execute(insert_sql, payload)


def load_platform_strength_pile_items(
    profile_id: int,
    facility_code: str,
    mysql_url: str | None = None,
) -> list[dict[str, Any]]:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    sql = text(
        """
        SELECT scour_depth_m, compressive_capacity_t, uplift_capacity_t, submerged_weight_t, sort_order
        FROM platform_strength_pile_info_item
        WHERE profile_id = :profile_id AND facility_code = :facility_code
        ORDER BY sort_order, id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(
            sql,
            {
                "profile_id": int(profile_id),
                "facility_code": _normalize_facility_code(facility_code),
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def replace_platform_strength_pile_items(
    profile_id: int,
    facility_code: str,
    items: list[dict[str, Any]],
    mysql_url: str | None = None,
) -> None:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    delete_sql = text(
        """
        DELETE FROM platform_strength_pile_info_item
        WHERE profile_id = :profile_id AND facility_code = :facility_code
        """
    )
    insert_sql = text(
        """
        INSERT INTO platform_strength_pile_info_item (
            profile_id, facility_code, scour_depth_m, compressive_capacity_t,
            uplift_capacity_t, submerged_weight_t, sort_order
        ) VALUES (
            :profile_id, :facility_code, :scour_depth_m, :compressive_capacity_t,
            :uplift_capacity_t, :submerged_weight_t, :sort_order
        )
        """
    )
    normalized_facility_code = _normalize_facility_code(facility_code)
    payload = [
        {
            "profile_id": int(profile_id),
            "facility_code": normalized_facility_code,
            "scour_depth_m": item.get("scour_depth_m"),
            "compressive_capacity_t": item.get("compressive_capacity_t"),
            "uplift_capacity_t": item.get("uplift_capacity_t"),
            "submerged_weight_t": item.get("submerged_weight_t"),
            "sort_order": int(item.get("sort_order", 0) or 0),
        }
        for item in items
    ]
    with engine.begin() as conn:
        conn.execute(
            delete_sql,
            {"profile_id": int(profile_id), "facility_code": normalized_facility_code},
        )
        if payload:
            conn.execute(insert_sql, payload)


def load_platform_strength_marine_items(
    profile_id: int,
    facility_code: str,
    mysql_url: str | None = None,
) -> list[dict[str, Any]]:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    sql = text(
        """
        SELECT layer_no, upper_limit_m, lower_limit_m, thickness_mm, density_t_per_m3, sort_order
        FROM platform_strength_marine_growth_item
        WHERE profile_id = :profile_id AND facility_code = :facility_code
        ORDER BY sort_order, id
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(
            sql,
            {
                "profile_id": int(profile_id),
                "facility_code": _normalize_facility_code(facility_code),
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def replace_platform_strength_marine_items(
    profile_id: int,
    facility_code: str,
    items: list[dict[str, Any]],
    mysql_url: str | None = None,
) -> None:
    ensure_oilfield_env_schema(mysql_url)
    engine = _create_mysql_engine(mysql_url)
    delete_sql = text(
        """
        DELETE FROM platform_strength_marine_growth_item
        WHERE profile_id = :profile_id AND facility_code = :facility_code
        """
    )
    insert_sql = text(
        """
        INSERT INTO platform_strength_marine_growth_item (
            profile_id, facility_code, layer_no, upper_limit_m,
            lower_limit_m, thickness_mm, density_t_per_m3, sort_order
        ) VALUES (
            :profile_id, :facility_code, :layer_no, :upper_limit_m,
            :lower_limit_m, :thickness_mm, :density_t_per_m3, :sort_order
        )
        """
    )
    normalized_facility_code = _normalize_facility_code(facility_code)
    payload = [
        {
            "profile_id": int(profile_id),
            "facility_code": normalized_facility_code,
            "layer_no": int(item.get("layer_no", 0) or 0),
            "upper_limit_m": item.get("upper_limit_m"),
            "lower_limit_m": item.get("lower_limit_m"),
            "thickness_mm": item.get("thickness_mm"),
            "density_t_per_m3": item.get("density_t_per_m3"),
            "sort_order": int(item.get("sort_order", 0) or 0),
        }
        for item in items
    ]
    with engine.begin() as conn:
        conn.execute(
            delete_sql,
            {"profile_id": int(profile_id), "facility_code": normalized_facility_code},
        )
        if payload:
            conn.execute(insert_sql, payload)
