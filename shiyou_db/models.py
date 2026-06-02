from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class FileType(Base):
    __tablename__ = "file_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    records: Mapped[list["FileRecord"]] = relationship("FileRecord", back_populates="file_type")


class FileRecord(Base):
    __tablename__ = "file_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_ext: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_type_id: Mapped[int] = mapped_column(ForeignKey("file_types.id"), nullable=False)
    module_code: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    logical_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    facility_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_rel_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    category_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_condition: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    design_stage_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    design_stage_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    discipline_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discipline_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_class_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file_class_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset_unit_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    asset_unit_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    module_unit_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    module_unit_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    drawing_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sub_sequence: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recognition_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recognition_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    file_type: Mapped[FileType] = relationship("FileType", back_populates="records")


Index("ix_file_records_type_module_path", FileRecord.file_type_id, FileRecord.module_code, FileRecord.logical_path)
Index("ix_file_records_facility", FileRecord.facility_code)
Index(
    "ix_file_records_module_facility_deleted_path",
    FileRecord.module_code,
    FileRecord.facility_code,
    FileRecord.is_deleted,
    FileRecord.logical_path,
)
Index("ix_file_records_hash", FileRecord.file_hash)
Index("ix_file_records_document_code", FileRecord.document_code)
Index("ix_file_records_recognition", FileRecord.recognition_status)


class DocumentCategory(Base):
    __tablename__ = "document_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope_code: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    discipline_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file_class_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    table_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentRebuildDirectory(Base):
    __tablename__ = "document_rebuild_directories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facility_code: Mapped[str] = mapped_column(String(100), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    directory_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_year: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


Index("ix_document_categories_scope_parent", DocumentCategory.scope_code, DocumentCategory.parent_code)
Index("ix_document_categories_code", DocumentCategory.code)
Index(
    "ix_document_rebuild_dirs_facility_sort",
    DocumentRebuildDirectory.facility_code,
    DocumentRebuildDirectory.project_type,
    DocumentRebuildDirectory.sort_order,
)
Index(
    "ix_document_rebuild_dirs_facility_type_deleted_sort",
    DocumentRebuildDirectory.facility_code,
    DocumentRebuildDirectory.project_type,
    DocumentRebuildDirectory.is_deleted,
    DocumentRebuildDirectory.sort_order,
    DocumentRebuildDirectory.seq_no,
)


class FacilityProfile(Base):
    __tablename__ = "facility_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    facility_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    op_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oilfield: Mapped[str | None] = mapped_column(String(255), nullable=True)
    facility_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    design_life: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class InspectionProject(Base):
    __tablename__ = "inspection_projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facility_code: Mapped[str] = mapped_column(String(100), nullable=False)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_year: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    findings: Mapped[list["InspectionFinding"]] = relationship(
        "InspectionFinding",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class InspectionFinding(Base):
    __tablename__ = "inspection_findings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("inspection_projects.id"), nullable=False)
    item_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    project: Mapped[InspectionProject] = relationship("InspectionProject", back_populates="findings")


class PlatformLoadInformationItem(Base):
    __tablename__ = "platform_load_information_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facility_code: Mapped[str] = mapped_column(String(100), nullable=False)
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rebuild_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rebuild_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    dry_weight_mt: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_weight_mt: Mapped[str | None] = mapped_column(String(100), nullable=True)
    weight_limit_mt: Mapped[str | None] = mapped_column(String(100), nullable=True)
    weight_delta_mt: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dry_center_xyz: Mapped[str | None] = mapped_column(String(255), nullable=True)
    center_xyz: Mapped[str | None] = mapped_column(String(255), nullable=True)
    center_radius_m: Mapped[str | None] = mapped_column(String(100), nullable=True)
    op_fx_kn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    op_fy_kn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    op_fz_kn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    op_mx_kn_m: Mapped[str | None] = mapped_column(String(100), nullable=True)
    op_my_kn_m: Mapped[str | None] = mapped_column(String(100), nullable=True)
    op_mz_kn_m: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fx_kn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fy_kn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fz_kn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mx_kn_m: Mapped[str | None] = mapped_column(String(100), nullable=True)
    my_kn_m: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mz_kn_m: Mapped[str | None] = mapped_column(String(100), nullable=True)
    safety_op: Mapped[str | None] = mapped_column(String(100), nullable=True)
    safety_extreme: Mapped[str | None] = mapped_column(String(100), nullable=True)
    overall_assessment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assessment_org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlatformLoadSummarySnapshot(Base):
    __tablename__ = "platform_load_summary_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    snapshot_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rows_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlatformSummarySnapshot(Base):
    __tablename__ = "platform_summary_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    snapshot_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    columns_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    rows_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuthRole(Base):
    __tablename__ = "auth_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    users: Mapped[list["AuthUser"]] = relationship("AuthUser", back_populates="role")


class AuthUser(Base):
    __tablename__ = "auth_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employee_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    branch_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    operation_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_code: Mapped[str] = mapped_column(ForeignKey("auth_roles.code"), nullable=False, default="engineer")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_algo: Mapped[str] = mapped_column(String(50), nullable=False, default="pbkdf2_sha256")
    password_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    role: Mapped[AuthRole] = relationship("AuthRole", back_populates="users")
    login_logs: Mapped[list["AuthLoginLog"]] = relationship("AuthLoginLog", back_populates="user")


class AuthLoginLog(Base):
    __tablename__ = "auth_login_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("auth_users.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped[AuthUser | None] = relationship("AuthUser", back_populates="login_logs")


Index("ix_facility_profiles_code", FacilityProfile.facility_code)
Index("ix_inspection_projects_facility_type", InspectionProject.facility_code, InspectionProject.project_type)
Index("ix_inspection_projects_sort", InspectionProject.facility_code, InspectionProject.project_type, InspectionProject.sort_order)
Index("ix_inspection_findings_project_sort", InspectionFinding.project_id, InspectionFinding.sort_order)
Index("ix_platform_load_information_facility_sort", PlatformLoadInformationItem.facility_code, PlatformLoadInformationItem.sort_order)
Index("ix_platform_load_summary_snapshots_key", PlatformLoadSummarySnapshot.snapshot_key)
Index("ix_platform_summary_snapshots_key", PlatformSummarySnapshot.snapshot_key)
Index("ix_auth_users_role", AuthUser.role_code)
Index("ix_auth_users_active", AuthUser.is_active, AuthUser.is_deleted)
Index("ix_auth_login_logs_user", AuthLoginLog.user_id)
Index("ix_auth_login_logs_username", AuthLoginLog.username)
Index("ix_auth_login_logs_logged_at", AuthLoginLog.logged_at)
