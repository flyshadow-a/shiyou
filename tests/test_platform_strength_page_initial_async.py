from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_platform_strength_page_initial_load_is_scheduled_not_run_synchronously(monkeypatch):
    from PyQt5.QtWidgets import QApplication, QWidget

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])
    sync_calls: list[str] = []
    scheduled_calls: list[str] = []

    monkeypatch.setattr(
        platform_strength_page,
        "default_platform",
        lambda: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "平台",
            "category": "井口平台",
            "start_time": "2020-01-01",
            "design_life": "20",
        },
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_facility_profile",
        lambda facility_code, defaults=None: dict(defaults or {}, facility_code=facility_code),
    )

    class FakeSacsView(QWidget):
        def bind_sliders(self, *_args, **_kwargs):
            return None

        def clear_view(self, *_args, **_kwargs):
            return None

        def load_inp(self, *_args, **_kwargs):
            raise AssertionError("model preview must not load synchronously in __init__")

    monkeypatch.setattr(platform_strength_page, "PyVistaSacsView", FakeSacsView)
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_load_strength_env_tables",
        lambda self: sync_calls.append("env"),
    )
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_autoload_inp_to_view",
        lambda self: sync_calls.append("model"),
    )
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: scheduled_calls.append("scheduled"),
        raising=False,
    )

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        assert sync_calls == []
        assert scheduled_calls == ["scheduled"]
    finally:
        page.deleteLater()
        app.processEvents()


def test_platform_strength_page_defers_vtk_preview_creation_until_model_load(monkeypatch):
    from PyQt5.QtWidgets import QApplication, QWidget

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])
    created_views: list[str] = []

    monkeypatch.setattr(
        platform_strength_page,
        "default_platform",
        lambda: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "平台",
            "category": "井口平台",
            "start_time": "2020-01-01",
            "design_life": "20",
        },
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_facility_profile",
        lambda facility_code, defaults=None: dict(defaults or {}, facility_code=facility_code),
    )

    class FakeSacsView(QWidget):
        def __init__(self, parent=None):
            created_views.append("created")
            super().__init__(parent)
            self._loaded_path = ""

        def bind_sliders(self, *_args, **_kwargs):
            return None

        def clear_view(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(platform_strength_page, "PyVistaSacsView", FakeSacsView)
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        assert created_views == []

        page._ensure_inp_view_created()

        assert created_views == ["created"]
    finally:
        page.deleteLater()
        app.processEvents()


def test_empty_model_preview_result_keeps_placeholder_without_creating_vtk(monkeypatch):
    from PyQt5.QtWidgets import QApplication, QWidget

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])
    created_views: list[str] = []

    monkeypatch.setattr(
        platform_strength_page,
        "default_platform",
        lambda: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "平台",
            "category": "井口平台",
            "start_time": "2020-01-01",
            "design_life": "20",
        },
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_facility_profile",
        lambda facility_code, defaults=None: dict(defaults or {}, facility_code=facility_code),
    )

    class FakeSacsView(QWidget):
        def __init__(self, parent=None):
            created_views.append("created")
            super().__init__(parent)

    monkeypatch.setattr(platform_strength_page, "PyVistaSacsView", FakeSacsView)
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        page._on_model_preview_loaded(
            {
                "seq": page._model_preview_load_seq,
                "path": "",
                "target_z": 9.1,
            }
        )

        assert created_views == []
        assert page.inp_view is None
        assert page.inp_view_placeholder.text().startswith("未找到可解析")
    finally:
        page.deleteLater()
        app.processEvents()


def test_load_strength_env_payload_collects_database_rows(monkeypatch):
    from pages import platform_strength_page

    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        platform_strength_page,
        "get_env_profile_id",
        lambda **kwargs: calls.append(("profile", kwargs)) or 321,
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_platform_strength_splash_items",
        lambda profile_id, facility_code, mysql_url=None: calls.append(
            ("splash", (profile_id, facility_code, mysql_url))
        ) or [{"sort_order": 1, "upper_limit_m": 1.0}],
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_platform_strength_pile_items",
        lambda profile_id, facility_code, mysql_url=None: calls.append(
            ("pile", (profile_id, facility_code, mysql_url))
        ) or [{"pile_head_id": "P1", "sort_order": 1}],
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_platform_strength_marine_items",
        lambda profile_id, facility_code, mysql_url=None: calls.append(
            ("marine", (profile_id, facility_code, mysql_url))
        ) or [{"layer_no": 1, "sort_order": 1}],
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_structure_model_info",
        lambda mysql_url, **kwargs: calls.append(("structure", (mysql_url, kwargs)))
        or {"mud_level_m": -80.0, "workpoint_m": 9.1, "level_threshold": 40},
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_horizontal_levels",
        lambda mysql_url, **kwargs: calls.append(("levels", (mysql_url, kwargs)))
        or [{"z_m": 9.1, "node_count": 50, "selected": 1}],
    )

    payload = platform_strength_page.load_strength_env_payload(
        {
            "seq": 7,
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "mysql_url": "mysql://example",
        }
    )

    assert payload["seq"] == 7
    assert payload["profile_id"] == 321
    assert payload["splash_items"] == [{"sort_order": 1, "upper_limit_m": 1.0}]
    assert payload["pile_items"] == [{"pile_head_id": "P1", "sort_order": 1}]
    assert payload["marine_items"] == [{"layer_no": 1, "sort_order": 1}]
    assert payload["structure_model_info"]["mud_level_m"] == -80.0
    assert payload["horizontal_levels"] == [{"z_m": 9.1, "node_count": 50, "selected": 1}]
    assert calls[0][0] == "profile"
    assert calls[-1][0] == "levels"


