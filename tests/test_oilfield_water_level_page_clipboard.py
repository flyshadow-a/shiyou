from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QApplication, QTableWidgetSelectionRange

_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return app


def _build_page(monkeypatch):
    from pages import oilfield_water_level_page

    monkeypatch.setattr(
        oilfield_water_level_page,
        "default_platform",
        lambda: {
            "facility_code": "P1",
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
        },
    )
    monkeypatch.setattr(
        oilfield_water_level_page.OilfieldWaterLevelPage,
        "_load_initial_tables_for_current_profile",
        lambda self: None,
    )
    return oilfield_water_level_page.OilfieldWaterLevelPage()


def test_oilfield_water_table_supports_copy_and_paste(monkeypatch):
    _ensure_app()
    QApplication.clipboard().clear()
    page = _build_page(monkeypatch)
    try:
        table = page.water_table
        table.item(2, 2).setText("1.23")
        table.item(3, 2).setText("4.56")
        table.setRangeSelected(QTableWidgetSelectionRange(2, 2, 3, 2), True)

        copy_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_C, Qt.ControlModifier)
        QApplication.sendEvent(table, copy_event)
        assert QApplication.clipboard().text() == "1.23\n4.56"

        table.item(2, 2).setText("")
        table.item(3, 2).setText("")
        table.clearSelection()
        table.setCurrentCell(2, 2)
        QApplication.clipboard().setText("7.89\n8.90")

        paste_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(table, paste_event)

        assert table.item(2, 2).text() == "7.89"
        assert table.item(3, 2).text() == "8.90"
    finally:
        page.deleteLater()
        QApplication.instance().processEvents()


def test_oilfield_wind_table_paste_skips_locked_columns(monkeypatch):
    _ensure_app()
    QApplication.clipboard().clear()
    page = _build_page(monkeypatch)
    try:
        table = page.wind_table
        table.setRangeSelected(QTableWidgetSelectionRange(3, 0, 3, 3), True)
        table.setCurrentCell(3, 0)
        QApplication.clipboard().setText("a\tb\tc\td")

        paste_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier)
        QApplication.sendEvent(table, paste_event)

        assert table.item(3, 0).text() == "主极值"
        assert table.item(3, 1).text() == "1 h"
        assert table.item(3, 2).text() == "c"
        assert table.item(3, 3).text() == "d"
    finally:
        page.deleteLater()
        QApplication.instance().processEvents()


def test_oilfield_tables_define_visible_selected_item_style(monkeypatch):
    _ensure_app()
    page = _build_page(monkeypatch)
    try:
        style = page.water_table.styleSheet()
        assert "QTableWidget::item:selected" in style
        assert "background-color: #dbe9ff" in style
        assert "color: #000000" in style
    finally:
        page.deleteLater()
        QApplication.instance().processEvents()
