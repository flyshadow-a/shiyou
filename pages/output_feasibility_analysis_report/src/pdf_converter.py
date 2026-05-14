from __future__ import annotations

from pathlib import Path


PDF_FORMAT_CODE = 17


def _safe_call(method, *args) -> None:
    try:
        method(*args)
    except Exception:
        pass


def build_pdf_output_path(docx_path: str | Path) -> str:
    return str(Path(docx_path).with_suffix(".pdf"))


def convert_docx_to_pdf(docx_path: str | Path, pdf_path: str | Path | None = None) -> str:
    source = Path(docx_path)
    target = Path(pdf_path) if pdf_path else Path(build_pdf_output_path(source))

    if not source.exists():
        raise FileNotFoundError(f"待转换的 Word 文件不存在: {source}")

    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "未安装 pywin32，无法将 Word 文档转换为 PDF。请先安装 pywin32，并确保本机已安装 Microsoft Word。"
        ) from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(str(source.resolve()))
        document.ExportAsFixedFormat(str(target.resolve()), PDF_FORMAT_CODE)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Word 转 PDF 失败: {exc}") from exc
    finally:
        if document is not None:
            _safe_call(document.Close, False)
        if word is not None:
            quit_method = None
            try:
                quit_method = getattr(word, "Quit", None)
            except Exception:
                quit_method = None
            if quit_method is None:
                try:
                    quit_method = getattr(getattr(word, "Application", word), "Quit", None)
                except Exception:
                    quit_method = None
            if quit_method is not None:
                _safe_call(quit_method)
        _safe_call(pythoncom.CoUninitialize)

    if not target.exists():
        raise RuntimeError(f"PDF 转换未生成输出文件: {target}")

    return str(target)
