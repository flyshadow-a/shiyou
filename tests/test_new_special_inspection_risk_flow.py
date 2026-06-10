import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QDialog

from pages.new_special_inspection_page import NewSpecialInspectionPage
from pages.special_strategy_rule_dialogs import normalize_rule_overrides

_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def _bare_page() -> NewSpecialInspectionPage:
    page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
    page.facility_code = "WC19-1D"
    page._risk_thread = None
    page._manual_fill_check_thread = None
    page.btn_update_risk = None
    page.btn_view_result = None
    page._rule_overrides = normalize_rule_overrides({})
    return page


def test_update_risk_starts_async_manual_fill_check_before_prepare():
    page = _bare_page()
    calls: list[str] = []
    captured: dict = {}

    page._validate_fatigue_groups = lambda: True
    page._run_pre_risk_rule_dialog_sequence = lambda: calls.append("pre_rules") or True
    page._collect_runtime_input_overrides = lambda: {}

    def collect_runtime_overrides():
        return {"rule_overrides": normalize_rule_overrides(page._rule_overrides)}

    def start_manual_fill_check(param_overrides, input_overrides):
        calls.append("manual_fill_check")
        captured["param_overrides"] = param_overrides
        captured["input_overrides"] = input_overrides

    page._collect_runtime_overrides = collect_runtime_overrides
    page._start_manual_fill_check_worker = start_manual_fill_check
    page._start_risk_calculation_worker = lambda **_kwargs: calls.append("start_worker")

    NewSpecialInspectionPage._on_update_risk_level(page)

    assert calls == ["pre_rules", "manual_fill_check"]
    assert captured["param_overrides"]["rule_overrides"] == normalize_rule_overrides({})
    assert captured["input_overrides"] == {}


def test_manual_fill_check_result_starts_prepare_after_single_client_dialog(monkeypatch):
    _ensure_app()
    page = _bare_page()
    rows = [{"joint_i": "301L", "joint_j": "401L"}]
    calls: list[str] = []
    captured: dict = {}

    class FakeManualDialog(QDialog):
        def __init__(self, dialog_rows, _parent=None):
            super().__init__()
            self.dialog_rows = dialog_rows
            self.result_entries = [{"FileIndex": 1, "Joint": "301L", "ManualBrace": "306L"}]

    created: list[FakeManualDialog] = []

    def make_dialog(*args, **kwargs):
        dialog = FakeManualDialog(*args, **kwargs)
        created.append(dialog)
        return dialog

    def start_worker(**kwargs):
        calls.append("start_worker")
        captured.update(kwargs)

    monkeypatch.setattr("pages.new_special_inspection_page.ManualBraceClientDialog", make_dialog)
    monkeypatch.setattr("pages.new_special_inspection_page.QDialog.exec_", lambda _dialog: QDialog.Accepted)
    page._close_active_manual_fill_check_progress = lambda: calls.append("close_progress")
    page._start_risk_calculation_worker = start_worker

    NewSpecialInspectionPage._on_manual_fill_check_finished(
        page,
        {
            "rows": rows,
            "param_overrides": {"rule_overrides": normalize_rule_overrides({})},
            "input_overrides": {},
        },
    )

    assert calls == ["close_progress", "start_worker"]
    assert created[0].dialog_rows == rows
    assert captured["stage"] == "prepare"
    assert captured["metadata"]["manual_fill_entries"] == [
        {"FileIndex": 1, "Joint": "301L", "ManualBrace": "306L"}
    ]


