"""
读取psilst文件
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


UI_ANALYSIS_INDEX_MARKERS = (
    "REPORT DESCRIPTION",
    "APPLIED LOAD SUMMARY",
    "MATRIX DECOMPOSITION DATA",
    "PILEHEAD MAXIMUM UNITY CHECK SUMMARY",
    "PILE GROUP SUMMARY",
    "PILEHEAD COMPARISON",
    "PILE MAXIMUM AXIAL CAPACITY SUMMARY",
)

_SEARCH_CHUNK_SIZE = 4 * 1024 * 1024


def _normalize_psilst_line(line: str) -> str:
    return line.rstrip("\r\n").rstrip().replace("\x0c", "")


def _find_bytes_marker(file_path: Path, marker: bytes, start: int = 0) -> int:
    marker_length = len(marker)
    overlap = max(marker_length - 1, 0)
    with file_path.open("rb") as handle:
        handle.seek(start)
        offset = start
        previous_tail = b""
        while True:
            chunk = handle.read(_SEARCH_CHUNK_SIZE)
            if not chunk:
                return -1
            data = previous_tail + chunk
            index = data.find(marker)
            if index != -1:
                return offset - len(previous_tail) + index
            previous_tail = data[-overlap:] if overlap else b""
            offset += len(chunk)


def _read_bytes_range(file_path: Path, start: int, end: int) -> bytes:
    with file_path.open("rb") as handle:
        handle.seek(start)
        return handle.read(max(0, end - start))


def _ui_analysis_marker_for_line(upper_line: str) -> str:
    stripped = upper_line.strip()
    if stripped.startswith("**** LOAD CASE STATUS REPORT"):
        return "LOAD CASE STATUS REPORT"
    if "INTERNAL FORCES ON STRUCTURE" in upper_line and "FOR LOAD CASE" in upper_line:
        return "INTERNAL FORCES ON STRUCTURE"
    for marker in (
        "M E M B E R  G R O U P  S U M M A R Y",
        "J O I N T   C A N   S U M M A R Y",
        "P I L E  G R O U P  S U M M A R Y",
        "S O I L  M A X I M U M  A X I A L  C A P A C I T Y  S U M M A R Y",
    ):
        if "*" in upper_line and marker in upper_line:
            return marker
    return ""


def _try_read_text(path: Path, encodings: Iterable[str]) -> str:
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding, errors="strict")
        except Exception as exc:  # pragma: no cover - fallback path
            last_error = exc
    raise RuntimeError(f"无法读取文件: {path}") from last_error


def read_text(path: str) -> str:
    """
    读取 psilst 文本文件，尽量保留原始布局。
    由于 SACS 输出常带固定宽度表格，这里不主动压缩空格。
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    text = _try_read_text(
        file_path,
        encodings=("utf-8", "gb18030", "latin-1"),
    )

    # 统一换行，去掉 form feed，保留空格布局
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "")
    text = text.replace("\x0c", "\n")  # form feed page break
    text = text.replace("\t", "    ")
    return text


def read_lines(path: str) -> list[str]:
    """
    读取文件并拆成行。只去掉行尾换行和右侧多余空白，不破坏左侧缩进。
    """
    text = read_text(path)
    return [line.rstrip() for line in text.split("\n")]


def read_ui_analysis_lines(path: str) -> list[str]:
    """流式读取结果页 UI 所需的 psilst 片段，避免整文件加载。"""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    chunks: list[bytes] = []

    file_size = file_path.stat().st_size
    status_start = _find_bytes_marker(file_path, b"**** LOAD CASE STATUS REPORT")
    axial_start = _find_bytes_marker(
        file_path,
        b"S O I L  M A X I M U M  A X I A L  C A P A C I T Y  S U M M A R Y",
        max(status_start, 0),
    )
    if status_start != -1 and axial_start != -1:
        early_end = _find_bytes_marker(file_path, b"SACS LOAD CASE REPORT", axial_start)
        if early_end == -1:
            early_end = _find_bytes_marker(file_path, b"PST VERSION", axial_start)
        if early_end == -1:
            early_end = axial_start + 200_000
        chunks.append(_read_bytes_range(file_path, status_start, early_end))

    member_start = _find_bytes_marker(
        file_path,
        b"M E M B E R  G R O U P  S U M M A R Y",
        max(axial_start, 0),
    )
    if member_start != -1:
        member_end = _find_bytes_marker(file_path, b"L O A D  P A T H  R E P O R T", member_start)
        if member_end == -1:
            member_end = _find_bytes_marker(file_path, b"SACS LOAD CASE REPORT", member_start)
        if member_end == -1:
            member_end = file_size
        chunks.append(_read_bytes_range(file_path, member_start, member_end))

    if not chunks:
        return read_lines(path)

    text = "\n".join(chunk.decode("latin-1", errors="ignore") for chunk in chunks)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "").replace("\x0c", "\n").replace("\t", "    ")
    lines = [line.rstrip() for line in text.split("\n")]

    # 保留末尾索引中的章节名，供依赖 end marker 的旧 parser 正常截断。
    lines.extend(UI_ANALYSIS_INDEX_MARKERS)
    return lines
