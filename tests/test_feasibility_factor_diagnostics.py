from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_MODULE_ROOT = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
if str(REPORT_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(REPORT_MODULE_ROOT))

from src.parsers.load_case_status_parser import parse_load_case_status
from src.parsers.pile_axial_capacity_summary_parser import parse_pile_axial_capacity_summary
from src.parsers.pile_head_capacity_summary_builder import build_pile_head_capacity_summary
from src.parsers.pile_head_force_parser import parse_pile_head_forces
from src.parsers.psilst_reader import read_ui_analysis_lines


FACTOR_PATH_TEXT = os.environ.get("FEASIBILITY_FACTOR_PATH", "").strip()
FACTOR_PATH = Path(FACTOR_PATH_TEXT) if FACTOR_PATH_TEXT else None


MINIMAL_FACTOR_LINES = [
    "          **** LOAD CASE STATUS REPORT ****",
    "     LOAD   LOAD   PRINT   DEAD   P-DELTA    LOAD    AMOD",
    "     CASE    ID    OPTION  LOAD    LOAD     FACTOR  FACTOR",
    "       1    OP11     YES    NO      NO        1.00    1.00",
    "       2    OL16     YES    NO      NO        1.00    1.00",
    "       3    EH11     YES    NO      NO        1.00    1.33",
    "       4    EL16     YES    NO      NO        1.00    1.33",
    "                                        INTERNAL FORCES ON STRUCTURE (KN   AND KN-M    ) FOR LOAD CASE OL16",
    "                                                    PILE HEAD COORDINATES",
    "     PILE   BATTER",
    "     JOINT  JOINT       FORCE(X)       FORCE(Y)       FORCE(Z)      MOMENT(X)      MOMENT(Y)      MOMENT(Z)",
    "     P101   P111      30315.626      -1571.200        317.665          5.901       4102.623      10058.362",
    "                                                     STRUCTURAL COORDINATES",
    "                                        INTERNAL FORCES ON STRUCTURE (KN   AND KN-M    ) FOR LOAD CASE EL16",
    "                                                    PILE HEAD COORDINATES",
    "     PILE   BATTER",
    "     JOINT  JOINT       FORCE(X)       FORCE(Y)       FORCE(Z)      MOMENT(X)      MOMENT(Y)      MOMENT(Z)",
    "     P101   P111      46458.635      -1571.200        317.665          5.901       4102.623      10058.362",
    "                                                     STRUCTURAL COORDINATES",
    "                               * * *  S O I L  M A X I M U M  A X I A L  C A P A C I T Y  S U M M A R Y  * * *",
    "PILE GRP  ********* PILE *********  ************** COMPRESSION *************  **************** TENSION ***************",
    " JT         PILEHEAD  WEIGHT  PEN.   CAPACITY    MAX.     CRITICAL CONDITION   CAPACITY    MAX.     CRITICAL CONDITION    *MAXIMUM*",
    "           O.D.  THK.               (INCL. WT)   LOAD      LOAD  LOAD SAFETY  (INCL. WT)   LOAD      LOAD  LOAD SAFETY    UNITY LOAD",
    "           CM    CM     KN     M       KN        KN        KN    CASE FACTOR     KN        KN        KN    CASE FACTOR    CHECK CASE",
    "P101 PA  243.80  9.50 6002.4 133.0  -89154.0  -46458.6  -46458.6 EL16   1.92   96017.2    7875.0    7875.0 LTL3  12.19     0.78 EL16",
    "***** SACS LOAD CASE REPORT *****",
]


