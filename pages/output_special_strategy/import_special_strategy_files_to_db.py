from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_PARENT = PROJECT_ROOT.parent
REPO_DB_DIR = PROJECT_ROOT / "shiyou_db"
LEGACY_DB_DIR = PROJECT_PARENT / "shiyou_db"
DEFAULT_DB_CONFIG = (REPO_DB_DIR if REPO_DB_DIR.exists() else LEGACY_DB_DIR) / "db_config.json"


def _ensure_import_path() -> None:
    for path in (PROJECT_ROOT, PROJECT_PARENT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _logical_path(facility_code: str, source_group: str, source: Path) -> str:
    if source_group == "model":
        return f"{facility_code}/当前模型/结构模型/{source.parent.name}"
    if source_group == "clplog":
        return f"{facility_code}/当前模型/倒塌分析/{source.parent.name}"
    if source_group == "ftglst":
        return f"{facility_code}/当前模型/疲劳分析/{source.parent.name}/结果"
    if source_group == "ftginp":
        return f"{facility_code}/当前模型/疲劳分析/{source.parent.name}/输入"
    return f"{facility_code}/当前模型/其他"


def _replace_same_name_records(service, *, facility_code: str, logical_path: str, original_name: str) -> None:
    rows = service.list_files(
            module_code="model_files",
            logical_path=logical_path,
            facility_code=facility_code,
        )
    for row in rows:
        if (row.get("original_name") or "").strip().lower() == original_name.strip().lower():
            row_id = row.get("id")
            if row_id is not None:
                service.soft_delete(int(row_id))


def import_config_files(config_path: Path, facility_code: str, db_config: Path) -> list[dict]:
    _ensure_import_path()
    from shiyou_db import FileMetadataService

    config = _load_json(config_path)
    service = FileMetadataService.from_config(str(db_config))
    service.seed_file_types()

    imported: list[dict] = []
    groups: list[tuple[str, list[str], str]] = [
        ("model", [config["model"]], "model"),
        ("clplog", list(config.get("clplog") or []), "collapse"),
        ("ftglst", list(config.get("ftglst") or []), "fatigue"),
        ("ftginp", list(config.get("ftginp") or []), "fatigue"),
    ]

    for source_group, paths, file_type_code in groups:
        for raw_path in paths:
            source = Path(raw_path).expanduser()
            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source}")
            logical_path = _logical_path(facility_code, source_group, source)
            _replace_same_name_records(
                service,
                facility_code=facility_code,
                logical_path=logical_path,
                original_name=source.name,
            )
            row = service.upload_file(
                str(source),
                file_type_code=file_type_code,
                module_code="model_files",
                logical_path=logical_path,
                facility_code=facility_code,
                remark=f"imported_from:{source_group}",
            )
            imported.append(row)
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description="Import special strategy source files into MySQL metadata storage.")
    parser.add_argument("--config", required=True, help="Run config JSON path.")
    parser.add_argument("--facility-code", required=True, help="Facility code such as WC19-1D or WC9-7.")
    parser.add_argument("--db-config", default=str(DEFAULT_DB_CONFIG), help="Database config JSON path.")
    args = parser.parse_args()

    rows = import_config_files(Path(args.config), args.facility_code, Path(args.db_config))
    print(f"Imported {len(rows)} records for facility {args.facility_code}.")
    for row in rows:
        print(f"{row['file_type_code']:>8} | {row['logical_path']} | {row['original_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
