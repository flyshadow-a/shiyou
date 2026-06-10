import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from pages.upgrade_special_inspection_result_page import UpgradeSpecialInspectionResultPage


_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def test_node_risk_pf_keeps_four_significant_digits():
    _ensure_app()
    page = UpgradeSpecialInspectionResultPage("WC19-1D")
    try:
        page._set_detail_rows(
            page.table_node,
            [
                {
                    "joint_a": "J001",
                    "joint_b": "B001",
                    "weld_type": "X Joint",
                    "pf": "0.000123456789",
                    "node_risk_level": "三级",
                }
            ],
            is_node=True,
        )

        assert page.table_node.item(page.HEADER_ROWS, 8).text() == "0.0001235"
    finally:
        page.deleteLater()


def test_node_risk_pr_alias_keeps_four_significant_digits():
    _ensure_app()
    page = UpgradeSpecialInspectionResultPage("WC19-1D")
    try:
        page._set_detail_rows(
            page.table_node,
            [
                {
                    "joint_a": "J001",
                    "joint_b": "B001",
                    "weld_type": "X Joint",
                    "pr": "0.987654321",
                    "node_risk_level": "二级",
                }
            ],
            is_node=True,
        )

        assert page.table_node.item(page.HEADER_ROWS, 8).text() == "0.9877"
    finally:
        page.deleteLater()


def test_component_risk_pf_keeps_four_significant_digits():
    _ensure_app()
    page = UpgradeSpecialInspectionResultPage("WC19-1D")
    try:
        page._set_detail_rows(
            page.table_comp,
            [
                {
                    "joint_a": "J001",
                    "joint_b": "B001",
                    "member_type": "X-Brace",
                    "pf": "0.000987654321",
                    "member_risk_level": "三级",
                }
            ],
            is_node=False,
        )

        assert page.table_comp.item(page.HEADER_ROWS, 8).text() == "0.0009877"
    finally:
        page.deleteLater()
