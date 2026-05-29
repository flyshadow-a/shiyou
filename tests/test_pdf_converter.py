from __future__ import annotations

import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile


from pages.output_feasibility_analysis_report.src.pdf_converter import (
    _compute_body_page_count,
    _configure_body_page_numbers,
    _sanitize_docx_for_word_com,
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

    def test_sanitize_docx_for_word_com_removes_document_ignorable_attribute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.subTest("mc prefix"):
                path = Path(tmp_dir) / "test_report_mc.docx"
                document_xml = (
                    b"<?xml version='1.0' encoding='utf-8'?>"
                    b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                    b'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
                    b'mc:Ignorable="w14 w15 wp14"><w:body /></w:document>'
                )
                with ZipFile(path, "w") as archive:
                    archive.writestr("word/document.xml", document_xml)
                    archive.writestr("word/_rels/document.xml.rels", b"<Relationships />")

                self.assertTrue(_sanitize_docx_for_word_com(path))

                with ZipFile(path) as archive:
                    cleaned_xml = archive.read("word/document.xml")
                    self.assertIn(b'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"', cleaned_xml)
                    self.assertNotIn(b"mc:Ignorable", cleaned_xml)
                    self.assertEqual(b"<Relationships />", archive.read("word/_rels/document.xml.rels"))

            with self.subTest("rewritten namespace prefix"):
                path = Path(tmp_dir) / "test_report_ns.docx"
                document_xml = (
                    b"<?xml version='1.0' encoding='utf-8'?>"
                    b'<ns0:document xmlns:ns0="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                    b'xmlns:ns1="http://schemas.openxmlformats.org/markup-compatibility/2006" '
                    b'ns1:Ignorable="w14 w15 wp14"><ns0:body /></ns0:document>'
                )
                with ZipFile(path, "w") as archive:
                    archive.writestr("word/document.xml", document_xml)

                self.assertTrue(_sanitize_docx_for_word_com(path))

                with ZipFile(path) as archive:
                    cleaned_xml = archive.read("word/document.xml")
                    self.assertIn(
                        b'xmlns:ns1="http://schemas.openxmlformats.org/markup-compatibility/2006"',
                        cleaned_xml,
                    )
                    self.assertNotIn(b"ns1:Ignorable", cleaned_xml)

    def test_convert_docx_to_pdf_ignores_word_quit_cleanup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            docx_path = Path(tmp_dir) / "file.docx"
            pdf_path = Path(tmp_dir) / "file.pdf"
            docx_path.write_bytes(b"fake docx")

            document = Mock()
            document.ExportAsFixedFormat.side_effect = lambda **kwargs: pdf_path.write_bytes(b"%PDF")
            word = Mock()
            word.Documents.Open.return_value = document
            del word.Quit
            word.Application.Quit.side_effect = AttributeError("Word.Application.Quit")
            win32com_client = Mock(DispatchEx=Mock(return_value=word))

            with patch(
                "pages.output_feasibility_analysis_report.src.pdf_converter._update_document_fields"
            ), patch(
                "pages.output_feasibility_analysis_report.src.pdf_converter._sanitize_docx_for_word_com"
            ), patch.dict(
                "sys.modules",
                {
                    "pythoncom": Mock(CoInitialize=Mock(), CoUninitialize=Mock()),
                    "win32com": SimpleNamespace(client=win32com_client),
                    "win32com.client": win32com_client,
                },
            ):
                result = convert_docx_to_pdf(docx_path, pdf_path)

        self.assertEqual(str(pdf_path), result)


if __name__ == "__main__":
    unittest.main()
