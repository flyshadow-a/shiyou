from types import SimpleNamespace

from pages.platform_summary_page import PlatformSummaryPage


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
