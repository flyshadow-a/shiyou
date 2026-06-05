from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, inspect, or_, select
from sqlalchemy.orm import joinedload, sessionmaker

from .config import AppSettings, load_settings
from .database import Base, build_engine
from .document_code_parser import parse_document_code_from_name
from .storage_share import ensure_storage_share_connected
from .models import (
    AuthRole,
    DocumentCategory,
    DocumentRebuildDirectory,
    FacilityProfile,
    FileRecord,
    FileType,
    InspectionFinding,
    InspectionProject,
    PlatformLoadInformationItem,
    PlatformLoadSummarySnapshot,
    PlatformSummarySnapshot,
)

DEFAULT_FILE_TYPES = [
    {"code": "model", "name": "结构模型", "description": "结构模型与分析输入"},
    {"code": "seismic", "name": "地震", "description": "地震分析相关文件"},
    {"code": "fatigue", "name": "疲劳", "description": "疲劳分析相关文件"},
    {"code": "collapse", "name": "倒塌", "description": "倒塌分析相关文件"},
    {"code": "drawing", "name": "图纸", "description": "图纸与示意图"},
    {"code": "inspection_doc", "name": "检测文档", "description": "检测报告与文档"},
    {"code": "history", "name": "历史资料", "description": "历史检查与重建资料"},
    {"code": "summary", "name": "汇总资料", "description": "汇总与统计资料"},
    {"code": "other", "name": "其他", "description": "其他文件"},
]

DEFAULT_AUTH_ROLES = [
    {"code": "engineer", "name": "工程师", "description": "普通工程师用户，可使用业务功能"},
    {"code": "admin", "name": "管理员", "description": "系统管理员角色，暂时预留"},
]

DEFAULT_DOCUMENT_CATEGORIES = [
    {"scope_code": "detail_design", "parent_code": "", "code": "detail_design", "name": "详细设计", "table_key": "design", "sort_order": 10},
    {"scope_code": "detail_design", "parent_code": "detail_design", "code": "detail_design/ST", "name": "结构(ST)", "discipline_code": "ST", "table_key": "design", "sort_order": 20},
    {"scope_code": "detail_design", "parent_code": "detail_design/ST", "code": "detail_design/ST/SPC", "name": "规格书", "discipline_code": "ST", "file_class_code": "SPC", "table_key": "design", "sort_order": 30},
    {"scope_code": "detail_design", "parent_code": "detail_design/ST", "code": "detail_design/ST/RPT", "name": "报告", "discipline_code": "ST", "file_class_code": "RPT", "table_key": "design", "sort_order": 40},
    {"scope_code": "detail_design", "parent_code": "detail_design/ST", "code": "detail_design/ST/DWG", "name": "图纸", "discipline_code": "ST", "file_class_code": "DWG", "table_key": "design", "sort_order": 50},
    {"scope_code": "detail_design", "parent_code": "detail_design/ST", "code": "detail_design/ST/MAL", "name": "料单", "discipline_code": "ST", "file_class_code": "MAL", "table_key": "design", "sort_order": 60},
    {"scope_code": "detail_design", "parent_code": "detail_design/ST", "code": "detail_design/ST/BOD", "name": "设计基础", "discipline_code": "ST", "file_class_code": "BOD", "table_key": "design", "sort_order": 70},
    {"scope_code": "detail_design", "parent_code": "detail_design", "code": "detail_design/GE", "name": "总体(GE)", "discipline_code": "GE", "table_key": "design", "sort_order": 80},
    {"scope_code": "detail_design", "parent_code": "detail_design/GE", "code": "detail_design/GE/DWG", "name": "图纸", "discipline_code": "GE", "file_class_code": "DWG", "table_key": "design", "sort_order": 90},
    {"scope_code": "detail_design", "parent_code": "detail_design/GE", "code": "detail_design/GE/SPC", "name": "规格书", "discipline_code": "GE", "file_class_code": "SPC", "table_key": "design", "sort_order": 100},
    {"scope_code": "detail_design", "parent_code": "detail_design/GE", "code": "detail_design/GE/RPT", "name": "报告", "discipline_code": "GE", "file_class_code": "RPT", "table_key": "design", "sort_order": 110},
    {"scope_code": "detail_design", "parent_code": "detail_design", "code": "detail_design/OTHER", "name": "其他", "table_key": "design", "sort_order": 120},
    {"scope_code": "detail_design", "parent_code": "detail_design/OTHER", "code": "detail_design/OTHER/OTHER", "name": "未分类/其他", "file_class_code": "OTR", "table_key": "design", "sort_order": 130},
    {"scope_code": "completion", "parent_code": "", "code": "completion", "name": "完工", "table_key": "design", "sort_order": 140},
    {"scope_code": "completion", "parent_code": "completion", "code": "completion/ST", "name": "结构(ST)", "discipline_code": "ST", "table_key": "design", "sort_order": 150},
    {"scope_code": "completion", "parent_code": "completion/ST", "code": "completion/ST/SPC", "name": "规格书", "discipline_code": "ST", "file_class_code": "SPC", "table_key": "design", "sort_order": 160},
    {"scope_code": "completion", "parent_code": "completion/ST", "code": "completion/ST/RPT", "name": "报告", "discipline_code": "ST", "file_class_code": "RPT", "table_key": "design", "sort_order": 170},
    {"scope_code": "completion", "parent_code": "completion/ST", "code": "completion/ST/DWG", "name": "图纸", "discipline_code": "ST", "file_class_code": "DWG", "table_key": "design", "sort_order": 180},
    {"scope_code": "completion", "parent_code": "completion/ST", "code": "completion/ST/MAL", "name": "料单", "discipline_code": "ST", "file_class_code": "MAL", "table_key": "design", "sort_order": 190},
    {"scope_code": "completion", "parent_code": "completion/ST", "code": "completion/ST/BOD", "name": "设计基础", "discipline_code": "ST", "file_class_code": "BOD", "table_key": "design", "sort_order": 200},
    {"scope_code": "completion", "parent_code": "completion", "code": "completion/GE", "name": "总体(GE)", "discipline_code": "GE", "table_key": "design", "sort_order": 210},
    {"scope_code": "completion", "parent_code": "completion/GE", "code": "completion/GE/DWG", "name": "图纸", "discipline_code": "GE", "file_class_code": "DWG", "table_key": "design", "sort_order": 220},
    {"scope_code": "completion", "parent_code": "completion/GE", "code": "completion/GE/SPC", "name": "规格书", "discipline_code": "GE", "file_class_code": "SPC", "table_key": "design", "sort_order": 230},
    {"scope_code": "completion", "parent_code": "completion/GE", "code": "completion/GE/RPT", "name": "报告", "discipline_code": "GE", "file_class_code": "RPT", "table_key": "design", "sort_order": 240},
    {"scope_code": "completion", "parent_code": "completion", "code": "completion/OTHER", "name": "其他", "file_class_code": "OTR", "table_key": "design", "sort_order": 250},
    {"scope_code": "rebuild_project", "parent_code": "", "code": "rebuild_project", "name": "历次改造文件", "table_key": "rebuild", "sort_order": 300},
    {"scope_code": "model_files", "parent_code": "", "code": "model_files", "name": "模型文件", "table_key": "model", "sort_order": 400},
]

_UNSET = object()
FILE_MANAGEMENT_MODULES = {"model_files", "doc_man"}
ROW_SEGMENT_RE = re.compile(r"^row_\d+$", re.IGNORECASE)


