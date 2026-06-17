from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_MODULE_ROOT = PROJECT_ROOT / "pages" / "output_feasibility_analysis_report"
if str(REPORT_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(REPORT_MODULE_ROOT))

from src.config_loader import load_doc_renderer_config  # noqa: E402


def test_splash_zone_report_header_uses_mm_unit() -> None:
    headers = load_doc_renderer_config()["table_headers"]["environment_splash_zone"]

    assert headers == ["飞溅区上限(m)", "飞溅区下限(m)", "腐蚀余量(mm)"]
