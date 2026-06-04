from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_oilfield_env_service_uses_shared_engine_builder(monkeypatch):
    from feasibility_analysis_services import oilfield_env_service

    calls: list[tuple[str, bool]] = []
    sentinel = object()

    def fake_build_engine_from_url(sqlalchemy_url: str, *, echo: bool = False):
        calls.append((sqlalchemy_url, echo))
        return sentinel

    monkeypatch.setattr(
        oilfield_env_service,
        "build_engine_from_url",
        fake_build_engine_from_url,
        raising=False,
    )

    engine = oilfield_env_service._create_mysql_engine("sqlite:///:memory:")

    assert engine is sentinel
    assert calls == [("sqlite:///:memory:", False)]


def test_oilfield_page_initial_starts_async_load_once(monkeypatch):
    from PyQt5.QtWidgets import QApplication

    from pages import oilfield_water_level_page

    app = QApplication.instance() or QApplication([])
    async_starts: list[str] = []

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
        oilfield_water_level_page,
        "load_facility_profile",
        lambda facility_code, defaults=None: {
            "facility_code": facility_code,
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
        },
    )
    monkeypatch.setattr(
        oilfield_water_level_page.OilfieldWaterLevelPage,
        "_load_env_top_records",
        lambda self: [{"branch": "B1", "op_company": "O1", "oilfield": "F1"}],
    )
    monkeypatch.setattr(
        oilfield_water_level_page.OilfieldWaterLevelPage,
        "_start_async_current_profile_load",
        lambda self: async_starts.append("start"),
    )

    page = oilfield_water_level_page.OilfieldWaterLevelPage()
    try:
        assert async_starts == ["start"]
    finally:
        page.deleteLater()
        app.processEvents()


def test_oilfield_page_initial_render_does_not_query_database_without_cache(monkeypatch):
    from PyQt5.QtWidgets import QApplication

    from pages import oilfield_water_level_page

    app = QApplication.instance() or QApplication([])
    async_starts: list[str] = []

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

    def fail_sync_database_call(*args, **kwargs):
        raise AssertionError("initial render must not query database synchronously")

    monkeypatch.setattr(oilfield_water_level_page, "load_facility_profile", fail_sync_database_call)
    monkeypatch.setattr(oilfield_water_level_page, "load_env_profiles", fail_sync_database_call)
    monkeypatch.setattr(oilfield_water_level_page, "get_env_profile_id", fail_sync_database_call)
    monkeypatch.setattr(oilfield_water_level_page, "load_water_level_items", fail_sync_database_call)
    monkeypatch.setattr(oilfield_water_level_page, "load_metric_items", fail_sync_database_call)
    monkeypatch.setattr(
        oilfield_water_level_page.OilfieldWaterLevelPage,
        "_start_async_current_profile_load",
        lambda self: async_starts.append("start"),
        raising=False,
    )

    oilfield_water_level_page.clear_oilfield_top_data_cache()
    page = oilfield_water_level_page.OilfieldWaterLevelPage()
    try:
        assert async_starts == ["start"]
        assert page.dropdown_bar.get_value("branch") == "B1"
        assert page.dropdown_bar.get_value("op_company") == "O1"
        assert page.dropdown_bar.get_value("oilfield") == "F1"
    finally:
        page.deleteLater()
        app.processEvents()


def test_oilfield_page_initial_render_hides_placeholder_values_and_disables_save(monkeypatch):
    from PyQt5.QtWidgets import QApplication

    from pages import oilfield_water_level_page

    app = QApplication.instance() or QApplication([])

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
        "_start_async_current_profile_load",
        lambda self: None,
        raising=False,
    )

    oilfield_water_level_page.clear_oilfield_top_data_cache()
    page = oilfield_water_level_page.OilfieldWaterLevelPage()
    try:
        assert page._table_text(page.water_table, 2, 2) == "数据正在读取中..."
        assert page._table_text(page.wind_table, 3, 2) == "数据正在读取中..."
        assert page._table_text(page.wave_table, 3, 2) == "数据正在读取中..."
        assert page._table_text(page.current_table, 3, 2) == "数据正在读取中..."
        assert not page.btn_save.isEnabled()
    finally:
        page.deleteLater()
        app.processEvents()


