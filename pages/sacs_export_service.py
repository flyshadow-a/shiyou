# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import text
from shiyou_db.database import build_engine_from_url
from shiyou_db.config import get_sacs_analysis_engine_exe, get_sacs_default_runx_path
from pages.sacs_runtime_service import ensure_analysis_bat, ensure_runx_in_workdir

from pages.sacs_storage_service import (
    get_job_runtime_dir,
    get_job_new_model_file,
    get_job_new_sea_file,
    get_job_runx_file,
    get_job_psiinp_file,
    get_job_jcninp_file,
    stage_support_files_for_job,
)
from pages.sacs_runtime_service import (
    ensure_analysis_bat,
    ensure_runx_in_workdir,
    ensure_support_inputs_in_workdir,
)

DEFAULT_NEW_MODEL_NAME = "sacinp.M1"
DEFAULT_NEW_SEA_NAME = "seainp.M1"

GENERATE_BAT = False

def resolve_sacs_analysis_engine_exe() -> str:
    exe_path = os.path.normpath(str(get_sacs_analysis_engine_exe() or "").strip())
    if not exe_path:
        raise ValueError("未配置 SACS AnalysisEngine.exe 路径，请在 db_config.json 中设置 sacs_analysis_engine_exe")
    if not os.path.isfile(exe_path):
        raise FileNotFoundError(f"SACS AnalysisEngine.exe 不存在: {exe_path}")
    return exe_path


