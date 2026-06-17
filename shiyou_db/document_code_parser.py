from __future__ import annotations

import os
import re
from typing import Any


DESIGN_STAGE_MAP = {
    "DD": "详细设计",
    "AB": "完工",
    "MD(DD)": "改造项目详细设计",
}

DISCIPLINE_MAP = {
    "ST": "结构",
    "GE": "总体",
    "SA": "安全",
    "PR": "工艺",
    "EL": "电气",
    "CO": "通讯",
    "CC": "防腐",
    "HV": "暖通",
    "IN": "仪表",
    "MA": "机械",
    "OU": "舾装",
    "PI": "配管",
    "GEN": "通用",
}

DISCIPLINE_GROUP_MAP = {
    "ST": "结构专业",
    "GE": "总体专业",
    "SA": "其它专业",
    "PR": "其它专业",
    "EL": "其它专业",
    "CO": "其它专业",
    "CC": "其它专业",
    "HV": "其它专业",
    "IN": "其它专业",
    "MA": "其它专业",
    "OU": "其它专业",
    "PI": "其它专业",
    "GEN": "其它专业",
}

FILE_CLASS_MAP = {
    "BOD": "设计基础数据",
    "DWG": "图纸",
    "SPC": "规格书",
    "CAL": "计算书",
    "RPT": "报告",
    "SBL": "标准符号表",
    "REQ": "请购书",
    "DDS": "数据表",
    "MAL": "材料清单",
    "DOP": "程序文件",
    "EQL": "设备清单",
    "LST": "清单",
    "CMO": "调试大纲",
    "IDX": "目录",
    "CMT": "调试表格",
    "MOD": "模型",
    "SPA": "备件清单",
    "OTR": "其他",
    "OMM": "操作维修手册",
    "ODP": "总体开发方案",
    "CE": "证书",
    "CMP": "调试程序",
    "IS": "说明书",
    "IOS": "方案说明",
    "ITP": "检验试验计划",
    "NDT": "焊接无损检验",
    "PLN": "计划",
    "RFQ": "寻价单",
    "STD": "标准图",
    "TST": "系统测试文件",
    "MR": "制造记录",
    "PL": "装箱单",
    "TIC": "运输安装调试文件",
    "QC": "质量控制",
}

STRUCTURE_FILE_CLASS_CODES = {"SPC", "RPT", "DWG", "MAL", "BOD"}
GENERAL_FILE_CLASS_CODES = {"DWG", "SPC", "RPT"}
OTHER_FILE_CLASS_CODE_ORDER = [
    "BOD",
    "DWG",
    "SPC",
    "CAL",
    "RPT",
    "SBL",
    "REQ",
    "DDS",
    "MAL",
    "DOP",
    "EQL",
    "LST",
    "CMO",
    "IDX",
    "CMT",
    "MOD",
    "SPA",
    "OTR",
    "OMM",
    "ODP",
    "CE",
    "CMP",
    "IS",
    "IOS",
    "ITP",
    "NDT",
    "PLN",
    "RFQ",
    "STD",
    "TST",
    "MR",
    "PL",
    "TIC",
    "QC",
]
OTHER_FILE_CLASS_CODES = set(OTHER_FILE_CLASS_CODE_ORDER)

FILE_CLASS_CODES_BY_DISCIPLINE_GROUP = {
    "结构专业": STRUCTURE_FILE_CLASS_CODES,
    "总体专业": GENERAL_FILE_CLASS_CODES,
    "其它专业": OTHER_FILE_CLASS_CODES,
}

OTHER_FILE_CLASS_NAMES = list(
    dict.fromkeys(FILE_CLASS_MAP[code] for code in OTHER_FILE_CLASS_CODE_ORDER if code in FILE_CLASS_MAP)
)

UNIT_MAP = {
    "DPP": "钻采平台",
    "WHP": "井口平台",
    "APP": "生活动力平台",
    "CEP": "中心平台",
    "DRP": "钻井平台",
    "PAP": "生产辅助平台",
    "PRP": "生产平台",
    "WGM": "风力发电平台",
    "WIP": "注水平台",
    "GEN": "多个单体通用",
}

MODULE_MAP = {
    "TS": "上部组块",
    "JK": "导管架",
    "LQ": "生活楼",
    "MDR": "模块钻机",
    "WO": "修井机",
    "EI": "电力组网",
    "FLR": "柔性立管",
    "BY": "浮筒系统",
    "GEN": "多个模块通用",
}

