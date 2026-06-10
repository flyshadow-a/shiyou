import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget  # noqa: E402

from pages.doc_man import DocManWidget, UploadStagingDialog  # noqa: E402
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

    def test_upload_staging_dialog_omits_design_stage_column(self) -> None:
        dialog = UploadStagingDialog()
        self.addCleanup(dialog.deleteLater)

        headers = [
            dialog.table.horizontalHeaderItem(index).text()
            for index in range(dialog.table.columnCount())
        ]

        self.assertEqual(
            ["序号", "文件名", "编码", "专业类别", "专业", "文件分类", "单体", "模块", "图号", "状态"],
            headers,
        )
        self.assertNotIn("设计阶段", headers)

        dialog._items = [
            {
                "path": os.path.join(tempfile.gettempdir(), "demo.pdf"),
                "category": "规格书",
                "meta": {
                    "document_code": "DD-ST-SP-WC19-1D-001",
                    "design_stage_name": "详细设计",
                    "discipline_group": "设计文件",
                    "discipline_name": "结构",
                    "file_class_name": "规格书",
                    "asset_unit_name": "WC19-1D平台",
                    "module_unit_name": "上部组块",
                    "drawing_no": "001",
                    "recognition_status": "recognized",
                },
            }
        ]
        dialog._refresh_table()
        row_values = [
            dialog.table.item(0, index).text()
            for index in range(dialog.table.columnCount())
        ]

        self.assertNotIn("详细设计", row_values)
        self.assertEqual("设计文件", row_values[headers.index("专业类别")])
        self.assertEqual("已识别", row_values[headers.index("状态")])

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


def test_open_upload_staging_handles_invalid_dialog_factory(monkeypatch):
    _ensure_app()
    widget = DocManWidget(lambda _segments: tempfile.gettempdir())
    invalid_dialog = QWidget()
    messages = []
    try:
        monkeypatch.setattr("pages.doc_man.UploadStagingDialog", lambda **_kwargs: invalid_dialog)
        monkeypatch.setattr(
            "pages.doc_man.QMessageBox.critical",
            lambda _parent, title, text: messages.append((title, text)),
        )

        widget._open_upload_staging()

        assert messages
        assert "上传文件分类窗口" in messages[0][1]
    finally:
        invalid_dialog.deleteLater()
        widget.deleteLater()