class FeasibilityFactorParserChainTests(unittest.TestCase):
    def test_minimal_factor_fixture_can_build_pile_capacity_tables(self) -> None:
        load_case_status = parse_load_case_status(MINIMAL_FACTOR_LINES)
        pile_head_forces = parse_pile_head_forces(MINIMAL_FACTOR_LINES)
        pile_axial_capacity = parse_pile_axial_capacity_summary(MINIMAL_FACTOR_LINES)
        pile_capacity = build_pile_head_capacity_summary(
            pile_head_forces,
            pile_axial_capacity,
            case_type_map=load_case_status.get("case_type_map", {}),
        )

        print(
            "minimal_factor_diagnostics",
            {
                "load_case_status_rows": len(load_case_status.get("rows", [])),
                "pile_head_force_rows": len(pile_head_forces.get("rows", [])),
                "pile_axial_capacity_rows": len(pile_axial_capacity.get("rows", [])),
                "operation_table_rows": len(pile_capacity.get("operation_table_rows", [])),
                "extreme_table_rows": len(pile_capacity.get("extreme_table_rows", [])),
                "operation_sample": pile_capacity.get("operation_table_rows", [])[:1],
                "extreme_sample": pile_capacity.get("extreme_table_rows", [])[:1],
            },
        )

        self.assertEqual(4, len(load_case_status.get("rows", [])))
        self.assertEqual(2, len(pile_head_forces.get("rows", [])))
        self.assertEqual(1, len(pile_axial_capacity.get("rows", [])))
        self.assertEqual(1, len(pile_capacity.get("operation_table_rows", [])))
        self.assertEqual(1, len(pile_capacity.get("extreme_table_rows", [])))

    def test_read_ui_analysis_lines_extracts_relevant_blocks_from_file(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            factor_path = Path(tmp_dir) / "psilst.factor"
            factor_path.write_text(
                "\n".join(
                    [
                        "unrelated header",
                        *MINIMAL_FACTOR_LINES,
                        "unrelated tail should not be required",
                    ]
                ),
                encoding="latin-1",
            )

            lines = read_ui_analysis_lines(str(factor_path))

        self.assertTrue(any("LOAD CASE STATUS REPORT" in line for line in lines))
        self.assertTrue(any("PILE HEAD COORDINATES" in line for line in lines))
        self.assertTrue(any("S O I L  M A X I M U M" in line for line in lines))
        self.assertIn("PILE GROUP SUMMARY", lines)


@unittest.skipUnless(
    FACTOR_PATH is not None and FACTOR_PATH.exists(),
    "需设置 FEASIBILITY_FACTOR_PATH 指向待诊断的 psilst.factor；默认不访问共享盘大文件。",
)
class FeasibilityFactorDiagnosticsTests(unittest.TestCase):
    def _read_relevant_factor_slice(self) -> list[str]:
        lines: list[str] = []
        assert FACTOR_PATH is not None
        with FACTOR_PATH.open("r", encoding="latin-1", errors="ignore") as factor_file:
            for line_number, line in enumerate(factor_file, start=1):
                if 64000 <= line_number <= 92400:
                    lines.append(line.rstrip().replace("\x0c", ""))
                if line_number > 92400:
                    break
        return lines

    def test_relevant_factor_slice_can_build_pile_capacity_tables(self) -> None:
        start = time.perf_counter()
        lines = self._read_relevant_factor_slice()

        load_case_status = parse_load_case_status(lines)
        pile_head_forces = parse_pile_head_forces(lines)
        pile_axial_capacity = parse_pile_axial_capacity_summary(lines)
        pile_capacity = build_pile_head_capacity_summary(
            pile_head_forces,
            pile_axial_capacity,
            case_type_map=load_case_status.get("case_type_map", {}),
        )
        elapsed = time.perf_counter() - start

        print(
            "factor_slice_diagnostics",
            {
                "factor_path": str(FACTOR_PATH),
                "slice_lines": len(lines),
                "load_case_status_rows": len(load_case_status.get("rows", [])),
                "pile_head_force_rows": len(pile_head_forces.get("rows", [])),
                "pile_axial_capacity_rows": len(pile_axial_capacity.get("rows", [])),
                "operation_table_rows": len(pile_capacity.get("operation_table_rows", [])),
                "extreme_table_rows": len(pile_capacity.get("extreme_table_rows", [])),
                "elapsed_seconds": round(elapsed, 3),
            },
        )

        self.assertEqual(72, len(load_case_status.get("rows", [])))
        self.assertGreater(len(pile_head_forces.get("rows", [])), 0)
        self.assertEqual(12, len(pile_axial_capacity.get("rows", [])))
        self.assertEqual(12, len(pile_capacity.get("operation_table_rows", [])))
        self.assertEqual(12, len(pile_capacity.get("extreme_table_rows", [])))

    @unittest.skipUnless(
        os.environ.get("RUN_FULL_FEASIBILITY_PARSE_DIAGNOSTIC") == "1",
        "完整 655MB 结果文件解析诊断耗时较长，默认跳过；需要时设置 RUN_FULL_FEASIBILITY_PARSE_DIAGNOSTIC=1。",
    )
    def test_full_ui_analysis_exceeds_short_timeout(self) -> None:
        timeout_seconds = int(os.environ.get("FEASIBILITY_FULL_PARSE_TIMEOUT", "30"))
        code = f"""
import sys
import time
from pathlib import Path
sys.path.insert(0, r"{REPORT_MODULE_ROOT}")
from src.report_service import build_analysis_results_for_ui
start = time.perf_counter()
result = build_analysis_results_for_ui(r"{FACTOR_PATH}")
pile_capacity = result.get("pile_axial_capacity_summary", {{}})
print({{
    "operation_table_rows": len(pile_capacity.get("operation_table_rows", [])),
    "extreme_table_rows": len(pile_capacity.get("extreme_table_rows", [])),
    "elapsed_seconds": round(time.perf_counter() - start, 3),
}})
"""

        start = time.perf_counter()
        try:
            completed = subprocess.run(
                [sys.executable, "-c", code],
                cwd=str(PROJECT_ROOT),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - start
            print(
                "full_ui_analysis_timeout",
                {
                    "factor_path": str(FACTOR_PATH),
                    "timeout_seconds": timeout_seconds,
                    "elapsed_seconds": round(elapsed, 3),
                    "diagnosis": "完整 build_analysis_results_for_ui 未在短超时内完成，页面空白/长时间加载的主因更可能是整文件解析耗时。",
                },
            )
            return

        print(
            "full_ui_analysis_completed",
            {
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "elapsed_seconds": round(time.perf_counter() - start, 3),
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
