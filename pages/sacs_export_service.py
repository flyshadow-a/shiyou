# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import create_engine, text


DEFAULT_NEW_MODEL_NAME = "sacinp.M1"
DEFAULT_NEW_SEA_NAME = "seainp.M1"

GENERATE_BAT = False
SACS_EXE_DIR = r"D:\Bentley SACS 2023"
RUNX_PATH = r"D:\hx\WC19-1D\Static\psiFACTOR.runx"


@dataclass
class ModelInfo:
    model_file: str
    sea_file: str
    new_model_file: str
    new_sea_file: str
    workpoint: float


@dataclass
class ExportGroup:
    group_id: str
    group_type: str
    od_mm: float
    wt_mm: float
    source_type: str


@dataclass
class ExportJoint:
    joint_id: str
    x: float
    y: float
    z: float
    fixity: Optional[str]
    joint_kind: str
    source_type: str


@dataclass
class ExportMember:
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
    source_type: str


@dataclass
class TopsideLegLoad:
    weight_no: int
    leg_no: int
    joint_id: str
    leg_load: float


@dataclass
class WellSlotTopLoad:
    slot_no: int
    top_load_fz: float
    joint_id: str


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


def write_text_lines(file_path: str, lines: List[str]) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)


def fill_parameters(value, width: int, decimals: int = 0) -> str:
    if value is None:
        return " " * width

    if isinstance(value, str):
        txt = value
    else:
        if decimals > 0:
            txt = f"{value:.{decimals}f}"
        else:
            if isinstance(value, float):
                if abs(value - int(value)) < 1e-9:
                    txt = str(int(value))
                else:
                    txt = f"{value:.3f}".rstrip("0").rstrip(".")
            else:
                txt = str(value)

    if len(txt) > width:
        return txt[:width]
    return txt.rjust(width)


def fetch_model_info(conn, job_name: str) -> ModelInfo:
    sql = text("""
        SELECT model_file, sea_file, new_model_file, new_sea_file, workpoint
        FROM wizard_model_info
        WHERE job_name = :job_name
        ORDER BY id DESC
        LIMIT 1
    """)
    row = conn.execute(sql, {"job_name": job_name}).mappings().first()
    if row is None:
        raise ValueError(f"wizard_model_info 中找不到 job={job_name} 的数据")

    model_file = str(row["model_file"]) if row["model_file"] else ""
    sea_file = str(row["sea_file"]) if row["sea_file"] else ""
    new_model_file = str(row["new_model_file"]) if row["new_model_file"] else ""
    new_sea_file = str(row["new_sea_file"]) if row["new_sea_file"] else ""
    workpoint = float(row["workpoint"]) if row["workpoint"] is not None else 9.1

    if not model_file:
        raise ValueError("wizard_model_info.model_file 为空")

    if not new_model_file:
        new_model_file = os.path.join(os.path.dirname(model_file), DEFAULT_NEW_MODEL_NAME)

    if (not new_sea_file) and sea_file:
        new_sea_file = os.path.join(os.path.dirname(sea_file), DEFAULT_NEW_SEA_NAME)

    return ModelInfo(
        model_file=model_file,
        sea_file=sea_file,
        new_model_file=new_model_file,
        new_sea_file=new_sea_file,
        workpoint=workpoint,
    )


