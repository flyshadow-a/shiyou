from __future__ import annotations

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_TEMPLATE_PATH = REPO_ROOT / "pages" / "output_special_strategy" / "xxx平台风险评级及检测策略报告.docx"
REPORT_METADATA_TEMPLATE_PATH = REPO_ROOT / "pages" / "output_special_strategy" / "report_metadata.template.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


class SpecialStrategyReportMetadataTemplateTests(unittest.TestCase):
    def test_report_metadata_template_covers_word_placeholders(self) -> None:
        with ZipFile(REPORT_TEMPLATE_PATH) as zf:
            root = ET.fromstring(zf.read("word/document.xml"))

        placeholder_keys: set[str] = set()
        for paragraph in root.findall(".//w:p", NS):
            text = "".join((node.text or "") for node in paragraph.findall(".//w:t", NS)).strip()
            if "{{" not in text:
                continue
            for match in re.finditer(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)", text):
                placeholder_keys.add(match.group(1))

        template_payload = json.loads(REPORT_METADATA_TEMPLATE_PATH.read_text(encoding="utf-8-sig"))
        self.assertIsInstance(template_payload, dict)
        self.assertEqual(set(template_payload.keys()), placeholder_keys)


if __name__ == "__main__":
    unittest.main()
