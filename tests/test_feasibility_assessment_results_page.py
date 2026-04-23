from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pages.feasibility_assessment_results_page import FeasibilityAssessmentResultsPage


class FeasibilityAssessmentResultsPageTests(unittest.TestCase):
    def test_format_basis_data_file_paragraph_formats_names(self) -> None:
        result = FeasibilityAssessmentResultsPage._format_basis_data_file_paragraph(
            ["完工文件A.pdf", "完工文件B.docx"]
        )
        self.assertEqual("（1）完工文件A.pdf；（2）完工文件B.docx。", result)

    def test_format_basis_data_file_paragraph_handles_empty(self) -> None:
        result = FeasibilityAssessmentResultsPage._format_basis_data_file_paragraph([])
        self.assertEqual("暂无文件。", result)


if __name__ == "__main__":
    unittest.main()
