from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelFileClassification:
    code: str
    model_type: str
    match_kind: str
    category: str
    file_type_code: str


_SINGLE_CURRENT_MODEL_CODES = {"sacinp", "seainp", "psiinp", "jcninp"}

_PREFIX_RULES: tuple[ModelFileClassification, ...] = (
    ModelFileClassification("sacinp", "SACS input data", "prefix", "结构模型文件", "model"),
    ModelFileClassification("seainp", "Seastate input data", "prefix", "海况文件", "model"),
    ModelFileClassification("jcninp", "Joint Can data", "prefix", "冲剪节点文件", "model"),
    ModelFileClassification("pilinp", "Pile input data", "prefix", "地震分析模型文件", "seismic"),
    ModelFileClassification("gapinp", "Gap input data", "prefix", "其他分析模型文件", "other"),
    ModelFileClassification("psiinp", "Pile/Soil Interaction input data", "prefix", "桩基文件", "model"),
    ModelFileClassification("dyninp", "Modal analysis input data", "prefix", "动力分析文件", "model"),
    ModelFileClassification(
        "dyrinp",
        "Dynamic response (earthquake) input data",
        "prefix",
        "动力分析文件(地震)",
        "seismic",
    ),
    ModelFileClassification("wvrinp", "Wave response input data", "prefix", "疲劳分析结果文件", "fatigue"),
    ModelFileClassification("ftginp", "Fatigue input data", "prefix", "疲劳分析模型文件", "fatigue"),
    ModelFileClassification(
        "clpinp",
        "Nonlinear collapse analysis input data",
        "prefix",
        "倒塌分析模型文件",
        "collapse",
    ),
    ModelFileClassification("towinp", "Tow analysis input data", "prefix", "其他分析模型文件", "other"),
    ModelFileClassification("fltinp", "Flotation/upending input data", "prefix", "其他分析模型文件", "other"),
    ModelFileClassification("lnhinp", "Launch analysis input data", "prefix", "其他分析模型文件", "other"),
    ModelFileClassification(
        "trninp",
        "Motion/Stability analysis input data",
        "prefix",
        "其他分析模型文件",
        "other",
    ),
    ModelFileClassification("mtoinp", "Material Take-Off input data", "prefix", "其他分析模型文件", "other"),
    ModelFileClassification("psilst", "Output listing for PSI analysis", "prefix", "静力分析结果文件", "model"),
    ModelFileClassification("saclst", "Output listing for static analysis", "prefix", "静力分析结果文件", "model"),
    ModelFileClassification(
        "ldflst",
        "Output listing for large deflection analysis",
        "prefix",
        "静力分析结果文件",
        "model",
    ),
    ModelFileClassification(
        "pillst",
        "Output listing for single pile analysis",
        "prefix",
        "静力分析结果文件",
        "model",
    ),
    ModelFileClassification(
        "gaplst",
        "Output listing for nonlinear Gap analysis",
        "prefix",
        "静力分析结果文件",
        "model",
    ),
    ModelFileClassification("dynlst", "Output listing for modal analysis", "prefix", "其他分析结果文件", "other"),
    ModelFileClassification(
        "eqklst",
        "Output listing for earthquake analysis",
        "prefix",
        "地震分析结果文件",
        "seismic",
    ),
    ModelFileClassification(
        "wvrlst",
        "Output listing for wave response analysis",
        "prefix",
        "其他分析结果文件",
        "other",
    ),
    ModelFileClassification("ftglst", "Output listing for fatigue analysis", "prefix", "疲劳分析结果文件", "fatigue"),
    ModelFileClassification(
        "clplst",
        "Output listing for nonlinear collapse analysis",
        "prefix",
        "倒塌分析结果文件",
        "collapse",
    ),
    ModelFileClassification("towlst", "Output listing for Tow analysis", "prefix", "其他分析结果文件", "other"),
    ModelFileClassification(
        "fltlst",
        "Output listing for flotation/upending analysis",
        "prefix",
        "其他分析结果文件",
        "other",
    ),
    ModelFileClassification("lnhlst", "Output listing for Launch analysis", "prefix", "其他分析结果文件", "other"),
    ModelFileClassification(
        "trnlst",
        "Output listing for Motion Stability analysis",
        "prefix",
        "其他分析结果文件",
        "other",
    ),
    ModelFileClassification(
        "mtolst",
        "Output listing for material take-off analysis",
        "prefix",
        "其他分析结果文件",
        "other",
    ),
    ModelFileClassification(
        "clplog",
        "Output log for nonlinear collapse analysis",
        "prefix",
        "倒塌分析日志文件",
        "collapse",
    ),
)

_SUFFIX_RULES: tuple[ModelFileClassification, ...] = (
    ModelFileClassification("runx", "SACS run file", "suffix", "其他", "other"),
)


def classify_model_file_name(filename: str) -> ModelFileClassification | None:
    name = os.path.basename(str(filename or "")).strip().lower()
    if not name:
        return None

    suffix = os.path.splitext(name)[1].lstrip(".")
    for rule in _SUFFIX_RULES:
        if suffix == rule.code:
            return rule

    for rule in _PREFIX_RULES:
        if name.startswith(rule.code):
            return rule
    return None


def is_single_current_model_code(code: str) -> bool:
    return str(code or "").strip().lower() in _SINGLE_CURRENT_MODEL_CODES
