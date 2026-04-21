from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from jinja2 import Environment, StrictUndefined

from pages.output_special_strategy.report_jinja2_generator import (
    NS,
    merge_metadata_into_context,
    paragraph_text,
    render_text_placeholders,
)
from services.special_strategy_runtime import generate_special_strategy_report


class SpecialStrategyReportMetadataTests(unittest.TestCase):
    def test_merge_metadata_into_context_keeps_runtime_context_stable(self) -> None:
        context = {
            "platform_name": "默认平台",
            "report_date": "2026-04-20",
            "member_inspection_total": 8,
            "node_summary_blocks": [{"title": "当前"}],
        }
        metadata = {
            "platform_name": "前端平台",
            "custom_text": "前端补充说明",
            "member_inspection_total": 99,
            "node_summary_blocks": "should-not-override",
            "section": {"name": "章节一"},
        }

        merged = merge_metadata_into_context(context, metadata)

        self.assertEqual(merged["platform_name"], "前端平台")
        self.assertEqual(merged["custom_text"], "前端补充说明")
        self.assertEqual(merged["section"], {"name": "章节一"})
        self.assertEqual(merged["member_inspection_total"], 8)
        self.assertEqual(merged["node_summary_blocks"], [{"title": "当前"}])
        self.assertEqual(merged["report_metadata"], metadata)

    def test_render_text_placeholders_supports_frontend_metadata(self) -> None:
        root = ET.fromstring(
            f"""
            <w:document xmlns:w="{NS["w"]}">
              <w:body>
                <w:p><w:r><w:t>补充说明：{{{{ custom_text }}}}</w:t></w:r></w:p>
                <w:tbl>
                  <w:tr>
                    <w:tc>
                      <w:p><w:r><w:t>{{{{ report_metadata.section.name }}}}</w:t></w:r></w:p>
                    </w:tc>
                  </w:tr>
                </w:tbl>
              </w:body>
            </w:document>
            """
        )
        env = Environment(undefined=StrictUndefined, autoescape=False, trim_blocks=True, lstrip_blocks=True)

        render_text_placeholders(
            root,
            {
                "custom_text": "由前端写入",
                "report_metadata": {"section": {"name": "附加章节"}},
            },
            env,
        )

        paragraphs = root.findall(".//w:p", NS)
        self.assertEqual(paragraph_text(paragraphs[0]), "补充说明：由前端写入")
        self.assertEqual(paragraph_text(paragraphs[1]), "附加章节")

    def test_generate_report_reads_runtime_report_metadata_json_at_report_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbook_path = root / "special_strategy.pipeline.xlsx"
            template_path = root / "template.docx"
            metadata_path = root / "report_metadata.json"
            workbook_path.write_text("demo", encoding="utf-8")
            template_path.write_text("demo", encoding="utf-8")
            metadata_path.write_text(
                json.dumps(
                    {
                        "platform_name": "前端平台名",
                        "custom_text": "前端补充内容",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            fake_paths = {
                "root": root,
                "params_json": root / "runtime_params.json",
                "intermediate_workbook": workbook_path,
                "output_report": root / "special_strategy.docx",
                "report_metadata_json": metadata_path,
                "state_json": root / "runtime_state.json",
            }
            fake_state = {
                "intermediate_workbook": str(workbook_path),
                "metadata": {"report_date": "2026-04-20"},
                "db_run_id": 12,
            }
            fake_cfg = {
                "report_template": str(template_path),
                "appendix_a_file": "",
                "appendix_b_file": "",
                "appendix_c_dirs": [],
                "include_word_plan_detail_tables": False,
            }
            captured: dict[str, dict] = {}

            def fake_context(_workbook_path: Path, _cfg: dict, metadata: dict) -> dict:
                captured["metadata"] = dict(metadata)
                return {
                    "platform_name": metadata.get("platform_name", ""),
                    "report_date": metadata.get("report_date", ""),
                }

            with patch("services.special_strategy_runtime.load_runtime_state", return_value=fake_state), patch(
                "services.special_strategy_runtime.load_base_config",
                return_value=fake_cfg,
            ), patch(
                "services.special_strategy_runtime.default_metadata",
                return_value={"platform_name": "默认平台", "report_date": "默认日期"},
            ), patch(
                "services.special_strategy_runtime.runtime_paths",
                return_value=fake_paths,
            ), patch(
                "services.special_strategy_runtime._context_from_workbook",
                side_effect=fake_context,
            ), patch(
                "services.special_strategy_runtime.render_report",
            ), patch(
                "services.special_strategy_runtime.insert_appendix_pdf_images",
            ), patch(
                "services.special_strategy_runtime.update_strategy_report",
            ), patch(
                "services.special_strategy_runtime._write_json",
            ):
                report_path = generate_special_strategy_report("WC19-1D")

        self.assertEqual(report_path, fake_paths["output_report"])
        self.assertEqual(captured["metadata"]["platform_name"], "前端平台名")
        self.assertEqual(captured["metadata"]["custom_text"], "前端补充内容")
        self.assertEqual(captured["metadata"]["report_date"], "2026-04-20")

    def test_generate_report_rejects_invalid_runtime_report_metadata_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbook_path = root / "special_strategy.pipeline.xlsx"
            metadata_path = root / "report_metadata.json"
            workbook_path.write_text("demo", encoding="utf-8")
            metadata_path.write_text("{invalid", encoding="utf-8")

            fake_paths = {
                "root": root,
                "params_json": root / "runtime_params.json",
                "intermediate_workbook": workbook_path,
                "output_report": root / "special_strategy.docx",
                "report_metadata_json": metadata_path,
                "state_json": root / "runtime_state.json",
            }
            fake_state = {
                "intermediate_workbook": str(workbook_path),
                "metadata": {},
            }
            fake_cfg = {
                "report_template": str(root / "template.docx"),
                "appendix_a_file": "",
                "appendix_b_file": "",
                "appendix_c_dirs": [],
                "include_word_plan_detail_tables": False,
            }

            with patch("services.special_strategy_runtime.load_runtime_state", return_value=fake_state), patch(
                "services.special_strategy_runtime.load_base_config",
                return_value=fake_cfg,
            ), patch(
                "services.special_strategy_runtime.default_metadata",
                return_value={"platform_name": "默认平台", "report_date": "默认日期"},
            ), patch(
                "services.special_strategy_runtime.runtime_paths",
                return_value=fake_paths,
            ):
                with self.assertRaisesRegex(ValueError, "报告占位符 JSON 解析失败"):
                    generate_special_strategy_report("WC19-1D")

    def test_generate_report_auto_writes_report_metadata_json_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_root = root / "special_strategy_run_20260421_090000_000001"
            run_root.mkdir(parents=True, exist_ok=True)
            workbook_path = run_root / "special_strategy.pipeline.xlsx"
            template_path = root / "template.docx"
            workbook_path.write_text("demo", encoding="utf-8")
            template_path.write_text("demo", encoding="utf-8")

            fake_paths = {
                "root": root,
                "params_json": root / "runtime_params.json",
                "intermediate_workbook": workbook_path,
                "output_report": root / "special_strategy.docx",
                "report_metadata_json": root / "report_metadata.json",
                "state_json": root / "runtime_state.json",
            }
            run_payload = {
                "id": 12,
                "facility_code": "WC19-1D",
                "intermediate_workbook": str(workbook_path),
                "output_report": str(run_root / "special_strategy.docx"),
                "metadata_json": {"report_date": "2026-04-21"},
                "params_json": {
                    "no_legs": 8,
                    "life_safety_level": "S-2",
                    "failure_consequence_level": "C-1",
                    "global_level_tag": "L-2",
                    "design_life": 26,
                },
            }
            fake_cfg = {
                "report_template": str(template_path),
                "appendix_a_file": "",
                "appendix_b_file": "",
                "appendix_c_dirs": [],
                "include_word_plan_detail_tables": False,
            }
            captured: dict[str, dict] = {}

            def fake_context(_workbook_path: Path, _cfg: dict, metadata: dict) -> dict:
                captured["metadata"] = dict(metadata)
                return {
                    "platform_name": metadata.get("platform_name", ""),
                    "report_date": metadata.get("report_date", ""),
                }

            with patch("services.special_strategy_runtime.load_strategy_run_by_id", return_value=run_payload), patch(
                "services.special_strategy_runtime.load_base_config",
                return_value=fake_cfg,
            ), patch(
                "services.special_strategy_runtime.runtime_paths",
                return_value=fake_paths,
            ), patch(
                "services.special_strategy_runtime.find_platform",
                return_value={
                    "facility_code": "WC19-1D",
                    "facility_name": "WC19-1D平台",
                    "oilfield": "文昌19-1油田",
                    "facility_type": "平台",
                    "category": "导管架平台",
                    "start_time": "2013-07-15",
                    "design_life": "15",
                },
            ), patch(
                "services.special_strategy_runtime.default_metadata",
                return_value={"platform_name": "WC19-1D平台", "report_date": "2026-04-21"},
            ), patch(
                "services.special_strategy_runtime._context_from_workbook",
                side_effect=fake_context,
            ), patch(
                "services.special_strategy_runtime.render_report",
            ), patch(
                "services.special_strategy_runtime.insert_appendix_pdf_images",
            ), patch(
                "services.special_strategy_runtime.update_strategy_report",
            ):
                generate_special_strategy_report("WC19-1D", run_id=12)

            metadata_path = run_root / "report_metadata.json"
            self.assertTrue(metadata_path.exists())
            payload = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(payload["oilfield_name"], "文昌19-1油田")
            self.assertEqual(payload["leg_count"], "8")
            self.assertEqual(payload["platform_type"], "导管架平台")
            self.assertEqual(payload["life_safety_level"], "S-2")
            self.assertEqual(payload["failure_consequence_level"], "C-1")
            self.assertEqual(payload["exposure_level"], "L-2")
            self.assertEqual(captured["metadata"]["oilfield_name"], "文昌19-1油田")
            self.assertEqual(captured["metadata"]["leg_count"], "8")

    def test_render_text_placeholders_reports_missing_placeholder_key(self) -> None:
        root = ET.fromstring(
            f"""
            <w:document xmlns:w="{NS["w"]}">
              <w:body>
                <w:p><w:r><w:t>{{{{ platform_name }}}} 平台位于 {{{{ oilfield_name }}}}</w:t></w:r></w:p>
              </w:body>
            </w:document>
            """
        )
        env = Environment(undefined=StrictUndefined, autoescape=False, trim_blocks=True, lstrip_blocks=True)

        with self.assertRaisesRegex(ValueError, "oilfield_name"):
            render_text_placeholders(
                root,
                {
                    "platform_name": "测试平台",
                },
                env,
            )


if __name__ == "__main__":
    unittest.main()
