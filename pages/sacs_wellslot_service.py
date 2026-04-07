# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set

from sqlalchemy import create_engine, text


Z_TOL = 1e-6


@dataclass
class ExistingJoint:
    joint_id: str
    x: float
    y: float
    z: float


@dataclass
class WellSlotConfig:
    slot_no: int
    x: float
    y: float
    conductor_od: float
    conductor_wt: float
    support_od: float
    support_wt: float
    top_load_fz: Optional[float]


@dataclass
class SlotConnection:
    slot_no: int
    level_z: float
    connection_type: str


@dataclass
class NewGroup:
    group_id: str
    group_type: str
    od_mm: float
    wt_mm: float
    od_cm: float
    wt_cm: float
    slot_no: int
    sequence_no: int


@dataclass
class NewJoint:
    joint_id: str
    x: float
    y: float
    z: float
    fixity: Optional[str]
    joint_kind: str
    slot_no: int
    sequence_no: int


@dataclass
class NewMember:
    joint_a: str
    joint_b: str
    group_id: str
    offset_ax_mm: float
    offset_ay_mm: float
    offset_az_mm: float
    offset_bx_mm: float
    offset_by_mm: float
    offset_bz_mm: float
    member_kind: str
    connection_type: Optional[str]
    slot_no: int
    sequence_no: int


def increment_prefix(prefix: str) -> str:
    if len(prefix) == 1:
        return chr(ord(prefix) + 1)
    return prefix[:-1] + chr(ord(prefix[-1]) + 1)


class IdGenerator:
    def __init__(self, used_ids: Set[str]) -> None:
        self.used_ids = used_ids

    def get_available(self, prefix: str, width: int = 4) -> str:
        if width <= len(prefix):
            raise ValueError(f"width={width} 必须大于 prefix 长度 {len(prefix)}")

        current_prefix = prefix
        num_len = width - len(current_prefix)

        while True:
            max_num_exclusive = 10 ** num_len
            for i in range(1, max_num_exclusive):
                candidate = f"{current_prefix}{i:0{num_len}d}"
                if candidate not in self.used_ids:
                    self.used_ids.add(candidate)
                    return candidate

            current_prefix = increment_prefix(current_prefix)
            num_len = width - len(current_prefix)
            if num_len <= 0:
                raise ValueError(f"prefix 递增后长度异常，当前 prefix={current_prefix}")