def test_load_model_preview_payload_resolves_empty_path_before_parsing(monkeypatch, tmp_path):
    from pages import platform_strength_page

    model_path = tmp_path / "sacinp.JKnew"
    model_path.write_text("", encoding="utf-8")
    parsed_paths: list[str] = []

    monkeypatch.setattr(
        platform_strength_page,
        "resolve_model_preview_file",
        lambda payload: str(model_path),
    )
    monkeypatch.setattr(
        platform_strength_page,
        "parse_sacs_full_robust_file",
        lambda file_path: parsed_paths.append(str(file_path)) or ({}, [], {}),
    )
    monkeypatch.setattr(
        platform_strength_page,
        "parse_mud_level_from_sacinp_file",
        lambda file_path: None,
    )

    payload = platform_strength_page.load_model_preview_payload(
        {
            "seq": 11,
            "facility_code": "P1",
            "path": "",
            "target_z": 9.1,
        }
    )

    assert parsed_paths == [str(model_path)]
    assert payload["path"] == str(model_path)


def test_autoload_model_preview_starts_worker_instead_of_parsing_on_ui_thread(monkeypatch, tmp_path):
    from PyQt5.QtWidgets import QApplication, QWidget

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])
    model_path = tmp_path / "sacinp.JKnew"
    model_path.write_text(
        "JOINT A001      0.0    0.0    9.1\n"
        "JOINT A002      1.0    0.0    9.1\n"
        "MEMBER A001A002 G01\n",
        encoding="utf-8",
    )
    sync_load_calls: list[str] = []
    async_load_calls: list[tuple[str, float]] = []

    monkeypatch.setattr(
        platform_strength_page,
        "default_platform",
        lambda: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "平台",
            "category": "井口平台",
            "start_time": "2020-01-01",
            "design_life": "20",
        },
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_facility_profile",
        lambda facility_code, defaults=None: dict(defaults or {}, facility_code=facility_code),
    )
    monkeypatch.setattr(
        platform_strength_page,
        "sync_platform_dropdowns",
        lambda dropdown_bar, changed_key=None: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "平台",
            "category": "井口平台",
            "start_time": "2020-01-01",
            "design_life": "20",
        },
    )

    class FakeSacsView(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._loaded_path = ""

        def bind_sliders(self, *_args, **_kwargs):
            return None

        def clear_view(self, *_args, **_kwargs):
            return None

        def load_inp(self, path, target_z=9.1):
            sync_load_calls.append(str(path))

    monkeypatch.setattr(platform_strength_page, "PyVistaSacsView", FakeSacsView)
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_resolve_current_preview_model_file",
        lambda self, facility_code: str(model_path),
    )
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_start_async_model_preview_load",
        lambda self, path, target_z: async_load_calls.append((str(path), float(target_z))),
        raising=False,
    )

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        page._autoload_inp_to_view()

        assert sync_load_calls == []
        assert async_load_calls == [("P1", 9.1)]
    finally:
        page.deleteLater()
        app.processEvents()


def test_autoload_model_preview_does_not_resolve_model_path_on_ui_thread(monkeypatch):
    from PyQt5.QtWidgets import QApplication, QWidget

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])
    async_payloads: list[tuple[str, float]] = []

    monkeypatch.setattr(
        platform_strength_page,
        "default_platform",
        lambda: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "平台",
            "category": "井口平台",
            "start_time": "2020-01-01",
            "design_life": "20",
        },
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_facility_profile",
        lambda facility_code, defaults=None: dict(defaults or {}, facility_code=facility_code),
    )
    monkeypatch.setattr(
        platform_strength_page,
        "sync_platform_dropdowns",
        lambda dropdown_bar, changed_key=None: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "平台",
            "category": "井口平台",
            "start_time": "2020-01-01",
            "design_life": "20",
        },
    )

    class FakeSacsView(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._loaded_path = ""

        def bind_sliders(self, *_args, **_kwargs):
            return None

        def clear_view(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(platform_strength_page, "PyVistaSacsView", FakeSacsView)
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_resolve_current_preview_model_file",
        lambda self, facility_code: (_ for _ in ()).throw(
            AssertionError("model path resolution must not run synchronously in _autoload_inp_to_view")
        ),
    )
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_start_async_model_preview_load",
        lambda self, facility_code, target_z: async_payloads.append((str(facility_code), float(target_z))),
        raising=False,
    )

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        page._autoload_inp_to_view()

        assert async_payloads == [("P1", 9.1)]
    finally:
        page.deleteLater()
        app.processEvents()
