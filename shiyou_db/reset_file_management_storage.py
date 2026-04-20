from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shiyou_db.service import FileMetadataService
else:
    from .service import FileMetadataService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hard-delete file management records and files for selected modules."
    )
    parser.add_argument(
        "--module",
        dest="modules",
        action="append",
        choices=["model_files", "doc_man"],
        help="Target module(s). Defaults to both model_files and doc_man.",
    )
    parser.add_argument(
        "--facility-code",
        default="",
        help="Optional facility code filter.",
    )
    parser.add_argument(
        "--config",
        default="",
        help="Optional db_config.json path.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    modules = args.modules or ["model_files", "doc_man"]
    facility_code = (args.facility_code or "").strip() or None
    config_path = (args.config or "").strip() or None

    service = FileMetadataService.from_config(config_path)
    total = 0

    for module_code in modules:
        rows = service.list_files(
            module_code=module_code,
            facility_code=facility_code,
            include_deleted=True,
        )
        for row in rows:
            record_id = row.get("id")
            if record_id is None:
                continue
            service.hard_delete(int(record_id))
            total += 1

    print(f"Deleted {total} file management record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
