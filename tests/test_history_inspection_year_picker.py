# -*- coding: utf-8 -*-
import datetime
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog

from pages.history_events_inspection_page import AddInspectionProjectDialog
from pages.history_inspection_summary_page import (
    AddPeriodicInspectionDialog,
    AddSpecialEventInspectionDialog,
    InspectionProjectEditDialog,
    WheelYearSpinBox,
    YearSelectLineEdit,
    YearWheelDialog,
)


_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


class FakeWheelDelta:
    def __init__(self, value: int):
        self._value = value

    def y(self) -> int:
        return self._value


class FakeWheelEvent:
    def __init__(self, angle_delta: int = 0, pixel_delta: int = 0):
        self._angle_delta = angle_delta
        self._pixel_delta = pixel_delta
        self.accepted = False

    def angleDelta(self) -> FakeWheelDelta:
        return FakeWheelDelta(self._angle_delta)

    def pixelDelta(self) -> FakeWheelDelta:
        return FakeWheelDelta(self._pixel_delta)

    def accept(self) -> None:
        self.accepted = True


def test_year_dialog_parses_existing_year_text() -> None:
    assert YearWheelDialog.parse_year("2025") == 2025
    assert YearWheelDialog.parse_year("2025年") == 2025
    assert YearWheelDialog.parse_year("2025-06-01") == 2025


def test_year_dialog_clamps_or_defaults_year() -> None:
    current_year = max(1950, min(2150, datetime.date.today().year))

    assert YearWheelDialog.parse_year("1940") == 1950
    assert YearWheelDialog.parse_year("2160") == 2150
    assert YearWheelDialog.parse_year("") == current_year


def test_wheel_year_spin_box_changes_value_with_mouse_wheel_and_wraps() -> None:
    _ensure_app()
    spin = WheelYearSpinBox()
    spin.setRange(1950, 2150)
    spin.setWrapping(True)
    spin.setValue(2150)

    event = FakeWheelEvent(angle_delta=120)
    spin.wheelEvent(event)

    assert event.accepted
    assert spin.value() == 1950

    spin.wheelEvent(FakeWheelEvent(angle_delta=-120))
    assert spin.value() == 2150


def test_wheel_year_spin_box_accumulates_small_deltas() -> None:
    _ensure_app()
    spin = WheelYearSpinBox()
    spin.setRange(1950, 2150)
    spin.setWrapping(True)
    spin.setValue(2025)

    spin.wheelEvent(FakeWheelEvent(angle_delta=40))
    assert spin.value() == 2025
    spin.wheelEvent(FakeWheelEvent(angle_delta=80))

    assert spin.value() == 2026


def test_year_select_line_edit_is_read_only_and_uses_current_year_default() -> None:
    _ensure_app()
    current_year = str(max(1950, min(2150, datetime.date.today().year)))

    edit = YearSelectLineEdit()

    assert edit.isReadOnly()
    assert edit.cursor().shape() == Qt.PointingHandCursor
    assert edit.text() == current_year


def test_year_select_line_edit_click_dialog_writes_selected_year(monkeypatch) -> None:
    _ensure_app()

    class FakeYearDialog:
        parse_year = staticmethod(YearWheelDialog.parse_year)

        def __init__(self, value, parent=None):
            self.initial_value = value

        def selected_year_text(self) -> str:
            return "2031"

    monkeypatch.setattr("pages.history_inspection_summary_page.YearWheelDialog", FakeYearDialog)
    monkeypatch.setattr(
        "pages.history_inspection_summary_page.exec_dialog_safely",
        lambda dialog, **kwargs: QDialog.Accepted,
    )

    edit = YearSelectLineEdit("2025")
    edit.open_year_dialog()

    assert edit.text() == "2031"


def test_inspection_project_dialogs_use_year_picker() -> None:
    _ensure_app()
    dialogs = [
        AddInspectionProjectDialog(),
        AddPeriodicInspectionDialog(),
        AddSpecialEventInspectionDialog(),
        InspectionProjectEditDialog(title_text="编辑检测项目", project_year="2028"),
    ]

    for dialog in dialogs:
        assert isinstance(dialog.year_edit, YearSelectLineEdit)
        assert dialog.year_edit.isReadOnly()

    assert dialogs[-1].year_edit.text() == "2028"
