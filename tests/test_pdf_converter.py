from __future__ import annotations

import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


from pages.output_feasibility_analysis_report.src.pdf_converter import (
    _compute_body_page_count,
    _configure_body_page_numbers,
    _update_body_header_footer_fields,
    _update_table_page_numbers,
    convert_docx_to_pdf,
)


class _ComCollection:
    def __init__(self, items):
        self._items = list(items)
        self.Count = len(self._items)

    def Item(self, index):
        return self._items[index - 1]


class PdfConverterTests(unittest.TestCase):
    def test_body_page_numbers_restart_at_body_section_only(self) -> None:
        sections = []
        for _ in range(4):
            footers = _ComCollection(
                [SimpleNamespace(PageNumbers=SimpleNamespace()) for _ in range(3)]
            )
            sections.append(Mock(Footers=footers))
        document = Mock(Sections=_ComCollection(sections))

        _configure_body_page_numbers(document, 3)

        self.assertFalse(hasattr(sections[0].Footers.Item(1).PageNumbers, "RestartNumberingAtSection"))
        self.assertFalse(hasattr(sections[1].Footers.Item(1).PageNumbers, "RestartNumberingAtSection"))
        self.assertTrue(sections[2].Footers.Item(1).PageNumbers.RestartNumberingAtSection)
        self.assertEqual(1, sections[2].Footers.Item(1).PageNumbers.StartingNumber)
        self.assertFalse(sections[3].Footers.Item(1).PageNumbers.RestartNumberingAtSection)

    def test_compute_body_page_count_excludes_cover_toc_and_overflow_page(self) -> None:
        sections = []
        for page_count in (1, 2, 10, 3):
            section = Mock()
            section.Range.ComputeStatistics.return_value = page_count
            sections.append(section)
        document = Mock(Sections=_ComCollection(sections))

        self.assertEqual(12, _compute_body_page_count(document, 3))

    def test_update_table_page_numbers_preserves_toc_format_when_supported(self) -> None:
        toc = Mock()
        _update_table_page_numbers(_ComCollection([toc]))

        toc.UpdatePageNumbers.assert_called_once_with()
        toc.Update.assert_not_called()

    def test_update_body_header_footer_fields_skips_cover_and_toc_sections(self) -> None:
        sections = []
        for _ in range(3):
            footer_fields = Mock()
            footer = SimpleNamespace(Range=SimpleNamespace(Fields=footer_fields))
            header_fields = Mock()
            header = SimpleNamespace(Range=SimpleNamespace(Fields=header_fields))
            sections.append(
                SimpleNamespace(
                    Footers=_ComCollection([footer, footer, footer]),
                    Headers=_ComCollection([header, header, header]),
                )
            )
        document = Mock(Sections=_ComCollection(sections))

        _update_body_header_footer_fields(document, 3, 12)

        self.assertFalse(sections[0].Footers.Item(1).Range.Fields.Update.called)
        self.assertFalse(sections[1].Footers.Item(1).Range.Fields.Update.called)
        self.assertTrue(sections[2].Footers.Item(1).Range.Fields.Update.called)

    def test_convert_docx_to_pdf_ignores_word_quit_cleanup_failure(self) -> None:
        document = Mock()
        word = Mock()
        word.Documents.Open.return_value = document
        del word.Quit
        word.Application.Quit.side_effect = AttributeError("Word.Application.Quit")

        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.resolve", side_effect=lambda *args, **kwargs: Path(r"D:\reports\file.docx")
        ), patch(
            "pages.output_feasibility_analysis_report.src.pdf_converter._update_document_fields"
        ), patch.dict(
            "sys.modules",
            {
                "pythoncom": Mock(CoInitialize=Mock(), CoUninitialize=Mock()),
                "win32com": Mock(),
                "win32com.client": Mock(DispatchEx=Mock(return_value=word)),
            },
        ):
            result = convert_docx_to_pdf(r"D:\reports\file.docx", r"D:\reports\file.pdf")

        self.assertEqual(r"D:\reports\file.pdf", result)


if __name__ == "__main__":
    unittest.main()