def test_oilfield_table_loading_message_is_cleared_when_data_applies(monkeypatch):
    from PyQt5.QtWidgets import QApplication

    from pages import oilfield_water_level_page

    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(
        oilfield_water_level_page.OilfieldWaterLevelPage,
        "_load_initial_tables_for_current_profile",
        lambda self: None,
        raising=False,
    )

    page = oilfield_water_level_page.OilfieldWaterLevelPage()
    try:
        page._set_table_loading_message()
        page._apply_table_data(
            {
                "water_items": [
                    {
                        "group_name": "",
                        "item_name": "海图基准面 (CD)",
                        "value": 9.87,
                        "unit": "m",
                        "sort_order": 1,
                    }
                ],
                "wind_items": [],
                "wave_items": [],
                "current_items": [],
            }
        )

        assert page._table_text(page.water_table, 2, 2) == "9.87"
        assert page._table_text(page.wind_table, 3, 2) == ""
        assert page._table_text(page.wave_table, 3, 2) == ""
        assert page._table_text(page.current_table, 3, 2) == ""
    finally:
        page.deleteLater()
        app.processEvents()


def test_oilfield_table_builders_do_not_embed_business_placeholder_values(monkeypatch):
    from PyQt5.QtWidgets import QApplication

    from pages import oilfield_water_level_page

    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(
        oilfield_water_level_page.OilfieldWaterLevelPage,
        "_load_initial_tables_for_current_profile",
        lambda self: None,
        raising=False,
    )

    page = oilfield_water_level_page.OilfieldWaterLevelPage()
    try:
        assert page._table_text(page.water_table, 2, 2) == ""
        assert page._table_text(page.water_table, 6, 2) == ""
        assert page._table_text(page.wind_table, 3, 2) == ""
        assert page._table_text(page.wave_table, 3, 2) == ""
        assert page._table_text(page.current_table, 3, 2) == ""
    finally:
        page.deleteLater()
        app.processEvents()


def test_oilfield_preheated_top_data_feeds_page_without_requery(monkeypatch):
    from PyQt5.QtWidgets import QApplication

    from pages import oilfield_water_level_page

    app = QApplication.instance() or QApplication([])
    profile_calls: list[str] = []
    records_calls: list[str] = []

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
        oilfield_water_level_page,
        "load_facility_profile",
        lambda facility_code, defaults=None: profile_calls.append(facility_code) or {
            "facility_code": facility_code,
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
        },
    )
    monkeypatch.setattr(
        oilfield_water_level_page,
        "load_env_profiles",
        lambda: records_calls.append("records") or [
            {"分公司": "B1", "作业公司": "O1", "油气田": "F1"}
        ],
    )

    oilfield_water_level_page.clear_oilfield_top_data_cache()
    oilfield_water_level_page.preheat_oilfield_top_data(force=True)
    assert profile_calls == ["P1"]
    assert records_calls == ["records"]

    def fail_load_facility_profile(*args, **kwargs):
        raise AssertionError("facility profile should come from preheated cache")

    def fail_load_env_profiles(*args, **kwargs):
        raise AssertionError("top records should come from preheated cache")

    monkeypatch.setattr(oilfield_water_level_page, "load_facility_profile", fail_load_facility_profile)
    monkeypatch.setattr(oilfield_water_level_page, "load_env_profiles", fail_load_env_profiles)
    monkeypatch.setattr(
        oilfield_water_level_page.OilfieldWaterLevelPage,
        "_load_tables_for_current_profile",
        lambda self: None,
    )

    page = oilfield_water_level_page.OilfieldWaterLevelPage()
    try:
        assert page.dropdown_bar.get_value("branch") == "B1"
        assert page.dropdown_bar.get_value("op_company") == "O1"
        assert page.dropdown_bar.get_value("oilfield") == "F1"
    finally:
        page.deleteLater()
        app.processEvents()
        oilfield_water_level_page.clear_oilfield_top_data_cache()


