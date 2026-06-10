import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QWidget

from core.dialog_utils import exec_dialog_safely


_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def test_exec_dialog_safely_uses_explicit_qdialog_exec(monkeypatch):
    _ensure_app()
    dialog = QDialog()
    seen = []

    monkeypatch.setattr(
        "core.dialog_utils.QDialog.exec_",
        lambda current: seen.append(current) or QDialog.Accepted,
    )

    try:
        assert exec_dialog_safely(dialog, title="测试", context="测试窗口") == QDialog.Accepted
        assert seen == [dialog]
    finally:
        dialog.deleteLater()


def test_exec_dialog_safely_handles_invalid_dialog(monkeypatch):
    _ensure_app()
    widget = QWidget()
    messages = []

    monkeypatch.setattr(
        "core.dialog_utils.QMessageBox.critical",
        lambda _parent, title, text: messages.append((title, text)),
    )

    try:
        assert exec_dialog_safely(widget, title="上传窗口错误", context="选择文件类别窗口") is None
        assert messages
        assert "选择文件类别窗口初始化失败" in messages[0][1]
    finally:
        widget.deleteLater()


def test_exec_dialog_safely_handles_exec_typeerror(monkeypatch):
    _ensure_app()
    dialog = QDialog()
    messages = []

    monkeypatch.setattr(
        "core.dialog_utils.QDialog.exec_",
        lambda _dialog: (_ for _ in ()).throw(
            TypeError("exec_(self): first argument of unbound method must have type 'QDialog'")
        ),
    )
    monkeypatch.setattr(
        "core.dialog_utils.QMessageBox.critical",
        lambda _parent, title, text: messages.append((title, text)),
    )

    try:
        assert exec_dialog_safely(dialog, title="上传窗口错误", context="选择文件类别窗口") is None
        assert messages
        assert "选择文件类别窗口打开失败" in messages[0][1]
    finally:
        dialog.deleteLater()
