from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run sacs_to_report.py from a JSON config file."
    )
    parser.add_argument("--config", required=True, help="JSON config path.")
    return parser.parse_args()


def add_repeatable(args_list: list[str], flag: str, values: list[str]) -> None:
    for value in values:
        args_list.extend([flag, str(value)])


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    cfg = json.loads(config_path.read_text(encoding="utf-8"))
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
