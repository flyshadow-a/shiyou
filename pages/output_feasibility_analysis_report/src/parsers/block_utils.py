from __future__ import annotations

from typing import Iterable


def contains_marker(line: str, marker: str) -> bool:
    return marker in line


def find_first_index(lines: list[str], marker: str, start: int = 0) -> int:
    """
    找到首个包含 marker 的行号；找不到返回 -1。
    """
    for i in range(start, len(lines)):
        if marker in lines[i]:
            return i
    return -1


def find_next_index(lines: list[str], markers: Iterable[str], start: int) -> int:
    """
    从 start 开始，找到首个命中任意 marker 的行号；找不到返回 -1。
    """
    marker_list = list(markers)
    for i in range(start, len(lines)):
        line = lines[i]
        for marker in marker_list:
            if marker in line:
                return i
    return -1


def extract_block(
    lines: list[str],
    start_marker: str,
    end_markers: list[str] | None = None,
    include_start: bool = True,
) -> list[str]:
    """
    根据起止 marker 截取文本块。
    """
    start_idx = find_first_index(lines, start_marker)
    if start_idx == -1:
        return []

    content_start = start_idx if include_start else start_idx + 1

    if not end_markers:
        return lines[content_start:]

    end_idx = find_next_index(lines, end_markers, start_idx + 1)
    if end_idx == -1:
        return lines[content_start:]

    return lines[content_start:end_idx]


def join_block(block_lines: list[str]) -> str:
    return "\n".join(block_lines).strip("\n")


def is_blank(line: str) -> bool:
    return not line.strip()