# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import List

_FACTOR_SEARCH_CHUNK_SIZE = 1024 * 1024
_FACTOR_MARKER_OVERLAP = 4096
_FACTOR_FORCE_SECTION_MAX_BYTES = 600_000
_FACTOR_FORCE_HEADER_LOOKAHEAD_BYTES = 20_000
_FACTOR_SUMMARY_SECTION_MAX_BYTES = 1_000_000
_FALLBACK_EDGE_BYTES = 2 * 1024 * 1024


def _find_factor_bytes_marker(path: str, marker: bytes, start: int = 0) -> int:
    marker_upper = marker.upper()
    marker_length = len(marker_upper)
    overlap = max(marker_length + 16, _FACTOR_MARKER_OVERLAP)
    offset = max(0, int(start or 0))
    previous_tail = b""

    with open(path, "rb") as handle:
        handle.seek(offset)
        while True:
            chunk = handle.read(_FACTOR_SEARCH_CHUNK_SIZE)
            if not chunk:
                return -1
            data = previous_tail + chunk
            index = data.upper().find(marker_upper)
            if index != -1:
                return offset - len(previous_tail) + index
            previous_tail = data[-overlap:]
            offset += len(chunk)


def _iter_factor_bytes_marker_positions(path: str, marker: bytes, start: int = 0):
    marker_upper = marker.upper()
    marker_length = len(marker_upper)
    overlap = max(marker_length + 16, _FACTOR_MARKER_OVERLAP)
    offset = max(0, int(start or 0))
    previous_tail = b""

    with open(path, "rb") as handle:
        handle.seek(offset)
        while True:
            chunk = handle.read(_FACTOR_SEARCH_CHUNK_SIZE)
            if not chunk:
                return
            data = previous_tail + chunk
            data_upper = data.upper()
            search_from = 0
            while True:
                index = data_upper.find(marker_upper, search_from)
                if index == -1:
                    break
                position = offset - len(previous_tail) + index
                if position >= start:
                    yield position
                search_from = index + marker_length
            previous_tail = data[-overlap:]
            offset += len(chunk)


def _read_factor_bytes_range(path: str, start: int, end: int) -> bytes:
    with open(path, "rb") as handle:
        handle.seek(max(0, int(start)))
        return handle.read(max(0, int(end) - int(start)))


def _find_next_form_feed(path: str, start: int, end: int) -> int:
    offset = max(0, int(start or 0))
    end = max(offset, int(end))

    with open(path, "rb") as handle:
        handle.seek(offset)
        while offset < end:
            chunk = handle.read(min(_FACTOR_SEARCH_CHUNK_SIZE, end - offset))
            if not chunk:
                return -1
            index = chunk.find(b"\x0c")
            if index != -1:
                return offset + index
            offset += len(chunk)

    return -1


def _find_line_start_before(path: str, position: int) -> int:
    position = max(0, int(position or 0))
    search_start = max(0, position - _FACTOR_MARKER_OVERLAP)
    data = _read_factor_bytes_range(path, search_start, position)
    line_break = max(data.rfind(b"\n"), data.rfind(b"\r"))
    if line_break == -1:
        return search_start
    return search_start + line_break + 1


def _read_factor_form_feed_sections(path: str, markers: List[bytes], file_size: int) -> List[bytes]:
    chunks: List[bytes] = []

    for marker in markers:
        for marker_pos in _iter_factor_bytes_marker_positions(path, marker):
            section_start = _find_line_start_before(path, marker_pos)
            max_section_end = min(file_size, section_start + _FACTOR_SUMMARY_SECTION_MAX_BYTES)
            form_feed_pos = _find_next_form_feed(path, section_start + 1, max_section_end)
            section_end = form_feed_pos if form_feed_pos != -1 else max_section_end
            chunks.append(_read_factor_bytes_range(path, section_start, section_end))

    return chunks


