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


def test_category_column_can_be_enabled_for_inspection_records() -> None:
    widget = _make_widget()
    widget.set_context(
        ["检测记录"],
        [_record(category="检测报告")],
        ["检测报告", "其他"],
        display_profile="inspection",
        overlay_from_db=False,
        editable_category=True,
    )

    category_item = widget.table.item(0, widget.COL_CATEGORY)

    assert category_item is not None
    assert category_item.flags() & Qt.ItemIsEditable

    category_item.setText("现场记录")

    assert widget._records[0]["category"] == "现场记录"
    assert category_item.toolTip() == "现场记录"


def test_category_column_stays_readonly_for_design_without_opt_in() -> None:
    widget = _make_widget()
    widget.set_context(
        ["详细设计"],
        [_record(category="图纸")],
        ["图纸", "其他"],
        display_profile="design",
        overlay_from_db=False,
    )

    category_item = widget.table.item(0, widget.COL_CATEGORY)

    assert category_item is not None
    assert not (category_item.flags() & Qt.ItemIsEditable)


def test_category_filter_is_hidden_by_default() -> None:
    widget = _make_widget()
    widget.set_context(
        ["详细设计"],
        [_record(category="图纸")],
        ["图纸", "其他"],
        display_profile="design",
        overlay_from_db=False,
    )

    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "类别"


def test_category_header_filter_can_filter_local_records_when_enabled() -> None:
    widget = _make_widget()
    widget.set_context(
        ["检测记录"],
        [
            _record(category="检测报告", filename="report.pdf"),
            _record(category="现场记录", filename="site.pdf"),
        ],
        ["检测报告", "现场记录"],
        display_profile="inspection",
        overlay_from_db=False,
        editable_category=True,
        enable_category_filter=True,
    )

    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "类别 ▼"

    widget._set_category_filter("现场记录")

    assert widget.table.rowCount() == 1
    assert widget.table.item(0, widget.COL_FILENAME).text() == "site.pdf"
    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "类别：现场记录 ▼"

    widget._set_category_filter("全部")

    assert widget.table.rowCount() == 2
    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "类别 ▼"


def test_design_header_filters_can_combine_discipline_and_category() -> None:
    widget = _make_widget()
    widget.set_context(
        ["详细设计"],
        [
            _record(category="图纸", filename="st_dwg.pdf", document_title="结构图纸", discipline_name="结构"),
            _record(category="报告", filename="st_rpt.pdf", document_title="结构报告", discipline_name="结构"),
            _record(category="图纸", filename="ge_dwg.pdf", document_title="总体图纸", discipline_name="总体"),
        ],
        ["图纸", "报告"],
        display_profile="design",
        overlay_from_db=False,
        enable_category_filter=True,
        enable_discipline_filter=True,
    )

    assert widget.table.horizontalHeaderItem(widget.COL_MTIME).text() == "专业 ▼"
    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "类别 ▼"

    widget._set_discipline_filter("结构")
    widget._set_category_filter("图纸")

    assert widget.table.rowCount() == 1
    assert widget.table.item(0, widget.COL_FILENAME).text() == "结构图纸"
    assert widget.table.horizontalHeaderItem(widget.COL_MTIME).text() == "专业：结构 ▼"
    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "类别：图纸 ▼"


def test_rebuild_header_filters_can_combine_discipline_and_category() -> None:
    widget = _make_widget()
    widget.set_context(
        ["历史改造信息", "directory_1"],
        [
            _record(category="图纸", filename="st_dwg.pdf", document_title="结构图纸", discipline_name="结构"),
            _record(category="报告", filename="st_rpt.pdf", document_title="结构报告", discipline_name="结构"),
            _record(category="图纸", filename="ge_dwg.pdf", document_title="总体图纸", discipline_name="总体"),
        ],
        ["图纸", "报告"],
        display_profile="rebuild",
        overlay_from_db=False,
        enable_category_filter=True,
        enable_discipline_filter=True,
    )

    assert widget.table.horizontalHeaderItem(widget.COL_MTIME).text() == "专业 ▼"
    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "类别 ▼"

    widget._set_discipline_filter("结构")
    widget._set_category_filter("图纸")

    assert widget.table.rowCount() == 1
    assert widget.table.item(0, widget.COL_FILENAME).text() == "结构图纸"
    assert widget.table.horizontalHeaderItem(widget.COL_MTIME).text() == "专业：结构 ▼"
    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "类别：图纸 ▼"

    widget._set_category_filter("全部")

    assert widget.table.rowCount() == 2
    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "类别 ▼"


def test_model_header_filter_can_filter_categories() -> None:
    widget = _make_widget()
    widget.set_context(
        ["当前模型", "静力"],
        [
            _record(category="结构模型文件", filename="sacinp"),
            _record(category="静力分析结果文件", filename="psilst"),
        ],
        ["结构模型文件", "静力分析结果文件"],
        display_profile="model",
        overlay_from_db=False,
        enable_category_filter=True,
    )

    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "模型类别 ▼"

    widget._set_category_filter("静力分析结果文件")

    assert widget.table.rowCount() == 1
    assert widget.table.item(0, widget.COL_FMT).text() == "psilst"
    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "模型类别：静力分析结果文件 ▼"

    widget._set_category_filter("全部")

    assert widget.table.rowCount() == 2
    assert widget.table.horizontalHeaderItem(widget.COL_CATEGORY).text() == "模型类别 ▼"