def resolve_runx_path(model_info: ModelInfo) -> str:
    # 优先使用已经复制到运行目录的 RUNX。
    # 这样即使 db_config.json 里配置了失效的模板路径，也不会阻塞计算。
    model_dir = os.path.dirname(model_info.new_model_file)
    candidates = [
        os.path.join(model_dir, "psiM1.runx"),
        os.path.join(model_dir, "psim1.runx"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return os.path.normpath(p)

    configured = os.path.normpath(str(get_sacs_default_runx_path() or "").strip())
    if configured and os.path.isfile(configured):
        return configured

    configured_hint = f"；当前 db_config.json 配置为：{configured}" if configured else ""
    raise FileNotFoundError(
        "未找到 RUNX 文件。新流程下 RUNX 不再由用户上传，"
        "请将服务端固定模板放到 项目根目录下的 psiM1.runx，"
        "或在 db_config.json 中设置有效的 sacs_default_runx_path" + configured_hint
    )

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
        new_model_file = get_job_new_model_file(job_name)

    if (not new_sea_file) and sea_file:
        new_sea_file = get_job_new_sea_file(job_name)

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


def _is_zero_value(value) -> bool:
    try:
        return abs(float(value)) < 1e-12
    except Exception:
        return False


def fill_parameters_vba(value, width: int, str_type: str = "String") -> str:
    """尽量模拟 VBA 的 FillParameters。"""
    if value is None or _is_zero_value(value):
        text = ""
    elif str_type.lower() == "number":
        text = str(value)
        if "e" in text.lower():
            text = f"{float(value):.6f}".rstrip("0").rstrip(".")
        if "." not in text:
            text = text + "."
    else:
        if isinstance(value, float):
            if abs(value - int(value)) < 1e-9:
                text = str(int(value))
            else:
                text = f"{value:.3f}".rstrip("0").rstrip(".")
        else:
            text = str(value)

    if len(text) > width:
        return text[:width]
    return text.rjust(width)


def build_group_lines(groups: List[ExportGroup]) -> List[str]:
    """按 VBA 的 GRUP 输出方式生成新增组。"""
    lines: List[str] = []
    for g in groups:
        gid = fill_parameters_vba(str(g.group_id or "").strip(), 3)
        od_cm = float(g.od_mm or 0.0) / 10.0
        wt_cm = float(g.wt_mm or 0.0) / 10.0
        head = (
            "GRUP "
            + gid
            + "         "
            + fill_parameters_vba(od_cm, 6, "Number")
            + fill_parameters_vba(wt_cm, 6, "Number")
            + " 20.008.00035.50 9    1.001.00     0.500"
        )
        group_type = str(g.group_type or "").strip().upper()
        if group_type == "SUPPORT":
            tail = "N7.8490   "
        elif group_type == "WISHBONE":
            tail = " 1.00-3   "
        else:
            tail = "F7.8490   "
        lines.append(head + tail + "\n")
    return lines


def build_joint_lines(joints: List[ExportJoint]) -> List[str]:
    lines: List[str] = []
    for j in joints:
        base = (
            "JOINT "
            + fill_parameters_vba(str(j.joint_id or "").strip(), 4)
            + " "
            + fill_parameters_vba(float(j.x), 7)
            + fill_parameters_vba(float(j.y), 7)
            + fill_parameters_vba(float(j.z), 7)
            + "                      "
        )
        if j.fixity:
            base += str(j.fixity).strip()
        lines.append(base.rstrip() + "\n")
    return lines


def _offset_mm_to_cm(value_mm: float) -> float:
    return float(value_mm or 0.0) / 10.0


def _member_has_offset(m: ExportMember) -> bool:
    return any([
        abs(float(m.offset_ax_mm or 0.0)) > 1e-9,
        abs(float(m.offset_ay_mm or 0.0)) > 1e-9,
        abs(float(m.offset_az_mm or 0.0)) > 1e-9,
        abs(float(m.offset_bx_mm or 0.0)) > 1e-9,
        abs(float(m.offset_by_mm or 0.0)) > 1e-9,
        abs(float(m.offset_bz_mm or 0.0)) > 1e-9,
    ])


def build_member_lines(members: List[ExportMember]) -> List[str]:
    """按 VBA 的 MEMBER / MEMBER OFFSETS 写法输出新增构件。"""
    lines: List[str] = []
    for m in members:
        joint_a = fill_parameters_vba(str(m.joint_a or "").strip(), 4)
        joint_b = fill_parameters_vba(str(m.joint_b or "").strip(), 4)
        group_id = fill_parameters_vba(str(m.group_id or "").strip(), 3)

        if _member_has_offset(m):
            lines.append("MEMBER1" + joint_a + joint_b + " " + group_id + "\n")
            offset_line = (
                "MEMBER OFFSETS                     "
                + fill_parameters_vba(_offset_mm_to_cm(m.offset_ax_mm), 6)
                + fill_parameters_vba(_offset_mm_to_cm(m.offset_ay_mm), 6)
                + fill_parameters_vba(_offset_mm_to_cm(m.offset_az_mm), 6)
                + fill_parameters_vba(_offset_mm_to_cm(m.offset_bx_mm), 6)
                + fill_parameters_vba(_offset_mm_to_cm(m.offset_by_mm), 6)
                + fill_parameters_vba(_offset_mm_to_cm(m.offset_bz_mm), 6)
            )
            lines.append(offset_line.rstrip() + "\n")
        else:
            lines.append("MEMBER " + joint_a + joint_b + " " + group_id + "\n")
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
    if not insert_lines:
        return list(original_lines)

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


def _line_starts_with(line: str, keyword: str) -> bool:
    return str(line or "").upper().startswith(keyword.upper())


def _is_comment_line(line: str) -> bool:
    return str(line or "").lstrip().startswith("*")


def _is_group_line(line: str) -> bool:
    return _line_starts_with(line, "GRUP")


def _is_joint_line(line: str) -> bool:
    return _line_starts_with(line, "JOINT")


def _is_member_line(line: str) -> bool:
    return str(line or "").upper().startswith("MEMBER")


def _new_block(title: str, data_lines: List[str]) -> List[str]:
    if not data_lines:
        return []
    now_text = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    return [
        f"***************  New added {title}  {now_text}\n",
        *data_lines,
        f"***************  End New added {title}\n",
    ]


def _strip_existing_new_sections(lines: List[str]) -> List[str]:
    """清理本程序生成的 New added 块，避免重复叠加。"""
    start_markers = (
        "NEW ADDED GROUPS",
        "NEW ADDED MEMBERS",
        "NEW ADDED JOINTS",
        "** NEW GROUPS START",
        "** NEW MEMBERS START",
        "** NEW JOINTS START",
    )
    end_markers = (
        "END NEW ADDED GROUPS",
        "END NEW ADDED MEMBERS",
        "END NEW ADDED JOINTS",
        "** NEW GROUPS END",
        "** NEW MEMBERS END",
        "** NEW JOINTS END",
    )

    out: List[str] = []
    skipping = False
    for line in lines:
        upper = str(line or "").strip().upper()
        if not skipping and any(marker in upper for marker in start_markers):
            skipping = True
            continue
        if skipping:
            if any(marker in upper for marker in end_markers):
                skipping = False
            continue
        out.append(line)
    return out


def _insert_new_blocks_like_vba(
    input_lines: List[str],
    group_block: List[str],
    member_block: List[str],
    joint_block: List[str],
) -> List[str]:
    """按 VBA UpdateModel 的方式插入新增块。"""
    if not (group_block or member_block or joint_block):
        return list(input_lines)

    output: List[str] = []
    process_group = False
    process_member = False
    process_joint = False
    group_inserted = not bool(group_block)
    member_inserted = not bool(member_block)
    joint_inserted = not bool(joint_block)

    for raw in input_lines:
        line = str(raw or "")

        if process_group and (not _is_group_line(line)) and (not _is_comment_line(line)):
            if not group_inserted:
                output.extend(group_block)
                group_inserted = True
            process_group = False

        if process_member and (not _is_member_line(line)) and (not _is_comment_line(line)) and (not _line_starts_with(line, "MEMB2")):
            if not member_inserted:
                output.extend(member_block)
                member_inserted = True
            process_member = False

        if process_joint and (not _is_joint_line(line)) and (not _is_comment_line(line)):
            if not joint_inserted:
                output.extend(joint_block)
                joint_inserted = True
            process_joint = False

        if _is_group_line(line):
            process_group = True
        if _is_member_line(line):
            process_member = True
        if _is_joint_line(line):
            process_joint = True

        output.append(raw)

    tail_blocks: List[str] = []
    if not group_inserted:
        tail_blocks.extend(group_block)
    if not member_inserted:
        tail_blocks.extend(member_block)
    if not joint_inserted:
        tail_blocks.extend(joint_block)

    if tail_blocks:
        output = append_before_final_end(output, tail_blocks)

    return output


def export_model_file(
    model_info: ModelInfo,
    new_groups: List[ExportGroup],
    new_joints: List[ExportJoint],
    new_members: List[ExportMember],
) -> None:
    input_lines = _strip_existing_new_sections(read_text_lines(model_info.model_file))

    group_block = _new_block("Groups", build_group_lines(new_groups))
    member_block = _new_block("Members", build_member_lines(new_members))
    joint_block = _new_block("Joints", build_joint_lines(new_joints))

    output_lines = _insert_new_blocks_like_vba(
        input_lines,
        group_block=group_block,
        member_block=member_block,
        joint_block=joint_block,
    )

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

    work_dir = os.path.dirname(model_info.new_model_file)
    runx_path = ensure_runx_in_workdir(work_dir)
    return ensure_analysis_bat(work_dir, runx_path)


def export_model_bundle(mysql_url: str, job_name: str, generate_bat_flag: bool = True) -> dict:
    global GENERATE_BAT
    old_flag = GENERATE_BAT
    GENERATE_BAT = generate_bat_flag

    try:
        engine = build_engine_from_url(mysql_url)

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

        runtime_dir = get_job_runtime_dir(job_name)

        # 复制计算辅助文件：
        # - RUNX 来自服务端固定模板；
        # - PSIINP / JCNINP 来自当前模型静力目录，复制后统一命名为 M1。
        # generate_bat_flag=True 时这些文件是计算必需文件，因此做强校验。
        support_files = stage_support_files_for_job(job_name, require_all=generate_bat_flag)

        runx_file = support_files.get("runx", "")
        psiinp_file = support_files.get("psiinp", "")
        jcninp_file = support_files.get("jcninp", "")

        bat_path = ""
        if generate_bat_flag:
            runx_file = ensure_runx_in_workdir(runtime_dir, runx_file or resolve_runx_path(model_info))
            psiinp_file, jcninp_file = ensure_support_inputs_in_workdir(
                runtime_dir,
                psiinp_path=psiinp_file,
                jcninp_path=jcninp_file,
            )
            bat_path = ensure_analysis_bat(
                runtime_dir,
                runx_path=runx_file,
                psiinp_path=psiinp_file,
                jcninp_path=jcninp_file,
            )

        return {
            "job_name": job_name,
            "model_dir": runtime_dir,
            "new_model_file": model_info.new_model_file,
            "new_sea_file": model_info.new_sea_file,
            "runx_file": runx_file,
            "psiinp_file": psiinp_file,
            "jcninp_file": jcninp_file,
            "bat_file": bat_path,
            "export_groups": len(new_groups),
            "export_joints": len(new_joints),
            "export_members": len(new_members),
            "wellslot_top_loads": len(wellslot_top_loads),
            "topside_leg_loads": len(topside_leg_loads),
        }
    finally:
        GENERATE_BAT = old_flag