def _read_factor_marker_ranges(
    path: str,
    section_markers: List[tuple[bytes, List[bytes]]],
    file_size: int,
) -> List[bytes]:
    chunks: List[bytes] = []

    for start_marker, end_markers in section_markers:
        marker_pos = _find_factor_bytes_marker(path, start_marker)
        if marker_pos == -1:
            continue
        section_start = _find_line_start_before(path, marker_pos)
        end_candidates = [
            end_pos
            for end_marker in end_markers
            for end_pos in [_find_factor_bytes_marker(path, end_marker, marker_pos + len(start_marker))]
            if end_pos != -1
        ]
        section_end = min(end_candidates) if end_candidates else file_size
        chunks.append(_read_factor_bytes_range(path, section_start, section_end))

    return chunks


def _read_factor_force_chunks(path: str, start: int, file_size: int) -> List[bytes]:
    chunks: List[bytes] = []
    try:
        force_positions = list(_iter_factor_bytes_marker_positions(path, b"FINAL PILE HEAD FORCES", start))
    except OSError:
        return chunks
    if not force_positions:
        return chunks

    for index, force_start in enumerate(force_positions):
        next_force_start = force_positions[index + 1] if index + 1 < len(force_positions) else file_size
        section_end = min(next_force_start, force_start + _FACTOR_FORCE_SECTION_MAX_BYTES, file_size)
        lookahead_end = min(section_end, force_start + _FACTOR_FORCE_HEADER_LOOKAHEAD_BYTES, file_size)
        header = _read_factor_bytes_range(path, force_start, lookahead_end).upper()
        if b"PILE HEAD COORDINATES" not in header:
            continue
        chunks.append(_read_factor_bytes_range(path, force_start, section_end))
    return chunks


def _decode_factor_chunks(chunks: List[bytes]) -> List[str]:
    if not chunks:
        return []
    text = "\n".join(chunk.decode("latin-1", errors="ignore") for chunk in chunks if chunk)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "").replace("\t", "    ")
    return [line.rstrip() for line in text.split("\n")]


def _read_result_factor_marker_lines(path: str) -> List[str]:
    file_size = os.path.getsize(path)
    chunks: List[bytes] = []

    status_start = _find_factor_bytes_marker(path, b"**** LOAD CASE STATUS REPORT")
    load_cases_start = _find_factor_bytes_marker(path, b"***** SEASTATE COMBINED LOAD CASES *****")
    axial_start = _find_factor_bytes_marker(
        path,
        b"S O I L  M A X I M U M  A X I A L  C A P A C I T Y  S U M M A R Y",
        max(status_start, 0),
    )

    early_starts = [pos for pos in (status_start, load_cases_start, axial_start) if pos != -1]
    if early_starts:
        early_start = min(early_starts)
        early_end_candidates: List[int] = []
        if axial_start != -1:
            for marker in (b"SACS LOAD CASE REPORT", b"PST VERSION"):
                marker_pos = _find_factor_bytes_marker(path, marker, axial_start)
                if marker_pos != -1:
                    early_end_candidates.append(marker_pos)
        if load_cases_start != -1:
            marker_pos = _find_factor_bytes_marker(path, b"SACS LOAD CASE REPORT", load_cases_start)
            if marker_pos != -1:
                early_end_candidates.append(marker_pos)
        early_end = min(early_end_candidates) if early_end_candidates else min(file_size, max(early_starts) + 800_000)
        chunks.append(_read_factor_bytes_range(path, early_start, early_end))

    chunks.extend(
        _read_factor_marker_ranges(
            path,
            [
                (
                    b"SEASTATE BASIC LOAD CASE DESCRIPTIONS",
                    [
                        b"SEASTATE BASIC LOAD CASE SUMMARY",
                        b"SEASTATE COMBINED LOAD CASES",
                    ],
                ),
                (
                    b"SEASTATE BASIC LOAD CASE SUMMARY",
                    [
                        b"SEASTATE COMBINED LOAD CASES",
                        b"SEASTATE COMBINED LOAD CASE SUMMARY",
                    ],
                ),
                (
                    b"SEASTATE COMBINED LOAD CASES",
                    [
                        b"SEASTATE COMBINED LOAD CASE SUMMARY",
                    ],
                ),
                (
                    b"SEASTATE COMBINED LOAD CASE SUMMARY",
                    [
                        b"SEASTATE LOAD CASE CENTER REPORT",
                        b"SACS-IV   MEMBER UNITY CHECK RANGE SUMMARY",
                        b"M E M B E R  G R O U P  S U M M A R Y",
                    ],
                ),
            ],
            file_size,
        )
    )

    chunks.extend(
        _read_factor_form_feed_sections(
            path,
            [
                b"M E M B E R  G R O U P  S U M M A R Y",
                b"J O I N T   C A N   S U M M A R Y",
                b"P I L E  G R O U P  S U M M A R Y",
            ],
            file_size,
        )
    )
    chunks.extend(_read_factor_force_chunks(path, max(status_start, 0), file_size))
    return _decode_factor_chunks(chunks)