def test_manual_fill_check_result_stops_when_dialog_is_cancelled(monkeypatch):
    _ensure_app()
    page = _bare_page()
    calls: list[str] = []
    monkeypatch.setattr(
        "pages.new_special_inspection_page.QMessageBox.information",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr("pages.new_special_inspection_page.QDialog.exec_", lambda _dialog: QDialog.Rejected)

    class FakeManualDialog(QDialog):
        def __init__(self, *_args, **_kwargs):
            super().__init__()

    monkeypatch.setattr("pages.new_special_inspection_page.ManualBraceClientDialog", FakeManualDialog)
    page._close_active_manual_fill_check_progress = lambda: None
    page._start_risk_calculation_worker = lambda **_kwargs: calls.append("start_worker")

    NewSpecialInspectionPage._on_manual_fill_check_finished(
        page,
        {
            "rows": [{"joint_i": "301L", "joint_j": "401L"}],
            "param_overrides": {"rule_overrides": normalize_rule_overrides({})},
            "input_overrides": {},
        },
    )

    assert calls == []


def test_prepare_result_runs_exclusion_dialogs_before_finalize():
    page = _bare_page()
    calls: list[str] = []
    captured: dict = {}
    page._pending_prepared_calculation = {"facility_code": "WC19-1D", "prepared_pipeline": {}}

    def run_post_rules(_prepared):
        calls.append("exclusion_rules")
        page._rule_overrides = normalize_rule_overrides(
            {
                "joint_exclusions": ["R001"],
            }
        )
        return True

    def collect_runtime_overrides():
        return {"rule_overrides": normalize_rule_overrides(page._rule_overrides)}

    def start_worker(**kwargs):
        calls.append("start_worker")
        captured.update(kwargs)

    page._run_post_risk_rule_dialog_sequence = run_post_rules
    page._collect_runtime_overrides = collect_runtime_overrides
    page._start_risk_calculation_worker = start_worker

    NewSpecialInspectionPage._begin_post_risk_rule_stage(page)

    assert calls == ["exclusion_rules", "start_worker"]
    assert captured["stage"] == "finalize"
    assert captured["param_overrides"]["rule_overrides"]["joint_exclusions"] == ["R001"]


def test_local_manual_fill_check_opens_client_dialog(monkeypatch):
    _ensure_app()
    page = _bare_page()
    rows = [{"joint_i": "301L", "joint_j": "401L"}]
    progress_calls = []

    monkeypatch.setattr("pages.new_special_inspection_page._use_fastapi_backend", lambda: False)
    monkeypatch.setattr(
        "pages.new_special_inspection_page.check_special_strategy_manual_fill_rows",
        lambda *_args, **_kwargs: rows,
    )
    page._show_manual_fill_check_progress = lambda: progress_calls.append("show") or object()
    page._close_manual_fill_check_progress = lambda _progress: progress_calls.append("close")

    class FakeManualDialog(QDialog):
        def __init__(self, dialog_rows, _parent=None):
            super().__init__()
            self.dialog_rows = dialog_rows
            self.result_entries = [{"ManualBrace": "306L"}]

    created: list[FakeManualDialog] = []

    def make_dialog(*args, **kwargs):
        dialog = FakeManualDialog(*args, **kwargs)
        created.append(dialog)
        return dialog

    monkeypatch.setattr("pages.new_special_inspection_page.ManualBraceClientDialog", make_dialog)
    monkeypatch.setattr("pages.new_special_inspection_page.QDialog.exec_", lambda _dialog: QDialog.Accepted)

    result = NewSpecialInspectionPage._collect_client_manual_fill_entries(page, {}, {})

    assert created[0].dialog_rows == rows
    assert result == [{"ManualBrace": "306L"}]
    assert progress_calls == ["show", "close"]


def test_local_manual_fill_handles_invalid_dialog_factory(monkeypatch):
    page = _bare_page()
    rows = [{"joint_i": "301L", "joint_j": "401L"}]
    messages = []

    monkeypatch.setattr("pages.new_special_inspection_page._use_fastapi_backend", lambda: False)
    monkeypatch.setattr(
        "pages.new_special_inspection_page.check_special_strategy_manual_fill_rows",
        lambda *_args, **_kwargs: rows,
    )
    page._show_manual_fill_check_progress = lambda: None
    page._close_manual_fill_check_progress = lambda _progress: None
    monkeypatch.setattr("pages.new_special_inspection_page.ManualBraceClientDialog", lambda *_args: object())
    monkeypatch.setattr(
        "pages.new_special_inspection_page.QMessageBox.critical",
        lambda _parent, title, text: messages.append((title, text)),
    )

    result = NewSpecialInspectionPage._collect_client_manual_fill_entries(page, {}, {})

    assert result is None
    assert messages
    assert "疲劳输入检查窗口" in messages[0][1]


def test_manual_fill_check_progress_closes_without_missing_rows(monkeypatch):
    page = _bare_page()
    progress_calls = []

    monkeypatch.setattr("pages.new_special_inspection_page._use_fastapi_backend", lambda: False)
    monkeypatch.setattr(
        "pages.new_special_inspection_page.check_special_strategy_manual_fill_rows",
        lambda *_args, **_kwargs: [],
    )
    page._show_manual_fill_check_progress = lambda: progress_calls.append("show") or object()
    page._close_manual_fill_check_progress = lambda _progress: progress_calls.append("close")

    result = NewSpecialInspectionPage._collect_client_manual_fill_entries(page, {}, {})

    assert result == []
    assert progress_calls == ["show", "close"]


def test_rule_dialog_uses_safe_exec(monkeypatch):
    page = _bare_page()
    messages = []

    monkeypatch.setattr("pages.new_special_inspection_page.SpecialStrategyRuleDialog", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        "pages.new_special_inspection_page.QMessageBox.critical",
        lambda _parent, title, text: messages.append((title, text)),
    )

    result = NewSpecialInspectionPage._open_rule_dialog(
        page,
        "member_exclusion",
        joint_ids=[],
        member_pairs=[],
        preview_available=False,
        current_rules=normalize_rule_overrides({}),
    )

    assert result is None
    assert messages
    assert "规则设置窗口" in messages[0][1]
