from __future__ import annotations

import sys
from pathlib import Path


REPORT_MODULE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = REPORT_MODULE_ROOT.parents[1]
EXTERNAL_DIR_NAME = "output_feasibility_analysis_report"


def _packaged_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return REPO_ROOT


def _external_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return REPO_ROOT


def candidate_asset_roots() -> list[Path]:
    roots: list[Path] = []
    for root in (
        _external_root() / EXTERNAL_DIR_NAME,
        _packaged_root() / EXTERNAL_DIR_NAME,
        REPORT_MODULE_ROOT,
    ):
        resolved = root.resolve()
        if resolved not in roots:
            roots.append(resolved)
    return roots


def first_existing_asset_path(*parts: str) -> Path:
    candidates = [root.joinpath(*parts) for root in candidate_asset_roots()]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
