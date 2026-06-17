import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QTableWidget

from pages.platform_summary_page import (
    DateWheelDialog,
    PlatformDetailDialog,
    PlatformSummaryPage,
    WheelSpinBox,
)


_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


class FakeTabWidget:
    def __init__(self, widgets):
        self._widgets = list(widgets)

    def count(self):
        return len(self._widgets)

    def widget(self, index):
        return self._widgets[index]


class DatabaseRefreshPage:
    def __init__(self):
        self.calls = []

    def refresh_from_database(self):
        self.calls.append("database")


class PlatformDropdownPage:
    def __init__(self):
        self.calls = []

    def _sync_platform_ui(self, changed_key=None):
        self.calls.append(("platform", changed_key))


class FakeDropdownBar:
    def __init__(self):
        self.options = {}
        self.values = {}

    def set_options(self, key, options, default=""):
        self.options[key] = list(options)
        self.values[key] = default


class PreferredPlatformDropdownPage:
    def __init__(self):
        self.calls = []
        self.dropdown_bar = FakeDropdownBar()

    def _sync_platform_ui(self, changed_key=None):
        self.calls.append(("platform", changed_key))


def test_notify_summary_pages_refresh_updates_database_and_platform_dropdown_pages():
    database_page = DatabaseRefreshPage()
    platform_page = PlatformDropdownPage()
    tab_widget = FakeTabWidget([database_page, platform_page])
    page = SimpleNamespace(window=lambda: SimpleNamespace(tab_widget=tab_widget))

    PlatformSummaryPage._notify_summary_pages_refresh(page)

    assert database_page.calls == ["database"]
    assert platform_page.calls == [("platform", None)]


def test_notify_summary_pages_refresh_selects_preferred_new_platform():
    platform_page = PreferredPlatformDropdownPage()
    tab_widget = FakeTabWidget([platform_page])
    page = SimpleNamespace(window=lambda: SimpleNamespace(tab_widget=tab_widget))

    PlatformSummaryPage._notify_summary_pages_refresh(page, preferred_facility_code="NEW-1")

    assert platform_page.dropdown_bar.options["facility_code"] == ["NEW-1"]
    assert platform_page.dropdown_bar.values["facility_code"] == "NEW-1"
    assert platform_page.calls == [("platform", "facility_code")]


def test_preferred_new_facility_code_uses_saved_source_as_baseline(monkeypatch):
    page = SimpleNamespace(
        current_facility_profiles=lambda: [
            {"facility_code": "OLD-1"},
            {"facility_code": "NEW-1"},
        ]
    )
    monkeypatch.setattr(
        "pages.platform_summary_page.load_platform_summary_source",
        lambda snapshot_key="latest": SimpleNamespace(profiles=[{"facility_code": "OLD-1"}]),
    )

    assert PlatformSummaryPage._preferred_new_facility_code_for_refresh(page) == "NEW-1"


def test_save_refreshes_platform_cache_before_notifying_dropdown_pages(monkeypatch):
    calls = []
    page = SimpleNamespace(
        table=object(),
        columns=["设施编码"],
        _preferred_new_facility_code_for_refresh=lambda: "NEW-1",
        _collect_snapshot_rows=lambda: [["NEW-1"]],
        _sync_profiles_to_database=lambda: (1, 0, []),
        _store_session_profiles_cache=lambda: calls.append("store-session-cache"),
        _notify_summary_pages_refresh=lambda preferred_facility_code=None: calls.append(
            ("notify", preferred_facility_code)
        ),
    )

    monkeypatch.setattr(
        "pages.platform_summary_page.save_platform_summary_snapshot",
        lambda *args, **kwargs: calls.append("save-snapshot"),
    )
    monkeypatch.setattr(
        "pages.platform_summary_page.refresh_platform_profiles_cache",
        lambda: calls.append("refresh-platform-cache"),
    )
    monkeypatch.setattr(
        "pages.platform_summary_page.QMessageBox.information",
        lambda *args, **kwargs: None,
    )

    PlatformSummaryPage.on_save_clicked(page)

    assert calls == [
        "save-snapshot",
        "refresh-platform-cache",
        "store-session-cache",
        ("notify", "NEW-1"),
    ]


def test_date_wheel_dialog_parses_existing_date_text():
    assert DateWheelDialog.parse_date_parts("2013/7/5") == (2013, 7, 5)
    assert DateWheelDialog.parse_date_parts("2013.07.05") == (2013, 7, 5)
    assert DateWheelDialog.parse_date_parts("2013年7月5日") == (2013, 7, 5)


def test_date_wheel_dialog_clamps_invalid_existing_date_parts():
    assert DateWheelDialog.parse_date_parts("1940-13-40") == (1950, 12, 31)
    assert DateWheelDialog.parse_date_parts("2060-02-31") == (2050, 2, 28)


def test_date_wheel_dialog_uses_month_day_limits():
    assert DateWheelDialog.days_in_month(2024, 2) == 29
    assert DateWheelDialog.days_in_month(2023, 2) == 28
    assert DateWheelDialog.days_in_month(2023, 4) == 30
    assert DateWheelDialog.days_in_month(2023, 12) == 31


