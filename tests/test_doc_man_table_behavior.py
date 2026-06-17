# -*- coding: utf-8 -*-
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QHeaderView

from pages.doc_man import DocManWidget


_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def _make_widget() -> DocManWidget:
    _ensure_app()
    return DocManWidget(lambda _segments: os.getcwd())


def _record(**overrides) -> dict:
    data = {
        "filename": "demo.pdf",
        "fmt": "PDF",
        "category": "图纸",
        "remark": "备注",
        "work_condition": "工况",
        "document_code": "DD-DWG-WC19-1D-ST-001",
        "document_title": "设计图纸",
        "design_stage_name": "详细设计",
        "discipline_name": "结构",
    }
    data.update(overrides)
    return data


def test_category_column_is_readonly_for_all_file_management_profiles() -> None:
    profiles = ["generic", "design", "rebuild", "model", "inspection"]

    for profile in profiles:
        widget = _make_widget()
        widget.set_context(
            ["测试目录"],
            [_record()],
            ["图纸", "模型类别"],
            display_profile=profile,
            overlay_from_db=False,
        )

        category_item = widget.table.item(0, widget.COL_CATEGORY)
        assert category_item is not None
        assert not (category_item.flags() & Qt.ItemIsEditable), profile


def test_remark_column_remains_editable_after_category_is_readonly() -> None:
    widget = _make_widget()
    widget.set_context(
        ["测试目录"],
        [_record()],
        ["图纸"],
        display_profile="design",
        overlay_from_db=False,
    )

    remark_item = widget.table.item(0, widget.COL_REMARK)

    assert remark_item is not None
    assert remark_item.flags() & Qt.ItemIsEditable


def test_design_code_and_name_columns_keep_layout_and_show_full_tooltips() -> None:
    widget = _make_widget()
    long_code = "DD-DWG-WC19-1D-ST-" + "1234567890" * 8
    long_title = "文昌平台结构专业详细设计超长文件名称" * 5

    widget.set_context(
        ["详细设计", "结构(ST)", "图纸"],
        [
            _record(
                document_code=long_code,
                document_title=long_title,
                filename="long.pdf",
            )
        ],
        ["图纸"],
        display_profile="design",
        overlay_from_db=False,
    )

    code_item = widget.table.item(0, widget.COL_WORK_CONDITION)
    name_item = widget.table.item(0, widget.COL_FILENAME)

    assert code_item is not None
    assert name_item is not None
    assert code_item.toolTip() == long_code
    assert name_item.toolTip() == long_title
    assert widget.table.horizontalHeader().sectionResizeMode(widget.COL_WORK_CONDITION) == QHeaderView.Stretch
    assert widget.table.horizontalHeader().sectionResizeMode(widget.COL_FILENAME) == QHeaderView.Stretch
    assert widget.table.horizontalHeader().sectionResizeMode(widget.COL_CATEGORY) == QHeaderView.Stretch
