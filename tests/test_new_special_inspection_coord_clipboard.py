# -*- coding: utf-8 -*-
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QAbstractItemView, QTableWidget, QTableWidgetItem

from core.table_clipboard import TableClipboardController
from pages.new_special_inspection_page import NewSpecialInspectionPage


_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _APP = app
    return app


def _item(text: str, *, editable: bool = True) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    flags = item.flags()
    if editable:
        flags |= Qt.ItemIsEditable
    else:
        flags &= ~Qt.ItemIsEditable
    item.setFlags(flags)
    return item


def _bare_page_with_coord_table() -> NewSpecialInspectionPage:
    page = NewSpecialInspectionPage.__new__(NewSpecialInspectionPage)
    table = QTableWidget(2, 3)
    for row in range(2):
        table.setItem(row, 0, _item(str(row + 1), editable=False))
        table.setItem(row, 1, _item(""))
        table.setItem(row, 2, _item(""))
    page.coord_table = table
    return page


def test_coord_table_clipboard_policy_allows_only_xy_columns() -> None:
    _ensure_app()
    page = _bare_page_with_coord_table()
    table = page.coord_table
    NewSpecialInspectionPage._install_coord_table_clipboard(page)

    assert isinstance(table._table_clipboard, TableClipboardController)
    assert table.selectionMode() == QAbstractItemView.ExtendedSelection
    assert table.selectionBehavior() == QAbstractItemView.SelectItems
    assert table._table_clipboard._can_paste_cell(0, 0) is False
    assert table._table_clipboard._can_paste_cell(0, 1) is True
    assert table._table_clipboard._can_paste_cell(1, 2) is True
    assert table._table_clipboard._can_paste_cell(2, 1) is False


def test_coord_table_paste_skips_readonly_label_column() -> None:
    _ensure_app()
    QApplication.clipboard().clear()
    page = _bare_page_with_coord_table()
    table = page.coord_table
    NewSpecialInspectionPage._install_coord_table_clipboard(page)

    QApplication.clipboard().setText("11\t22\t33\n44\t55\t66")
    table.setCurrentCell(0, 0)
    table._table_clipboard.paste_from_clipboard()

    assert table.item(0, 0).text() == "1"
    assert table.item(0, 1).text() == "22"
    assert table.item(0, 2).text() == "33"
    assert table.item(1, 0).text() == "2"
    assert table.item(1, 1).text() == "55"
    assert table.item(1, 2).text() == "66"
