from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from src.report_service import generate_report_with_project_defaults

try:
    from fastapi import FastAPI, HTTPException
except ImportError:  # pragma: no cover
    FastAPI = None
    HTTPException = RuntimeError


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _build_output_path(filename: str | None = None, output_path: str | None = None) -> str:
    if output_path:
        return output_path
    if filename:
        return str(PROJECT_ROOT / "output" / filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(PROJECT_ROOT / "output" / f"report_autofill_api_{timestamp}.docx")


def create_app() -> Any:
    if FastAPI is None:
        raise ImportError("未安装 fastapi，请先安装 fastapi 和 uvicorn。")

    app = FastAPI(title="WordTemplate Report API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/generate-report")
    def generate_report_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            output_path = _build_output_path(payload.get("output_filename"), payload.get("output_path"))
            result = generate_report_with_project_defaults(
                project_root=PROJECT_ROOT,
                chapter_1_3_sources=payload.get("chapter_1_3", {}),
                factor_path=payload.get("factor_path"),
                template_path=payload.get("template_path"),
                output_path=output_path,
            )
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "message": "report generated",
            "output_path": result,
        }

    return app


app = create_app() if FastAPI is not None else None