def _decode_psilst_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "gbk", "cp936", "latin-1"):
        try:
            return data.decode(encoding, errors="ignore")
        except Exception:
            continue
    return data.decode("latin-1", errors="ignore")


def _normalise_text_to_lines(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "").replace("\t", "    ")
    return [line.rstrip() for line in text.split("\n")]


def _read_full_lines_streaming(path: str) -> List[str]:
    # 小文件兼容旧版 read_lines：返回完整行列表。
    # 用二进制逐行读，避免 read()+split() 产生额外大内存峰值。
    lines: List[str] = []
    with open(path, "rb") as handle:
        for raw in handle:
            line = _decode_psilst_bytes(raw).rstrip("\r\n")
            lines.append(line.replace("\ufeff", "").replace("\t", "    "))
    return lines


def read_lines(path: str) -> List[str]:
    """兼容 report_service 旧接口。

    旧版 report_service 会同时 import read_lines 和 read_ui_analysis_lines。
    v11 只保留 read_ui_analysis_lines，导致 ImportError。

    小文件：返回完整行列表，保持旧行为。
    大文件：返回 UI 关键段落，避免 psilst.M1 过大触发 MemoryError。
    """
    path = os.path.normpath(str(path or "").strip())
    if not path or not os.path.isfile(path):
        return []

    try:
        max_full_bytes = int(os.environ.get("SHIYOU_PSILST_FULL_READ_LIMIT_MB", "64")) * 1024 * 1024
    except Exception:
        max_full_bytes = 64 * 1024 * 1024

    try:
        file_size = os.path.getsize(path)
    except OSError:
        return []

    if file_size <= max_full_bytes:
        return _read_full_lines_streaming(path)

    return read_ui_analysis_lines(path)

def read_ui_analysis_lines(path: str) -> List[str]:
    """读取可行性评估 UI 解析需要的 psilst 关键段落。

    原实现一次性读取完整 psilst.M1 并 split，结果文件很大时会触发
    MemoryError。这里参考项目中平台载荷页面的处理方式：先按 marker
    读取关键区段；找不到 marker 时只读文件头尾作为兜底，避免爆内存。
    """
    path = os.path.normpath(str(path or "").strip())
    if not path or not os.path.isfile(path):
        return []

    try:
        marker_lines = _read_result_factor_marker_lines(path)
        if marker_lines:
            return marker_lines
    except OSError:
        pass

    file_size = os.path.getsize(path)
    head = _read_factor_bytes_range(path, 0, min(file_size, _FALLBACK_EDGE_BYTES))
    tail_start = max(0, file_size - _FALLBACK_EDGE_BYTES)
    tail = _read_factor_bytes_range(path, tail_start, file_size)
    return _decode_factor_chunks([head, tail])
