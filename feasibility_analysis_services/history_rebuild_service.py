from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from shiyou_db.runtime_db import get_mysql_url


# 当前先把页面里的演示数据沉淀到 service 层，
# 这样既可以用于初始化数据库，也方便后续直接替换成数据库读取结果。
DEFAULT_HISTORY_REBUILD_DATA: dict[str, dict[str, list[dict[str, Any]]]] = {
    "历史改造信息": {
        "projects": [
            {
                "index": 1,
                "facility_code": "WC19-1WHPC",
                "facility_name": "文昌19-1WHPC井口平台",
                "name": "WC19-1WHPC平台增加调压井改造",
                "year": "2009年",
                "conclusion": "完成井口流程和局部结构补强校核后，新增调压井改造满足运行要求，可按现状继续使用。",
                "files": [
                    {"name": "调压井改造方案说明书.pdf", "type": "PDF", "updated": "2009-06-18", "note": "方案版"},
                    {"name": "调压井结构校核报告.docx", "type": "Word", "updated": "2009-06-24", "note": "校核结论"},
                    {"name": "调压井改造总图.dwg", "type": "CAD", "updated": "2009-06-25", "note": "施工图"},
                ],
            },
            {
                "index": 2,
                "facility_code": "WC19-1WHPC",
                "facility_name": "文昌19-1WHPC井口平台",
                "name": "WC19-1油田产能释放改造",
                "year": "2016年",
                "conclusion": "经复核，上部组块荷载增长在可控范围内，配套加固后满足产能释放改造需求。",
                "files": [
                    {"name": "产能释放改造请示.pdf", "type": "PDF", "updated": "2016-03-08", "note": "立项材料"},
                    {"name": "产能释放新增设备清单.xlsx", "type": "Excel", "updated": "2016-03-12", "note": "设备统计"},
                    {"name": "产能释放结构复核报告.pdf", "type": "PDF", "updated": "2016-03-28", "note": "复核报告"},
                ],
            },
            {
                "index": 3,
                "facility_code": "WC19-1WHPC",
                "facility_name": "文昌19-1WHPC井口平台",
                "name": "WC19-1详细设计项目旧平台结构改造",
                "year": "2011年",
                "conclusion": "原平台结构经补强设计后可承接新增模块荷载，施工条件和后续运行条件均满足要求。",
                "files": [
                    {"name": "旧平台结构改造设计说明.docx", "type": "Word", "updated": "2011-04-16", "note": "设计说明"},
                    {"name": "旧平台节点补强详图.dwg", "type": "CAD", "updated": "2011-04-18", "note": "详图文件"},
                    {"name": "旧平台结构改造计算书.pdf", "type": "PDF", "updated": "2011-04-20", "note": "计算成果"},
                ],
            },
            {
                "index": 4,
                "facility_code": "WC19-1WHPC",
                "facility_name": "文昌19-1WHPC井口平台",
                "name": "WC19-1平台增加救生筏和逃生软梯安装甲板",
                "year": "2016年",
                "conclusion": "新增逃生设施对应的局部甲板和支撑构件校核通过，改造后安全疏散能力得到提升。",
                "files": [
                    {"name": "救生设施改造布置图.pdf", "type": "PDF", "updated": "2016-09-02", "note": "布置图"},
                    {"name": "逃生软梯安装方案.docx", "type": "Word", "updated": "2016-09-06", "note": "施工方案"},
                    {"name": "甲板补强复核单.xlsx", "type": "Excel", "updated": "2016-09-08", "note": "校核记录"},
                ],
            },
            {
                "index": 5,
                "facility_code": "WC19-1WHPC",
                "facility_name": "文昌19-1WHPC井口平台",
                "name": "WC19-1平台A3井增加放空管线",
                "year": "2011年",
                "conclusion": "新增放空管线对现有平台整体影响较小，完成支架优化后可满足长期运行要求。",
                "files": [
                    {"name": "A3井放空管线改造图.dwg", "type": "CAD", "updated": "2011-11-10", "note": "施工图"},
                    {"name": "放空管线材料统计表.xlsx", "type": "Excel", "updated": "2011-11-12", "note": "材料表"},
                    {"name": "放空管线改造总结.pdf", "type": "PDF", "updated": "2011-11-20", "note": "总结材料"},
                ],
            },
        ]
    },
    "特检延寿": {
        "projects": [
            {
                "index": 1,
                "facility_code": "WC19-1WHPC",
                "facility_name": "文昌19-1WHPC井口平台",
                "name": "平台特检延寿评估项目",
                "year": "2022年",
                "conclusion": "结合近年检测和校核结果，平台延寿条件基本具备，建议按整改闭环后进入延寿实施阶段。",
                "files": [
                    {"name": "特检延寿评估报告.pdf", "type": "PDF", "updated": "2022-05-16", "note": "评估结论"},
                    {"name": "延寿整改项清单.xlsx", "type": "Excel", "updated": "2022-05-18", "note": "整改项"},
                ],
            }
        ]
    },
    "特殊事件检测（台风、碰撞等）": {
        "projects": [
            {
                "index": 1,
                "facility_code": "WC19-1WHPC",
                "facility_name": "文昌19-1WHPC井口平台",
                "name": "台风后损伤复核项目",
                "year": "2020年",
                "conclusion": "本次台风造成局部附属构件受损，主体结构未见明显失效，完成修复后可恢复正常生产。",
                "files": [
                    {"name": "台风后巡检记录.pdf", "type": "PDF", "updated": "2020-08-23", "note": "巡检记录"},
                    {"name": "损伤修复方案.docx", "type": "Word", "updated": "2020-08-25", "note": "修复方案"},
                ],
            }
        ]
    },
}


