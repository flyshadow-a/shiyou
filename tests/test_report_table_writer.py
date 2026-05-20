from __future__ import annotations

import sys
import unittest
from pathlib import Path

from docx import Document


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_MODULE_ROOT = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
if str(REPORT_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(REPORT_MODULE_ROOT))

from src.renderers.table_writer import (  # noqa: E402
    NON_BREAKING_HYPHEN,
    write_basic_case_loads_table,
    write_pile_capacity_table,
)


class ReportTableWriterTests(unittest.TestCase):
    def test_chapter4_load_table_formats_large_and_small_numbers(self) -> None:
        document = Document()
        table = document.add_table(rows=2, cols=9)

        write_basic_case_loads_table(
            table,
            [
                {
                    "label": "CR01",
                    "fx": 12345.678,
                    "fy": 9999.999,
                    "fz": -12.345,
                    "mx": 0,
                    "my": "10000.4",
                    "mz": "abc",
                    "dead_load": "",
                    "buoyancy": -12345.678,
                }
            ],
        )

        row = table.rows[1].cells
        self.assertEqual("12346", row[1].text)
        self.assertEqual("10000.00", row[2].text)
        self.assertEqual(f"{NON_BREAKING_HYPHEN}12.35", row[3].text)
        self.assertEqual("0.00", row[4].text)
        self.assertEqual("10000", row[5].text)
        self.assertEqual("abc", row[6].text)
        self.assertEqual("", row[7].text)
        self.assertEqual(f"{NON_BREAKING_HYPHEN}12346", row[8].text)

    def test_pile_capacity_table_formats_only_numeric_columns(self) -> None:
        document = Document()
        table = document.add_table(rows=3, cols=10)

        write_pile_capacity_table(
            table,
            [
                {
                    "pile_head_id": "P108",
                    "compression_capacity_kn": "110887.125",
                    "tension_capacity_kn": "9999.1",
                    "pile_weight_kn": "6864.3",
                    "compression_case": "OL12",
                    "compression_load_kn": "38993.3",
                    "tension_case": "OL18",
                    "tension_load_kn": "47123.9",
                    "compression_sf": "2.424",
                    "tension_sf": "2.9",
                }
            ],
        )

        row = table.rows[2].cells
        self.assertEqual("P108", row[0].text)
        self.assertEqual("110887", row[1].text)
        self.assertEqual("9999.10", row[2].text)
        self.assertEqual("6864.30", row[3].text)
        self.assertEqual("OL12", row[4].text)
        self.assertEqual("38993", row[5].text)
        self.assertEqual("OL18", row[6].text)
        self.assertEqual("47124", row[7].text)
        self.assertEqual("2.42", row[8].text)
        self.assertEqual("2.90", row[9].text)


if __name__ == "__main__":
    unittest.main()
