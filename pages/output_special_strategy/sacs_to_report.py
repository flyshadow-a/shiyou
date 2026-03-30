from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# inspection_tool.py is the single-file business core for Modules 1-9.
from inspection_tool import discover_data_bundle, run as run_inspection_pipeline
from report_jinja2_generator import (
    build_appendix_pdf_plan,
    build_appendix_sections,
    build_row_cap_notes,
    build_missing_requirements,
    insert_appendix_pdf_images,
    load_context_from_workbook,
    render_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SACS(input package) -> Python workbook -> Jinja2 DOCX report in one command."
    )
    parser.add_argument("--template-xlsm", required=True, help="Risk-matrix/config xlsm used by inspection pipeline.")
    parser.add_argument(
        "--params-json",
        default="",
        help="Optional standalone calculation-parameter json. When provided, risk matrices and manual calculation parameters are read from this file instead of the xlsm control sheets.",
    )
    parser.add_argument("--data-dir", default="", help="Auto-discover full input package from data directory.")
    parser.add_argument("--model", default="", help="SACS model input file (*.inp / sacinp.*).")
    parser.add_argument("--clplog", action="append", default=[], help="Collapse analysis log file, repeatable.")
    parser.add_argument("--ftglst", action="append", default=[], help="Fatigue report file, repeatable.")
    parser.add_argument("--ftginp", action="append", default=[], help="Fatigue input file, repeatable.")
    parser.add_argument(
        "--manual-fill-workbook",
        default="",
        help="Optional workbook path with user-filled FatigueSelectorAudit.ManualBrace for JSLC manual completion.",
    )
    parser.add_argument(
        "--interactive-manual-fill",
        action="store_true",
        help="Prompt ManualBrace by GUI input dialog (fallback terminal) when JSLC selector mapping is missing, then continue in one run.",
    )
    parser.add_argument("--report-template", required=True, help="DOCX report template.")
    parser.add_argument("--output-report", required=True, help="Output DOCX report path.")
    parser.add_argument("--appendix-a-file", default="", help="Appendix A file path.")
    parser.add_argument("--appendix-b-file", default="", help="Appendix B file path.")
    parser.add_argument("--appendix-c-dir", action="append", default=[], help="Appendix C directory path, repeatable.")
    parser.add_argument(
        "--include-word-plan-detail-tables",
        action="store_true",
        help="Fill Table 43/44 detail rows in Word. Default keeps these large detail tables only in Excel.",
    )
    parser.add_argument(
        "--intermediate-workbook",
        default="",
        help="Optional output workbook path. Defaults to <output-report>.pipeline.xlsx",
    )
    parser.add_argument("--policy", default="strict", choices=["strict", "loose"], help="Inspection policy mode.")
    parser.add_argument(
        "--enable-topology-inference",
        action="store_true",
        help="Enable non-VBA topology inference for fatigue selector completion (default: disabled for strict VBA).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for strategy sampling.")
    parser.add_argument(
        "--platform-name",
        default="{{platform_name}}",
        help="Placeholder/default platform name when metadata json does not provide one.",
    )
    parser.add_argument(
        "--report-date",
        default="{{report_date}}",
        help="Placeholder/default report date when metadata json does not provide one.",
    )
    parser.add_argument(
        "--metadata-json",
        default="",
        help="Optional json file with metadata fields: platform_name, report_date.",
    )
    parser.add_argument(
        "--full-rows",
        action="store_true",
        help="Deprecated: row caps are disabled by default.",
    )
    parser.add_argument(
        "--limit-rows",
        action="store_true",
        help="Enable row caps for large reports (disabled by default).",
    )
    parser.add_argument("--detail-row-limit", type=int, default=250, help="Row limit for Table 7/8/16 detail lists.")
    parser.add_argument("--future-row-limit", type=int, default=500, help="Total row limit for Table 17 future-node list.")
    parser.add_argument("--fatigue-row-limit", type=int, default=800, help="Row limit for Table 3 fatigue-failure list.")
    parser.add_argument("--collapse-row-limit", type=int, default=80, help="Row limit for Table 4/5 collapse-failure lists.")
    parser.add_argument(
        "--non-vba-post-filters",
        action="store_true",
        help="Enable legacy non-VBA post filters/rebuilds in report context (default: strict VBA behavior).",
    )
    return parser.parse_args()


def load_metadata(args: argparse.Namespace) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if args.metadata_json:
        p = Path(args.metadata_json).resolve()
        if p.exists():
            metadata = json.loads(p.read_text(encoding="utf-8"))

    if not str(metadata.get("platform_name", "")).strip():
        metadata["platform_name"] = args.platform_name
    if not str(metadata.get("report_date", "")).strip():
        metadata["report_date"] = args.report_date
    return metadata


def resolve_intermediate_path(output_report: Path, custom_path: str) -> Path:
    if custom_path.strip():
        return Path(custom_path).resolve()
    output_name = output_report.name
    suffix = output_report.suffix if output_report.suffix else ".docx"
    stem = output_name[: -len(suffix)] if output_name.endswith(suffix) else output_name
    return output_report.with_name(f"{stem}.pipeline.xlsx")