def _default_mysql_url() -> str:
    return get_mysql_url().strip()


def _build_database_url(database_name: str | None = None, mysql_url: str | None = None) -> URL:
    raw_url = (mysql_url or _default_mysql_url()).strip()
    if not raw_url:
        raise ValueError("主业务数据库连接未配置")
    url = make_url(raw_url)
    if database_name:
        return url.set(database=database_name)
    return url


def _build_server_url(mysql_url: str | None = None) -> URL:
    # 先连到 MySQL 服务级别，再创建 history_rebuild_info 数据库。
    raw_url = (mysql_url or _default_mysql_url()).strip()
    if not raw_url:
        raise ValueError("主业务数据库连接未配置")
    url = make_url(raw_url)
    return url.set(database=None)


def ensure_history_rebuild_schema(mysql_url: str | None = None, database_name: str | None = None) -> None:
    # 这一层先把当前业务库里的两张业务表建好：
    # 1) project 表存改造项目主信息
    # 2) file 表存项目关联文件
    db_engine = create_engine(_build_database_url(database_name, mysql_url), future=True, pool_pre_ping=True)
    with db_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS history_rebuild_projects (
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    facility_code VARCHAR(64) NOT NULL,
                    facility_name VARCHAR(255) NOT NULL DEFAULT '',
                    folder_name VARCHAR(128) NOT NULL,
                    project_order INT NOT NULL DEFAULT 0,
                    project_name VARCHAR(255) NOT NULL,
                    project_year VARCHAR(32) NOT NULL DEFAULT '',
                    conclusion_text TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_history_project (facility_code, folder_name, project_name, project_year)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS history_rebuild_project_files (
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    project_id BIGINT NOT NULL,
                    file_order INT NOT NULL DEFAULT 0,
                    file_name VARCHAR(255) NOT NULL,
                    file_type VARCHAR(64) NOT NULL DEFAULT '',
                    updated_text VARCHAR(64) NOT NULL DEFAULT '',
                    note_text VARCHAR(255) NOT NULL DEFAULT '',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_project_file (project_id, file_name),
                    CONSTRAINT fk_history_project_files_project
                        FOREIGN KEY (project_id) REFERENCES history_rebuild_projects (id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )


def seed_history_rebuild_demo_data(mysql_url: str | None = None, database_name: str | None = None) -> int:
    # 当前先把页面里已有的演示数据落库；后续数据库接入真实数据后，
    # 这里可以替换成初始化脚本或迁移脚本。
    ensure_history_rebuild_schema(mysql_url=mysql_url, database_name=database_name)
    engine = create_engine(_build_database_url(database_name, mysql_url), future=True, pool_pre_ping=True)
    inserted_projects = 0

    with engine.begin() as conn:
        for folder_name, folder_data in DEFAULT_HISTORY_REBUILD_DATA.items():
            for project in folder_data.get("projects", []):
                conn.execute(
                    text(
                        """
                        INSERT INTO history_rebuild_projects (
                            facility_code, facility_name, folder_name, project_order,
                            project_name, project_year, conclusion_text
                        ) VALUES (
                            :facility_code, :facility_name, :folder_name, :project_order,
                            :project_name, :project_year, :conclusion_text
                        )
                        ON DUPLICATE KEY UPDATE
                            facility_name = VALUES(facility_name),
                            project_order = VALUES(project_order),
                            conclusion_text = VALUES(conclusion_text)
                        """
                    ),
                    {
                        "facility_code": project.get("facility_code", ""),
                        "facility_name": project.get("facility_name", ""),
                        "folder_name": folder_name,
                        "project_order": int(project.get("index", 0) or 0),
                        "project_name": project.get("name", ""),
                        "project_year": project.get("year", ""),
                        "conclusion_text": project.get("conclusion", ""),
                    },
                )
                project_id = conn.execute(
                    text(
                        """
                        SELECT id FROM history_rebuild_projects
                        WHERE facility_code = :facility_code
                          AND folder_name = :folder_name
                          AND project_name = :project_name
                          AND project_year = :project_year
                        """
                    ),
                    {
                        "facility_code": project.get("facility_code", ""),
                        "folder_name": folder_name,
                        "project_name": project.get("name", ""),
                        "project_year": project.get("year", ""),
                    },
                ).scalar_one()

                conn.execute(
                    text("DELETE FROM history_rebuild_project_files WHERE project_id = :project_id"),
                    {"project_id": project_id},
                )
                for file_order, file_info in enumerate(project.get("files", []), start=1):
                    conn.execute(
                        text(
                            """
                            INSERT INTO history_rebuild_project_files (
                                project_id, file_order, file_name, file_type, updated_text, note_text
                            ) VALUES (
                                :project_id, :file_order, :file_name, :file_type, :updated_text, :note_text
                            )
                            """
                        ),
                        {
                            "project_id": project_id,
                            "file_order": file_order,
                            "file_name": file_info.get("name", ""),
                            "file_type": file_info.get("type", ""),
                            "updated_text": file_info.get("updated", ""),
                            "note_text": file_info.get("note", ""),
                        },
                    )
                inserted_projects += 1

    return inserted_projects


def get_history_rebuild_projects(
    facility_code: str,
    *,
    folder_name: str = "历史改造信息",
    mysql_url: str | None = None,
    database_name: str | None = None,
) -> list[dict[str, Any]]:
    # 预留给页面和报告的统一读取接口：
    # - 有数据库记录时优先读库
    # - 暂无记录时回退到当前占位数据
    engine = create_engine(_build_database_url(database_name, mysql_url), future=True, pool_pre_ping=True)
    projects: list[dict[str, Any]] = []
    try:
        with engine.connect() as conn:
            project_rows = conn.execute(
                text(
                    """
                    SELECT id, project_order, project_name, project_year, conclusion_text, facility_name
                    FROM history_rebuild_projects
                    WHERE facility_code = :facility_code AND folder_name = :folder_name
                    ORDER BY project_order ASC, id ASC
                    """
                ),
                {"facility_code": facility_code, "folder_name": folder_name},
            ).mappings().all()
            if not project_rows:
                return _fallback_projects(facility_code, folder_name)

            files_by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
            file_rows = conn.execute(
                text(
                    """
                    SELECT project_id, file_order, file_name, file_type, updated_text, note_text
                    FROM history_rebuild_project_files
                    WHERE project_id IN (
                        SELECT id FROM history_rebuild_projects
                        WHERE facility_code = :facility_code AND folder_name = :folder_name
                    )
                    ORDER BY project_id ASC, file_order ASC, id ASC
                    """
                ),
                {"facility_code": facility_code, "folder_name": folder_name},
            ).mappings().all()
            for row in file_rows:
                files_by_project[int(row["project_id"])] .append(
                    {
                        "name": row["file_name"],
                        "type": row["file_type"],
                        "updated": row["updated_text"],
                        "note": row["note_text"],
                    }
                )

            for row in project_rows:
                project_id = int(row["id"])
                projects.append(
                    {
                        "index": int(row["project_order"] or 0),
                        "facility_code": facility_code,
                        "facility_name": row["facility_name"] or "",
                        "name": row["project_name"] or "",
                        "year": row["project_year"] or "",
                        "conclusion": row["conclusion_text"] or "",
                        "files": files_by_project.get(project_id, []),
                    }
                )
            return projects
    except Exception:
        return _fallback_projects(facility_code, folder_name)


def build_history_rebuild_summary(
    facility_code: str,
    *,
    folder_name: str = "历史改造信息",
    mysql_url: str | None = None,
    database_name: str | None = None,
) -> str:
    # 报告中使用的格式固定为“年份+结论；年份+结论……”。
    projects = get_history_rebuild_projects(
        facility_code,
        folder_name=folder_name,
        mysql_url=mysql_url,
        database_name=database_name,
    )
    fragments = []
    for project in projects:
        year = str(project.get("year", "")).strip()
        conclusion = str(project.get("conclusion", "")).strip().rstrip("；;。")
        if not conclusion:
            continue
        fragments.append(f"{year}{conclusion}" if year else conclusion)
    if not fragments:
        return ""
    return "；".join(fragments) + "。"


def _fallback_projects(facility_code: str, folder_name: str) -> list[dict[str, Any]]:
    # 数据库未初始化或未命中时回退到当前占位数据，保证页面和报告都不断链。
    folder_data = DEFAULT_HISTORY_REBUILD_DATA.get(folder_name, {"projects": []})
    matched = [
        project
        for project in folder_data.get("projects", [])
        if str(project.get("facility_code", "")).strip() == facility_code.strip()
    ]
    if matched:
        return matched
    return folder_data.get("projects", [])
