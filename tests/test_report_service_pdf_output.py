from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_MODULE_ROOT = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
if str(REPORT_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(REPORT_MODULE_ROOT))

from src.report_service import generate_report


class ReportServicePdfOutputTests(unittest.TestCase):
    @patch("src.report_service.convert_docx_to_pdf")
    @patch("src.report_service.render_report_doc")
    @patch("src.report_service.build_chapter_1_3_context", return_value={})
    @patch("src.report_service.build_analysis_results_for_ui")
    @patch("src.report_service.parse_combo_case_loads", return_value=[])
    @patch("src.report_service.parse_combo_case_desc", return_value=[])
    @patch("src.report_service.parse_basic_case_loads", return_value=[])
    @patch("src.report_service.parse_basic_case_desc", return_value=[])
    @patch("src.report_service.validate_combo_case_loads_against_desc")
    @patch("src.report_service.validate_basic_case_loads_against_desc")
    @patch("src.report_service.read_lines", return_value=["stub"])
    def test_generate_report_renders_docx_then_converts_to_requested_pdf(
        self,
        _mock_read_lines,
        _mock_validate_basic,
        _mock_validate_combo,
        _mock_parse_basic_desc,
        _mock_parse_basic_loads,
        _mock_parse_combo_desc,
        _mock_parse_combo_loads,
        mock_build_analysis_results,
        _mock_build_context,
        mock_render_report_doc,
        mock_convert_docx_to_pdf,
    ) -> None:
        mock_build_analysis_results.return_value = {
            "analysis_summary": {},
            "member_group_summary": {},
            "member_summary": {"max_uc": 0.5, "is_pass_text": "满足"},
            "joint_can_summary": {},
            "joint_summary": {"max_uc": 0.6, "is_pass_text": "满足"},
            "pile_group_summary": {},
            "pile_summary": {},
            "pile_axial_capacity_summary": {
                "operation_compression": {"min_sf": 2.0, "is_pass_text": "满足"},
                "operation_tension": {"min_sf": 2.0, "is_pass_text": "满足"},
                "extreme_compression": {"min_sf": 2.0, "is_pass_text": "满足"},
                "extreme_tension": {"min_sf": 2.0, "is_pass_text": "满足"},
            },
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            factor_path = Path(tmp_dir) / "psilst.factor"
            factor_path.write_text("fake factor", encoding="utf-8")
            template_path = Path(tmp_dir) / "template.docx"
            template_path.write_text("fake template", encoding="utf-8")
            pdf_path = Path(tmp_dir) / "report.pdf"
            docx_path = Path(tmp_dir) / "report.docx"
            mock_render_report_doc.return_value = str(docx_path)
            mock_convert_docx_to_pdf.return_value = str(pdf_path)

            result = generate_report(
                factor_path=str(factor_path),
                template_path=str(template_path),
                output_path=str(pdf_path),
            )

        self.assertEqual(str(pdf_path), result)
        self.assertEqual(str(docx_path), mock_render_report_doc.call_args.kwargs["output_path"])
        mock_convert_docx_to_pdf.assert_called_once_with(str(docx_path), pdf_path)


if __name__ == "__main__":
    unittest.main()