def test_oilfield_preheated_page_data_feeds_tables_without_requery(monkeypatch):
    from PyQt5.QtWidgets import QApplication

    from pages import oilfield_water_level_page

    app = QApplication.instance() or QApplication([])

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
        oilfield_water_level_page,
        "load_facility_profile",
        lambda facility_code, defaults=None: {
            "facility_code": facility_code,
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
        },
    )
    monkeypatch.setattr(
        oilfield_water_level_page,
        "load_env_profiles",
        lambda: [{"分公司": "B1", "作业公司": "O1", "油气田": "F1"}],
    )
    monkeypatch.setattr(oilfield_water_level_page, "get_env_profile_id", lambda **kwargs: 101)
    monkeypatch.setattr(
        oilfield_water_level_page,
        "load_water_level_items",
        lambda profile_id: [
            {
                "group_name": "",
                "item_name": "海图基准面 (CD)",
                "value": 9.87,
                "unit": "m",
                "sort_order": 1,
            }
        ],
    )
    monkeypatch.setattr(
        oilfield_water_level_page,
        "load_metric_items",
        lambda table_name, profile_id: [
            {
                "group_name": "主极值",
                "item_name": "1 h",
                "return_period": 1,
                "value": 8.76,
                "unit": "m/s",
                "sort_order": 1,
            }
        ],
    )

    oilfield_water_level_page.clear_oilfield_top_data_cache()
    oilfield_water_level_page.preheat_oilfield_top_data(force=True)

    def fail_get_env_profile_id(*args, **kwargs):
        raise AssertionError("profile id should come from preheated page cache")

    def fail_load_water_level_items(*args, **kwargs):
        raise AssertionError("water items should come from preheated page cache")

    def fail_load_metric_items(*args, **kwargs):
        raise AssertionError("metric items should come from preheated page cache")

    monkeypatch.setattr(oilfield_water_level_page, "get_env_profile_id", fail_get_env_profile_id)
    monkeypatch.setattr(oilfield_water_level_page, "load_water_level_items", fail_load_water_level_items)
    monkeypatch.setattr(oilfield_water_level_page, "load_metric_items", fail_load_metric_items)

    page = oilfield_water_level_page.OilfieldWaterLevelPage()
    try:
        assert page._table_text(page.water_table, 2, 2) == "9.87"
        assert page._table_text(page.wind_table, 3, 2) == "8.76"
    finally:
        page.deleteLater()
        app.processEvents()
        oilfield_water_level_page.clear_oilfield_top_data_cache()


def test_oilfield_async_worker_waits_for_running_preheat_cache(monkeypatch):
    from pages import oilfield_water_level_page

    emitted: list[object] = []
    failed: list[str] = []
    cached_data = {
        "table_data": {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "profile_id": 101,
            "water_items": [{"item_name": "海图基准面 (CD)", "value": 9.87}],
            "wind_items": [],
            "wave_items": [],
            "current_items": [],
        }
    }

    oilfield_water_level_page.clear_oilfield_top_data_cache()

    with oilfield_water_level_page._OILFIELD_TOP_DATA_CACHE_LOCK:
        oilfield_water_level_page._OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS = True
        oilfield_water_level_page._OILFIELD_TOP_DATA_PREHEAT_DONE.clear()

    original_wait = oilfield_water_level_page._OILFIELD_TOP_DATA_PREHEAT_DONE.wait
    wait_calls: list[float | None] = []

    def fake_wait(timeout=None):
        wait_calls.append(timeout)
        if timeout == 3:
            return False
        with oilfield_water_level_page._OILFIELD_TOP_DATA_CACHE_LOCK:
            oilfield_water_level_page._OILFIELD_TOP_DATA_CACHE = cached_data
            oilfield_water_level_page._OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS = False
            oilfield_water_level_page._OILFIELD_TOP_DATA_PREHEAT_DONE.set()
        return True

    monkeypatch.setattr(oilfield_water_level_page._OILFIELD_TOP_DATA_PREHEAT_DONE, "wait", fake_wait)

    worker = oilfield_water_level_page._OilfieldEnvPageLoadWorker()
    worker.finished.connect(emitted.append)
    worker.failed.connect(failed.append)

    try:
        worker.run()
        assert failed == []
        assert emitted == [cached_data]
        assert wait_calls == [None]
    finally:
        monkeypatch.setattr(oilfield_water_level_page._OILFIELD_TOP_DATA_PREHEAT_DONE, "wait", original_wait)
        oilfield_water_level_page.clear_oilfield_top_data_cache()
