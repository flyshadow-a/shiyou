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


def test_empty_model_preview_result_clears_existing_vtk_view(monkeypatch):
    from PyQt5.QtWidgets import QApplication, QWidget

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])
    cleared_messages: list[str] = []

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
            super().__init__(parent)
            self._loaded_path = "C:/upload/model_files/sacinp.JKnew"

        def bind_sliders(self, *_args, **_kwargs):
            return None

        def clear_view(self, message=""):
            cleared_messages.append(str(message))
            self._loaded_path = ""

    monkeypatch.setattr(platform_strength_page, "PyVistaSacsView", FakeSacsView)
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        assert page._ensure_inp_view_created() is True

        page._on_model_preview_loaded(
            {
                "seq": page._model_preview_load_seq,
                "path": "",
                "target_z": 9.1,
            }
        )

        assert cleared_messages
        assert "未找到可解析的 SACS 结构模型文件" in cleared_messages[-1]
        assert page.inp_view._loaded_path == ""
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


def test_model_preview_fallback_scan_does_not_use_unscoped_upload_model_for_other_platform(tmp_path):
    from pages import platform_strength_page

    upload_root = tmp_path / "upload" / "model_files"
    upload_root.mkdir(parents=True)
    unscoped_model = upload_root / "sacinp.JKnew"
    unscoped_model.write_text(
        "JOINT A001      0.0    0.0    9.1\n"
        "JOINT A002      1.0    0.0    9.1\n"
        "MEMBER A001A002 G01\n",
        encoding="utf-8",
    )

    assert platform_strength_page._find_best_inp_file_for_preview(
        "NO_DATA_PLATFORM",
        str(upload_root),
        "",
    ) == ""


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
        lambda self, facility_code, target_z, **_kwargs: async_load_calls.append(
            (str(facility_code), float(target_z))
        ),
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
        lambda self, facility_code, target_z, **_kwargs: async_payloads.append(
            (str(facility_code), float(target_z))
        ),
        raising=False,
    )

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        page._autoload_inp_to_view()

        assert async_payloads == [("P1", 9.1)]
    finally:
        page.deleteLater()
        app.processEvents()


def test_pile_edit_dialog_table_uses_excel_clipboard_controller(monkeypatch):
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QKeyEvent
    from PyQt5.QtWidgets import QApplication, QAbstractItemView, QDialog, QTableWidget, QWidget

    from core.table_clipboard import TableClipboardController
    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])

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
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )
    monkeypatch.setattr(
        platform_strength_page.PlatformStrengthPage,
        "_get_strength_profile_context",
        lambda self, create_if_missing=False: (123, "P1"),
    )
    monkeypatch.setattr(
        platform_strength_page,
        "load_platform_strength_pile_items",
        lambda profile_id, facility_code: [
            {
                "pile_head_id": "A001",
                "scour_depth_m": 1.0,
                "compressive_capacity_t": 2.0,
                "uplift_capacity_t": 3.0,
                "submerged_weight_t": 4.0,
                "is_display_row": True,
            },
            {
                "pile_head_id": "A002",
                "scour_depth_m": 5.0,
                "compressive_capacity_t": 6.0,
                "uplift_capacity_t": 7.0,
                "submerged_weight_t": 8.0,
            },
        ],
    )

    captured: dict[str, object] = {}

    def fake_exec(dialog: QDialog) -> int:
        captured["dialog"] = dialog
        tables = dialog.findChildren(QTableWidget)
        captured["table"] = tables[-1]
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", fake_exec)

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        for col, value in enumerate(["11", "22", "33", "44"]):
            page._set_table_text(page.tbl_pile, 0, col, value)

        page._open_pile_edit_dialog()
        edit_table = captured["table"]

        assert isinstance(edit_table._table_clipboard, TableClipboardController)
        assert edit_table.selectionBehavior() == QAbstractItemView.SelectItems
        assert edit_table.selectionMode() == QAbstractItemView.ExtendedSelection
        assert edit_table.editTriggers() == (
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        assert edit_table._table_clipboard._can_paste_cell(0, 0) is True
        assert edit_table._table_clipboard._can_paste_cell(0, 4) is True
        assert edit_table._table_clipboard._can_paste_cell(2, 0) is False

        item = edit_table.item(0, 0)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        assert edit_table._table_clipboard._can_paste_cell(0, 0) is False

        item.setFlags(item.flags() | Qt.ItemIsEditable)
        QApplication.clipboard().clear()
        edit_table.clearSelection()
        edit_table.setCurrentCell(0, 1)
        edit_table._table_clipboard.copy_selection()
        assert QApplication.clipboard().text() == "1"

        QApplication.clipboard().setText("99")
        edit_table.clearSelection()
        edit_table.setCurrentCell(1, 1)
        edit_table._table_clipboard.paste_from_clipboard()
        assert edit_table.item(1, 1).text() == "99"

        add_button = next(
            button
            for button in captured["dialog"].findChildren(QWidget)
            if getattr(button, "text", lambda: "")() == "新增行"
        )
        add_button.click()

        new_row = edit_table.rowCount() - 1
        assert [edit_table.item(new_row, col).text() for col in range(edit_table.columnCount())] == [
            "",
            "",
            "",
            "",
            "",
        ]
    finally:
        page.deleteLater()
        app.processEvents()


def test_horizontal_level_dialog_deletes_selected_columns_and_renumbers(monkeypatch):
    from PyQt5.QtCore import QItemSelectionModel
    from PyQt5.QtWidgets import QApplication, QAbstractItemView, QDialog, QTableWidget, QWidget

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])

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
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )

    captured: dict[str, object] = {}

    def fake_exec(dialog: QDialog) -> int:
        captured["dialog"] = dialog
        captured["table"] = dialog.findChildren(QTableWidget)[-1]
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", fake_exec)

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        page._horizontal_levels = [
            (30.0, 1, True),
            (20.0, 1, True),
            (10.0, 1, True),
            (0.0, 1, True),
        ]

        page._on_update_horizontal_levels_to_db()

        edit_table = captured["table"]
        assert edit_table.columnCount() == 5
        assert edit_table.editTriggers() == QAbstractItemView.DoubleClicked
        assert (
            "QTableWidget::item:selected {\n"
            "                background-color: #dbeafe;\n"
            "            }"
        ) in edit_table.styleSheet()
        assert "QHeaderView::section:selected" not in edit_table.styleSheet()
        assert "QTableWidget::item:selected" in edit_table.styleSheet()

        for col in (2, 4):
            selection = edit_table.selectionModel()
            selection.select(
                edit_table.model().index(0, col),
                QItemSelectionModel.Select | QItemSelectionModel.Columns,
            )
        delete_button = next(
            button
            for button in captured["dialog"].findChildren(QWidget)
            if getattr(button, "text", lambda: "")() == "删除选中列"
        )
        delete_button.click()

        assert edit_table.columnCount() == 3
        assert [edit_table.item(0, col).text() for col in range(edit_table.columnCount())] == [
            "Z(m)",
            "30",
            "10",
        ]
        assert [
            edit_table.horizontalHeaderItem(col).text()
            for col in range(edit_table.columnCount())
        ] == ["编号", "1", "2"]
    finally:
        page.deleteLater()
        app.processEvents()


