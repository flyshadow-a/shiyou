"""
读取psilst文件
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


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