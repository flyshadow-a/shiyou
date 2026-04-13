# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

from sqlalchemy import create_engine, text


XY_TOL = 1e-6
Z_TOL = 1e-6


@dataclass
class Joint:
    joint_id: str
    x: float
    y: float
    z: float


@dataclass
class Leg:
    leg_no: int
    joint_id: str
    x: float
    y: float
    z: float


@dataclass
class Level:
    level_no: int
    z: float
    occurrence: int
    selected: int


@dataclass
class TopsideWeight:
    weight_no: int
    x: float
    y: float
    z: float
    weight_t: float


def ensure_tables(engine) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS topside_weight_leg_loads (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        job_name VARCHAR(100) NOT NULL,
        weight_no INT NOT NULL,
        leg_no INT NOT NULL,
        source_x DOUBLE NULL,
        source_y DOUBLE NULL,
        source_z DOUBLE NULL,
        source_weight_t DOUBLE NULL,
        used_level_z DOUBLE NULL,
        joint_id VARCHAR(20) NOT NULL,
        joint_x DOUBLE NULL,
        joint_y DOUBLE NULL,
        joint_z DOUBLE NULL,
        f_uniform DOUBLE NULL,
        f_moment_y DOUBLE NULL,
        f_moment_x DOUBLE NULL,
        leg_load DOUBLE NULL,
        KEY idx_twll_job_weight (job_name, weight_no),
        KEY idx_twll_job_joint (job_name, joint_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


def delete_old_results(conn, job_name: str) -> None:
    conn.execute(
        text("DELETE FROM topside_weight_leg_loads WHERE job_name = :job_name"),
        {"job_name": job_name}
    )


def fetch_workpoint(conn, job_name: str) -> float:
    sql = text("""
        SELECT workpoint
        FROM wizard_model_info
        WHERE job_name = :job_name
        ORDER BY id DESC
        LIMIT 1
    """)
    row = conn.execute(sql, {"job_name": job_name}).mappings().first()
    if row is None or row["workpoint"] is None:
        raise ValueError(f"wizard_model_info 中找不到 job={job_name} 的 workpoint")
    return float(row["workpoint"])


def fetch_selected_levels(conn, job_name: str) -> List[Level]:
    sql = text("""
        SELECT level_no, z, occurrence, selected
        FROM wizard_levels
        WHERE job_name = :job_name
          AND selected = 1
        ORDER BY level_no
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()
    result = []
    for r in rows:
        if r["z"] is None:
            continue
        result.append(
            Level(
                level_no=int(r["level_no"]),
                z=float(r["z"]),
                occurrence=int(r["occurrence"]) if r["occurrence"] is not None else 0,
                selected=int(r["selected"]) if r["selected"] is not None else 0,
            )
        )
    return result


def fetch_legs(conn, job_name: str) -> List[Leg]:
    sql = text("""
        SELECT leg_no, joint_id, x, y, z
        FROM wizard_legs
        WHERE job_name = :job_name
        ORDER BY leg_no
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()
    result = []
    for r in rows:
        result.append(
            Leg(
                leg_no=int(r["leg_no"]),
                joint_id=str(r["joint_id"]),
                x=float(r["x"]),
                y=float(r["y"]),
                z=float(r["z"]),
            )
        )
    return result


def fetch_joints(conn, job_name: str) -> List[Joint]:
    sql = text("""
        SELECT joint_id, x, y, z
        FROM joints
        WHERE job_name = :job_name
          AND x IS NOT NULL
          AND y IS NOT NULL
          AND z IS NOT NULL
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()
    result = []
    for r in rows:
        result.append(
            Joint(
                joint_id=str(r["joint_id"]),
                x=float(r["x"]),
                y=float(r["y"]),
                z=float(r["z"]),
            )
        )
    return result


def fetch_topside_weights(conn, job_name: str) -> List[TopsideWeight]:
    sql = text("""
        SELECT weight_no, x, y, z, weight_t
        FROM topside_weights
        WHERE job_name = :job_name
        ORDER BY weight_no
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()
    result = []
    for r in rows:
        if r["x"] is None or r["y"] is None or r["z"] is None or r["weight_t"] is None:
            continue
        result.append(
            TopsideWeight(
                weight_no=int(r["weight_no"]),
                x=float(r["x"]),
                y=float(r["y"]),
                z=float(r["z"]),
                weight_t=float(r["weight_t"]),
            )
        )
    return result


def choose_used_level_z(weight_z: float, selected_levels: List[Level], workpoint: float) -> float:
    lower_levels = [lv.z for lv in selected_levels if lv.z < weight_z]
    if lower_levels:
        used_level = max(lower_levels)
    else:
        used_level = workpoint

    if used_level < workpoint:
        used_level = workpoint
    return used_level


def find_leg_joint_on_level(
    leg: Leg,
    joints: List[Joint],
    used_level_z: float,
    xy_tol: float = XY_TOL,
    z_tol: float = Z_TOL,
) -> Joint:
    same_leg_same_level = [
        j for j in joints
        if abs(j.z - used_level_z) <= z_tol
        and abs(j.x - leg.x) <= xy_tol
        and abs(j.y - leg.y) <= xy_tol
    ]
    if same_leg_same_level:
        return same_leg_same_level[0]

    same_level = [j for j in joints if abs(j.z - used_level_z) <= z_tol]
    if same_level:
        return min(same_level, key=lambda j: (j.x - leg.x) ** 2 + (j.y - leg.y) ** 2)

    unique_z = sorted(set(j.z for j in joints))
    if not unique_z:
        raise ValueError("joints 表为空，无法寻找主腿对应节点")

    nearest_z = min(unique_z, key=lambda z: abs(z - used_level_z))
    nearest_level = [j for j in joints if abs(j.z - nearest_z) <= z_tol]
    if not nearest_level:
        raise ValueError(f"找不到 used_level_z={used_level_z} 对应的主腿节点")

    print(f"[WARN] used_level_z={used_level_z} 没有对应 joint，自动改用最近层 z={nearest_z}")
    return min(nearest_level, key=lambda j: (j.x - leg.x) ** 2 + (j.y - leg.y) ** 2)


def transform_one_topside_weight(
    weight: TopsideWeight,
    selected_levels: List[Level],
    workpoint: float,
    legs: List[Leg],
    joints: List[Joint],
) -> List[Dict[str, Any]]:
    if not legs:
        raise ValueError("wizard_legs 中没有主腿数据")

    used_level_z = choose_used_level_z(weight.z, selected_levels, workpoint)

    leg_joints: List[tuple[Leg, Joint]] = []
    for leg in legs:
        joint = find_leg_joint_on_level(leg, joints, used_level_z)
        leg_joints.append((leg, joint))

    n = len(leg_joints)
    xs = [j.x for _, j in leg_joints]
    ys = [j.y for _, j in leg_joints]

    xc = sum(xs) / n
    yc = sum(ys) / n

    ex = weight.x - xc
    ey = weight.y - yc

    uniform = weight.weight_t / n

    sum_dx2 = sum((x - xc) ** 2 for x in xs)
    sum_dy2 = sum((y - yc) ** 2 for y in ys)

    moment_y_total = weight.weight_t * ex
    moment_x_total = weight.weight_t * ey

    rows: List[Dict[str, Any]] = []
    for leg, joint in leg_joints:
        dx = joint.x - xc
        dy = joint.y - yc

        f_moment_y = 0.0 if abs(sum_dx2) < 1e-12 else moment_y_total * dx / sum_dx2
        f_moment_x = 0.0 if abs(sum_dy2) < 1e-12 else moment_x_total * dy / sum_dy2

        leg_load = uniform + f_moment_y + f_moment_x

        rows.append(
            {
                "weight_no": weight.weight_no,
                "leg_no": leg.leg_no,
                "source_x": weight.x,
                "source_y": weight.y,
                "source_z": weight.z,
                "source_weight_t": weight.weight_t,
                "used_level_z": used_level_z,
                "joint_id": joint.joint_id,
                "joint_x": joint.x,
                "joint_y": joint.y,
                "joint_z": joint.z,
                "f_uniform": uniform,
                "f_moment_y": f_moment_y,
                "f_moment_x": f_moment_x,
                "leg_load": leg_load,
            }
        )

    return rows


def insert_results(conn, job_name: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    sql = text("""
        INSERT INTO topside_weight_leg_loads (
            job_name, weight_no, leg_no,
            source_x, source_y, source_z, source_weight_t,
            used_level_z,
            joint_id, joint_x, joint_y, joint_z,
            f_uniform, f_moment_y, f_moment_x, leg_load
        ) VALUES (
            :job_name, :weight_no, :leg_no,
            :source_x, :source_y, :source_z, :source_weight_t,
            :used_level_z,
            :joint_id, :joint_x, :joint_y, :joint_z,
            :f_uniform, :f_moment_y, :f_moment_x, :leg_load
        )
    """)

    payload = [{"job_name": job_name, **r} for r in rows]
    conn.execute(sql, payload)


def transform_topside_weights_to_db(mysql_url: str, job_name: str, overwrite_job: bool = True) -> dict:
    engine = create_engine(mysql_url, future=True, pool_pre_ping=True)
    ensure_tables(engine)

    with engine.begin() as conn:
        workpoint = fetch_workpoint(conn, job_name)
        levels = fetch_selected_levels(conn, job_name)
        legs = fetch_legs(conn, job_name)
        joints = fetch_joints(conn, job_name)
        weights = fetch_topside_weights(conn, job_name)

        if not levels:
            raise ValueError(f"job={job_name} 在 wizard_levels 中没有 selected=1 的水平层")
        if not legs:
            raise ValueError(f"job={job_name} 在 wizard_legs 中没有主腿数据")
        if not weights:
            raise ValueError(f"job={job_name} 在 topside_weights 中没有组块重量数据")

        if overwrite_job:
            delete_old_results(conn, job_name)

        all_rows: List[Dict[str, Any]] = []
        for w in weights:
            rows = transform_one_topside_weight(
                weight=w,
                selected_levels=levels,
                workpoint=workpoint,
                legs=legs,
                joints=joints,
            )
            all_rows.extend(rows)

        insert_results(conn, job_name, all_rows)

    return {
        "job_name": job_name,
        "workpoint": workpoint,
        "selected_levels": len(levels),
        "main_legs": len(legs),
        "topside_weights": len(weights),
        "output_rows": len(all_rows),
    }