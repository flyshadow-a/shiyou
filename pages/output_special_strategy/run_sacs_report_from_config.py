from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.app_paths import external_path
from services.file_db_adapter import shared_storage_dir


FACILITY_CODE_HINTS = {
    "wc19_1d": "WC19-1D",
    "wc9_7": "WC9-7",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run sacs_to_report.py from a JSON config file."
    )
    parser.add_argument("--config", required=True, help="JSON config path.")
    return parser.parse_args()


def add_repeatable(args_list: list[str], flag: str, values: list[str]) -> None:
    for value in values:
        args_list.extend([flag, str(value)])


def _resolve_path(config_path: Path, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    candidate = Path(text)
    if candidate.is_absolute():
        return str(candidate)
    return str((config_path.parent / candidate).resolve())


def _detect_facility_code(config_path: Path) -> str | None:
    stem = config_path.stem.lower()
    for hint, facility_code in FACILITY_CODE_HINTS.items():
        if hint in stem:
            return facility_code
    return None


def _runtime_output_root(config_path: Path) -> Path | None:
    facility_code = _detect_facility_code(config_path)
    if not facility_code:
        return None
    shared_root = shared_storage_dir("special_strategy_runtime")
    if shared_root:
        candidate = Path(shared_root) / facility_code
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate.resolve()
        except Exception:
            pass
    candidate = Path(external_path("special_strategy_runtime", facility_code))
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate.resolve()


def _resolve_output_path(config_path: Path, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    runtime_root = _runtime_output_root(config_path)
    if runtime_root is None:
        return _resolve_path(config_path, text)
    return str((runtime_root / Path(text).name).resolve())


def _normalize_config_paths(config_path: Path, payload: dict) -> dict:
    cfg = dict(payload)
    single_keys = (
        "template_xlsm",
        "config_xlsm",
        "params_json",
        "report_template",
        "manual_fill_workbook",
        "appendix_a_file",
        "appendix_b_file",
        "model",
    )
    multi_keys = ("appendix_c_dirs", "clplog", "ftglst", "ftginp")
    for key in single_keys:
        if key in cfg:
            cfg[key] = _resolve_path(config_path, cfg.get(key))
    for key in ("output_report", "intermediate_workbook"):
        if key in cfg:
            cfg[key] = _resolve_output_path(config_path, cfg.get(key))
    for key in multi_keys:
        values = cfg.get(key)
        if isinstance(values, list):
            cfg[key] = [_resolve_path(config_path, value) for value in values if str(value or "").strip()]
    return cfg


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    cfg = _normalize_config_paths(
        config_path,
        json.loads(config_path.read_text(encoding="utf-8-sig")),
    )
    # Config runner -> sacs_to_report.py -> inspection_tool.py (single-file core)
    script_path = Path(__file__).resolve().with_name("sacs_to_report.py")

    config_xlsm = str(cfg.get("config_xlsm") or cfg["template_xlsm"])

    cli: list[str] = [
        sys.executable,
        str(script_path),
        "--template-xlsm",
        config_xlsm,
        "--model",
        str(cfg["model"]),
        "--report-template",
        str(cfg["report_template"]),
        "--output-report",
        str(cfg["output_report"]),
        "--intermediate-workbook",
        str(cfg["intermediate_workbook"]),
        "--policy",
        str(cfg.get("policy", "strict")),
        "--platform-name",
        str(cfg.get("platform_name", "{{platform_name}}")),
        "--report-date",
        str(cfg.get("report_date", "{{report_date}}")),
    ]

    params_json = str(cfg.get("params_json", "")).strip()
    if params_json:
        cli.extend(["--params-json", params_json])

    manual_fill_workbook = str(cfg.get("manual_fill_workbook", "")).strip()
    if manual_fill_workbook:
        cli.extend(["--manual-fill-workbook", manual_fill_workbook])
    appendix_a_file = str(cfg.get("appendix_a_file", "")).strip()
    appendix_b_file = str(cfg.get("appendix_b_file", "")).strip()
    appendix_c_dirs = [str(x) for x in cfg.get("appendix_c_dirs", [])]
    include_word_plan_detail_tables = bool(cfg.get("include_word_plan_detail_tables", False))
    if appendix_a_file:
        cli.extend(["--appendix-a-file", appendix_a_file])
    if appendix_b_file:
        cli.extend(["--appendix-b-file", appendix_b_file])
    add_repeatable(cli, "--appendix-c-dir", appendix_c_dirs)
    if include_word_plan_detail_tables:
        cli.append("--include-word-plan-detail-tables")

    if bool(cfg.get("enable_topology_inference", False)):
        cli.append("--enable-topology-inference")
    if bool(cfg.get("interactive_manual_fill", False)):
        cli.append("--interactive-manual-fill")

    add_repeatable(cli, "--clplog", [str(x) for x in cfg.get("clplog", [])])
    add_repeatable(cli, "--ftglst", [str(x) for x in cfg.get("ftglst", [])])
    add_repeatable(cli, "--ftginp", [str(x) for x in cfg.get("ftginp", [])])

    print("[RUN]", " ".join(f'"{x}"' if " " in x else x for x in cli))
    completed = subprocess.run(cli, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