def main() -> int:
    args = parse_args()

    template_xlsm = Path(args.template_xlsm).resolve()
    report_template = Path(args.report_template).resolve()
    output_report = Path(args.output_report).resolve()
    output_report.parent.mkdir(parents=True, exist_ok=True)
    intermediate = resolve_intermediate_path(output_report, args.intermediate_workbook)
    intermediate.parent.mkdir(parents=True, exist_ok=True)

    if args.data_dir:
        bundle = discover_data_bundle(args.data_dir)
        model_file = Path(bundle["model_file"]).resolve()
        clplog_files = [Path(p).resolve() for p in bundle["clplog_files"]]
        ftglst_files = [Path(p).resolve() for p in bundle["ftglst_files"]]
        ftginp_files = [Path(p).resolve() for p in bundle["ftginp_files"]]
        print(f"[INFO] data-dir: {Path(args.data_dir).resolve()}")
        print(f"[INFO] model: {model_file}")
        print(f"[INFO] clplog files: {len(clplog_files)}")
        print(f"[INFO] ftglst files: {len(ftglst_files)}")
        print(f"[INFO] ftginp files: {len(ftginp_files)}")
    else:
        if not args.model:
            raise ValueError("--model is required when --data-dir is not provided")
        if not args.clplog:
            raise ValueError("at least one --clplog is required when --data-dir is not provided")
        if not args.ftglst:
            raise ValueError("at least one --ftglst is required when --data-dir is not provided")
        model_file = Path(args.model).resolve()
        clplog_files = [Path(p).resolve() for p in args.clplog]
        ftglst_files = [Path(p).resolve() for p in args.ftglst]
        ftginp_files = [Path(p).resolve() for p in args.ftginp]

    must_exist = [template_xlsm, model_file, report_template, *clplog_files, *ftglst_files]
    if args.params_json:
        must_exist.append(Path(args.params_json).resolve())
    for p in must_exist:
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
    for optional_file in [args.appendix_a_file, args.appendix_b_file]:
        if optional_file and (not Path(optional_file).resolve().exists()):
            raise FileNotFoundError(f"Appendix file not found: {Path(optional_file).resolve()}")
    for appendix_dir in args.appendix_c_dir:
        if appendix_dir and (not Path(appendix_dir).resolve().is_dir()):
            raise FileNotFoundError(f"Appendix directory not found: {Path(appendix_dir).resolve()}")

    print("[1/3] Running inspection pipeline...")
    run_inspection_pipeline(
        template_xlsm=template_xlsm,
        model_file=model_file,
        clplog_file=clplog_files,
        ftglst_file=ftglst_files,
        out_xlsx=intermediate,
        policy_mode=args.policy,
        seed=args.seed,
        params_json=(Path(args.params_json).resolve() if args.params_json else None),
        ftginp_files=ftginp_files,
        manual_fill_workbook=(Path(args.manual_fill_workbook).resolve() if args.manual_fill_workbook else None),
        interactive_manual_fill=bool(args.interactive_manual_fill),
        enable_topology_inference=args.enable_topology_inference,
    )
    print(f"Intermediate workbook: {intermediate}")

    print("[2/3] Building render context...")
    metadata = load_metadata(args)
    row_limits: dict[str, int] | None = None
    if args.limit_rows and (not args.full_rows):
        row_limits = {
            "fatigue_failure_rows": args.fatigue_row_limit,
            "collapse_member_rows": args.collapse_row_limit,
            "collapse_joint_rows": args.collapse_row_limit,
            "node_risk_rows_current": args.detail_row_limit,
            "member_risk_rows": args.detail_row_limit,
            "member_inspection_rows": args.detail_row_limit,
            "node_inspection_rows_future": args.future_row_limit,
        }

    # One-click full workflow:
    # always apply VBA delete macros in report statistics stage.
    # Equivalent to executing the corresponding delete-button effects in sequence.
    apply_member_delete = True
    apply_joint_delete_current = True
    apply_joint_delete_future = True

    context = load_context_from_workbook(
        intermediate,
        metadata,
        row_limits=row_limits,
        strict_vba_algorithms=not args.non_vba_post_filters,
        apply_vba_member_delete_rules=apply_member_delete,
        apply_vba_joint_delete_rules_current=apply_joint_delete_current,
        apply_vba_joint_delete_rules_future=apply_joint_delete_future,
    )
    context["appendix_sections"] = build_appendix_sections(
        appendix_a_file=args.appendix_a_file,
        appendix_b_file=args.appendix_b_file,
        appendix_c_dirs=list(args.appendix_c_dir),
    )
    context["appendix_pdf_plan"] = build_appendix_pdf_plan(
        appendix_a_file=args.appendix_a_file,
        appendix_b_file=args.appendix_b_file,
        appendix_c_dirs=list(args.appendix_c_dir),
    )
    context["include_word_plan_detail_tables"] = bool(args.include_word_plan_detail_tables)
    missing = build_missing_requirements(context)
    if missing:
        print("Missing/empty fields detected:")
        for item in missing:
            print(f"- {item}")

    cap_notes = build_row_cap_notes(context)
    if cap_notes:
        print("Row caps applied for DOCX performance:")
        for item in cap_notes:
            print(f"- {item}")

    print("[3/3] Rendering DOCX...")
    render_report(report_template, output_report, context)
    if context.get("appendix_pdf_plan"):
        insert_appendix_pdf_images(output_report, context)
    print(f"Report generated: {output_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