def ensure_tables(engine) -> None:
    ddl_list = [
        """
        CREATE TABLE IF NOT EXISTS new_groups (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            group_id VARCHAR(20) NOT NULL,
            group_type VARCHAR(30) NOT NULL,
            od_mm DOUBLE NULL,
            wt_mm DOUBLE NULL,
            od_cm DOUBLE NULL,
            wt_cm DOUBLE NULL,
            slot_no INT NOT NULL,
            sequence_no INT NOT NULL,
            mark VARCHAR(50) NULL,
            KEY idx_ng_job_group (job_name, group_id),
            KEY idx_ng_job_slot (job_name, slot_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS new_joints (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            joint_id VARCHAR(20) NOT NULL,
            x DOUBLE NULL,
            y DOUBLE NULL,
            z DOUBLE NULL,
            fixity VARCHAR(20) NULL,
            joint_kind VARCHAR(30) NOT NULL,
            slot_no INT NOT NULL,
            sequence_no INT NOT NULL,
            mark VARCHAR(50) NULL,
            KEY idx_nj_job_joint (job_name, joint_id),
            KEY idx_nj_job_slot (job_name, slot_no),
            KEY idx_nj_job_z (job_name, z)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,
        """
        CREATE TABLE IF NOT EXISTS new_members (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_name VARCHAR(100) NOT NULL,
            joint_a VARCHAR(20) NOT NULL,
            joint_b VARCHAR(20) NOT NULL,
            group_id VARCHAR(20) NOT NULL,
            offset_ax_mm DOUBLE NULL,
            offset_ay_mm DOUBLE NULL,
            offset_az_mm DOUBLE NULL,
            offset_bx_mm DOUBLE NULL,
            offset_by_mm DOUBLE NULL,
            offset_bz_mm DOUBLE NULL,
            member_kind VARCHAR(30) NOT NULL,
            connection_type VARCHAR(50) NULL,
            slot_no INT NOT NULL,
            sequence_no INT NOT NULL,
            mark VARCHAR(50) NULL,
            KEY idx_nm_job_slot (job_name, slot_no),
            KEY idx_nm_job_group (job_name, group_id),
            KEY idx_nm_job_a (job_name, joint_a),
            KEY idx_nm_job_b (job_name, joint_b)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    ]

    with engine.begin() as conn:
        for ddl in ddl_list:
            conn.execute(text(ddl))


def delete_old_results(conn, job_name: str) -> None:
    for table_name in ["new_members", "new_joints", "new_groups"]:
        conn.execute(
            text(f"DELETE FROM {table_name} WHERE job_name = :job_name"),
            {"job_name": job_name}
        )


def fetch_mudline(conn, job_name: str) -> float:
    sql = text("""
        SELECT mudline
        FROM wizard_model_info
        WHERE job_name = :job_name
        ORDER BY id DESC
        LIMIT 1
    """)
    row = conn.execute(sql, {"job_name": job_name}).mappings().first()
    if row is None or row["mudline"] is None:
        raise ValueError(f"wizard_model_info 中找不到 job={job_name} 的 mudline")
    return float(row["mudline"])


def fetch_forbidden_joint_ids(conn, job_name: str) -> Set[str]:
    sql = text("""
        SELECT joint_id
        FROM forbidden_target_joints
        WHERE job_name = :job_name
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()
    return {str(r["joint_id"]).strip() for r in rows if r["joint_id"] is not None}


def fetch_existing_joints(conn, job_name: str, forbidden_ids: Set[str]) -> List[ExistingJoint]:
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
        joint_id = str(r["joint_id"]).strip()
        if joint_id in forbidden_ids:
            continue
        result.append(
            ExistingJoint(
                joint_id=joint_id,
                x=float(r["x"]),
                y=float(r["y"]),
                z=float(r["z"]),
            )
        )
    return result


def fetch_existing_group_ids(conn, job_name: str) -> Set[str]:
    group_ids: Set[str] = set()

    rows1 = conn.execute(
        text("SELECT group_id FROM sacs_groups WHERE job_name = :job_name"),
        {"job_name": job_name}
    ).mappings().all()
    for r in rows1:
        if r["group_id"] is not None:
            group_ids.add(str(r["group_id"]))

    rows2 = conn.execute(
        text("SELECT group_id FROM new_groups WHERE job_name = :job_name"),
        {"job_name": job_name}
    ).mappings().all()
    for r in rows2:
        if r["group_id"] is not None:
            group_ids.add(str(r["group_id"]))

    return group_ids


def fetch_existing_joint_ids(conn, job_name: str) -> Set[str]:
    joint_ids: Set[str] = set()

    rows1 = conn.execute(
        text("SELECT joint_id FROM joints WHERE job_name = :job_name"),
        {"job_name": job_name}
    ).mappings().all()
    for r in rows1:
        if r["joint_id"] is not None:
            joint_ids.add(str(r["joint_id"]))

    rows2 = conn.execute(
        text("SELECT joint_id FROM new_joints WHERE job_name = :job_name"),
        {"job_name": job_name}
    ).mappings().all()
    for r in rows2:
        if r["joint_id"] is not None:
            joint_ids.add(str(r["joint_id"]))

    return joint_ids


def fetch_well_slots(conn, job_name: str) -> List[WellSlotConfig]:
    sql = text("""
        SELECT
            slot_no, x, y,
            conductor_od, conductor_wt,
            support_od, support_wt,
            top_load_fz
        FROM well_slots
        WHERE job_name = :job_name
        ORDER BY slot_no
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()

    result = []
    for r in rows:
        if r["x"] is None or r["y"] is None:
            continue
        result.append(
            WellSlotConfig(
                slot_no=int(r["slot_no"]),
                x=float(r["x"]),
                y=float(r["y"]),
                conductor_od=float(r["conductor_od"]),
                conductor_wt=float(r["conductor_wt"]),
                support_od=float(r["support_od"]),
                support_wt=float(r["support_wt"]),
                top_load_fz=float(r["top_load_fz"]) if r["top_load_fz"] is not None else None,
            )
        )
    return result


def fetch_well_slot_connections(conn, job_name: str) -> Dict[int, List[SlotConnection]]:
    sql = text("""
        SELECT slot_no, level_z, connection_type
        FROM well_slot_connections
        WHERE job_name = :job_name
        ORDER BY slot_no, level_z
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()

    result: Dict[int, List[SlotConnection]] = {}
    for r in rows:
        if r["level_z"] is None or r["connection_type"] is None:
            continue

        slot_no = int(r["slot_no"])
        result.setdefault(slot_no, []).append(
            SlotConnection(
                slot_no=slot_no,
                level_z=float(r["level_z"]),
                connection_type=str(r["connection_type"]).strip(),
            )
        )

    for slot_no in result:
        result[slot_no].sort(key=lambda x: x.level_z)

    return result


def find_closest_existing_joint(
    target_x: float,
    target_y: float,
    target_z: float,
    existing_joints: List[ExistingJoint],
    z_tol: float = Z_TOL,
) -> ExistingJoint:
    same_z = [j for j in existing_joints if abs(j.z - target_z) <= z_tol]
    if same_z:
        return min(same_z, key=lambda j: (j.x - target_x) ** 2 + (j.y - target_y) ** 2)

    unique_z = sorted(set(j.z for j in existing_joints))
    if not unique_z:
        raise ValueError("原模型 joints 为空，无法寻找连接点")

    nearest_z = min(unique_z, key=lambda z: abs(z - target_z))
    nearest_layer_joints = [j for j in existing_joints if abs(j.z - nearest_z) <= z_tol]
    if not nearest_layer_joints:
        raise ValueError(f"找不到 target_z={target_z} 的连接节点")

    print(f"[WARN] target_z={target_z} 层没有原模型节点，自动改用最近层 z={nearest_z} 连接")
    return min(nearest_layer_joints, key=lambda j: (j.x - target_x) ** 2 + (j.y - target_y) ** 2)


def build_one_well_slot(
    slot: WellSlotConfig,
    connections: List[SlotConnection],
    mudline: float,
    existing_joints: List[ExistingJoint],
    group_id_gen: IdGenerator,
    joint_id_gen: IdGenerator,
    seq_start_group: int,
    seq_start_joint: int,
    seq_start_member: int,
) -> Tuple[List[NewGroup], List[NewJoint], List[NewMember], int, int, int]:
    new_groups: List[NewGroup] = []
    new_joints: List[NewJoint] = []
    new_members: List[NewMember] = []

    seq_group = seq_start_group
    seq_joint = seq_start_joint
    seq_member = seq_start_member

    cz = mudline - 6.0 * slot.conductor_od / 1000.0

    conductor_group_id = group_id_gen.get_available("CN", width=3)
    seq_group += 1
    new_groups.append(
        NewGroup(
            group_id=conductor_group_id,
            group_type="CONDUCTOR",
            od_mm=slot.conductor_od,
            wt_mm=slot.conductor_wt,
            od_cm=slot.conductor_od / 10.0,
            wt_cm=slot.conductor_wt / 10.0,
            slot_no=slot.slot_no,
            sequence_no=seq_group,
        )
    )

    support_group_id = group_id_gen.get_available("CN", width=3)
    seq_group += 1
    new_groups.append(
        NewGroup(
            group_id=support_group_id,
            group_type="SUPPORT",
            od_mm=slot.support_od,
            wt_mm=slot.support_wt,
            od_cm=slot.support_od / 10.0,
            wt_cm=slot.support_wt / 10.0,
            slot_no=slot.slot_no,
            sequence_no=seq_group,
        )
    )

    wishbone_group_id = group_id_gen.get_available("WB", width=3)
    seq_group += 1
    new_groups.append(
        NewGroup(
            group_id=wishbone_group_id,
            group_type="WISHBONE",
            od_mm=slot.conductor_od,
            wt_mm=slot.conductor_wt,
            od_cm=slot.conductor_od / 10.0,
            wt_cm=slot.conductor_wt / 10.0,
            slot_no=slot.slot_no,
            sequence_no=seq_group,
        )
    )

    first_joint_id = joint_id_gen.get_available("CN", width=4)
    seq_joint += 1
    first_joint = NewJoint(
        joint_id=first_joint_id,
        x=slot.x,
        y=slot.y,
        z=cz,
        fixity="111111",
        joint_kind="CONDUCTOR_BOTTOM",
        slot_no=slot.slot_no,
        sequence_no=seq_joint,
    )
    new_joints.append(first_joint)

    previous_conductor_joint = first_joint

    for conn in connections:
        current_joint_id = joint_id_gen.get_available("CN", width=4)
        seq_joint += 1
        current_joint = NewJoint(
            joint_id=current_joint_id,
            x=slot.x,
            y=slot.y,
            z=conn.level_z,
            fixity=None,
            joint_kind="CONDUCTOR_LEVEL",
            slot_no=slot.slot_no,
            sequence_no=seq_joint,
        )
        new_joints.append(current_joint)

        seq_member += 1
        new_members.append(
            NewMember(
                joint_a=previous_conductor_joint.joint_id,
                joint_b=current_joint.joint_id,
                group_id=conductor_group_id,
                offset_ax_mm=0.0,
                offset_ay_mm=0.0,
                offset_az_mm=0.0,
                offset_bx_mm=0.0,
                offset_by_mm=0.0,
                offset_bz_mm=0.0,
                member_kind="CONDUCTOR",
                connection_type=None,
                slot_no=slot.slot_no,
                sequence_no=seq_member,
            )
        )

        closest_joint = find_closest_existing_joint(
            target_x=current_joint.x,
            target_y=current_joint.y,
            target_z=current_joint.z,
            existing_joints=existing_joints,
        )

        ctype = conn.connection_type.strip()

        if ctype == "导向连接":
            wb_joint_id = joint_id_gen.get_available("CN", width=4)
            seq_joint += 1
            wb_joint = NewJoint(
                joint_id=wb_joint_id,
                x=current_joint.x,
                y=current_joint.y,
                z=current_joint.z,
                fixity=None,
                joint_kind="WISHBONE",
                slot_no=slot.slot_no,
                sequence_no=seq_joint,
            )
            new_joints.append(wb_joint)

            seq_member += 1
            new_members.append(
                NewMember(
                    joint_a=current_joint.joint_id,
                    joint_b=wb_joint.joint_id,
                    group_id=wishbone_group_id,
                    offset_ax_mm=0.0,
                    offset_ay_mm=0.0,
                    offset_az_mm=slot.conductor_od,
                    offset_bx_mm=0.0,
                    offset_by_mm=0.0,
                    offset_bz_mm=0.0,
                    member_kind="WISHBONE",
                    connection_type=ctype,
                    slot_no=slot.slot_no,
                    sequence_no=seq_member,
                )
            )

            seq_member += 1
            new_members.append(
                NewMember(
                    joint_a=wb_joint.joint_id,
                    joint_b=closest_joint.joint_id,
                    group_id=support_group_id,
                    offset_ax_mm=0.0,
                    offset_ay_mm=0.0,
                    offset_az_mm=0.0,
                    offset_bx_mm=0.0,
                    offset_by_mm=0.0,
                    offset_bz_mm=0.0,
                    member_kind="SUPPORT",
                    connection_type=ctype,
                    slot_no=slot.slot_no,
                    sequence_no=seq_member,
                )
            )

        elif ctype == "焊接":
            seq_member += 1
            new_members.append(
                NewMember(
                    joint_a=current_joint.joint_id,
                    joint_b=closest_joint.joint_id,
                    group_id=support_group_id,
                    offset_ax_mm=0.0,
                    offset_ay_mm=0.0,
                    offset_az_mm=0.0,
                    offset_bx_mm=0.0,
                    offset_by_mm=0.0,
                    offset_bz_mm=0.0,
                    member_kind="SUPPORT",
                    connection_type=ctype,
                    slot_no=slot.slot_no,
                    sequence_no=seq_member,
                )
            )

        elif ctype == "无连接":
            pass

        else:
            raise ValueError(f"slot_no={slot.slot_no}, level_z={conn.level_z} 出现未知连接类型: {ctype}")

        previous_conductor_joint = current_joint

    return new_groups, new_joints, new_members, seq_group, seq_joint, seq_member


def insert_new_groups(conn, job_name: str, rows: List[NewGroup]) -> None:
    if not rows:
        return
    sql = text("""
        INSERT INTO new_groups (
            job_name, group_id, group_type,
            od_mm, wt_mm, od_cm, wt_cm,
            slot_no, sequence_no, mark
        ) VALUES (
            :job_name, :group_id, :group_type,
            :od_mm, :wt_mm, :od_cm, :wt_cm,
            :slot_no, :sequence_no, :mark
        )
    """)
    payload = [
        {
            "job_name": job_name,
            "group_id": r.group_id,
            "group_type": r.group_type,
            "od_mm": r.od_mm,
            "wt_mm": r.wt_mm,
            "od_cm": r.od_cm,
            "wt_cm": r.wt_cm,
            "slot_no": r.slot_no,
            "sequence_no": r.sequence_no,
            "mark": "New",
        }
        for r in rows
    ]
    conn.execute(sql, payload)


def insert_new_joints(conn, job_name: str, rows: List[NewJoint]) -> None:
    if not rows:
        return
    sql = text("""
        INSERT INTO new_joints (
            job_name, joint_id, x, y, z,
            fixity, joint_kind, slot_no, sequence_no, mark
        ) VALUES (
            :job_name, :joint_id, :x, :y, :z,
            :fixity, :joint_kind, :slot_no, :sequence_no, :mark
        )
    """)
    payload = [
        {
            "job_name": job_name,
            "joint_id": r.joint_id,
            "x": r.x,
            "y": r.y,
            "z": r.z,
            "fixity": r.fixity,
            "joint_kind": r.joint_kind,
            "slot_no": r.slot_no,
            "sequence_no": r.sequence_no,
            "mark": "New",
        }
        for r in rows
    ]
    conn.execute(sql, payload)


def insert_new_members(conn, job_name: str, rows: List[NewMember]) -> None:
    if not rows:
        return
    sql = text("""
        INSERT INTO new_members (
            job_name,
            joint_a, joint_b, group_id,
            offset_ax_mm, offset_ay_mm, offset_az_mm,
            offset_bx_mm, offset_by_mm, offset_bz_mm,
            member_kind, connection_type,
            slot_no, sequence_no, mark
        ) VALUES (
            :job_name,
            :joint_a, :joint_b, :group_id,
            :offset_ax_mm, :offset_ay_mm, :offset_az_mm,
            :offset_bx_mm, :offset_by_mm, :offset_bz_mm,
            :member_kind, :connection_type,
            :slot_no, :sequence_no, :mark
        )
    """)
    payload = [
        {
            "job_name": job_name,
            "joint_a": r.joint_a,
            "joint_b": r.joint_b,
            "group_id": r.group_id,
            "offset_ax_mm": r.offset_ax_mm,
            "offset_ay_mm": r.offset_ay_mm,
            "offset_az_mm": r.offset_az_mm,
            "offset_bx_mm": r.offset_bx_mm,
            "offset_by_mm": r.offset_by_mm,
            "offset_bz_mm": r.offset_bz_mm,
            "member_kind": r.member_kind,
            "connection_type": r.connection_type,
            "slot_no": r.slot_no,
            "sequence_no": r.sequence_no,
            "mark": "New",
        }
        for r in rows
    ]
    conn.execute(sql, payload)


def generate_wellslot_to_db(mysql_url: str, job_name: str, overwrite_job: bool = True) -> dict:
    engine = create_engine(mysql_url, future=True, pool_pre_ping=True)
    ensure_tables(engine)

    with engine.begin() as conn:
        if overwrite_job:
            delete_old_results(conn, job_name)

        mudline = fetch_mudline(conn, job_name)
        forbidden_ids = fetch_forbidden_joint_ids(conn, job_name)
        existing_joints = fetch_existing_joints(conn, job_name, forbidden_ids)
        well_slots = fetch_well_slots(conn, job_name)
        connection_map = fetch_well_slot_connections(conn, job_name)

        if not well_slots:
            raise ValueError(f"job={job_name} 在 well_slots 中没有数据")

        used_group_ids = fetch_existing_group_ids(conn, job_name)
        used_joint_ids = fetch_existing_joint_ids(conn, job_name)

        group_id_gen = IdGenerator(used_group_ids)
        joint_id_gen = IdGenerator(used_joint_ids)

        all_new_groups: List[NewGroup] = []
        all_new_joints: List[NewJoint] = []
        all_new_members: List[NewMember] = []

        seq_group = 0
        seq_joint = 0
        seq_member = 0

        for slot in well_slots:
            slot_conns = connection_map.get(slot.slot_no, [])

            ng, nj, nm, seq_group, seq_joint, seq_member = build_one_well_slot(
                slot=slot,
                connections=slot_conns,
                mudline=mudline,
                existing_joints=existing_joints,
                group_id_gen=group_id_gen,
                joint_id_gen=joint_id_gen,
                seq_start_group=seq_group,
                seq_start_joint=seq_joint,
                seq_start_member=seq_member,
            )

            all_new_groups.extend(ng)
            all_new_joints.extend(nj)
            all_new_members.extend(nm)

        insert_new_groups(conn, job_name, all_new_groups)
        insert_new_joints(conn, job_name, all_new_joints)
        insert_new_members(conn, job_name, all_new_members)

    return {
        "job_name": job_name,
        "mudline": mudline,
        "well_slots": len(well_slots),
        "new_groups": len(all_new_groups),
        "new_joints": len(all_new_joints),
        "new_members": len(all_new_members),
    }