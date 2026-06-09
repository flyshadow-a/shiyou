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
from src.parsers.basic_case_desc_parser import parse_basic_case_desc
from src.parsers.basic_case_loads_parser import parse_basic_case_loads
from src.parsers.joint_can_summary_builder import build_joint_can_summary
from src.parsers.joint_can_summary_parser import parse_joint_can_summary
from src.parsers.member_group_summary_parser import parse_member_group_summary
from src.parsers.psilst_reader import read_lines, read_ui_analysis_lines


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
    "                                        FINAL PILE HEAD FORCES (KN   AND KN-M    ) FOR LOAD CASE OL16",
    "                                                    PILE HEAD COORDINATES",
    "     PILE   BATTER",
    "     JOINT  JOINT       FORCE(X)       FORCE(Y)       FORCE(Z)      MOMENT(X)      MOMENT(Y)      MOMENT(Z)",
    "     001P   101P     -30315.626      -1571.200        317.665          5.901       4102.623      10058.362",
    "                                                     STRUCTURAL COORDINATES",
    "                                        FINAL PILE HEAD FORCES (KN   AND KN-M    ) FOR LOAD CASE EL16",
    "                                                    PILE HEAD COORDINATES",
    "     PILE   BATTER",
    "     JOINT  JOINT       FORCE(X)       FORCE(Y)       FORCE(Z)      MOMENT(X)      MOMENT(Y)      MOMENT(Z)",
    "     001P   101P     -46458.635      -1571.200        317.665          5.901       4102.623      10058.362",
    "                                                     STRUCTURAL COORDINATES",
    "                               * * *  S O I L  M A X I M U M  A X I A L  C A P A C I T Y  S U M M A R Y  * * *",
    "PILE GRP  ********* PILE *********  ************** COMPRESSION *************  **************** TENSION ***************",
    " JT         PILEHEAD  WEIGHT  PEN.   CAPACITY    MAX.     CRITICAL CONDITION   CAPACITY    MAX.     CRITICAL CONDITION    *MAXIMUM*",
    "           O.D.  THK.               (INCL. WT)   LOAD      LOAD  LOAD SAFETY  (INCL. WT)   LOAD      LOAD  LOAD SAFETY    UNITY LOAD",
    "           CM    CM     KN     M       KN        KN        KN    CASE FACTOR     KN        KN        KN    CASE FACTOR    CHECK CASE",
    "001P PA  243.80  9.50 6002.4 133.0  -89154.0  -46458.6  -46458.6 EL16   1.92   96017.2    7875.0    7875.0 LTL3  12.19     0.78 EL16",
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

    def test_pile_head_forces_only_read_final_pile_head_coordinates_block(self) -> None:
        lines = [
            "                                        FINAL PILE HEAD FORCES (KN   AND KN-M    ) FOR LOAD CASE T688",
            "                                                    PILE HEAD COORDINATES",
            "     PILE   BATTER",
            "     JOINT  JOINT       FORCE(X)       FORCE(Y)       FORCE(Z)      MOMENT(X)      MOMENT(Y)      MOMENT(Z)",
            "     001P   101P     -32140.752      -5682.946       -649.623         23.159      -3529.758      30538.847",
            "                                                     STRUCTURAL COORDINATES",
            "     PILE   BATTER",
            "     JOINT  JOINT       FORCE(X)       FORCE(Y)       FORCE(Z)      MOMENT(X)      MOMENT(Y)      MOMENT(Z)",
            "     001P   101P       2456.450      -5105.631     -32140.752     -22746.325     -13237.139         23.159",
            "                                        INTERNAL FORCES ON STRUCTURE (KN   AND KN-M    ) FOR LOAD CASE T688",
            "                                                    PILE HEAD COORDINATES",
            "     PILE   BATTER",
            "     JOINT  JOINT       FORCE(X)       FORCE(Y)       FORCE(Z)      MOMENT(X)      MOMENT(Y)      MOMENT(Z)",
            "     001P   101P      32140.937       5682.956        649.610        -23.157       3529.725     -30538.893",
        ]

        result = parse_pile_head_forces(lines)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("T688", result["rows"][0]["load_case"])
        self.assertEqual("001P", result["rows"][0]["pile_head_id"])
        self.assertEqual(-32140.752, result["rows"][0]["axial_force_kn"])

    def test_pile_axial_capacity_skips_load_header_like_rows(self) -> None:
        lines = [
            "                               * * *  S O I L  M A X I M U M  A X I A L  C A P A C I T Y  S U M M A R Y  * * *",
            "001P PA  OD THK WEIGHT PEN. CAPACITY MAX. CRITICAL LOAD SAFETY CAPACITY MAX. CRITICAL LOAD SAFETY UNITY CASE",
            "001P PA  243.80  9.50 6002.4 133.0  -89154.0  -46458.6  -46458.6 EL16   1.92   96017.2    7875.0    7875.0 LTL3  12.19     0.78 EL16",
            "***** SACS LOAD CASE REPORT *****",
        ]

        result = parse_pile_axial_capacity_summary(lines)

        self.assertEqual(1, len(result["rows"]))
        self.assertEqual("001P", result["rows"][0]["pile_head_id"])

    def test_joint_summary_builder_uses_original_strength_uc_like_readpsilist(self) -> None:
        lines = [
            "* * J O I N T   C A N   S U M M A R Y * *",
            "(UNITY CHECK ORDER)",
            "      **************** ORIGINAL ******************   ************ LOAD DESIGN ***********   *** STRENGTH ANALYSIS ****",
            "                                      LOAD    STRN                                  LOAD    STRN    BRACE   LOAD",
            "JOINT DIAMETER THICKNESS  YLD STRS    UC      UC     DIAMETER THICKNESS  YLD STRS    UC      UC     JOINT   CASE",
            " 636W  61.000    1.600    355.000   0.329   2.600     61.000    1.600    355.000   0.329     0.100   W643   EL1A",
            " 175L 320.001    8.500    355.000   1.431   0.844    320.001    8.500    355.000   1.431     5.000   205L   EL14",
            "P I L E  G R O U P  S U M M A R Y",
        ]

        parsed = parse_joint_can_summary(lines)
        built = build_joint_can_summary(parsed)

        self.assertEqual(2.6, parsed["rows"][0]["orig_strn_uc"])
        self.assertEqual(0.1, parsed["rows"][0]["design_strn_uc"])
        self.assertEqual("636W", built["max_joint"])
        self.assertEqual("EL1A", built["max_case"])
        self.assertEqual(2.6, built["max_uc"])

    def test_read_ui_analysis_lines_extracts_relevant_blocks_from_file(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            factor_path = Path(tmp_dir) / "psilst.factor"
            factor_path.write_text(
                "\n".join(
                    [
                        "unrelated header",
                        *MINIMAL_FACTOR_LINES,
                        "* *  P I L E  G R O U P  S U M M A R Y  * *",
                        "       0.0    25.937   7.294 0.00478    85014.8   7470.5 -52465.2  215.62  -75.03   21.37 -290.65   P201     EL16      0.872",
                        "\x0c",
                        "unrelated tail should not be required",
                    ]
                ),
                encoding="latin-1",
            )

            lines = read_ui_analysis_lines(str(factor_path))

        self.assertTrue(any("LOAD CASE STATUS REPORT" in line for line in lines))
        self.assertTrue(any("FINAL PILE HEAD FORCES" in line for line in lines))
        self.assertTrue(any("PILE HEAD COORDINATES" in line for line in lines))
        self.assertTrue(any("S O I L  M A X I M U M" in line for line in lines))
        self.assertTrue(any("P I L E  G R O U P  S U M M A R Y" in line for line in lines))

    def test_read_ui_analysis_lines_extracts_member_and_joint_summary_blocks(self) -> None:
        import tempfile

        member_marker = "* * *  M E M B E R  G R O U P  S U M M A R Y  * * *"
        joint_marker = "* * J O I N T   C A N   S U M M A R Y * *"

        with tempfile.TemporaryDirectory() as tmp_dir:
            factor_path = Path(tmp_dir) / "psilst.factor"
            factor_path.write_bytes(
                "\n".join(
                    [
                        "          **** LOAD CASE STATUS REPORT ****",
                        "                               * * *  S O I L  M A X I M U M  A X I A L  C A P A C I T Y  S U M M A R Y  * * *",
                        "001P PA  243.80  9.50 6002.4 133.0  -89154.0  -46458.6  -46458.6 EL16   1.92   96017.2    7875.0    7875.0 LTL3  12.19     0.78 EL16",
                        "***** SACS LOAD CASE REPORT *****",
                        "unrelated middle content",
                        member_marker,
                        "1A1 601L-611L OP17   0.43   0.9    -54.5   33.1    1.8   .2E+03 .6E+06 .3E+03 .3E+03   HYDRO    0.92   0.92   0.85   0.85",
                        "\x0c",
                        member_marker,
                        "1B1 501L-511L OP16   0.68  11.8   -112.1   -7.1   -2.5    177.5  979.2  235.1  235.1   HYDRO   23.61  23.61   0.85   0.85",
                        "\x0c",
                        joint_marker,
                        " 636W  61.000    1.600    355.000   0.329   2.600     61.000    1.600    355.000   0.329     2.600   W643   EL1A",
                        "\x0c",
                        joint_marker,
                        " 615W  61.000    1.600    355.000   0.453   2.594     61.000    1.600    355.000   0.453     2.594   W613   OL17",
                        "\x0c",
                    ]
                ).encode("latin-1")
            )

            lines = read_ui_analysis_lines(str(factor_path))

        self.assertTrue(any(member_marker in line for line in lines))
        self.assertTrue(any("601L-611L" in line for line in lines))
        self.assertTrue(any("501L-511L" in line for line in lines))
        self.assertTrue(any(joint_marker in line for line in lines))
        self.assertTrue(any("636W" in line for line in lines))
        self.assertTrue(any("615W" in line for line in lines))

    def test_large_report_read_lines_keeps_basic_case_sections(self) -> None:
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            factor_path = Path(tmp_dir) / "psilst.M1"
            factor_path.write_bytes(
                "\n".join(
                    [
                        "noise before",
                        "** SEASTATE BASIC LOAD CASE DESCRIPTIONS **",
                        "CASE LABEL DESCRIPTION",
                        "1 OP1 OPERATING CASE",
                        "2 EL1 EXTREME CASE",
                        "****** SEASTATE BASIC LOAD CASE SUMMARY ******",
                        "CASE LABEL FX FY FZ MX MY MZ DEAD BUOY",
                        "1 OP1 1 2 3 4 5 6 7 8",
                        "2 EL1 9 10 11 12 13 14 15 16",
                        "***** SEASTATE COMBINED LOAD CASES *****",
                        "COMBINED BASIC LOAD CASE",
                        "101 OL1 1 1.0",
                        "****** SEASTATE COMBINED LOAD CASE SUMMARY ******",
                        "101 OL1 1 2 3 4 5 6",
                        *MINIMAL_FACTOR_LINES,
                        "tail",
                    ]
                ).encode("latin-1")
            )

            with patch("src.parsers.psilst_reader.os.path.getsize", return_value=1024 * 1024 * 1024):
                lines = read_lines(str(factor_path))

        self.assertEqual(2, len(parse_basic_case_desc(lines)))
        self.assertEqual(2, len(parse_basic_case_loads(lines)))

    def test_member_and_joint_raw_blocks_include_all_paginated_sections(self) -> None:
        member_marker = "* * *  M E M B E R  G R O U P  S U M M A R Y  * * *"
        joint_marker = "* * J O I N T   C A N   S U M M A R Y * *"
        joint_headers = [
            "(UNITY CHECK ORDER)",
            "      **************** ORIGINAL ******************   ************ LOAD DESIGN ***********   *** STRENGTH ANALYSIS ****",
            "                                      LOAD    STRN                                  LOAD    STRN    BRACE   LOAD",
            "JOINT DIAMETER THICKNESS  YLD STRS    UC      UC     DIAMETER THICKNESS  YLD STRS    UC      UC     JOINT   CASE",
        ]
        lines = [
            member_marker,
            "1A1 601L-611L OP17   0.43   0.9    -54.5   33.1    1.8   .2E+03 .6E+06 .3E+03 .3E+03   HYDRO    0.92   0.92   0.85   0.85",
            member_marker,
            "1B1 501L-511L OP16   0.68  11.8   -112.1   -7.1   -2.5    177.5  979.2  235.1  235.1   HYDRO   23.61  23.61   0.85   0.85",
            joint_marker,
            *joint_headers,
            " 636W  61.000    1.600    355.000   0.329   2.600     61.000    1.600    355.000   0.329     2.600   W643   EL1A",
            joint_marker,
            *joint_headers,
            " 615W  61.000    1.600    355.000   0.453   2.594     61.000    1.600    355.000   0.453     2.594   W613   OL17",
            "P I L E  G R O U P  S U M M A R Y",
        ]

        member = parse_member_group_summary(lines)
        joint = parse_joint_can_summary(lines)

        self.assertEqual(2, len(member["rows"]))
        self.assertIn("601L-611L", member["raw_block"])
        self.assertIn("501L-511L", member["raw_block"])
        self.assertEqual(2, len(joint["rows"]))
        self.assertIn("636W", joint["raw_block"])
        self.assertIn("615W", joint["raw_block"])

    def test_joint_can_parser_ignores_non_unity_check_summary_blocks(self) -> None:
        lines = [
            "* * J O I N T   C A N   S U M M A R Y * *",
            "SOME OTHER REPORT ORDER",
            " 202X  61.000    1.600    355.000 202.680  14.040     61.000    1.600    355.000   0.329     2.600   W643   EL1A",
            "P I L E  G R O U P  S U M M A R Y",
        ]

        joint = parse_joint_can_summary(lines)

        self.assertEqual([], joint["rows"])
        self.assertEqual("", joint["raw_block"])

    def test_joint_can_parser_keeps_large_uc_values_in_valid_unity_check_block(self) -> None:
        lines = [
            "* * J O I N T   C A N   S U M M A R Y * *",
            "(UNITY CHECK ORDER)",
            "      **************** ORIGINAL ******************   ************ LOAD DESIGN ***********   *** STRENGTH ANALYSIS ****",
            "                                      LOAD    STRN                                  LOAD    STRN    BRACE   LOAD",
            "JOINT DIAMETER THICKNESS  YLD STRS    UC      UC     DIAMETER THICKNESS  YLD STRS    UC      UC     JOINT   CASE",
            " 999X  61.000    1.600    355.000  202.68  114.04     61.000    1.600    355.000   0.329     0.100   W643   EL1A",
            " 636W  61.000    1.600    355.000   0.329   2.600     61.000    1.600    355.000   0.329     0.100   W643   EL1A",
            "P I L E  G R O U P  S U M M A R Y",
        ]

        parsed = parse_joint_can_summary(lines)
        built = build_joint_can_summary(parsed)

        self.assertEqual(2, len(parsed["rows"]))
        self.assertEqual("999X", parsed["rows"][0]["joint"])
        self.assertEqual(202.68, parsed["rows"][0]["orig_load_uc"])
        self.assertEqual(114.04, parsed["rows"][0]["orig_strn_uc"])
        self.assertEqual("999X", built["max_joint"])
        self.assertEqual("EL1A", built["max_case"])
        self.assertEqual(114.04, built["max_uc"])


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
