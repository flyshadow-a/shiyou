from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from docx import Document
from PIL import Image

from pages.output_special_strategy.report_jinja2_generator import (
    APPENDIX_A_HEADING,
    NS,
    insert_appendix_pdf_images,
)


class SpecialStrategyAppendixInsertTests(unittest.TestCase):
    def test_appendix_image_is_inserted_when_heading_is_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            docx_path = root / "report.docx"
            image_path = root / "appendix.png"

            document = Document()
            document.add_paragraph("正文")
            document.save(docx_path)

            image = Image.new("RGB", (20, 20), color=(20, 120, 200))
            image.save(image_path)

            stats = insert_appendix_pdf_images(
                docx_path,
                {
                    "appendix_generated_plan": [
                        {"heading": APPENDIX_A_HEADING, "files": [image_path]},
                    ],
                },
            )

            with ZipFile(docx_path) as archive:
                document_root = ET.fromstring(archive.read("word/document.xml"))

            paragraphs = []
            drawing_count = 0
            for paragraph in document_root.findall(".//w:p", NS):
                text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
                if text:
                    paragraphs.append(text)
                if paragraph.findall(".//w:drawing", NS):
                    drawing_count += 1

            self.assertIn(APPENDIX_A_HEADING, paragraphs)
            self.assertGreaterEqual(drawing_count, 1)
            self.assertEqual(stats["planned_files"], 1)
            self.assertGreaterEqual(stats["inserted_images"], 1)
            self.assertEqual(stats["missing_files"], 0)


if __name__ == "__main__":
    unittest.main()