class FakeWheelDelta:
    def __init__(self, value):
        self._value = value

    def y(self):
        return self._value


class FakeWheelEvent:
    def __init__(self, angle_delta=0, pixel_delta=0):
        self._angle_delta = angle_delta
        self._pixel_delta = pixel_delta
        self.accepted = False

    def angleDelta(self):
        return FakeWheelDelta(self._angle_delta)

    def pixelDelta(self):
        return FakeWheelDelta(self._pixel_delta)

    def accept(self):
        self.accepted = True


def test_wheel_spin_box_changes_value_with_mouse_wheel_and_wraps():
    _ensure_app()
    spin = WheelSpinBox()
    spin.setRange(1, 12)
    spin.setWrapping(True)
    spin.setValue(12)

    event = FakeWheelEvent(angle_delta=120)
    spin.wheelEvent(event)

    assert event.accepted
    assert spin.value() == 1

    spin.wheelEvent(FakeWheelEvent(angle_delta=-120))

    assert spin.value() == 12


def test_wheel_spin_box_accumulates_small_touchpad_deltas():
    _ensure_app()
    spin = WheelSpinBox()
    spin.setRange(1, 12)
    spin.setWrapping(True)
    spin.setValue(6)

    spin.wheelEvent(FakeWheelEvent(angle_delta=40))
    assert spin.value() == 6
    spin.wheelEvent(FakeWheelEvent(angle_delta=80))

    assert spin.value() == 7


def test_date_wheel_dialog_uses_mouse_wheel_spin_boxes():
    _ensure_app()
    dialog = DateWheelDialog("2024-02-29")

    assert isinstance(dialog.year_spin, WheelSpinBox)
    assert isinstance(dialog.month_spin, WheelSpinBox)
    assert isinstance(dialog.day_spin, WheelSpinBox)
    assert dialog.year_spin.wrapping()
    assert dialog.month_spin.wrapping()
    assert dialog.day_spin.wrapping()
    assert dialog.year_spin.lineEdit().isReadOnly()


def test_platform_detail_date_fields_are_normalized_and_not_editable():
    _ensure_app()
    dialog = PlatformDetailDialog(
        {
            "投产时间": "2013/7/5",
            "服役到期时间": "2028年07月15日",
        },
        is_new=True,
    )

    start_item = dialog.table.item(7, 1)
    due_item = dialog.table.item(9, 1)

    assert start_item.text() == "2013-07-05"
    assert due_item.text() == "2028-07-15"
    assert not (start_item.flags() & Qt.ItemIsEditable)
    assert not (due_item.flags() & Qt.ItemIsEditable)


def test_platform_detail_clicking_date_field_writes_selected_date(monkeypatch):
    _ensure_app()

    class FakeDateDialog:
        parse_date_parts = staticmethod(DateWheelDialog.parse_date_parts)

        def __init__(self, value, parent=None):
            self.initial_value = value

        def selected_date_text(self):
            return "2024-02-29"

    monkeypatch.setattr("pages.platform_summary_page.DateWheelDialog", FakeDateDialog)
    monkeypatch.setattr(
        "pages.platform_summary_page.exec_dialog_safely",
        lambda dialog, **kwargs: QDialog.Accepted,
    )

    dialog = PlatformDetailDialog({"投产时间": "2024-02-01"}, is_new=True)
    dialog._on_detail_table_cell_clicked(7, 1)

    assert dialog.table.item(7, 1).text() == "2024-02-29"


def test_summary_table_date_item_is_normalized_and_not_editable():
    item = PlatformSummaryPage._make_summary_table_item(
        SimpleNamespace(),
        "投产时间",
        "2013/7/5",
    )

    assert item.text() == "2013-07-05"
    assert not (item.flags() & Qt.ItemIsEditable)


def test_summary_table_clicking_date_field_writes_selected_date(monkeypatch):
    _ensure_app()
    calls = []
    page = SimpleNamespace(
        table=QTableWidget(1, 1),
        columns=["服役到期时间"],
        _store_session_profiles_cache=lambda: calls.append("store"),
        _schedule_summary_pages_refresh=lambda: calls.append("refresh"),
    )
    page.table.setItem(
        0,
        0,
        PlatformSummaryPage._make_summary_table_item(page, "服役到期时间", "2028-07-15"),
    )

    class FakeDateDialog:
        def __init__(self, value, parent=None):
            self.initial_value = value

        def selected_date_text(self):
            return "2029-01-02"

    monkeypatch.setattr("pages.platform_summary_page.DateWheelDialog", FakeDateDialog)
    monkeypatch.setattr(
        "pages.platform_summary_page.exec_dialog_safely",
        lambda dialog, **kwargs: QDialog.Accepted,
    )

    PlatformSummaryPage._on_summary_table_cell_clicked(page, 0, 0)

    assert page.table.item(0, 0).text() == "2029-01-02"
    assert calls == ["store", "refresh"]
