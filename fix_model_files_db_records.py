from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_PARENT = PROJECT_ROOT.parent
REPO_DB_DIR = PROJECT_ROOT / "shiyou_db"
LEGACY_DB_DIR = PROJECT_PARENT / "shiyou_db"
DEFAULT_DB_CONFIG = (REPO_DB_DIR if REPO_DB_DIR.exists() else LEGACY_DB_DIR) / "db_config.json"
WC19_CONFIG = PROJECT_ROOT / "pages" / "output_special_strategy" / "wc19_1d_run_config.json"
WC97_CONFIG = PROJECT_ROOT / "pages" / "output_special_strategy" / "wc9_7_run_config.json"
TARGET_FACILITIES = ("WC19-1D", "WC9-7")


def _ensure_import_path() -> None:
    for path in (PROJECT_ROOT, PROJECT_PARENT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _normalize_path(text: str | None) -> str:
    return str(text or "").replace("\\", "/").strip().strip("/")


def _category_label(text: str) -> str:
    value = text.strip()
    mapping = {
        "结构模型": "结构模型文件",
        "结构模型文件": "结构模型文件",
        "海况": "海况文件",
        "海况文件": "海况文件",
        "桩基": "桩基文件",
        "桩基文件": "桩基文件",
        "建模": "建模文件",
        "建模文件": "建模文件",
        "静力分析结果": "静力分析结果文件",
        "静力分析结果文件": "静力分析结果文件",
        "动力分析": "动力分析文件",
        "动力分析文件": "动力分析文件",
        "疲劳分析模型": "疲劳分析模型文件",
        "疲劳分析模型文件": "疲劳分析模型文件",
        "疲劳分析结果": "疲劳分析结果文件",
        "疲劳分析结果文件": "疲劳分析结果文件",
        "倒塌分析模型": "倒塌分析模型文件",
        "倒塌分析模型文件": "倒塌分析模型文件",
        "倒塌分析结果": "倒塌分析结果文件",
        "倒塌分析结果文件": "倒塌分析结果文件",
        "地震分析模型": "地震分析模型文件",
        "地震分析模型文件": "地震分析模型文件",
        "地震分析结果": "地震分析结果文件",
        "地震分析结果文件": "地震分析结果文件",
        "其他模型": "其他模型文件",
        "其他模型文件": "其他模型文件",
        "其他结果": "其他结果文件",
        "其他结果文件": "其他结果文件",
        "其他": "其他",
    }
    return mapping.get(value, value or "其他")


def _infer_leaf_and_category(original_name: str, file_type_code: str | None) -> tuple[str, str]:
    name = original_name.lower()
    code = (file_type_code or "").lower()

    if name.startswith("sacinp"):
        return "静力", "结构模型文件"
    if name.startswith("seainp"):
        return "静力", "海况文件"
    if name.startswith("psiinp"):
        return "静力", "桩基文件"
    if name.startswith("jcninp"):
        return "静力", "建模文件"
    if name.startswith("dyninp"):
        return "地震", "动力分析文件"
    if name.startswith("pilinp"):
        return "地震", "地震分析模型文件"
    if name == "lst":
        return "地震", "地震分析结果文件"
    if name.startswith("ftginp") or code == "fatigue" and not name.startswith("ftglst"):
        return "疲劳", "疲劳分析模型文件"
    if name.startswith("ftglst") or code == "fatigue":
        return "疲劳", "疲劳分析结果文件"
    if name.startswith("clpinp"):
        return "倒塌", "倒塌分析模型文件"
    if name in {"clplog", "clplst", "clprst"} or code == "collapse":
        return "倒塌", "倒塌分析结果文件"
    if code == "seismic":
        return "地震", "地震分析结果文件"
    if code == "inspection_doc":
        return "其他模型", "其他"
    return "其他模型", "其他"


def _normalize_current_model_upload_path(row) -> str | None:
    path = _normalize_path(row.logical_path)
    facility_code = (row.facility_code or "").strip()
    if not facility_code:
        return None
    prefix = f"{facility_code}/当前模型/"
    if not path.startswith(prefix):
        return None

    segments = path.split("/")
    if len(segments) < 3:
        return None

    third = segments[2]
    leaf_alias = {
        "结构模型": "静力",
        "静力": "静力",
        "地震分析": "地震",
        "地震": "地震",
        "疲劳分析": "疲劳",
        "疲劳": "疲劳",
        "倒塌分析": "倒塌",
        "倒塌": "倒塌",
        "其他": "其他模型",
        "其他模型": "其他模型",
    }.get(third)

    if leaf_alias is None:
        return None

    if "用户上传" not in segments and "手动上传" not in segments:
        return None

    category = ""
    if "用户上传" in segments:
        upload_index = segments.index("用户上传")
        if upload_index + 1 < len(segments):
            category = _category_label(segments[upload_index + 1])
        elif upload_index - 1 >= 0:
            category = _category_label(segments[upload_index - 1])
    elif "手动上传" in segments:
        category = ""

    if not category:
        leaf_alias, category = _infer_leaf_and_category(row.original_name or "", getattr(row.file_type, "code", None))

    return f"{facility_code}/当前模型/{leaf_alias}/用户上传/{category}"


def _dedupe_key(row) -> tuple[str, str, str, str]:
    return (
        (row.facility_code or "").strip(),
        _normalize_path(row.logical_path).lower(),
        (row.original_name or "").strip().lower(),
        (row.file_hash or "").strip().lower(),
    )


def run_migration(*, db_config: Path, apply_changes: bool) -> dict[str, int]:
    _ensure_import_path()
    from pages.output_special_strategy.import_special_strategy_files_to_db import import_config_files
    from shiyou_db import FileMetadataService
    from shiyou_db.models import FileRecord
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    stats = {
        "imported": 0,
        "paths_updated": 0,
        "duplicates_deleted": 0,
    }

    service = FileMetadataService.from_config(str(db_config))
    service.seed_file_types()

    config_map = {
        "WC19-1D": WC19_CONFIG,
        "WC9-7": WC97_CONFIG,
    }

    if apply_changes:
        for facility_code, config_path in config_map.items():
            if config_path.exists():
                rows = import_config_files(config_path, facility_code, db_config)
                stats["imported"] += len(rows)

    with service.session_factory() as session:
        stmt = (
            select(FileRecord)
            .options(joinedload(FileRecord.file_type))
            .where(
                FileRecord.module_code == "model_files",
                FileRecord.facility_code.in_(TARGET_FACILITIES),
                FileRecord.is_deleted.is_(False),
            )
            .order_by(FileRecord.id.asc())
        )
        rows = session.execute(stmt).scalars().all()

        for row in rows:
            new_path = _normalize_current_model_upload_path(row)
            if new_path and _normalize_path(row.logical_path) != _normalize_path(new_path):
                if apply_changes:
                    row.logical_path = new_path
                stats["paths_updated"] += 1

        if apply_changes:
            session.commit()

        rows = session.execute(stmt).scalars().all()
        groups: dict[tuple[str, str, str, str], list[FileRecord]] = defaultdict(list)
        for row in rows:
            groups[_dedupe_key(row)].append(row)

        for key, group in groups.items():
            if len(group) <= 1:
                continue
            if not key[-1]:
                continue
            ordered = sorted(
                group,
                key=lambda item: (item.uploaded_at or item.updated_at, item.id),
                reverse=True,
            )
            keep = ordered[0]
            for row in ordered[1:]:
                if apply_changes:
                    row.is_deleted = True
                stats["duplicates_deleted"] += 1

        if apply_changes:
            session.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix model_files logical_path records and remove exact duplicates.")
    parser.add_argument("--db-config", default=str(DEFAULT_DB_CONFIG), help="Database config JSON path.")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, do not apply changes.")
    args = parser.parse_args()

    stats = run_migration(db_config=Path(args.db_config), apply_changes=not args.dry_run)
    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(mode)
    for key, value in stats.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