class FileMetadataService:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.engine = build_engine(settings)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self._ensure_schema()
        self.storage_root = Path(settings.storage_root)
        ok, message = ensure_storage_share_connected(settings)
        if not ok:
            print(f"[FileMetadataService] storage share auto-connect failed: {message}")

    @classmethod
    def from_config(cls, config_path: str | None = None) -> "FileMetadataService":
        return cls(load_settings(config_path))

    def _ensure_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        inspector = inspect(self.engine)
        statements: list[str] = []
        if inspector.has_table("file_records"):
            columns = {str(col.get("name") or "") for col in inspector.get_columns("file_records")}
            if "storage_rel_path" not in columns:
                statements.append("ALTER TABLE file_records ADD COLUMN storage_rel_path VARCHAR(500) NULL AFTER storage_path")
            if "category_name" not in columns:
                statements.append("ALTER TABLE file_records ADD COLUMN category_name VARCHAR(255) NULL AFTER updated_at")
            if "work_condition" not in columns:
                statements.append("ALTER TABLE file_records ADD COLUMN work_condition VARCHAR(255) NULL AFTER category_name")
            document_columns = [
                ("document_code", "VARCHAR(255)", "remark"),
                ("document_title", "VARCHAR(500)", "document_code"),
                ("design_stage_code", "VARCHAR(50)", "document_title"),
                ("design_stage_name", "VARCHAR(100)", "design_stage_code"),
                ("discipline_code", "VARCHAR(50)", "design_stage_name"),
                ("discipline_name", "VARCHAR(100)", "discipline_code"),
                ("file_class_code", "VARCHAR(50)", "discipline_name"),
                ("file_class_name", "VARCHAR(100)", "file_class_code"),
                ("asset_unit_code", "VARCHAR(50)", "file_class_name"),
                ("asset_unit_name", "VARCHAR(100)", "asset_unit_code"),
                ("module_unit_code", "VARCHAR(50)", "asset_unit_name"),
                ("module_unit_name", "VARCHAR(100)", "module_unit_code"),
                ("drawing_no", "VARCHAR(50)", "module_unit_name"),
                ("sub_sequence", "VARCHAR(50)", "drawing_no"),
                ("recognition_status", "VARCHAR(50)", "sub_sequence"),
                ("recognition_message", "VARCHAR(500)", "recognition_status"),
            ]
            for name, sql_type, after in document_columns:
                if name not in columns:
                    statements.append(f"ALTER TABLE file_records ADD COLUMN {name} {sql_type} NULL AFTER {after}")
            file_indexes = {str(idx.get("name") or "") for idx in inspector.get_indexes("file_records")}
            if "ix_file_records_module_facility_deleted_path" not in file_indexes:
                statements.append(
                    "CREATE INDEX ix_file_records_module_facility_deleted_path "
                    "ON file_records (module_code, facility_code, is_deleted, logical_path)"
                )

        if inspector.has_table("document_rebuild_directories"):
            rebuild_columns = {
                str(col.get("name") or "")
                for col in inspector.get_columns("document_rebuild_directories")
            }
            if "project_type" not in rebuild_columns:
                statements.append(
                    "ALTER TABLE document_rebuild_directories "
                    "ADD COLUMN project_type VARCHAR(50) NULL AFTER facility_code"
                )
            if "summary_text" not in rebuild_columns:
                statements.append(
                    "ALTER TABLE document_rebuild_directories "
                    "ADD COLUMN summary_text TEXT NULL AFTER project_year"
                )
            rebuild_indexes = {
                str(idx.get("name") or "")
                for idx in inspector.get_indexes("document_rebuild_directories")
            }
            if "ix_document_rebuild_dirs_facility_type_deleted_sort" not in rebuild_indexes:
                statements.append(
                    "CREATE INDEX ix_document_rebuild_dirs_facility_type_deleted_sort "
                    "ON document_rebuild_directories "
                    "(facility_code, project_type, is_deleted, sort_order, seq_no)"
                )

        if statements:
            with self.engine.begin() as conn:
                for sql in statements:
                    conn.exec_driver_sql(sql)

        if not inspector.has_table("platform_load_information_items"):
            return

        load_columns = {str(col.get("name") or "") for col in inspector.get_columns("platform_load_information_items")}
        load_statements: list[str] = []
        if "dry_weight_mt" not in load_columns:
            load_statements.append("ALTER TABLE platform_load_information_items ADD COLUMN dry_weight_mt VARCHAR(100) NULL AFTER rebuild_content")
        if "dry_center_xyz" not in load_columns:
            load_statements.append("ALTER TABLE platform_load_information_items ADD COLUMN dry_center_xyz VARCHAR(255) NULL AFTER weight_delta_mt")
        for name, after in [
            ("op_fx_kn", "center_radius_m"),
            ("op_fy_kn", "op_fx_kn"),
            ("op_fz_kn", "op_fy_kn"),
            ("op_mx_kn_m", "op_fz_kn"),
            ("op_my_kn_m", "op_mx_kn_m"),
            ("op_mz_kn_m", "op_my_kn_m"),
        ]:
            if name not in load_columns:
                load_statements.append(f"ALTER TABLE platform_load_information_items ADD COLUMN {name} VARCHAR(100) NULL AFTER {after}")

        if load_statements:
            with self.engine.begin() as conn:
                for sql in load_statements:
                    conn.exec_driver_sql(sql)

    def seed_file_types(self) -> None:
        with self.session_factory() as session:
            existing = {item.code: item for item in session.execute(select(FileType)).scalars().all()}
            changed = False
            for index, item in enumerate(DEFAULT_FILE_TYPES, start=1):
                row = existing.get(item["code"])
                if row is None:
                    session.add(
                        FileType(
                            code=item["code"],
                            name=item["name"],
                            description=item.get("description"),
                            sort_order=index,
                            is_active=True,
                        )
                    )
                    changed = True
                else:
                    if row.name != item["name"] or row.description != item.get("description") or row.sort_order != index:
                        row.name = item["name"]
                        row.description = item.get("description")
                        row.sort_order = index
                        changed = True
            if changed:
                session.commit()

    def seed_auth_roles(self) -> None:
        with self.session_factory() as session:
            existing = {item.code: item for item in session.execute(select(AuthRole)).scalars().all()}
            changed = False
            for index, item in enumerate(DEFAULT_AUTH_ROLES, start=1):
                row = existing.get(item["code"])
                if row is None:
                    session.add(
                        AuthRole(
                            code=item["code"],
                            name=item["name"],
                            description=item.get("description"),
                            sort_order=index * 10,
                            is_active=True,
                        )
                    )
                    changed = True
                else:
                    sort_order = index * 10
                    if row.name != item["name"] or row.description != item.get("description") or row.sort_order != sort_order:
                        row.name = item["name"]
                        row.description = item.get("description")
                        row.sort_order = sort_order
                        changed = True
            if changed:
                session.commit()

    def seed_document_categories(self) -> None:
        with self.session_factory() as session:
            existing = {item.code: item for item in session.execute(select(DocumentCategory)).scalars().all()}
            changed = False
            for item in DEFAULT_DOCUMENT_CATEGORIES:
                code = str(item["code"])
                row = existing.get(code)
                if row is None:
                    session.add(
                        DocumentCategory(
                            scope_code=str(item.get("scope_code") or ""),
                            parent_code=(str(item.get("parent_code") or "").strip() or None),
                            code=code,
                            name=str(item.get("name") or code),
                            discipline_code=(str(item.get("discipline_code") or "").strip() or None),
                            file_class_code=(str(item.get("file_class_code") or "").strip() or None),
                            table_key=(str(item.get("table_key") or "").strip() or None),
                            sort_order=int(item.get("sort_order") or 0),
                            is_active=True,
                        )
                    )
                    changed = True
                    continue
                for attr in ("scope_code", "code", "name", "discipline_code", "file_class_code", "table_key"):
                    new_value = str(item.get(attr) or "").strip() or None
                    if attr in ("scope_code", "code", "name"):
                        new_value = new_value or code
                    if getattr(row, attr) != new_value:
                        setattr(row, attr, new_value)
                        changed = True
                parent_code = str(item.get("parent_code") or "").strip() or None
                if row.parent_code != parent_code:
                    row.parent_code = parent_code
                    changed = True
                sort_order = int(item.get("sort_order") or 0)
                if row.sort_order != sort_order:
                    row.sort_order = sort_order
                    changed = True
                if not row.is_active:
                    row.is_active = True
                    changed = True
            if changed:
                session.commit()

    def list_document_categories(self, scope_code: str | None = None) -> list[dict]:
        with self.session_factory() as session:
            stmt = select(DocumentCategory).where(DocumentCategory.is_active.is_(True))
            if scope_code:
                stmt = stmt.where(DocumentCategory.scope_code == scope_code)
            stmt = stmt.order_by(DocumentCategory.sort_order.asc(), DocumentCategory.id.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._document_category_to_dict(row) for row in rows]

    def list_rebuild_directories(self, facility_code: str, project_type: str | None = None) -> list[dict]:
        code = (facility_code or "").strip()
        if not code:
            return []
        ptype = (project_type or "").strip() or None
        with self.session_factory() as session:
            stmt = (
                select(DocumentRebuildDirectory)
                .where(DocumentRebuildDirectory.facility_code == code)
                .where(DocumentRebuildDirectory.is_deleted.is_(False))
            )
            if ptype:
                if ptype == "history_rebuild":
                    stmt = stmt.where(
                        or_(
                            DocumentRebuildDirectory.project_type == ptype,
                            DocumentRebuildDirectory.project_type.is_(None),
                        )
                    )
                else:
                    stmt = stmt.where(DocumentRebuildDirectory.project_type == ptype)
            stmt = stmt.order_by(DocumentRebuildDirectory.sort_order.asc(), DocumentRebuildDirectory.seq_no.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._rebuild_directory_to_dict(row) for row in rows]

    def create_rebuild_directory(
        self,
        facility_code: str,
        *,
        project_type: str | None = None,
        directory_name: str | None = None,
        project_name: str | None = None,
        project_year: str | None = None,
        summary_text: str | None = None,
    ) -> dict:
        code = (facility_code or "").strip()
        if not code:
            raise ValueError("facility_code is required")
        ptype = (project_type or "").strip() or "history_rebuild"
        with self.session_factory() as session:
            with session.begin():
                existing = session.execute(
                    select(DocumentRebuildDirectory)
                    .where(DocumentRebuildDirectory.facility_code == code)
                    .where(
                        or_(
                            DocumentRebuildDirectory.project_type == ptype,
                            DocumentRebuildDirectory.project_type.is_(None),
                        )
                        if ptype == "history_rebuild"
                        else DocumentRebuildDirectory.project_type == ptype
                    )
                    .where(DocumentRebuildDirectory.is_deleted.is_(False))
                    .with_for_update()
                ).scalars().all()
                next_seq = max([int(row.seq_no or 0) for row in existing] or [0]) + 1
                name = (directory_name or "").strip() or f"第{next_seq}次改造项目"
                row = DocumentRebuildDirectory(
                    facility_code=code,
                    project_type=ptype,
                    seq_no=next_seq,
                    directory_name=name,
                    project_name=(project_name or "").strip() or name,
                    project_year=(project_year or "").strip() or None,
                    summary_text=(summary_text or "").strip() or None,
                    sort_order=next_seq * 10,
                    is_deleted=False,
                )
                session.add(row)
            session.refresh(row)
            return self._rebuild_directory_to_dict(row)

    def update_rebuild_directory(self, directory_id: int, **values) -> dict:
        with self.session_factory() as session:
            row = session.get(DocumentRebuildDirectory, int(directory_id))
            if row is None or row.is_deleted:
                raise ValueError(f"Document rebuild directory not found: {directory_id}")
            for key in ("directory_name", "project_name", "project_year", "summary_text"):
                if key in values:
                    setattr(row, key, (str(values.get(key) or "").strip() or None))
            if not row.directory_name:
                row.directory_name = f"第{row.seq_no}次改造项目"
            row.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(row)
            return self._rebuild_directory_to_dict(row)

    def delete_rebuild_directory(self, directory_id: int) -> None:
        with self.session_factory() as session:
            row = session.get(DocumentRebuildDirectory, int(directory_id))
            if row is None:
                raise ValueError(f"Document rebuild directory not found: {directory_id}")
            row.is_deleted = True
            row.updated_at = datetime.utcnow()
            session.commit()

    def delete_rebuild_directory_with_files(
        self,
        directory_id: int,
        *,
        module_code: str,
        logical_path_prefix: str,
        facility_code: str | None = None,
    ) -> int:
        prefix = self._normalize_logical_path(logical_path_prefix)
        with self.session_factory() as session:
            with session.begin():
                directory = session.get(
                    DocumentRebuildDirectory,
                    int(directory_id),
                    with_for_update=True,
                )
                if directory is None:
                    raise ValueError(f"Document rebuild directory not found: {directory_id}")
                directory.is_deleted = True
                directory.updated_at = datetime.utcnow()

                stmt = (
                    select(FileRecord)
                    .where(FileRecord.module_code == module_code)
                    .where(FileRecord.is_deleted.is_(False))
                )
                prefix_condition = self._logical_path_prefix_condition(prefix)
                if prefix_condition is not None:
                    stmt = stmt.where(prefix_condition)
                if facility_code:
                    stmt = stmt.where(FileRecord.facility_code == facility_code)
                rows = session.execute(stmt.with_for_update()).scalars().all()
                now = datetime.utcnow()
                for row in rows:
                    row.is_deleted = True
                    row.updated_at = now
                return len(rows)

    def list_file_types(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.execute(select(FileType).order_by(FileType.sort_order, FileType.id)).scalars().all()
            return [self._file_type_to_dict(row) for row in rows]

    def upload_file(
        self,
        local_path: str,
        *,
        file_type_code: str,
        module_code: str,
        logical_path: str | None = None,
        facility_code: str | None = None,
        category_name: str | None = None,
        work_condition: str | None = None,
        remark: str | None = None,
        source_modified_at: datetime | None = None,
    ) -> dict:
        source = Path(local_path).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Local file not found: {source}")

        normalized_facility = (facility_code or "").strip() or None
        normalized_logical = self._normalize_logical_path(logical_path)
        normalized_category = (category_name or "").strip() or None
        normalized_work_condition = (work_condition or "").strip() or None
        stored = self._store_file(
            source,
            module_code=module_code,
            logical_path=normalized_logical,
            facility_code=normalized_facility,
            category_name=normalized_category,
        )
        if source_modified_at is None:
            source_modified_at = datetime.fromtimestamp(source.stat().st_mtime)
        parsed_meta = parse_document_code_from_name(source.name)
        if normalized_category is None and parsed_meta.get("file_class_name"):
            normalized_category = str(parsed_meta.get("file_class_name") or "").strip() or None
        if normalized_category is None and module_code == "doc_man":
            normalized_category = "未分类/其他"

        try:
            with self.session_factory() as session:
                with session.begin():
                    file_type = session.execute(
                        select(FileType).where(FileType.code == file_type_code)
                    ).scalar_one_or_none()
                    if file_type is None:
                        raise ValueError(f"Unknown file type code: {file_type_code}")

                    record = FileRecord(
                        original_name=source.name,
                        stored_name=stored["stored_name"],
                        file_ext=source.suffix.lower().lstrip("."),
                        file_type_id=file_type.id,
                        module_code=module_code,
                        logical_path=normalized_logical,
                        facility_code=normalized_facility,
                        storage_path=stored["absolute_path"],
                        storage_rel_path=stored["relative_path"],
                        file_size=stored["size"],
                        file_hash=stored["sha256"],
                        source_modified_at=source_modified_at,
                        category_name=normalized_category,
                        work_condition=normalized_work_condition,
                        remark=(remark or "").strip() or None,
                        document_code=(parsed_meta.get("document_code") or None),
                        document_title=(parsed_meta.get("document_title") or None),
                        design_stage_code=(parsed_meta.get("design_stage_code") or None),
                        design_stage_name=(parsed_meta.get("design_stage_name") or None),
                        discipline_code=(parsed_meta.get("discipline_code") or None),
                        discipline_name=(parsed_meta.get("discipline_name") or None),
                        file_class_code=(parsed_meta.get("file_class_code") or None),
                        file_class_name=(parsed_meta.get("file_class_name") or None),
                        asset_unit_code=(parsed_meta.get("asset_unit_code") or None),
                        asset_unit_name=(parsed_meta.get("asset_unit_name") or None),
                        module_unit_code=(parsed_meta.get("module_unit_code") or None),
                        module_unit_name=(parsed_meta.get("module_unit_name") or None),
                        drawing_no=(parsed_meta.get("drawing_no") or None),
                        sub_sequence=(parsed_meta.get("sub_sequence") or None),
                        recognition_status=(parsed_meta.get("recognition_status") or None),
                        recognition_message=(parsed_meta.get("recognition_message") or None),
                        is_deleted=False,
                    )
                    session.add(record)
                session.refresh(record)
                session.refresh(file_type)
                return self._record_to_dict(record)
        except Exception:
            stored_path = Path(stored["absolute_path"])
            try:
                if stored_path.exists():
                    stored_path.unlink()
                    self._cleanup_empty_parents(stored_path.parent)
            except Exception:
                pass
            raise

    def list_files(
        self,
        *,
        file_type_code: str | None = None,
        module_code: str | None = None,
        logical_path: str | None = None,
        logical_path_prefix: str | None = None,
        logical_path_prefixes: list[str] | None = None,
        facility_code: str | None = None,
        document_code_query: str | None = None,
        document_title_query: str | None = None,
        include_deleted: bool = False,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict]:
        with self.session_factory() as session:
            stmt = select(FileRecord).options(joinedload(FileRecord.file_type))
            if file_type_code:
                stmt = stmt.join(FileRecord.file_type).where(FileType.code == file_type_code)
            if module_code:
                stmt = stmt.where(FileRecord.module_code == module_code)
            if logical_path:
                stmt = stmt.where(FileRecord.logical_path == self._normalize_logical_path(logical_path))
            elif logical_path_prefixes:
                prefix_conditions = [
                    condition
                    for condition in (
                        self._logical_path_prefix_condition(prefix)
                        for prefix in logical_path_prefixes
                    )
                    if condition is not None
                ]
                if prefix_conditions:
                    stmt = stmt.where(or_(*prefix_conditions))
            elif logical_path_prefix:
                prefix = self._normalize_logical_path(logical_path_prefix)
                prefix_condition = self._logical_path_prefix_condition(prefix)
                if prefix_condition is not None:
                    stmt = stmt.where(prefix_condition)
            if facility_code:
                stmt = stmt.where(FileRecord.facility_code == facility_code)
            code_pattern = self._contains_like_pattern(document_code_query)
            if code_pattern:
                stmt = stmt.where(
                    or_(
                        FileRecord.document_code.like(code_pattern, escape="\\"),
                        FileRecord.logical_path.like(code_pattern, escape="\\"),
                        FileRecord.original_name.like(code_pattern, escape="\\"),
                    )
                )
            title_pattern = self._contains_like_pattern(document_title_query)
            if title_pattern:
                stmt = stmt.where(
                    or_(
                        FileRecord.document_title.like(title_pattern, escape="\\"),
                        FileRecord.original_name.like(title_pattern, escape="\\"),
                        FileRecord.logical_path.like(title_pattern, escape="\\"),
                    )
                )
            if not include_deleted:
                stmt = stmt.where(FileRecord.is_deleted.is_(False))
            stmt = stmt.order_by(FileRecord.uploaded_at.desc(), FileRecord.updated_at.desc(), FileRecord.id.desc())
            if offset is not None:
                stmt = stmt.offset(max(0, int(offset)))
            if limit is not None:
                stmt = stmt.limit(max(0, int(limit)))
            rows = session.execute(stmt).scalars().all()
            return [self._record_to_dict(row) for row in rows]

    def count_files(
        self,
        *,
        file_type_code: str | None = None,
        module_code: str | None = None,
        logical_path: str | None = None,
        logical_path_prefix: str | None = None,
        logical_path_prefixes: list[str] | None = None,
        facility_code: str | None = None,
        document_code_query: str | None = None,
        document_title_query: str | None = None,
        include_deleted: bool = False,
    ) -> int:
        with self.session_factory() as session:
            stmt = select(func.count(FileRecord.id))
            if file_type_code:
                stmt = stmt.join(FileRecord.file_type).where(FileType.code == file_type_code)
            if module_code:
                stmt = stmt.where(FileRecord.module_code == module_code)
            if logical_path:
                stmt = stmt.where(FileRecord.logical_path == self._normalize_logical_path(logical_path))
            elif logical_path_prefixes:
                prefix_conditions = [
                    condition
                    for condition in (
                        self._logical_path_prefix_condition(prefix)
                        for prefix in logical_path_prefixes
                    )
                    if condition is not None
                ]
                if prefix_conditions:
                    stmt = stmt.where(or_(*prefix_conditions))
            elif logical_path_prefix:
                prefix = self._normalize_logical_path(logical_path_prefix)
                prefix_condition = self._logical_path_prefix_condition(prefix)
                if prefix_condition is not None:
                    stmt = stmt.where(prefix_condition)
            if facility_code:
                stmt = stmt.where(FileRecord.facility_code == facility_code)
            code_pattern = self._contains_like_pattern(document_code_query)
            if code_pattern:
                stmt = stmt.where(
                    or_(
                        FileRecord.document_code.like(code_pattern, escape="\\"),
                        FileRecord.logical_path.like(code_pattern, escape="\\"),
                        FileRecord.original_name.like(code_pattern, escape="\\"),
                    )
                )
            title_pattern = self._contains_like_pattern(document_title_query)
            if title_pattern:
                stmt = stmt.where(
                    or_(
                        FileRecord.document_title.like(title_pattern, escape="\\"),
                        FileRecord.original_name.like(title_pattern, escape="\\"),
                        FileRecord.logical_path.like(title_pattern, escape="\\"),
                    )
                )
            if not include_deleted:
                stmt = stmt.where(FileRecord.is_deleted.is_(False))
            return int(session.execute(stmt).scalar() or 0)

    def download_file(self, record_id: int, target_dir: str, *, download_name: str | None = None) -> str:
        with self.session_factory() as session:
            row = session.get(FileRecord, record_id)
            if row is None or row.is_deleted:
                raise ValueError(f"File record not found: {record_id}")
            source = self._resolve_row_storage_path(row)
            if not source.exists():
                raise FileNotFoundError(f"Stored file missing on disk: {source}")
            target_root = Path(target_dir).expanduser().resolve()
            target_root.mkdir(parents=True, exist_ok=True)
            target_name = self._safe_filename(self._strip_save_dialog_wildcard(download_name or row.original_name))
            target = target_root / target_name
            shutil.copy2(source, target)
            return str(target)

    def soft_delete(self, record_id: int) -> None:
        with self.session_factory() as session:
            with session.begin():
                row = session.get(FileRecord, record_id, with_for_update=True)
                if row is None:
                    raise ValueError(f"File record not found: {record_id}")
                row.is_deleted = True
                row.updated_at = datetime.utcnow()

    def soft_delete_files_by_prefix(
        self,
        *,
        module_code: str,
        logical_path_prefix: str,
        facility_code: str | None = None,
        file_type_code: str | None = None,
    ) -> int:
        prefix = self._normalize_logical_path(logical_path_prefix)
        with self.session_factory() as session:
            with session.begin():
                stmt = select(FileRecord).where(FileRecord.module_code == module_code)
                if file_type_code:
                    stmt = stmt.join(FileRecord.file_type).where(FileType.code == file_type_code)
                prefix_condition = self._logical_path_prefix_condition(prefix)
                if prefix_condition is not None:
                    stmt = stmt.where(prefix_condition)
                if facility_code:
                    stmt = stmt.where(FileRecord.facility_code == facility_code)
                stmt = stmt.where(FileRecord.is_deleted.is_(False)).with_for_update()
                rows = session.execute(stmt).scalars().all()
                now = datetime.utcnow()
                for row in rows:
                    row.is_deleted = True
                    row.updated_at = now
                return len(rows)

    def hard_delete(self, record_id: int) -> None:
        with self.session_factory() as session:
            row = session.get(FileRecord, int(record_id))
            if row is None:
                raise ValueError(f"File record not found: {record_id}")
            target_path = self._resolve_row_storage_path(row)
            session.delete(row)
            session.commit()

        if target_path and target_path.exists():
            try:
                target_path.unlink()
            except FileNotFoundError:
                pass
            except Exception:
                pass
            self._cleanup_empty_parents(target_path.parent)

    def update_file_record(
        self,
        record_id: int,
        *,
        category_name: str | object = _UNSET,
        work_condition: str | object = _UNSET,
        remark: str | object = _UNSET,
        expected_updated_at: datetime | object = _UNSET,
    ) -> dict:
        with self.session_factory() as session:
            with session.begin():
                row = session.get(FileRecord, int(record_id), with_for_update=True)
                if row is None:
                    raise ValueError(f"File record not found: {record_id}")
                if expected_updated_at is not _UNSET and not self._same_lock_timestamp(
                    row.updated_at,
                    expected_updated_at,
                ):
                    raise ValueError("文件记录已被其他用户修改，请刷新后重试。")
                if category_name is not _UNSET:
                    row.category_name = (str(category_name or "").strip() or None)
                if work_condition is not _UNSET:
                    row.work_condition = (str(work_condition or "").strip() or None)
                if remark is not _UNSET:
                    row.remark = (str(remark or "").strip() or None)
                row.updated_at = datetime.utcnow()
            session.refresh(row)
            return self._record_to_dict(row)

    def get_facility_profile(self, facility_code: str) -> dict | None:
        code = (facility_code or "").strip()
        if not code:
            return None
        with self.session_factory() as session:
            row = session.execute(
                select(FacilityProfile).where(FacilityProfile.facility_code == code)
            ).scalar_one_or_none()
            return self._facility_profile_to_dict(row) if row else None

    def list_facility_profiles(self) -> list[dict]:
        with self.session_factory() as session:
            rows = session.execute(
                select(FacilityProfile).order_by(
                    FacilityProfile.id.asc(),
                )
            ).scalars().all()
            return [self._facility_profile_to_dict(row) for row in rows]

    def upsert_facility_profile(self, facility_code: str, **values) -> dict:
        code = (facility_code or "").strip()
        if not code:
            raise ValueError("facility_code is required")
        with self.session_factory() as session:
            row = session.execute(
                select(FacilityProfile).where(FacilityProfile.facility_code == code)
            ).scalar_one_or_none()
            if row is None:
                row = FacilityProfile(facility_code=code)
                session.add(row)
            for key in (
                "facility_name",
                "branch",
                "op_company",
                "oilfield",
                "facility_type",
                "category",
                "start_time",
                "design_life",
                "description_text",
            ):
                if key in values:
                    setattr(row, key, (values.get(key) or "").strip() or None)
            row.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(row)
            return self._facility_profile_to_dict(row)

    def list_inspection_projects(
        self,
        *,
        facility_code: str,
        project_type: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict]:
        code = (facility_code or "").strip()
        if not code:
            return []
        with self.session_factory() as session:
            stmt = select(InspectionProject).where(InspectionProject.facility_code == code)
            if project_type:
                stmt = stmt.where(InspectionProject.project_type == project_type)
            if not include_deleted:
                stmt = stmt.where(InspectionProject.is_deleted.is_(False))
            stmt = stmt.order_by(
                InspectionProject.sort_order.asc(),
                InspectionProject.project_year.asc(),
                InspectionProject.created_at.asc(),
                InspectionProject.id.asc(),
            )
            rows = session.execute(stmt).scalars().all()
            return [self._inspection_project_to_dict(row) for row in rows]

    def create_inspection_project(
        self,
        *,
        facility_code: str,
        project_type: str,
        project_name: str,
        project_year: str | None = None,
        event_date: str | None = None,
        summary_text: str | None = None,
        sort_order: int | None = None,
    ) -> dict:
        code = (facility_code or "").strip()
        ptype = (project_type or "").strip()
        pname = (project_name or "").strip()
        if not code or not ptype or not pname:
            raise ValueError("facility_code, project_type and project_name are required")
        with self.session_factory() as session:
            if sort_order is None:
                existing = session.execute(
                    select(InspectionProject.sort_order)
                    .where(
                        InspectionProject.facility_code == code,
                        InspectionProject.project_type == ptype,
                    )
                    .order_by(InspectionProject.sort_order.desc())
                    .limit(1)
                ).scalar_one_or_none()
                sort_order = (existing or 0) + 1
            row = InspectionProject(
                facility_code=code,
                project_type=ptype,
                project_name=pname,
                project_year=(project_year or "").strip() or None,
                event_date=(event_date or "").strip() or None,
                summary_text=(summary_text or "").strip() or None,
                sort_order=int(sort_order),
                is_deleted=False,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._inspection_project_to_dict(row)

    def update_inspection_project(self, project_id: int, **values) -> dict:
        with self.session_factory() as session:
            row = session.get(InspectionProject, int(project_id))
            if row is None:
                raise ValueError(f"Inspection project not found: {project_id}")
            for key in ("project_name", "project_year", "event_date", "summary_text", "sort_order"):
                if key in values:
                    value = values.get(key)
                    if key == "sort_order":
                        setattr(row, key, int(value or 0))
                    else:
                        setattr(row, key, (value or "").strip() or None)
            row.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(row)
            return self._inspection_project_to_dict(row)

    def soft_delete_inspection_project(self, project_id: int) -> None:
        with self.session_factory() as session:
            row = session.get(InspectionProject, int(project_id))
            if row is None:
                raise ValueError(f"Inspection project not found: {project_id}")
            row.is_deleted = True
            row.updated_at = datetime.utcnow()
            session.commit()

    def soft_delete_inspection_project_with_files(
        self,
        project_id: int,
        *,
        module_code: str,
        logical_path_prefix: str,
        facility_code: str | None = None,
    ) -> int:
        prefix = self._normalize_logical_path(logical_path_prefix)
        with self.session_factory() as session:
            with session.begin():
                project = session.get(InspectionProject, int(project_id), with_for_update=True)
                if project is None:
                    raise ValueError(f"Inspection project not found: {project_id}")
                project.is_deleted = True
                project.updated_at = datetime.utcnow()

                stmt = (
                    select(FileRecord)
                    .where(FileRecord.module_code == module_code)
                    .where(FileRecord.is_deleted.is_(False))
                )
                prefix_condition = self._logical_path_prefix_condition(prefix)
                if prefix_condition is not None:
                    stmt = stmt.where(prefix_condition)
                if facility_code:
                    stmt = stmt.where(FileRecord.facility_code == facility_code)
                rows = session.execute(stmt.with_for_update()).scalars().all()
                now = datetime.utcnow()
                for row in rows:
                    row.is_deleted = True
                    row.updated_at = now
                return len(rows)

    def list_inspection_findings(self, project_id: int, *, include_deleted: bool = False) -> list[dict]:
        with self.session_factory() as session:
            stmt = select(InspectionFinding).where(InspectionFinding.project_id == int(project_id))
            if not include_deleted:
                stmt = stmt.where(InspectionFinding.is_deleted.is_(False))
            stmt = stmt.order_by(InspectionFinding.sort_order.asc(), InspectionFinding.id.asc())
            rows = session.execute(stmt).scalars().all()
            return [self._inspection_finding_to_dict(row) for row in rows]

    def replace_inspection_findings(self, project_id: int, rows: list[dict]) -> list[dict]:
        with self.session_factory() as session:
            project = session.get(InspectionProject, int(project_id))
            if project is None:
                raise ValueError(f"Inspection project not found: {project_id}")
            for row in session.execute(
                select(InspectionFinding).where(InspectionFinding.project_id == int(project_id))
            ).scalars().all():
                session.delete(row)
            for index, item in enumerate(rows, start=1):
                finding = InspectionFinding(
                    project_id=int(project_id),
                    item_code=(item.get("item_code") or item.get("node") or "").strip() or None,
                    item_type=(item.get("item_type") or "").strip() or None,
                    risk_level=(item.get("risk_level") or item.get("level") or "").strip() or None,
                    conclusion=(item.get("conclusion") or "").strip() or None,
                    sort_order=int(item.get("sort_order") or index),
                    is_deleted=False,
                )
                session.add(finding)
            session.commit()
        return self.list_inspection_findings(int(project_id))

    def list_platform_load_information_items(self, facility_code: str) -> list[dict]:
        code = (facility_code or "").strip()
        if not code:
            return []
        with self.session_factory() as session:
            stmt = (
                select(PlatformLoadInformationItem)
                .where(PlatformLoadInformationItem.facility_code == code)
                .order_by(PlatformLoadInformationItem.sort_order.asc(), PlatformLoadInformationItem.id.asc())
            )
            rows = session.execute(stmt).scalars().all()
            return [self._platform_load_information_item_to_dict(row) for row in rows]

    def replace_platform_load_information_items(self, facility_code: str, rows: list[dict]) -> list[dict]:
        code = (facility_code or "").strip()
        if not code:
            raise ValueError("facility_code is required")
        with self.session_factory() as session:
            for row in session.execute(
                select(PlatformLoadInformationItem).where(PlatformLoadInformationItem.facility_code == code)
            ).scalars().all():
                session.delete(row)

            for index, item in enumerate(rows, start=1):
                record = PlatformLoadInformationItem(
                    facility_code=code,
                    seq_no=int(item.get("seq_no") or item.get("seq") or item.get("sort_order") or index - 1),
                    project_name=(item.get("project_name") or "").strip() or None,
                    rebuild_time=(item.get("rebuild_time") or "").strip() or None,
                    rebuild_content=(item.get("rebuild_content") or "").strip() or None,
                    dry_weight_mt=(item.get("dry_weight_mt") or "").strip() or None,
                    total_weight_mt=(item.get("total_weight_mt") or "").strip() or None,
                    weight_limit_mt=(item.get("weight_limit_mt") or "").strip() or None,
                    weight_delta_mt=(item.get("weight_delta_mt") or "").strip() or None,
                    dry_center_xyz=(item.get("dry_center_xyz") or "").strip() or None,
                    center_xyz=(item.get("center_xyz") or "").strip() or None,
                    center_radius_m=(item.get("center_radius_m") or "").strip() or None,
                    op_fx_kn=(item.get("op_fx_kn") or "").strip() or None,
                    op_fy_kn=(item.get("op_fy_kn") or "").strip() or None,
                    op_fz_kn=(item.get("op_fz_kn") or "").strip() or None,
                    op_mx_kn_m=(item.get("op_mx_kn_m") or "").strip() or None,
                    op_my_kn_m=(item.get("op_my_kn_m") or "").strip() or None,
                    op_mz_kn_m=(item.get("op_mz_kn_m") or "").strip() or None,
                    fx_kn=(item.get("fx_kn") or "").strip() or None,
                    fy_kn=(item.get("fy_kn") or "").strip() or None,
                    fz_kn=(item.get("fz_kn") or "").strip() or None,
                    mx_kn_m=(item.get("mx_kn_m") or "").strip() or None,
                    my_kn_m=(item.get("my_kn_m") or "").strip() or None,
                    mz_kn_m=(item.get("mz_kn_m") or "").strip() or None,
                    safety_op=(item.get("safety_op") or "").strip() or None,
                    safety_extreme=(item.get("safety_extreme") or "").strip() or None,
                    overall_assessment=(item.get("overall_assessment") or "").strip() or None,
                    assessment_org=(item.get("assessment_org") or "").strip() or None,
                    sort_order=int(item.get("sort_order") or index),
                )
                session.add(record)

            session.commit()
        return self.list_platform_load_information_items(code)

    def save_platform_load_summary_snapshot(
        self,
        rows: list[dict],
        *,
        snapshot_key: str = "latest",
        snapshot_name: str | None = None,
    ) -> dict:
        key = (snapshot_key or "latest").strip() or "latest"
        normalized_rows = list(rows or [])
        with self.session_factory() as session:
            record = session.execute(
                select(PlatformLoadSummarySnapshot).where(
                    PlatformLoadSummarySnapshot.snapshot_key == key
                )
            ).scalar_one_or_none()
            if record is None:
                record = PlatformLoadSummarySnapshot(snapshot_key=key)
                session.add(record)
            record.snapshot_name = (snapshot_name or "载荷汇总信息").strip() or None
            record.rows_json = json.dumps(normalized_rows, ensure_ascii=False)
            record.row_count = len(normalized_rows)
            record.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(record)
            return self._platform_load_summary_snapshot_to_dict(record)

    def load_platform_summary_snapshot(self, snapshot_key: str = "latest") -> dict | None:
        key = (snapshot_key or "latest").strip() or "latest"
        with self.session_factory() as session:
            record = session.execute(
                select(PlatformSummarySnapshot).where(
                    PlatformSummarySnapshot.snapshot_key == key
                )
            ).scalar_one_or_none()
            if record is None:
                return None
            return self._platform_summary_snapshot_to_dict(record)

    def save_platform_summary_snapshot(
        self,
        columns: list[str],
        rows: list[list[str]],
        *,
        snapshot_key: str = "latest",
        snapshot_name: str | None = None,
    ) -> dict:
        key = (snapshot_key or "latest").strip() or "latest"
        normalized_columns = [str(col or "") for col in (columns or [])]
        normalized_rows = [[str(cell or "") for cell in row] for row in (rows or [])]
        with self.session_factory() as session:
            record = session.execute(
                select(PlatformSummarySnapshot).where(
                    PlatformSummarySnapshot.snapshot_key == key
                )
            ).scalar_one_or_none()
            if record is None:
                record = PlatformSummarySnapshot(snapshot_key=key)
                session.add(record)
            record.snapshot_name = (snapshot_name or "平台汇总信息").strip() or None
            record.columns_json = json.dumps(normalized_columns, ensure_ascii=False)
            record.rows_json = json.dumps(normalized_rows, ensure_ascii=False)
            record.row_count = len(normalized_rows)
            record.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(record)
            return self._platform_summary_snapshot_to_dict(record)

    def _store_file(
        self,
        source: Path,
        *,
        module_code: str,
        logical_path: str | None,
        facility_code: str | None,
        category_name: str | None,
    ) -> dict:
        target_dir = self._build_target_dir(
            module_code=module_code,
            logical_path=logical_path,
            facility_code=facility_code,
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        stored_name = self._build_stored_name(
            source.name,
            target_dir=target_dir,
            keep_readable=(module_code in FILE_MANAGEMENT_MODULES),
        )
        target = target_dir / stored_name
        shutil.copy2(source, target)
        return {
            "stored_name": stored_name,
            "absolute_path": str(target.resolve()),
            "relative_path": target.relative_to(self.storage_root).as_posix(),
            "size": target.stat().st_size,
            "sha256": self._sha256(target),
        }

    def _build_target_dir(
        self,
        *,
        module_code: str,
        logical_path: str | None,
        facility_code: str | None,
    ) -> Path:
        safe_module = self._safe_segment(module_code or "general")
        logical_segments = self._storage_segments(
            module_code=module_code,
            logical_path=logical_path,
            facility_code=facility_code,
        )
        if module_code in FILE_MANAGEMENT_MODULES:
            return self.storage_root / safe_module / Path(*logical_segments)

        day = datetime.utcnow().strftime("%Y%m%d")
        return self.storage_root / safe_module / Path(*logical_segments) / day

    def _storage_segments(
        self,
        *,
        module_code: str,
        logical_path: str | None,
        facility_code: str | None,
    ) -> list[str]:
        normalized_logical = self._normalize_logical_path(logical_path)
        logical_segments = [self._safe_storage_segment(part) for part in (normalized_logical or "").split("/") if part]
        facility_segment = self._safe_storage_segment(facility_code or "") if facility_code else ""
        if facility_segment:
            if logical_segments and logical_segments[0].casefold() == facility_segment.casefold():
                logical_segments = logical_segments[1:]
            logical_segments.insert(0, facility_segment)
        if module_code in FILE_MANAGEMENT_MODULES and logical_segments and ROW_SEGMENT_RE.match(logical_segments[-1]):
            logical_segments = logical_segments[:-1]
        return logical_segments or ["root"]

    def _build_stored_name(self, original_name: str, *, target_dir: Path, keep_readable: bool) -> str:
        original = str(original_name or "").strip() or "unnamed"
        if not keep_readable:
            stem, suffix = os.path.splitext(original)
            return f"{self._safe_segment(stem)}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}{suffix.lower()}"

        candidate = self._safe_filename(original)
        stem, suffix = os.path.splitext(candidate)
        target = target_dir / candidate
        counter = 1
        while target.exists():
            candidate = f"{stem} ({counter}){suffix}"
            target = target_dir / candidate
            counter += 1
        return candidate

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fp:
            for chunk in iter(lambda: fp.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _normalize_logical_path(logical_path: str | None) -> str | None:
        if logical_path is None:
            return None
        text = str(logical_path).replace("\\", "/").strip().strip("/")
        return text or None

    @staticmethod
    def _contains_like_pattern(value: str | None) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        text = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{text}%"

    @classmethod
    def _logical_path_prefix_condition(cls, logical_path_prefix: str | None):
        prefix = cls._normalize_logical_path(logical_path_prefix)
        if not prefix:
            return None
        return or_(
            FileRecord.logical_path == prefix,
            FileRecord.logical_path.startswith(f"{prefix}/", autoescape=True),
        )

    @staticmethod
    def _normalize_storage_rel_path(storage_rel_path: str | None) -> str | None:
        if storage_rel_path is None:
            return None
        text = str(storage_rel_path).replace("\\", "/").strip().strip("/")
        return text or None

    def _resolve_row_storage_path(self, row: FileRecord) -> Path:
        storage_rel = self._normalize_storage_rel_path(getattr(row, "storage_rel_path", None))
        if storage_rel:
            rel_segments = [segment for segment in storage_rel.split("/") if segment]
            return (self.storage_root / Path(*rel_segments)).resolve()

        raw_storage = str(getattr(row, "storage_path", "") or "").strip()
        raw_path = Path(raw_storage)
        if raw_path.is_absolute():
            return raw_path.resolve()

        return (self.storage_root / raw_path).resolve()

    def _cleanup_empty_parents(self, path: Path) -> None:
        current = path
        stop = self.storage_root.resolve()
        while True:
            try:
                if current == stop or not current.exists():
                    break
                current.rmdir()
                current = current.parent
            except OSError:
                break

    @staticmethod
    def _safe_segment(text: str) -> str:
        filtered = []
        for ch in text.strip():
            if ch.isalnum() or ch in ("-", "_", "."):
                filtered.append(ch)
            else:
                filtered.append("_")
        return "".join(filtered).strip("._") or "default"

    @staticmethod
    def _safe_storage_segment(text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return "default"
        invalid = '<>:"/\\\\|?*'
        filtered = []
        for ch in raw:
            if ord(ch) < 32 or ch in invalid:
                filtered.append("_")
            else:
                filtered.append(ch)
        cleaned = "".join(filtered).strip(" .")
        return cleaned or "default"

    @staticmethod
    def _strip_save_dialog_wildcard(text: str) -> str:
        cleaned = str(text or "").strip()
        while cleaned.endswith(".*") or cleaned.endswith("*"):
            cleaned = cleaned[:-2] if cleaned.endswith(".*") else cleaned[:-1]
            cleaned = cleaned.rstrip(" .")
        return cleaned

    @classmethod
    def _safe_filename(cls, text: str) -> str:
        cleaned = cls._safe_storage_segment(text)
        if cleaned in {"default", ".", ".."}:
            return "unnamed"
        return cleaned

    @staticmethod
    def _file_type_to_dict(row: FileType) -> dict:
        return {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "description": row.description,
            "sort_order": row.sort_order,
            "is_active": row.is_active,
        }

    @staticmethod
    def _utc_to_local_naive(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone().replace(tzinfo=None)

    @staticmethod
    def _same_lock_timestamp(current: datetime | None, expected: object) -> bool:
        if expected in (None, ""):
            return True
        if not isinstance(expected, datetime):
            return False
        current_dt = current.replace(tzinfo=None) if current and current.tzinfo else current
        expected_dt = expected.replace(tzinfo=None) if expected.tzinfo else expected
        if current_dt is None:
            return False
        return abs((current_dt - expected_dt).total_seconds()) < 0.001

    def _record_to_dict(self, row: FileRecord) -> dict:
        uploaded_at = self._utc_to_local_naive(row.uploaded_at)
        updated_at = self._utc_to_local_naive(row.updated_at)
        display_modified_at = uploaded_at or updated_at or row.source_modified_at
        return {
            "id": row.id,
            "original_name": row.original_name,
            "stored_name": row.stored_name,
            "file_ext": row.file_ext,
            "file_type_id": row.file_type_id,
            "file_type_code": row.file_type.code if row.file_type else None,
            "file_type_name": row.file_type.name if row.file_type else None,
            "module_code": row.module_code,
            "logical_path": row.logical_path,
            "facility_code": row.facility_code,
            "storage_path": row.storage_path,
            "storage_rel_path": row.storage_rel_path,
            "file_size": row.file_size,
            "file_hash": row.file_hash,
            "source_modified_at": display_modified_at,
            "source_file_modified_at": row.source_modified_at,
            "uploaded_at": uploaded_at,
            "updated_at": updated_at,
            "lock_updated_at": row.updated_at,
            "category_name": row.category_name,
            "work_condition": row.work_condition,
            "remark": row.remark,
            "document_code": row.document_code,
            "document_title": row.document_title,
            "design_stage_code": row.design_stage_code,
            "design_stage_name": row.design_stage_name,
            "discipline_code": row.discipline_code,
            "discipline_name": row.discipline_name,
            "file_class_code": row.file_class_code,
            "file_class_name": row.file_class_name,
            "asset_unit_code": row.asset_unit_code,
            "asset_unit_name": row.asset_unit_name,
            "module_unit_code": row.module_unit_code,
            "module_unit_name": row.module_unit_name,
            "drawing_no": row.drawing_no,
            "sub_sequence": row.sub_sequence,
            "recognition_status": row.recognition_status,
            "recognition_message": row.recognition_message,
            "is_deleted": row.is_deleted,
        }

    @staticmethod
    def _document_category_to_dict(row: DocumentCategory) -> dict:
        return {
            "id": row.id,
            "scope_code": row.scope_code,
            "parent_code": row.parent_code,
            "code": row.code,
            "name": row.name,
            "discipline_code": row.discipline_code,
            "file_class_code": row.file_class_code,
            "table_key": row.table_key,
            "sort_order": row.sort_order,
            "is_active": row.is_active,
        }

    @staticmethod
    def _rebuild_directory_to_dict(row: DocumentRebuildDirectory) -> dict:
        return {
            "id": row.id,
            "facility_code": row.facility_code,
            "project_type": row.project_type,
            "seq_no": row.seq_no,
            "directory_name": row.directory_name,
            "project_name": row.project_name,
            "project_year": row.project_year,
            "summary_text": row.summary_text,
            "sort_order": row.sort_order,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "is_deleted": row.is_deleted,
        }

    @staticmethod
    def _facility_profile_to_dict(row: FacilityProfile) -> dict:
        return {
            "id": row.id,
            "facility_code": row.facility_code,
            "facility_name": row.facility_name,
            "branch": row.branch,
            "op_company": row.op_company,
            "oilfield": row.oilfield,
            "facility_type": row.facility_type,
            "category": row.category,
            "start_time": row.start_time,
            "design_life": row.design_life,
            "description_text": row.description_text,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _inspection_project_to_dict(row: InspectionProject) -> dict:
        return {
            "id": row.id,
            "facility_code": row.facility_code,
            "project_type": row.project_type,
            "project_name": row.project_name,
            "project_year": row.project_year,
            "event_date": row.event_date,
            "summary_text": row.summary_text,
            "sort_order": row.sort_order,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "is_deleted": row.is_deleted,
        }

    @staticmethod
    def _inspection_finding_to_dict(row: InspectionFinding) -> dict:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "item_code": row.item_code,
            "item_type": row.item_type,
            "risk_level": row.risk_level,
            "conclusion": row.conclusion,
            "sort_order": row.sort_order,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "is_deleted": row.is_deleted,
        }

    @staticmethod
    def _platform_load_information_item_to_dict(row: PlatformLoadInformationItem) -> dict:
        return {
            "id": row.id,
            "facility_code": row.facility_code,
            "seq_no": row.seq_no,
            "project_name": row.project_name,
            "rebuild_time": row.rebuild_time,
            "rebuild_content": row.rebuild_content,
            "dry_weight_mt": row.dry_weight_mt,
            "total_weight_mt": row.total_weight_mt,
            "weight_limit_mt": row.weight_limit_mt,
            "weight_delta_mt": row.weight_delta_mt,
            "dry_center_xyz": row.dry_center_xyz,
            "center_xyz": row.center_xyz,
            "center_radius_m": row.center_radius_m,
            "op_fx_kn": row.op_fx_kn,
            "op_fy_kn": row.op_fy_kn,
            "op_fz_kn": row.op_fz_kn,
            "op_mx_kn_m": row.op_mx_kn_m,
            "op_my_kn_m": row.op_my_kn_m,
            "op_mz_kn_m": row.op_mz_kn_m,
            "fx_kn": row.fx_kn,
            "fy_kn": row.fy_kn,
            "fz_kn": row.fz_kn,
            "mx_kn_m": row.mx_kn_m,
            "my_kn_m": row.my_kn_m,
            "mz_kn_m": row.mz_kn_m,
            "safety_op": row.safety_op,
            "safety_extreme": row.safety_extreme,
            "overall_assessment": row.overall_assessment,
            "assessment_org": row.assessment_org,
            "sort_order": row.sort_order,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _platform_load_summary_snapshot_to_dict(row: PlatformLoadSummarySnapshot) -> dict:
        try:
            rows = json.loads(row.rows_json or "[]")
        except Exception:
            rows = []
        return {
            "id": row.id,
            "snapshot_key": row.snapshot_key,
            "snapshot_name": row.snapshot_name,
            "rows": rows,
            "row_count": row.row_count,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _platform_summary_snapshot_to_dict(row: PlatformSummarySnapshot) -> dict:
        try:
            columns = json.loads(row.columns_json or "[]")
        except Exception:
            columns = []
        try:
            rows = json.loads(row.rows_json or "[]")
        except Exception:
            rows = []
        return {
            "id": row.id,
            "snapshot_key": row.snapshot_key,
            "snapshot_name": row.snapshot_name,
            "columns": columns,
            "rows": rows,
            "row_count": row.row_count,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
