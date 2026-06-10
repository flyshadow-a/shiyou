from typing import Any

from PyQt5.QtWidgets import QDialog, QMessageBox, QWidget


def exec_dialog_safely(
    dialog: object,
    *,
    title: str = "窗口错误",
    context: str = "窗口",
    parent: QWidget | None = None,
) -> int | None:
    """Safely execute a QDialog without relying on bound exec_ lookup."""
    if not isinstance(dialog, QDialog):
        QMessageBox.critical(parent, title, f"{context}初始化失败，请重新打开页面后再试。")
        return None
    try:
        return int(QDialog.exec_(dialog))
    except TypeError as exc:
        QMessageBox.critical(parent or dialog.parentWidget(), title, f"{context}打开失败：\n{exc}")
        return None


def accepted(result: Any) -> bool:
    return result == QDialog.Accepted
