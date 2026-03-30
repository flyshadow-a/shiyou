from __future__ import annotations

import argparse
from pathlib import Path

from inspection_tool import export_calc_source_json_from_xlsm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export calculation-source parameters from an xlsm workbook to a standalone json file."
    )
    parser.add_argument("--source-xlsm", required=True, help="Workbook that stores calculation parameters and matrices.")
    parser.add_argument(
        "--out-json",
        default="",
        help="Output json path. Defaults to <source-xlsm stem>_calc_params.json in the same directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = Path(args.source_xlsm).resolve()
    if not source.exists():
        raise FileNotFoundError(f"source xlsm not found: {source}")
    out_json = (
        Path(args.out_json).resolve()
        if str(args.out_json).strip()
        else source.with_name(f"{source.stem}_calc_params.json")
    )
    exported = export_calc_source_json_from_xlsm(source, out_json)
    print(exported)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
