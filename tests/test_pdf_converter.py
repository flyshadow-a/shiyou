from __future__ import annotations

import unittest

from pathlib import Path
from unittest.mock import Mock, patch


from pages.output_feasibility_analysis_report.src.pdf_converter import convert_docx_to_pdf


class PdfConverterTests(unittest.TestCase):
    def test_convert_docx_to_pdf_ignores_word_quit_cleanup_failure(self) -> None:
        document = Mock()
        word = Mock()
        word.Documents.Open.return_value = document
        del word.Quit
        word.Application.Quit.side_effect = AttributeError("Word.Application.Quit")

        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.resolve", side_effect=lambda *args, **kwargs: Path(r"D:\reports\file.docx")
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
