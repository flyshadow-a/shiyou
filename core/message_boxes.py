from __future__ import annotations

from PyQt5.QtWidgets import QMessageBox, QWidget


def ask_yes_no(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    default_yes: bool = False,
) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

    yes_button = box.button(QMessageBox.Yes)
    no_button = box.button(QMessageBox.No)
    if yes_button is not None:
        yes_button.setText("是")
    if no_button is not None:
        no_button.setText("否")

    default_button = yes_button if default_yes else no_button
    if default_button is not None:
        box.setDefaultButton(default_button)

    return box.exec_() == QMessageBox.Yes
