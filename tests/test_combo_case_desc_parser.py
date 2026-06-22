from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_MODULE_ROOT = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
if str(REPORT_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(REPORT_MODULE_ROOT))

from src.parsers.combo_case_desc_parser import parse_combo_case_desc  # noqa: E402


def _combo_detail_line(load_label: str, percent: str, suffix: str = "LOAD") -> str:
    return f"{'':12}{load_label:<15}     {percent:>6} {suffix}"


def test_parse_combo_case_desc_uses_vba_fixed_width_detail_rows() -> None:
    rows = parse_combo_case_desc(
        [
            "***** SEASTATE COMBINED LOAD CASES *****",
            "",
            "COMBINED LOAD CASE",
            "LOAD CASE LABEL",
            "BASIC LOAD CASE             PERCENT",
            "",
            "",
            "         155  OP01",
            _combo_detail_line("DX00", "1.300"),
            _combo_detail_line("DY27", "0.014"),
            "TOTAL                         2560.796      -28.773        0.000",
            "         156  OP02",
            _combo_detail_line("DX00", "0.593"),
            _combo_detail_line("DY90", "0.594"),
            "****** SEASTATE COMBINED LOAD CASE SUMMARY ******",
        ]
    )

    assert rows == [
        {
            "case": 155,
            "label": "OP01",
            "desc": "DX00*0.013+DY27*0.000",
        },
        {
            "case": 156,
            "label": "OP02",
            "desc": "DX00*0.006+DY90*0.006",
        },
    ]


def test_parse_combo_case_desc_ignores_numeric_total_lines() -> None:
    rows = parse_combo_case_desc(
        [
            "***** SEASTATE COMBINED LOAD CASES *****",
            "         190  E01A",
            _combo_detail_line("DE31", "100.000"),
            _combo_detail_line("LVDS", "-37.500"),
            "TOTAL                         100.000      200.000      300.000",
            "****** SEASTATE COMBINED LOAD CASE SUMMARY ******",
        ]
    )

    assert rows == [
        {
            "case": 190,
            "label": "E01A",
            "desc": "DE31*1.000+LVDS*-0.375",
        }
    ]


def test_parse_combo_case_desc_ignores_numeric_load_value_lines_like_vba() -> None:
    rows = parse_combo_case_desc(
        [
            "***** SEASTATE COMBINED LOAD CASES *****",
            "         156  OP02",
            _combo_detail_line("DX00", "0.593"),
            _combo_detail_line("DY90", "0.594"),
            "            DX00           1264.000         0.000",
            "            DY90             -0.020         0.000",
            "            TOTAL          1264.000         0.000",
            "****** SEASTATE COMBINED LOAD CASE SUMMARY ******",
        ]
    )

    assert rows == [
        {
            "case": 156,
            "label": "OP02",
            "desc": "DX00*0.006+DY90*0.006",
        }
    ]
