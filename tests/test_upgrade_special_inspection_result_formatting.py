import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox

from pages.upgrade_special_inspection_result_page import UpgradeSpecialInspectionResultPage


_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def _bare_result_page_with_detail_tables() -> UpgradeSpecialInspectionResultPage:
    _ensure_app()
    page = UpgradeSpecialInspectionResultPage.__new__(UpgradeSpecialInspectionResultPage)
    page.cb_rows = QComboBox()
    page.cb_rows.addItems(["10", "20", "50", "100", "全部"])
    page.table_comp = UpgradeSpecialInspectionResultPage._make_detail_table(page, is_node=False)
    page.table_node = UpgradeSpecialInspectionResultPage._make_detail_table(page, is_node=True)
    return page


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


def test_detail_rows_render_only_current_limit_by_default():
    page = _bare_result_page_with_detail_tables()
    try:
        rows = [{"joint_a": f"J{i:03d}", "pf": "0.1"} for i in range(200)]

        page._set_detail_rows(page.table_node, rows, is_node=True)

        assert page.table_node.property("detail_row_count") == 200
        assert page.table_node.rowCount() == page.HEADER_ROWS + 10
        assert page.table_node.item(page.HEADER_ROWS, 0).text() == "J000"
        assert page.table_node.item(page.HEADER_ROWS + 9, 0).text() == "J009"
    finally:
        page.table_comp.deleteLater()
        page.table_node.deleteLater()
        page.cb_rows.deleteLater()


def test_apply_row_limit_renders_more_detail_rows_on_demand():
    page = _bare_result_page_with_detail_tables()
    try:
        rows = [{"joint_a": f"J{i:03d}", "pf": "0.1"} for i in range(200)]
        page._set_detail_rows(page.table_node, rows, is_node=True)
        page._set_detail_rows(page.table_comp, rows, is_node=False)

        page.cb_rows.setCurrentText("20")
        page._apply_row_limit()

        assert page.table_node.rowCount() == page.HEADER_ROWS + 20
        assert page.table_node.item(page.HEADER_ROWS + 19, 0).text() == "J019"
        assert page.table_comp.rowCount() == page.HEADER_ROWS + 20
    finally:
        page.table_comp.deleteLater()
        page.table_node.deleteLater()
        page.cb_rows.deleteLater()


def test_result_loading_waits_for_node_table_ready():
    page = UpgradeSpecialInspectionResultPage.__new__(UpgradeSpecialInspectionResultPage)
    page._result_loading_active = True
    page._result_waiting_for_elevation = False
    page._result_waiting_for_node_table = True
    calls: list[bool] = []
    page._set_result_loading = lambda loading: calls.append(loading)

    UpgradeSpecialInspectionResultPage._finish_result_loading_if_ready(page)

    assert calls == []

    page._result_waiting_for_node_table = False
    UpgradeSpecialInspectionResultPage._finish_result_loading_if_ready(page)

    assert calls == [False]
