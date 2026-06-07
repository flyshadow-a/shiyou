from pages.special_inspection_strategy import SpecialInspectionStrategy


def test_special_strategy_syncs_when_oilfield_changes(monkeypatch):
    page = SpecialInspectionStrategy.__new__(SpecialInspectionStrategy)
    calls = []

    monkeypatch.setattr(
        page,
        "_sync_platform_ui",
        lambda changed_key=None: calls.append(changed_key),
    )

    page._on_top_filter_changed("oilfield", "WC9-7")

    assert calls == ["oilfield"]
