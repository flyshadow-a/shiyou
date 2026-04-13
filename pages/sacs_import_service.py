# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text


# =========================
# 通用工具
# =========================
def read_text_lines(file_path: str) -> List[str]:
    encodings = ["utf-8", "gbk", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc, errors="strict") as f:
                return f.readlines()
        except Exception:
            continue
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def substr(line: str, start_1_based: int, length: int) -> str:
    start = start_1_based - 1
    return line[start:start + length]


def to_float_or_none(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def parse_coord(line: str, main_start: int, cm_start: int) -> Optional[float]:
    """
    按你原 VBA 逻辑读取坐标：
    X = Mid(a, 12, 7) + Mid(a, 33, 7)/100
    Y = Mid(a, 19, 7) + Mid(a, 40, 7)/100
    Z = Mid(a, 26, 7) + Mid(a, 47, 7)/100
    """
    main_val = to_float_or_none(substr(line, main_start, 7))
    if main_val is None:
        return None

    cm_val = to_float_or_none(substr(line, cm_start, 7))
    if cm_val is not None:
        main_val = main_val + cm_val / 100.0

    return main_val


def insert_many(conn, table_name: str, columns: List[str], rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    col_sql = ", ".join(columns)
    val_sql = ", ".join([f":{c}" for c in columns])
    sql = text(f"INSERT INTO {table_name} ({col_sql}) VALUES ({val_sql})")
    conn.execute(sql, rows)


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


# =========================
# 建表：基础模型表
# =========================
def ensure_model_tables(engine) -> None:
    ddl_list = [
        """
        CREATE TABLE IF NOT EXISTS joints (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            joint_id VARCHAR(20) NOT NULL,
            x DOUBLE NULL,
            y DOUBLE NULL,
            z DOUBLE NULL,
            mark VARCHAR(50) NULL,
            KEY idx_joints_job_joint (job_name, joint_id),
            KEY idx_joints_job_z (job_name, z)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS members (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            joint_a VARCHAR(20) NOT NULL,
            joint_b VARCHAR(20) NOT NULL,
            group_id VARCHAR(20) NULL,
            mark VARCHAR(50) NULL,
            KEY idx_members_job_a (job_name, joint_a),
            KEY idx_members_job_b (job_name, joint_b),
            KEY idx_members_job_group (job_name, group_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS sacs_groups (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            group_id VARCHAR(20) NOT NULL,
            od DOUBLE NULL,
            mark VARCHAR(50) NULL,
            KEY idx_groups_job_group (job_name, group_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS load_cases (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            load_case VARCHAR(20) NOT NULL,
            load_type VARCHAR(20) NULL,
            mark VARCHAR(50) NULL,
            KEY idx_loadcases_job_case (job_name, load_case)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS wizard_model_info (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            model_file TEXT NULL,
            sea_file TEXT NULL,
            new_model_file TEXT NULL,
            new_sea_file TEXT NULL,
            mudline DOUBLE NULL,
            workpoint DOUBLE NULL,
            autorun_file TEXT NULL,
            KEY idx_model_info_job (job_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS wizard_levels (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            level_no INT NOT NULL,
            z DOUBLE NULL,
            occurrence INT NULL,
            selected TINYINT(1) NULL,
            KEY idx_levels_job_z (job_name, z)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS wizard_legs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            leg_no INT NOT NULL,
            joint_id VARCHAR(20) NOT NULL,
            x DOUBLE NULL,
            y DOUBLE NULL,
            z DOUBLE NULL,
            KEY idx_legs_job_joint (job_name, joint_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS leg_candidates (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            candidate_no INT NOT NULL,
            joint_id VARCHAR(20) NOT NULL,
            x DOUBLE NULL,
            y DOUBLE NULL,
            z DOUBLE NULL,
            max_od DOUBLE NULL,
            KEY idx_leg_candidates_job_joint (job_name, joint_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    ]

    with engine.begin() as conn:
        for ddl in ddl_list:
            conn.execute(text(ddl))


def delete_model_job_data(conn, job_name: str) -> None:
    tables = [
        "wizard_legs",
        "leg_candidates",
        "wizard_levels",
        "wizard_model_info",
        "load_cases",
        "members",
        "joints",
        "sacs_groups",
    ]
    for table_name in tables:
        conn.execute(
            text(f"DELETE FROM {table_name} WHERE job_name = :job_name"),
            {"job_name": job_name}
        )


# =========================
# 建表：dummy 禁连节点表
# =========================
def ensure_dummy_table(engine) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS forbidden_target_joints (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        job_name VARCHAR(100) NOT NULL,
        dummy_name VARCHAR(100) NULL,
        joint_id VARCHAR(20) NOT NULL,
        source_line TEXT NULL,
        reason VARCHAR(200) NULL,
        KEY idx_ftj_job_joint (job_name, joint_id),
        KEY idx_ftj_job_dummy (job_name, dummy_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def delete_dummy_rows(conn, job_name: str) -> None:
    conn.execute(
        text("DELETE FROM forbidden_target_joints WHERE job_name = :job_name"),
        {"job_name": job_name}
    )


# =========================
# 解析原模型文件
# =========================
def parse_model_file(model_file: str, job_name: str) -> Tuple[
    Optional[float], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]
]:
    lines = read_text_lines(model_file)

    mudline = None
    joints: List[Dict[str, Any]] = []
    members: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    load_cases: List[Dict[str, Any]] = []

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")

        if line.startswith("LDOPT"):
            v = to_float_or_none(substr(line, 33, 9))
            if v is not None:
                mudline = v

        if line.startswith("GRUP"):
            group_id = substr(line, 6, 3).strip()
            if group_id:
                od = to_float_or_none(substr(line, 18, 6))
                groups.append(
                    {
                        "job_name": job_name,
                        "group_id": group_id,
                        "od": od,
                        "mark": "In Model",
                    }
                )

        if line.startswith("MEMBER"):
            chunk8 = substr(line, 8, 8).strip()
            chunk7 = substr(line, 8, 7).strip()
            if chunk8 and chunk7 != "OFFSETS":
                members.append(
                    {
                        "job_name": job_name,
                        "joint_a": substr(line, 8, 4).strip(),
                        "joint_b": substr(line, 12, 4).strip(),
                        "group_id": substr(line, 17, 3).strip(),
                        "mark": "In Model",
                    }
                )

        if line.startswith("JOINT"):
            chunk8 = substr(line, 8, 8).strip()
            chunk7 = substr(line, 8, 7).strip()
            if chunk8 and chunk7 != "OFFSETS":
                joints.append(
                    {
                        "job_name": job_name,
                        "joint_id": substr(line, 7, 4).strip(),
                        "x": parse_coord(line, 12, 33),
                        "y": parse_coord(line, 19, 40),
                        "z": parse_coord(line, 26, 47),
                        "mark": "In Model",
                    }
                )

        if line.startswith("LOADCN"):
            lc = substr(line, 7, 4).strip()
            if lc:
                load_cases.append(
                    {
                        "job_name": job_name,
                        "load_case": lc,
                        "load_type": "Basic",
                        "mark": "In Model",
                    }
                )

        if line.startswith("LCOMB"):
            lc = substr(line, 7, 4).strip()
            if lc:
                load_cases.append(
                    {
                        "job_name": job_name,
                        "load_case": lc,
                        "load_type": "Combined",
                        "mark": "In Model",
                    }
                )

    return mudline, joints, members, groups, load_cases


def parse_sea_file(sea_file: str, job_name: str) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    lines = read_text_lines(sea_file)

    mudline = None
    load_cases: List[Dict[str, Any]] = []

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")

        if line.startswith("LDOPT"):
            v = to_float_or_none(substr(line, 33, 9))
            if v is not None:
                mudline = v

        if line.startswith("LOADCN"):
            lc = substr(line, 7, 4).strip()
            if lc:
                load_cases.append(
                    {
                        "job_name": job_name,
                        "load_case": lc,
                        "load_type": "Basic",
                        "mark": "In Seainp",
                    }
                )

        if line.startswith("LCOMB"):
            lc = substr(line, 7, 4).strip()
            if lc:
                load_cases.append(
                    {
                        "job_name": job_name,
                        "load_case": lc,
                        "load_type": "Combined",
                        "mark": "In Seainp",
                    }
                )

    return mudline, load_cases


# =========================
# 水平层 / 主腿识别
# =========================
def detect_levels(joints: List[Dict[str, Any]], threshold: int) -> List[Dict[str, Any]]:
    counter = Counter()

    for j in joints:
        z = j["z"]
        if z is not None:
            counter[z] += 1

    selected_levels = [(z, occ) for z, occ in counter.items() if occ > threshold]
    selected_levels.sort(key=lambda x: x[0], reverse=True)

    rows = []
    for idx, (z, occ) in enumerate(selected_levels, start=1):
        rows.append(
            {
                "level_no": idx,
                "z": z,
                "occurrence": occ,
                "selected": 1,
            }
        )
    return rows


def detect_main_legs(
    joints: List[Dict[str, Any]],
    members: List[Dict[str, Any]],
    groups: List[Dict[str, Any]],
    workpoint: float,
    tol: float = 1e-6
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    group_od: Dict[str, float] = {}
    for g in groups:
        gid = g["group_id"]
        od = g["od"]
        if gid and od is not None and gid not in group_od:
            group_od[gid] = od

    joint_member_groups: Dict[str, List[str]] = defaultdict(list)
    for m in members:
        a = m["joint_a"]
        b = m["joint_b"]
        gid = m["group_id"]
        if a:
            joint_member_groups[a].append(gid)
        if b:
            joint_member_groups[b].append(gid)

    candidates: List[Dict[str, Any]] = []
    candidate_no = 0

    for j in joints:
        z = j["z"]
        if z is None:
            continue

        if abs(z - workpoint) <= tol:
            joint_id = j["joint_id"]
            related_group_ids = joint_member_groups.get(joint_id, [])
            ods = [group_od[g] for g in related_group_ids if g in group_od]

            if not ods:
                continue

            candidate_no += 1
            candidates.append(
                {
                    "candidate_no": candidate_no,
                    "joint_id": joint_id,
                    "x": j["x"],
                    "y": j["y"],
                    "z": j["z"],
                    "max_od": max(ods),
                }
            )

    if not candidates:
        return [], []

    global_max_od = max(c["max_od"] for c in candidates)

    legs: List[Dict[str, Any]] = []
    leg_no = 0
    for c in candidates:
        if abs(c["max_od"] - global_max_od) <= tol:
            leg_no += 1
            legs.append(
                {
                    "leg_no": leg_no,
                    "joint_id": c["joint_id"],
                    "x": c["x"],
                    "y": c["y"],
                    "z": c["z"],
                }
            )

    return candidates, legs


# =========================
# 解析 dummy block
# =========================
def parse_dummy_delete_joints(model_file: str, job_name: str) -> List[Dict[str, Any]]:
    lines = read_text_lines(model_file)

    results: List[Dict[str, Any]] = []

    in_dummy_block = False
    current_dummy_name: Optional[str] = None

    for raw in lines:
        line = raw.rstrip("\r\n")
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("*") or stripped.startswith("//") or stripped.startswith("Rem "):
            continue

        if stripped.startswith("DUMMY "):
            in_dummy_block = True
            current_dummy_name = stripped
            continue

        if in_dummy_block:
            upper = stripped.upper()

            if upper.startswith("KEEP "):
                continue

            if upper.startswith("DELETE "):
                tokens = stripped.split()
                joint_ids = tokens[1:]
                for jid in joint_ids:
                    results.append(
                        {
                            "job_name": job_name,
                            "dummy_name": current_dummy_name,
                            "joint_id": jid.strip(),
                            "source_line": normalize_spaces(stripped),
                            "reason": "Appears in DELETE line under DUMMY block",
                        }
                    )
                continue

            in_dummy_block = False
            current_dummy_name = None

    dedup: Dict[str, Dict[str, Any]] = {}
    for r in results:
        key = f"{r['job_name']}||{r['joint_id']}"
        if key not in dedup:
            dedup[key] = r

    return list(dedup.values())


# =========================
# 对外服务函数
# =========================
def import_sacs_model_to_db(
    mysql_url: str,
    job_name: str,
    model_file: str,
    sea_file: Optional[str] = None,
    workpoint: float = 9.1,
    level_threshold: int = 40,
    overwrite_job: bool = True,
) -> Dict[str, Any]:
    """
    导入原模型文件到数据库：
    - wizard_model_info
    - joints
    - members
    - sacs_groups
    - load_cases
    - wizard_levels
    - leg_candidates
    - wizard_legs
    """
    if not os.path.exists(model_file):
        raise FileNotFoundError(f"找不到 model_file: {model_file}")

    if sea_file and (not os.path.exists(sea_file)):
        raise FileNotFoundError(f"找不到 sea_file: {sea_file}")

    engine = create_engine(mysql_url, future=True, pool_pre_ping=True)
    ensure_model_tables(engine)

    model_mudline, joints, members, groups, model_load_cases = parse_model_file(model_file, job_name)

    sea_mudline = None
    sea_load_cases: List[Dict[str, Any]] = []
    if sea_file:
        sea_mudline, sea_load_cases = parse_sea_file(sea_file, job_name)

    mudline = sea_mudline if sea_mudline is not None else model_mudline

    levels = detect_levels(joints, level_threshold)
    leg_candidates, legs = detect_main_legs(joints, members, groups, workpoint)

    new_model_file = os.path.join(os.path.dirname(model_file), "sacinp.M1")
    new_sea_file = os.path.join(os.path.dirname(sea_file), "seainp.M1") if sea_file else None

    with engine.begin() as conn:
        if overwrite_job:
            delete_model_job_data(conn, job_name)

        insert_many(
            conn,
            "wizard_model_info",
            [
                "job_name",
                "model_file",
                "sea_file",
                "new_model_file",
                "new_sea_file",
                "mudline",
                "workpoint",
                "autorun_file",
            ],
            [
                {
                    "job_name": job_name,
                    "model_file": model_file,
                    "sea_file": sea_file,
                    "new_model_file": new_model_file,
                    "new_sea_file": new_sea_file,
                    "mudline": mudline,
                    "workpoint": workpoint,
                    "autorun_file": None,
                }
            ],
        )

        insert_many(
            conn,
            "joints",
            ["job_name", "joint_id", "x", "y", "z", "mark"],
            joints,
        )

        insert_many(
            conn,
            "members",
            ["job_name", "joint_a", "joint_b", "group_id", "mark"],
            members,
        )

        insert_many(
            conn,
            "sacs_groups",
            ["job_name", "group_id", "od", "mark"],
            groups,
        )

        all_load_cases = model_load_cases + sea_load_cases
        insert_many(
            conn,
            "load_cases",
            ["job_name", "load_case", "load_type", "mark"],
            all_load_cases,
        )

        level_rows = []
        for row in levels:
            level_rows.append(
                {
                    "job_name": job_name,
                    "level_no": row["level_no"],
                    "z": row["z"],
                    "occurrence": row["occurrence"],
                    "selected": row["selected"],
                }
            )

        insert_many(
            conn,
            "wizard_levels",
            ["job_name", "level_no", "z", "occurrence", "selected"],
            level_rows,
        )

        candidate_rows = []
        for row in leg_candidates:
            candidate_rows.append(
                {
                    "job_name": job_name,
                    "candidate_no": row["candidate_no"],
                    "joint_id": row["joint_id"],
                    "x": row["x"],
                    "y": row["y"],
                    "z": row["z"],
                    "max_od": row["max_od"],
                }
            )

        insert_many(
            conn,
            "leg_candidates",
            ["job_name", "candidate_no", "joint_id", "x", "y", "z", "max_od"],
            candidate_rows,
        )

        leg_rows = []
        for row in legs:
            leg_rows.append(
                {
                    "job_name": job_name,
                    "leg_no": row["leg_no"],
                    "joint_id": row["joint_id"],
                    "x": row["x"],
                    "y": row["y"],
                    "z": row["z"],
                }
            )

        insert_many(
            conn,
            "wizard_legs",
            ["job_name", "leg_no", "joint_id", "x", "y", "z"],
            leg_rows,
        )

    return {
        "job_name": job_name,
        "mudline": mudline,
        "workpoint": workpoint,
        "joints": len(joints),
        "members": len(members),
        "groups": len(groups),
        "load_cases": len(model_load_cases) + len(sea_load_cases),
        "levels": len(levels),
        "leg_candidates": len(leg_candidates),
        "main_legs": len(legs),
        "new_model_file": new_model_file,
        "new_sea_file": new_sea_file,
    }


def import_dummy_joints_to_db(
    mysql_url: str,
    job_name: str,
    model_file: str,
    overwrite_job: bool = True,
) -> Dict[str, Any]:
    """
    导入 DUMMY block 中 DELETE 的节点到 forbidden_target_joints
    """
    if not os.path.exists(model_file):
        raise FileNotFoundError(f"找不到 model_file: {model_file}")

    engine = create_engine(mysql_url, future=True, pool_pre_ping=True)
    ensure_dummy_table(engine)

    rows = parse_dummy_delete_joints(model_file, job_name)

    with engine.begin() as conn:
        if overwrite_job:
            delete_dummy_rows(conn, job_name)
        if rows:
            conn.execute(text("""
                INSERT INTO forbidden_target_joints (
                    job_name, dummy_name, joint_id, source_line, reason
                ) VALUES (
                    :job_name, :dummy_name, :joint_id, :source_line, :reason
                )
            """), rows)

    return {
        "job_name": job_name,
        "dummy_joint_count": len(rows),
    }


def import_model_bundle_to_db(
    mysql_url: str,
    job_name: str,
    model_file: str,
    sea_file: Optional[str] = None,
    workpoint: float = 9.1,
    level_threshold: int = 40,
    overwrite_job: bool = True,
) -> Dict[str, Any]:
    """
    一次性导入：
    1. 原模型基础表
    2. dummy 禁连节点表
    """
    result_model = import_sacs_model_to_db(
        mysql_url=mysql_url,
        job_name=job_name,
        model_file=model_file,
        sea_file=sea_file,
        workpoint=workpoint,
        level_threshold=level_threshold,
        overwrite_job=overwrite_job,
    )

    result_dummy = import_dummy_joints_to_db(
        mysql_url=mysql_url,
        job_name=job_name,
        model_file=model_file,
        overwrite_job=overwrite_job,
    )

    merged: Dict[str, Any] = {}
    if result_model:
        merged.update(result_model)
    if result_dummy:
        merged.update(result_dummy)

    if "job_name" not in merged:
        merged["job_name"] = job_name

    return merged
