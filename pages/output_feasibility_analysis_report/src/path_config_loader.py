from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.resource_paths import first_existing_asset_path


def _default_config_path() -> Path:
    return first_existing_asset_path("config", "path_config.json")


def _config_root(config_path: str | Path | None = None) -> Path:
    path = Path(config_path) if config_path else _default_config_path()
    return path.resolve().parent.parent


@lru_cache(maxsize=4)
def load_path_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else _default_config_path()
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _format_path(template: str, *, facility_code: str, config: dict[str, Any]) -> Path:
    return Path(
        template.format(
            facility_code=facility_code,
            special_strategy_images_root=str(config.get("special_strategy_images_root", "")),
            report_image_output_root=str(config.get("report_image_output_root", "")),
        )
    )


def get_overall_model_config(facility_code: str) -> dict[str, Any]:
    config = load_path_config()
    section = config.get("analysis_model", {}).get("overall_model", {})
    directory = _format_path(str(section.get("directory", "")), facility_code=facility_code, config=config)
    return {
        "directory": directory,
        "preferred_file": str(section.get("preferred_file", "3d.png")),
        "fallback_extensions": tuple(section.get("fallback_extensions", [".png", ".jpg", ".jpeg"])),
    }


def get_coordinate_system_config(facility_code: str) -> dict[str, Any]:
    config = load_path_config()
    section = config.get("analysis_model", {}).get("coordinate_system", {})
    directory = _format_path(str(section.get("directory", "")), facility_code=facility_code, config=config)
    output_root = Path(str(config.get("report_image_output_root", "")))
    return {
        "directory": directory,
        "xy_file": str(section.get("xy_file", "XY_-14.png")),
        "yz_file": str(section.get("yz_file", "YZ_Left.png")),
        "output_path": output_root / facility_code / str(section.get("output_file", "coordinate_system.png")),
    }


def get_report_defaults() -> dict[str, Path]:
    config = load_path_config()
    config_root = _config_root()
    section = config.get("report_defaults", {})
    return {
        "template_path": config_root / str(section.get("template_file", "xxx平台改建可行性评估报告纯净版.docx")),
    }
