from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shiyou_db.service import FileMetadataService
else:
    from .service import FileMetadataService


def infer_file_type(path: Path) -> str:
    lower = str(path).lower()
    suffix = path.suffix.lower().lstrip(".")
    if "collapse" in lower or suffix.startswith("clp"):
        return "collapse"
    if "fatigue" in lower or suffix.startswith("ftg") or suffix in {"wjt", "wit", "d"}:
        return "fatigue"
    if "seismic" in lower or suffix.startswith("sei"):
        return "seismic"
    if suffix in {"sacinp", "seainp", "psiinp", "inp", "jknew"}:
        return "model"
    if suffix in {"dwg", "dxf"}:
        return "drawing"
    if suffix in {"doc", "docx", "pdf"}:
        return "inspection_doc"
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy upload folders into shiyou_db metadata storage.")
    parser.add_argument("--source-root", required=True, help="Legacy upload root to scan.")
    parser.add_argument("--module-code", default="legacy", help="Module code written into metadata.")
    parser.add_argument("--logical-prefix", default="", help="Logical path prefix, such as upload/model_files.")
    parser.add_argument("--facility-code", default="", help="Optional platform/facility code.")
    parser.add_argument("--config", default=None, help="Path to db_config.json.")
    args = parser.parse_args()

    service = FileMetadataService.from_config(args.config)
    service.seed_file_types()

    source_root = Path(args.source_root).expanduser().resolve()
    if not source_root.exists():
        raise FileNotFoundError(f"Source root not found: {source_root}")

    migrated = 0
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        relative_parent = path.parent.relative_to(source_root)
        logical_parts = [part for part in [args.logical_prefix.strip("/"), str(relative_parent).replace("\\", "/")] if part and part != "."]
        service.upload_file(
            str(path),
            file_type_code=infer_file_type(path),
            module_code=args.module_code,
            logical_path="/".join(logical_parts) or None,
            facility_code=(args.facility_code or None),
        )
        migrated += 1

    print(f"Migrated {migrated} files from {source_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