DOCUMENT_CODE_RE = re.compile(
    r"(?P<stage>MD\(DD\)|DD|AB)"
    r"[-_]"
    r"(?P<class>[A-Z]{2,4})"
    r"[-_]"
    r"(?P<unit>[A-Z0-9]+)"
    r"(?:[（(](?P<module>[A-Z0-9]+)[）)])?"
    r"[-_]"
    r"(?P<discipline>[A-Z]{2,4})"
    r"[-_]"
    r"(?P<drawing>\d{4})"
    r"(?:[（(](?P<sub>\d{2})[）)])?",
    re.IGNORECASE,
)

DOCUMENT_TITLE_SEPARATOR_RE = re.compile(r"^[\s\-_]+|[\s\-_]+$")


def _resolve_unit_name(unit_code: str) -> str:
    if unit_code in UNIT_MAP:
        return UNIT_MAP[unit_code]
    for base_code in sorted(UNIT_MAP, key=len, reverse=True):
        if unit_code.startswith(base_code):
            return UNIT_MAP[base_code]
    return ""


def _normalize_module_code(module_code: str) -> str:
    return (module_code or "").upper() or "TS"


def _is_valid_class_for_discipline(file_class: str, discipline: str) -> bool:
    group = DISCIPLINE_GROUP_MAP.get(discipline, "")
    allowed = FILE_CLASS_CODES_BY_DISCIPLINE_GROUP.get(group)
    if not allowed:
        return True
    return file_class in allowed


def parse_document_code_from_name(filename: str) -> dict[str, Any]:
    """
    Parse standard engineering document codes from file names.

    Non-standard files are deliberately returned as unclassified so the UI can
    place them under "未分类/其他" and allow manual maintenance.
    """
    base_name = os.path.basename(str(filename or "").strip())
    stem, _ext = os.path.splitext(base_name)
    match = DOCUMENT_CODE_RE.search(stem.upper())
    if not match:
        return {
            "document_code": "",
            "document_title": stem,
            "recognition_status": "unclassified",
            "recognition_message": "未识别到标准文件编码",
        }

    stage = match.group("stage").upper()
    file_class = match.group("class").upper()
    unit = match.group("unit").upper()
    module = _normalize_module_code(match.group("module") or "")
    discipline = match.group("discipline").upper()
    drawing = match.group("drawing")
    sub = match.group("sub") or ""
    code_raw = stem[match.start() : match.end()]
    code = re.sub(r"_", "-", code_raw)
    title = DOCUMENT_TITLE_SEPARATOR_RE.sub("", stem.replace(code_raw, ""))

    status = "recognized"
    notes: list[str] = []
    if stage not in DESIGN_STAGE_MAP:
        status = "partial"
        notes.append(f"未知设计阶段:{stage}")
    if file_class not in FILE_CLASS_MAP:
        status = "partial"
        notes.append(f"未知文件分类:{file_class}")
    if discipline not in DISCIPLINE_MAP:
        status = "partial"
        notes.append(f"未知专业:{discipline}")
    elif file_class in FILE_CLASS_MAP and not _is_valid_class_for_discipline(file_class, discipline):
        status = "partial"
        notes.append(f"文件分类不适用于该专业:{discipline}-{file_class}")
    if not _resolve_unit_name(unit):
        status = "partial"
        notes.append(f"未知单体:{unit}")
    if module and module not in MODULE_MAP:
        status = "partial"
        notes.append(f"未知模块:{module}")
    try:
        drawing_number = int(drawing)
        if drawing_number < 1 or drawing_number > 9999:
            status = "partial"
            notes.append(f"图号超出范围:{drawing}")
    except Exception:
        status = "partial"
        notes.append(f"图号格式错误:{drawing}")
    if sub:
        try:
            sub_number = int(sub)
            if sub_number < 1 or sub_number > 99:
                status = "partial"
                notes.append(f"次级序列号超出范围:{sub}")
        except Exception:
            status = "partial"
            notes.append(f"次级序列号格式错误:{sub}")

    return {
        "document_code": code,
        "document_title": title,
        "design_stage_code": stage,
        "design_stage_name": DESIGN_STAGE_MAP.get(stage, ""),
        "file_class_code": file_class,
        "file_class_name": FILE_CLASS_MAP.get(file_class, ""),
        "discipline_code": discipline,
        "discipline_name": DISCIPLINE_MAP.get(discipline, ""),
        "discipline_group": DISCIPLINE_GROUP_MAP.get(discipline, ""),
        "asset_unit_code": unit,
        "asset_unit_name": _resolve_unit_name(unit),
        "module_unit_code": module,
        "module_unit_name": MODULE_MAP.get(module, ""),
        "drawing_no": drawing,
        "sub_sequence": sub,
        "recognition_status": status,
        "recognition_message": "；".join(notes),
    }