def fetch_original_joint_z(conn, job_name: str) -> Dict[str, float]:
    sql = text("""
        SELECT joint_id, z
        FROM joints
        WHERE job_name = :job_name
          AND joint_id IS NOT NULL
          AND z IS NOT NULL
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()
    return {str(r["joint_id"]).strip(): float(r["z"]) for r in rows}


def fetch_new_groups(conn, job_name: str) -> List[ExportGroup]:
    result: List[ExportGroup] = []

    rows1 = conn.execute(text("""
        SELECT group_id, group_type, od_mm, wt_mm
        FROM new_groups
        WHERE job_name = :job_name
        ORDER BY sequence_no
    """), {"job_name": job_name}).mappings().all()
    for r in rows1:
        result.append(
            ExportGroup(
                group_id=str(r["group_id"]),
                group_type=str(r["group_type"]),
                od_mm=float(r["od_mm"]),
                wt_mm=float(r["wt_mm"]),
                source_type="WELLSLOT",
            )
        )

    rows2 = conn.execute(text("""
        SELECT group_id, group_type, od_mm, wt_mm
        FROM new_riser_groups
        WHERE job_name = :job_name
        ORDER BY sequence_no
    """), {"job_name": job_name}).mappings().all()
    for r in rows2:
        result.append(
            ExportGroup(
                group_id=str(r["group_id"]),
                group_type=str(r["group_type"]),
                od_mm=float(r["od_mm"]),
                wt_mm=float(r["wt_mm"]),
                source_type="RISER",
            )
        )

    return result


def fetch_new_joints(conn, job_name: str) -> List[ExportJoint]:
    result: List[ExportJoint] = []

    rows1 = conn.execute(text("""
        SELECT joint_id, x, y, z, fixity, joint_kind
        FROM new_joints
        WHERE job_name = :job_name
        ORDER BY sequence_no
    """), {"job_name": job_name}).mappings().all()
    for r in rows1:
        result.append(
            ExportJoint(
                joint_id=str(r["joint_id"]),
                x=float(r["x"]),
                y=float(r["y"]),
                z=float(r["z"]),
                fixity=str(r["fixity"]) if r["fixity"] else None,
                joint_kind=str(r["joint_kind"]),
                source_type="WELLSLOT",
            )
        )

    rows2 = conn.execute(text("""
        SELECT joint_id, x, y, z, fixity, joint_kind
        FROM new_riser_joints
        WHERE job_name = :job_name
        ORDER BY sequence_no
    """), {"job_name": job_name}).mappings().all()
    for r in rows2:
        result.append(
            ExportJoint(
                joint_id=str(r["joint_id"]),
                x=float(r["x"]),
                y=float(r["y"]),
                z=float(r["z"]),
                fixity=str(r["fixity"]) if r["fixity"] else None,
                joint_kind=str(r["joint_kind"]),
                source_type="RISER",
            )
        )

    return result


def fetch_new_members(conn, job_name: str) -> List[ExportMember]:
    result: List[ExportMember] = []

    rows1 = conn.execute(text("""
        SELECT joint_a, joint_b, group_id,
               offset_ax_mm, offset_ay_mm, offset_az_mm,
               offset_bx_mm, offset_by_mm, offset_bz_mm,
               member_kind, connection_type
        FROM new_members
        WHERE job_name = :job_name
        ORDER BY sequence_no
    """), {"job_name": job_name}).mappings().all()
    for r in rows1:
        result.append(
            ExportMember(
                joint_a=str(r["joint_a"]),
                joint_b=str(r["joint_b"]),
                group_id=str(r["group_id"]),
                offset_ax_mm=float(r["offset_ax_mm"] or 0.0),
                offset_ay_mm=float(r["offset_ay_mm"] or 0.0),
                offset_az_mm=float(r["offset_az_mm"] or 0.0),
                offset_bx_mm=float(r["offset_bx_mm"] or 0.0),
                offset_by_mm=float(r["offset_by_mm"] or 0.0),
                offset_bz_mm=float(r["offset_bz_mm"] or 0.0),
                member_kind=str(r["member_kind"]),
                connection_type=str(r["connection_type"]) if r["connection_type"] else None,
                source_type="WELLSLOT",
            )
        )

    rows2 = conn.execute(text("""
        SELECT joint_a, joint_b, group_id,
               offset_ax_mm, offset_ay_mm, offset_az_mm,
               offset_bx_mm, offset_by_mm, offset_bz_mm,
               member_kind, connection_type
        FROM new_riser_members
        WHERE job_name = :job_name
        ORDER BY sequence_no
    """), {"job_name": job_name}).mappings().all()
    for r in rows2:
        result.append(
            ExportMember(
                joint_a=str(r["joint_a"]),
                joint_b=str(r["joint_b"]),
                group_id=str(r["group_id"]),
                offset_ax_mm=float(r["offset_ax_mm"] or 0.0),
                offset_ay_mm=float(r["offset_ay_mm"] or 0.0),
                offset_az_mm=float(r["offset_az_mm"] or 0.0),
                offset_bx_mm=float(r["offset_bx_mm"] or 0.0),
                offset_by_mm=float(r["offset_by_mm"] or 0.0),
                offset_bz_mm=float(r["offset_bz_mm"] or 0.0),
                member_kind=str(r["member_kind"]),
                connection_type=str(r["connection_type"]) if r["connection_type"] else None,
                source_type="RISER",
            )
        )

    return result


def fetch_topside_leg_loads(conn, job_name: str) -> List[TopsideLegLoad]:
    sql = text("""
        SELECT weight_no, leg_no, joint_id, leg_load
        FROM topside_weight_leg_loads
        WHERE job_name = :job_name
        ORDER BY weight_no, leg_no
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()
    return [
        TopsideLegLoad(
            weight_no=int(r["weight_no"]),
            leg_no=int(r["leg_no"]),
            joint_id=str(r["joint_id"]),
            leg_load=float(r["leg_load"]),
        )
        for r in rows
    ]


def fetch_wellslot_top_loads(conn, job_name: str) -> List[WellSlotTopLoad]:
    sql = text("""
        SELECT ws.slot_no, ws.top_load_fz, nj.joint_id
        FROM well_slots ws
        JOIN (
            SELECT slot_no, MAX(z) AS max_z
            FROM new_joints
            WHERE job_name = :job_name
            GROUP BY slot_no
        ) t
            ON ws.slot_no = t.slot_no
        JOIN new_joints nj
            ON nj.job_name = :job_name
           AND nj.slot_no = t.slot_no
           AND nj.z = t.max_z
        WHERE ws.job_name = :job_name
          AND ws.top_load_fz IS NOT NULL
        ORDER BY ws.slot_no
    """)
    rows = conn.execute(sql, {"job_name": job_name}).mappings().all()
    return [
        WellSlotTopLoad(
            slot_no=int(r["slot_no"]),
            top_load_fz=float(r["top_load_fz"]),
            joint_id=str(r["joint_id"]),
        )
        for r in rows
    ]


def build_group_lines(groups: List[ExportGroup]) -> List[str]:
    lines: List[str] = []
    for g in groups:
        line = (
            "GRUP "
            + fill_parameters(g.group_id, 3)
            + "         "
            + fill_parameters(g.od_mm / 10.0, 6, 2)
            + fill_parameters(g.wt_mm / 10.0, 6, 2)
        )
        lines.append(line + "\n")
    return lines


def build_joint_lines(joints: List[ExportJoint]) -> List[str]:
    lines: List[str] = []
    for j in joints:
        base = (
            "JOINT "
            + fill_parameters(j.joint_id, 4)
            + fill_parameters(j.x, 7, 2)
            + fill_parameters(j.y, 7, 2)
            + fill_parameters(j.z, 7, 2)
        )
        if j.fixity:
            base += " " + j.fixity
        lines.append(base + "\n")
    return lines


def build_member_lines(members: List[ExportMember]) -> List[str]:
    lines: List[str] = []
    for m in members:
        base = (
            "MEMBER "
            + fill_parameters(m.joint_a, 4)
            + fill_parameters(m.joint_b, 4)
            + fill_parameters(m.group_id, 3)
        )
        lines.append(base + "\n")

        has_offset = any([
            abs(m.offset_ax_mm) > 1e-9,
            abs(m.offset_ay_mm) > 1e-9,
            abs(m.offset_az_mm) > 1e-9,
            abs(m.offset_bx_mm) > 1e-9,
            abs(m.offset_by_mm) > 1e-9,
            abs(m.offset_bz_mm) > 1e-9,
        ])
        if has_offset:
            off = (
                "MEMB2  OFFSETS "
                + fill_parameters(m.joint_a, 4)
                + fill_parameters(m.joint_b, 4)
                + fill_parameters(m.offset_ax_mm, 7, 1)
                + fill_parameters(m.offset_ay_mm, 7, 1)
                + fill_parameters(m.offset_az_mm, 7, 1)
                + fill_parameters(m.offset_bx_mm, 7, 1)
                + fill_parameters(m.offset_by_mm, 7, 1)
                + fill_parameters(m.offset_bz_mm, 7, 1)
            )
            lines.append(off + "\n")
    return lines


def build_dead_load_lines(
    wellslot_top_loads: List[WellSlotTopLoad],
    topside_leg_loads: List[TopsideLegLoad],
) -> List[str]:
    lines: List[str] = []

    for w in wellslot_top_loads:
        line = (
            "LOAD   "
            + fill_parameters(w.joint_id, 4)
            + "                  "
            + fill_parameters(-1.0 * w.top_load_fz, 7, 2)
            + "                       GLOB JOIN   SLOT"
            + str(w.slot_no)
        )
        lines.append(line + "\n")

    seq = 0
    for r in topside_leg_loads:
        seq += 1
        line = (
            "LOAD   "
            + fill_parameters(r.joint_id, 4)
            + "                  "
            + fill_parameters(-1.0 * r.leg_load, 7, 2)
            + "                       GLOB JOIN   STWN"
            + str(seq)
        )
        lines.append(line + "\n")

    return lines


def append_before_final_end(original_lines: List[str], insert_lines: List[str]) -> List[str]:
    out = list(original_lines)
    end_idx = None
    for i in range(len(out) - 1, -1, -1):
        if out[i].strip().upper() == "END":
            end_idx = i
            break

    if end_idx is None:
        if out and not out[-1].endswith("\n"):
            out[-1] += "\n"
        out.extend(insert_lines)
        return out

    return out[:end_idx] + insert_lines + out[end_idx:]


def export_model_file(
    model_info: ModelInfo,
    new_groups: List[ExportGroup],
    new_joints: List[ExportJoint],
    new_members: List[ExportMember],
) -> None:
    input_lines = read_text_lines(model_info.model_file)

    insert_lines: List[str] = []
    insert_lines.append("\n")
    insert_lines.append("** ----------------------------\n")
    insert_lines.append("** NEW GROUPS\n")
    insert_lines.append("** ----------------------------\n")
    insert_lines.extend(build_group_lines(new_groups))
    insert_lines.append("\n")
    insert_lines.append("** ----------------------------\n")
    insert_lines.append("** NEW JOINTS\n")
    insert_lines.append("** ----------------------------\n")
    insert_lines.extend(build_joint_lines(new_joints))
    insert_lines.append("\n")
    insert_lines.append("** ----------------------------\n")
    insert_lines.append("** NEW MEMBERS\n")
    insert_lines.append("** ----------------------------\n")
    insert_lines.extend(build_member_lines(new_members))
    insert_lines.append("\n")

    output_lines = append_before_final_end(input_lines, insert_lines)
    write_text_lines(model_info.new_model_file, output_lines)


def export_sea_file(
    model_info: ModelInfo,
    wellslot_top_loads: List[WellSlotTopLoad],
    topside_leg_loads: List[TopsideLegLoad],
) -> None:
    if not model_info.sea_file or not model_info.new_sea_file:
        return

    input_lines = read_text_lines(model_info.sea_file)

    insert_lines: List[str] = []
    insert_lines.append("\n")
    insert_lines.append("** ----------------------------\n")
    insert_lines.append("** NEW DEAD LOADS\n")
    insert_lines.append("** ----------------------------\n")
    insert_lines.extend(build_dead_load_lines(wellslot_top_loads, topside_leg_loads))
    insert_lines.append("\n")

    output_lines = append_before_final_end(input_lines, insert_lines)
    write_text_lines(model_info.new_sea_file, output_lines)


def generate_bat(model_info: ModelInfo) -> Optional[str]:
    if not GENERATE_BAT:
        return None

    bat_path = os.path.join(os.path.dirname(model_info.new_model_file), "AutoRunM1_python.bat")
    lines = [
        "@echo off\n",
        f'cd /d "{SACS_EXE_DIR}"\n',
        f'"{os.path.join(SACS_EXE_DIR, "AnalysisEngine.exe")}" "{RUNX_PATH}" "{SACS_EXE_DIR}"\n',
        "echo.\n",
        "echo ExitCode=%errorlevel%\n",
        "pause\n",
    ]
    write_text_lines(bat_path, lines)
    return bat_path


def export_model_bundle(mysql_url: str, job_name: str, generate_bat_flag: bool = True) -> dict:
    global GENERATE_BAT
    old_flag = GENERATE_BAT
    GENERATE_BAT = generate_bat_flag

    try:
        engine = create_engine(mysql_url, future=True, pool_pre_ping=True)

        with engine.begin() as conn:
            model_info = fetch_model_info(conn, job_name)
            new_groups = fetch_new_groups(conn, job_name)
            new_joints = fetch_new_joints(conn, job_name)
            new_members = fetch_new_members(conn, job_name)
            topside_leg_loads = fetch_topside_leg_loads(conn, job_name)
            wellslot_top_loads = fetch_wellslot_top_loads(conn, job_name)

        if not os.path.exists(model_info.model_file):
            raise FileNotFoundError(f"原始模型文件不存在: {model_info.model_file}")

        if model_info.sea_file and (not os.path.exists(model_info.sea_file)):
            raise FileNotFoundError(f"原始海况文件不存在: {model_info.sea_file}")

        export_model_file(
            model_info=model_info,
            new_groups=new_groups,
            new_joints=new_joints,
            new_members=new_members,
        )

        if model_info.sea_file and model_info.new_sea_file:
            export_sea_file(
                model_info=model_info,
                wellslot_top_loads=wellslot_top_loads,
                topside_leg_loads=topside_leg_loads,
            )

        bat_path = generate_bat(model_info) if generate_bat_flag else None

        return {
            "job_name": job_name,
            "new_model_file": model_info.new_model_file,
            "new_sea_file": model_info.new_sea_file,
            "export_groups": len(new_groups),
            "export_joints": len(new_joints),
            "export_members": len(new_members),
            "wellslot_top_loads": len(wellslot_top_loads),
            "topside_leg_loads": len(topside_leg_loads),
            "bat_file": bat_path,
        }
    finally:
        GENERATE_BAT = old_flag