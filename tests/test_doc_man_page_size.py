import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication  # noqa: E402

from pages.doc_man import DocManWidget  # noqa: E402
from services import file_db_adapter  # noqa: E402


_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def _record(index: int) -> dict:
    return {
        "index": index,
        "filename": f"file_{index}.pdf",
        "fmt": "PDF",
        "mtime": "",
        "path": "",
        "remark": "",
    }


class DocManPageSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _ensure_app()

    def test_page_size_combo_starts_at_30_without_10(self) -> None:
        widget = DocManWidget(lambda _segments: tempfile.gettempdir())
        self.addCleanup(widget.deleteLater)

        options = [
            widget.page_size_combo.itemText(index)
            for index in range(widget.page_size_combo.count())
        ]

        self.assertEqual(["30", "50", "100", "全部"], options)
        self.assertEqual("30", widget.page_size_combo.currentText())

    def test_page_size_combo_changes_local_visible_rows(self) -> None:
        widget = DocManWidget(lambda _segments: tempfile.gettempdir())
        self.addCleanup(widget.deleteLater)
        records = [_record(index) for index in range(1, 66)]
        widget.set_context(["demo"], records, [], overlay_from_db=False)

        self.assertEqual(30, widget.table.rowCount())

        widget.page_size_combo.setCurrentText("50")
        self.assertEqual(50, widget.table.rowCount())
        self.assertEqual(0, widget._current_page)

        widget.page_size_combo.setCurrentText("全部")
        self.assertEqual(65, widget.table.rowCount())
        self.assertEqual(0, widget._current_page)


def test_load_docman_record_page_treats_zero_page_size_as_all(monkeypatch):
    captured = {}

    def fake_list_files_by_prefix(**kwargs):
        captured["kwargs"] = kwargs
        return [
            {"id": index, "original_name": f"file_{index}.pdf"}
            for index in range(1, 4)
        ]

    monkeypatch.setattr(file_db_adapter, "count_files_by_prefix", lambda **_kwargs: 3)
    monkeypatch.setattr(file_db_adapter, "list_files_by_prefix", fake_list_files_by_prefix)
    monkeypatch.setattr(file_db_adapter, "resolve_storage_path", lambda row, config_path=None: "")

    page = file_db_adapter.load_docman_record_page(["demo"], page=2, page_size=0)

    assert page["total"] == 3
    assert page["page"] == 0
    assert page["page_size"] == 3
    assert captured["kwargs"]["limit"] == 3
    assert captured["kwargs"]["offset"] == 0