def test_main_marine_table_remains_read_only(monkeypatch):
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QKeyEvent
    from PyQt5.QtWidgets import QApplication, QAbstractItemView

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(
        platform_strength_page,
        "default_platform",
        lambda: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "platform",
            "category": "wellhead",
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
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        table = page.tbl_marine

        assert not hasattr(table, "_table_clipboard")
        assert table.editTriggers() == QAbstractItemView.NoEditTriggers
        assert table.columnCount() == 4
        assert table.item(0, 3).text() == "1"
        assert table.item(1, 3).text() == ""
        assert table.item(2, 3).text() == ""
        assert table.item(3, 3).text() == ""
        assert table.item(4, 3).text() == ""

        original = table.item(1, 3).text()
        QApplication.clipboard().setText("100\t200\n300\t400")
        table.setCurrentCell(1, 3)
        QApplication.sendEvent(table, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.ControlModifier))

        assert table.item(1, 3).text() == original
    finally:
        page.deleteLater()
        app.processEvents()


def test_marine_edit_dialog_table_uses_excel_clipboard_controller(monkeypatch):
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QKeyEvent
    from PyQt5.QtWidgets import QApplication, QAbstractItemView, QDialog, QTableWidget

    from core.table_clipboard import TableClipboardController
    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(
        platform_strength_page,
        "default_platform",
        lambda: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "platform",
            "category": "wellhead",
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
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )

    captured: dict[str, object] = {}

    def fake_exec(dialog: QDialog) -> int:
        captured["dialog"] = dialog
        captured["table"] = dialog.findChildren(QTableWidget)[-1]
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", fake_exec)

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        page._open_marine_edit_dialog()
        table = captured["table"]

        assert table.columnCount() == 2
        assert isinstance(table._table_clipboard, TableClipboardController)
        assert table.selectionBehavior() == QAbstractItemView.SelectItems
        assert table.selectionMode() == QAbstractItemView.ExtendedSelection
        assert table.editTriggers() == (
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        assert table._table_clipboard._can_paste_cell(0, 0) is False
        assert table._table_clipboard._can_paste_cell(0, 1) is True
        assert table._table_clipboard._can_paste_cell(3, 1) is True
        assert table._table_clipboard._can_paste_cell(3, 2) is False
        assert table._table_clipboard._can_paste_cell(4, 1) is False

        QApplication.clipboard().setText("100\t200\n300\t400")
        table.setCurrentCell(0, 1)
        table._table_clipboard.paste_from_clipboard()

        assert table.item(0, 1).text() == "100"
        assert table.item(1, 1).text() == "300"

        QApplication.clipboard().setText("1.6\t2.0")
        table.clearSelection()
        table.setCurrentCell(3, 1)
        table._table_clipboard.paste_from_clipboard()

        assert table.item(3, 1).text() == "1.6"
    finally:
        page.deleteLater()
        app.processEvents()


def test_marine_tables_expand_to_actual_layer_count(monkeypatch):
    from PyQt5.QtWidgets import QApplication, QDialog, QTableWidget

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(
        platform_strength_page,
        "default_platform",
        lambda: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "platform",
            "category": "wellhead",
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
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )

    captured: dict[str, object] = {}

    def fake_exec(dialog: QDialog) -> int:
        captured["dialog"] = dialog
        captured["table"] = dialog.findChildren(QTableWidget)[-1]
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", fake_exec)

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        items = [
            {
                "layer_no": layer_no,
                "upper_limit_m": layer_no,
                "lower_limit_m": -layer_no,
                "thickness_mm": layer_no * 10,
                "density_t_per_m3": 1.6,
                "sort_order": layer_no,
            }
            for layer_no in range(1, 13)
        ]

        page._apply_marine_items(items)

        assert page.tbl_marine.columnCount() == 15
        assert page.tbl_marine.item(0, 14).text() == "12"
        assert page.tbl_marine.item(1, 14).text() == "12"
        assert page.tbl_marine.item(2, 14).text() == "-12"
        assert page.tbl_marine.item(3, 14).text() == "120"
        assert page.tbl_marine.item(4, 3).text() == "1.6"

        collected = page._collect_quick_assessment_marine_items()
        assert len(collected) == 12
        assert collected[-1]["layer_no"] == 12
        assert collected[-1]["thickness_mm"] == 120

        page._open_marine_edit_dialog()
        edit_table = captured["table"]

        assert edit_table.columnCount() == 13
        assert edit_table.horizontalHeaderItem(12).text() == "12"
        assert edit_table.item(0, 12).text() == "12"
        assert edit_table.item(1, 12).text() == "-12"
        assert edit_table.item(2, 12).text() == "120"
        assert edit_table.item(3, 12).text() == "1.6"
    finally:
        page.deleteLater()
        app.processEvents()


def test_marine_edit_dialog_adds_and_deletes_selected_layers(monkeypatch):
    from PyQt5.QtCore import QItemSelectionModel
    from PyQt5.QtWidgets import QApplication, QDialog, QTableWidget, QWidget

    from pages import platform_strength_page

    app = QApplication.instance() or QApplication([])

    monkeypatch.setattr(
        platform_strength_page,
        "default_platform",
        lambda: {
            "branch": "B1",
            "op_company": "O1",
            "oilfield": "F1",
            "facility_code": "P1",
            "facility_name": "Platform 1",
            "facility_type": "platform",
            "category": "wellhead",
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
        platform_strength_page.PlatformStrengthPage,
        "_schedule_initial_page_load",
        lambda self: None,
    )

    captured: dict[str, object] = {}

    def fake_exec(dialog: QDialog) -> int:
        captured["dialog"] = dialog
        captured["table"] = dialog.findChildren(QTableWidget)[-1]
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec_", fake_exec)

    page = platform_strength_page.PlatformStrengthPage(main_window=None)
    try:
        page._apply_marine_items([
            {"layer_no": 1, "upper_limit_m": 10, "lower_limit_m": 0, "thickness_mm": 1, "density_t_per_m3": 1.2},
            {"layer_no": 2, "upper_limit_m": 20, "lower_limit_m": 10, "thickness_mm": 2, "density_t_per_m3": 1.2},
        ])
        page._open_marine_edit_dialog()

        dialog = captured["dialog"]
        table = captured["table"]
        add_button = next(
            button
            for button in dialog.findChildren(QWidget)
            if getattr(button, "text", lambda: "")() == "增加层"
        )
        delete_button = next(
            button
            for button in dialog.findChildren(QWidget)
            if getattr(button, "text", lambda: "")() == "删除选中层"
        )

        assert table.columnCount() == 3
        add_button.click()
        add_button.click()

        assert table.columnCount() == 5
        assert [table.horizontalHeaderItem(col).text() for col in range(table.columnCount())] == [
            "项目",
            "1",
            "2",
            "3",
            "4",
        ]
        assert [table.item(row, 4).text() for row in range(table.rowCount())] == ["", "", "", ""]

        for col in (2, 4):
            table.selectionModel().select(
                table.model().index(0, col),
                QItemSelectionModel.Select | QItemSelectionModel.Columns,
            )
        delete_button.click()

        assert table.columnCount() == 3
        assert [table.horizontalHeaderItem(col).text() for col in range(table.columnCount())] == [
            "项目",
            "1",
            "2",
        ]
        assert table.item(0, 1).text() == "10"
        assert table.item(0, 2).text() == ""

        table.selectionModel().select(
            table.model().index(0, 1),
            QItemSelectionModel.Select | QItemSelectionModel.Columns,
        )
        table.selectionModel().select(
            table.model().index(0, 2),
            QItemSelectionModel.Select | QItemSelectionModel.Columns,
        )
        delete_button.click()

        assert table.columnCount() == 2
        assert table.horizontalHeaderItem(1).text() == "1"
        assert [table.item(row, 1).text() for row in range(table.rowCount())] == ["", "", "", ""]
    finally:
        page.deleteLater()
        app.processEvents()
