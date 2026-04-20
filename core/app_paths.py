from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def packaged_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return REPO_ROOT


def external_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return REPO_ROOT


def resource_path(*parts: str) -> str:
    return str(packaged_root().joinpath(*parts))


def external_path(*parts: str) -> str:
    return str(external_root().joinpath(*parts))


def existing_paths(*parts: str) -> list[str]:
    paths: list[str] = []
    for base in (external_root(), packaged_root()):
        current = str(base.joinpath(*parts).resolve())
        if current not in paths:
            paths.append(current)
    return paths


def first_existing_path(*parts: str) -> str:
    candidates = existing_paths(*parts)
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return candidates[0]


def existing_dirs(*parts: str) -> list[str]:
    return [path for path in existing_paths(*parts) if Path(path).exists()]
