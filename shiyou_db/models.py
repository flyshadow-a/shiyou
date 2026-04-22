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
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    file_type: Mapped[FileType] = relationship("FileType", back_populates="records")


Index("ix_file_records_type_module_path", FileRecord.file_type_id, FileRecord.module_code, FileRecord.logical_path)
Index("ix_file_records_facility", FileRecord.facility_code)
Index("ix_file_records_hash", FileRecord.file_hash)


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
    total_weight_mt: Mapped[str | None] = mapped_column(String(100), nullable=True)
    weight_limit_mt: Mapped[str | None] = mapped_column(String(100), nullable=True)
    weight_delta_mt: Mapped[str | None] = mapped_column(String(100), nullable=True)
    center_xyz: Mapped[str | None] = mapped_column(String(255), nullable=True)
    center_radius_m: Mapped[str | None] = mapped_column(String(100), nullable=True)
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


Index("ix_facility_profiles_code", FacilityProfile.facility_code)
Index("ix_inspection_projects_facility_type", InspectionProject.facility_code, InspectionProject.project_type)
Index("ix_inspection_projects_sort", InspectionProject.facility_code, InspectionProject.project_type, InspectionProject.sort_order)
Index("ix_inspection_findings_project_sort", InspectionFinding.project_id, InspectionFinding.sort_order)
Index("ix_platform_load_information_facility_sort", PlatformLoadInformationItem.facility_code, PlatformLoadInformationItem.sort_order)
