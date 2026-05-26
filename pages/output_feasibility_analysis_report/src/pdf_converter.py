from __future__ import annotations

from pathlib import Path


PDF_FORMAT_CODE = 17
WD_STATISTIC_PAGES = 2
SECTION_PAGES_FIELD = "SECTIONPAGES"
TOTAL_PAGES_FIELD = "NUMPAGES"
PAGE_FIELD = "PAGE"
HEADER_FOOTER_INDEXES = range(1, 4)
BODY_PAGE_COUNT_OFFSET = 1


def _safe_call(method, *args) -> None:
    try:
        method(*args)
    except Exception:
        pass


def _update_collection_items(collection) -> None:
    try:
        count = int(collection.Count)
    except Exception:
        return
    for index in range(1, count + 1):
        try:
            item = collection.Item(index)
        except Exception:
            continue
        update = getattr(item, "Update", None)
        if update is not None:
            _safe_call(update)


def _update_table_page_numbers(collection) -> None:
    try:
        count = int(collection.Count)
    except Exception:
        return
    for index in range(1, count + 1):
        try:
            item = collection.Item(index)
        except Exception:
            continue
        update_page_numbers = getattr(item, "UpdatePageNumbers", None)
        if update_page_numbers is not None:
            _safe_call(update_page_numbers)
            continue
        update = getattr(item, "Update", None)
        if update is not None:
            _safe_call(update)


def _field_code_text(field) -> str:
    try:
        return str(field.Code.Text)
    except Exception:
        return ""


def _field_code_upper(field) -> str:
    return _field_code_text(field).upper()


def _fields_contain_page_number(fields) -> bool:
    try:
        count = int(fields.Count)
    except Exception:
        return False
    for index in range(1, count + 1):
        try:
            field = fields.Item(index)
        except Exception:
            continue
        code = _field_code_upper(field)
        if PAGE_FIELD in code or SECTION_PAGES_FIELD in code or TOTAL_PAGES_FIELD in code:
            return True
    return False


def _range_contains_page_number(range_obj) -> bool:
    fields = getattr(range_obj, "Fields", None)
    return fields is not None and _fields_contain_page_number(fields)


def _section_contains_page_number(section) -> bool:
    for collection_name in ("Footers", "Headers"):
        collection = getattr(section, collection_name, None)
        if collection is None:
            continue
        for index in HEADER_FOOTER_INDEXES:
            try:
                item = collection.Item(index)
                range_obj = item.Range
            except Exception:
                continue
            if _range_contains_page_number(range_obj):
                return True
    return False


def _first_numbered_section_index(document) -> int | None:
    sections = getattr(document, "Sections", None)
    if sections is None:
        return None
    try:
        count = int(sections.Count)
    except Exception:
        return None
    for index in range(1, count + 1):
        try:
            section = sections.Item(index)
        except Exception:
            continue
        if _section_contains_page_number(section):
            return index
    return None


def _configure_body_page_numbers(document, first_body_section_index: int | None) -> None:
    if first_body_section_index is None:
        return
    sections = getattr(document, "Sections", None)
    if sections is None:
        return
    try:
        section_count = int(sections.Count)
    except Exception:
        return
    for section_index in range(first_body_section_index, section_count + 1):
        try:
            section = sections.Item(section_index)
            footers = section.Footers
        except Exception:
            continue
        for footer_index in HEADER_FOOTER_INDEXES:
            try:
                page_numbers = footers.Item(footer_index).PageNumbers
                page_numbers.RestartNumberingAtSection = section_index == first_body_section_index
                if section_index == first_body_section_index:
                    page_numbers.StartingNumber = 1
            except Exception:
                continue


def _compute_body_page_count(document, first_body_section_index: int | None) -> int | None:
    if first_body_section_index is None:
        return None
    sections = getattr(document, "Sections", None)
    if sections is None:
        return None
    try:
        section_count = int(sections.Count)
    except Exception:
        return None
    total_pages = 0
    for section_index in range(first_body_section_index, section_count + 1):
        try:
            section = sections.Item(section_index)
            total_pages += int(section.Range.ComputeStatistics(WD_STATISTIC_PAGES))
        except Exception:
            continue
    if not total_pages:
        return None
    return max(1, total_pages - BODY_PAGE_COUNT_OFFSET)


def _set_total_page_fields(fields, total_pages: int | None) -> None:
    if total_pages is None:
        return
    try:
        count = int(fields.Count)
    except Exception:
        return
    for index in range(count, 0, -1):
        try:
            field = fields.Item(index)
        except Exception:
            continue
        code = _field_code_upper(field)
        if SECTION_PAGES_FIELD not in code and TOTAL_PAGES_FIELD not in code:
            continue
        try:
            field.Result.Text = str(total_pages)
            field.Unlink()
        except Exception:
            continue


def _update_body_header_footer_fields(
    document,
    first_body_section_index: int | None,
    total_pages: int | None = None,
) -> None:
    if first_body_section_index is None:
        return
    sections = getattr(document, "Sections", None)
    if sections is None:
        return
    try:
        section_count = int(sections.Count)
    except Exception:
        return
    for section_index in range(first_body_section_index, section_count + 1):
        try:
            section = sections.Item(section_index)
        except Exception:
            continue
        for collection_name in ("Footers", "Headers"):
            collection = getattr(section, collection_name, None)
            if collection is None:
                continue
            for item_index in HEADER_FOOTER_INDEXES:
                try:
                    fields = collection.Item(item_index).Range.Fields
                except Exception:
                    continue
                update = getattr(fields, "Update", None)
                if update is not None:
                    _safe_call(update)
                _set_total_page_fields(fields, total_pages)


def _update_document_fields(document) -> None:
    first_body_section_index = _first_numbered_section_index(document)
    _configure_body_page_numbers(document, first_body_section_index)

    _update_table_page_numbers(getattr(document, "TablesOfContents", None))
    _update_collection_items(getattr(document, "TablesOfFigures", None))
    _safe_call(getattr(document, "Repaginate", lambda: None))
    total_pages = _compute_body_page_count(document, first_body_section_index)
    _update_body_header_footer_fields(document, first_body_section_index, total_pages)


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
        _update_document_fields(document)
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
