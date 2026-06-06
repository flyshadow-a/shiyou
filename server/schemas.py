# server/schemas.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrategyRunRequest(BaseModel):
    facility_code: str
    param_overrides: dict[str, Any] = Field(default_factory=dict)
    input_overrides: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImageExportRequest(BaseModel):
    facility_code: str
    run_id: int | None = None
    mode: str = "risk"
    show_level_ii: bool = False


class ReportGenerateRequest(BaseModel):
    facility_code: str
    run_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    output_path: str | None = None
    generate_pdf: bool = True
    pdf_timeout_seconds: int = 300


class FeasibilityRunRequest(BaseModel):
    facility_code: str
    analysis_mode: str = "auto"  # auto / original / rebuild
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeasibilityReportGenerateRequest(BaseModel):
    facility_code: str
    run_id: int | None = None
    report_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    output_path: str | None = None


class FeasibilityResultRequest(BaseModel):
    run_id: int | None = None
    pile_capacity_input_rows: list[dict[str, Any]] = Field(default_factory=list)


class FeasibilityExportFilesRequest(BaseModel):
    facility_code: str
    analysis_mode: str = "auto"
    include_model_files: bool = True
    include_result_file: bool = True

class FeasibilityCreateModelRequest(BaseModel):
    facility_code: str
    metadata: dict[str, Any] = Field(default_factory=dict)
