# -*- coding: utf-8 -*-

import os


WINDOWS_INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def strip_save_dialog_wildcard(filename: str) -> str:
    """Remove wildcard suffixes such as `.*` returned by native save dialogs."""
    cleaned = str(filename or "").strip()
    while cleaned.endswith(".*") or cleaned.endswith("*"):
        cleaned = cleaned[:-2] if cleaned.endswith(".*") else cleaned[:-1]
        cleaned = cleaned.rstrip(" .")
    return cleaned


def sanitize_download_filename(filename: str, fallback: str = "download") -> str:
    """Return a Windows-safe filename while preserving extensionless SACS names."""
    raw_name = os.path.basename(str(filename or "").strip())
    raw_name = strip_save_dialog_wildcard(raw_name)

    filtered = []
    for ch in raw_name:
        if ord(ch) < 32 or ch in WINDOWS_INVALID_FILENAME_CHARS:
            filtered.append("_")
        else:
            filtered.append(ch)

    cleaned = "".join(filtered).strip(" .")
    if cleaned and cleaned not in {".", ".."}:
        return cleaned

    fallback_name = os.path.basename(str(fallback or "download").strip())
    fallback_name = strip_save_dialog_wildcard(fallback_name)
    fallback_cleaned = "".join(
        "_" if ord(ch) < 32 or ch in WINDOWS_INVALID_FILENAME_CHARS else ch
        for ch in fallback_name
    ).strip(" .")
    return fallback_cleaned if fallback_cleaned and fallback_cleaned not in {".", ".."} else "download"


def normalize_download_save_path(save_path: str, fallback_name: str = "download") -> str:
    if not save_path:
        return ""

    directory, filename = os.path.split(str(save_path))
    safe_name = sanitize_download_filename(filename, fallback=fallback_name)
    return os.path.join(directory, safe_name) if directory else safe_name


def unique_download_target_path(target_dir: str, filename: str) -> str:
    safe_name = sanitize_download_filename(filename)
    target_path = os.path.join(target_dir, safe_name)
    root, ext = os.path.splitext(target_path)
    suffix = 1
    while os.path.exists(target_path):
        target_path = f"{root} ({suffix}){ext}"
        suffix += 1
    return target_path
