from __future__ import annotations

import hashlib
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, select
from sqlalchemy.orm import joinedload, sessionmaker

from .config import AppSettings, load_settings
from .database import Base, build_engine
from .models import (
    FacilityProfile,
    FileRecord,
    FileType,
    InspectionFinding,
    InspectionProject,
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
        self.storage_root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_config(cls, config_path: str | None = None) -> "FileMetadataService":
        return cls(load_settings(config_path))

    def _ensure_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        inspector = inspect(self.engine)
        if not inspector.has_table("file_records"):
            return

        columns = {str(col.get("name") or "") for col in inspector.get_columns("file_records")}
        statements: list[str] = []
        if "storage_rel_path" not in columns:
            statements.append("ALTER TABLE file_records ADD COLUMN storage_rel_path VARCHAR(500) NULL AFTER storage_path")
        if "category_name" not in columns:
            statements.append("ALTER TABLE file_records ADD COLUMN category_name VARCHAR(255) NULL AFTER updated_at")
        if "work_condition" not in columns:
            statements.append("ALTER TABLE file_records ADD COLUMN work_condition VARCHAR(255) NULL AFTER category_name")

        if statements:
            with self.engine.begin() as conn:
                for sql in statements:
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

        with self.session_factory() as session:
            file_type = session.execute(select(FileType).where(FileType.code == file_type_code)).scalar_one_or_none()
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
                is_deleted=False,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            session.refresh(file_type)
            return self._record_to_dict(record)

    def list_files(
        self,
        *,
        file_type_code: str | None = None,
        module_code: str | None = None,
        logical_path: str | None = None,
        facility_code: str | None = None,
        include_deleted: bool = False,
    ) -> list[dict]:
        with self.session_factory() as session:
            stmt = select(FileRecord).options(joinedload(FileRecord.file_type))
            if file_type_code:
                stmt = stmt.join(FileRecord.file_type).where(FileType.code == file_type_code)
            if module_code:
                stmt = stmt.where(FileRecord.module_code == module_code)
            if logical_path:
                stmt = stmt.where(FileRecord.logical_path == self._normalize_logical_path(logical_path))
            if facility_code:
                stmt = stmt.where(FileRecord.facility_code == facility_code)
            if not include_deleted:
                stmt = stmt.where(FileRecord.is_deleted.is_(False))
            stmt = stmt.order_by(FileRecord.source_modified_at.desc(), FileRecord.uploaded_at.desc(), FileRecord.id.desc())
            rows = session.execute(stmt).scalars().all()
            return [self._record_to_dict(row) for row in rows]

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
            target = target_root / (download_name or row.original_name)
            shutil.copy2(source, target)
            return str(target)

    def soft_delete(self, record_id: int) -> None:
        with self.session_factory() as session:
            row = session.get(FileRecord, record_id)
            if row is None:
                raise ValueError(f"File record not found: {record_id}")
            row.is_deleted = True
            row.updated_at = datetime.utcnow()
            session.commit()

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
    ) -> dict:
        with self.session_factory() as session:
            row = session.get(FileRecord, int(record_id))
            if row is None:
                raise ValueError(f"File record not found: {record_id}")
            if category_name is not _UNSET:
                row.category_name = (str(category_name or "").strip() or None)
            if work_condition is not _UNSET:
                row.work_condition = (str(work_condition or "").strip() or None)
            if remark is not _UNSET:
                row.remark = (str(remark or "").strip() or None)
            row.updated_at = datetime.utcnow()
            session.commit()
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

    def _record_to_dict(self, row: FileRecord) -> dict:
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
            "source_modified_at": row.source_modified_at,
            "uploaded_at": row.uploaded_at,
            "updated_at": row.updated_at,
            "category_name": row.category_name,
            "work_condition": row.work_condition,
            "remark": row.remark,
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
