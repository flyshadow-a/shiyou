from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.table import Table

NON_BREAKING_HYPHEN = "\u2011"


def _format_chapter4_table_number(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip().replace(NON_BREAKING_HYPHEN, "-").replace(",", "")
    else:
        text = str(value).strip()

    if not text:
        return ""

    try:
        number = float(text)
    except ValueError:
        return str(value)

    if abs(number) >= 10000:
        return f"{number:.0f}"
    return f"{number:.2f}"


def _write_chapter4_number_cell(cell, value: Any) -> None:
    write_cell(cell, _protect_negative_number(_format_chapter4_table_number(value)))


def _normalize_cell_text(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def _protect_negative_number(value: str) -> str:
    if value.startswith("-") and len(value) > 1 and value[1].isdigit():
        return NON_BREAKING_HYPHEN + value[1:]
    return value


def find_table_by_header_row(document_tables: Iterable[Table], expected_headers: list[str]) -> Table:
    normalized_expected = [_normalize_cell_text(item) for item in expected_headers]

    for table in document_tables:
        if not table.rows:
            continue

        header_cells = table.rows[0].cells
        if len(header_cells) < len(normalized_expected):
            continue

        actual_headers = [
            _normalize_cell_text(cell.text) for cell in header_cells[: len(normalized_expected)]
        ]
        if actual_headers == normalized_expected:
            return table

    raise ValueError(f"未找到表头为 {expected_headers} 的表格")


def write_cell(cell, value: str) -> None:
    paragraph = cell.paragraphs[0]
    paragraph.clear()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.left_indent = Pt(0)
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)

    if value:
        run = paragraph.add_run(value)
        run.font.size = Pt(12)
        run.font.name = "Times New Roman"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        run._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
        run._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
        run._element.rPr.rFonts.set(qn("w:cs"), "Times New Roman")


def write_analysis_summary_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    for row_index, item in enumerate(items, start=1):
        if row_index >= len(table.rows):
            raise ValueError("分析汇总信息表格行数不足")

        row = table.rows[row_index]
        write_cell(row.cells[0], str(item.get("check_item", "")))
        write_cell(row.cells[1], str(item.get("position", "")))
        _write_chapter4_number_cell(row.cells[2], item.get("value", ""))
        write_cell(row.cells[3], str(item.get("case", "")))
        write_cell(row.cells[4], str(item.get("is_pass", "")))


def find_tables_by_header_rows(
    document_tables: Iterable[Table], expected_header_rows: list[list[str]]
) -> list[Table]:
    normalized_expected = [
        [_normalize_cell_text(item) for item in row] for row in expected_header_rows
    ]
    matched_tables: list[Table] = []

    for table in document_tables:
        if len(table.rows) < len(normalized_expected):
            continue

        is_match = True
        for row_index, expected_row in enumerate(normalized_expected):
            actual_row = [
                _normalize_cell_text(cell.text)
                for cell in table.rows[row_index].cells[: len(expected_row)]
            ]
            if actual_row != expected_row:
                is_match = False
                break

        if is_match:
            matched_tables.append(table)

    return matched_tables


def ensure_table_row_count(table: Table, required_rows: int) -> None:
    while len(table.rows) < required_rows:
        table._tbl.append(deepcopy(table.rows[-1]._tr))


def trim_table_row_count(table: Table, required_rows: int) -> None:
    while len(table.rows) > required_rows:
        table._tbl.remove(table.rows[-1]._tr)


def ensure_table_column_count(table: Table, required_columns: int) -> None:
    while len(table.columns) < required_columns:
        table.add_column(Pt(36))


def trim_table_column_count(table: Table, required_columns: int) -> None:
    while len(table.columns) > required_columns:
        column_index = len(table.columns) - 1
        for row in table.rows:
            row._tr.remove(row.cells[column_index]._tc)

        tbl_grid = table._tbl.tblGrid
        grid_columns = tbl_grid.gridCol_lst
        if len(grid_columns) > required_columns:
            tbl_grid.remove(grid_columns[-1])


def clear_row(row) -> None:
    for cell in row.cells:
        write_cell(cell, "")


def write_pile_capacity_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    start_row_index = 2
    required_rows = start_row_index + len(items)
    ensure_table_row_count(table, required_rows)

    for row_index, item in enumerate(items, start=start_row_index):
        row = table.rows[row_index]
        write_cell(row.cells[0], str(item.get("pile_head_id", "")))
        _write_chapter4_number_cell(row.cells[1], item.get("compression_capacity_kn", ""))
        _write_chapter4_number_cell(row.cells[2], item.get("tension_capacity_kn", ""))
        _write_chapter4_number_cell(row.cells[3], item.get("pile_weight_kn", ""))
        write_cell(row.cells[4], str(item.get("compression_case", "")))
        _write_chapter4_number_cell(row.cells[5], item.get("compression_load_kn", ""))
        write_cell(row.cells[6], str(item.get("tension_case", "")))
        _write_chapter4_number_cell(row.cells[7], item.get("tension_load_kn", ""))
        _write_chapter4_number_cell(row.cells[8], item.get("compression_sf", ""))
        _write_chapter4_number_cell(row.cells[9], item.get("tension_sf", ""))

    trim_table_row_count(table, required_rows)


def write_basic_case_desc_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    start_row_index = 1
    required_rows = start_row_index + len(items)
    ensure_table_row_count(table, required_rows)

    for row_index, item in enumerate(items, start=start_row_index):
        row = table.rows[row_index]
        write_cell(row.cells[0], str(item.get("case", "")))
        write_cell(row.cells[1], str(item.get("label", "")))
        write_cell(row.cells[2], str(item.get("desc", "")))

    trim_table_row_count(table, required_rows)


def write_basic_case_loads_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    start_row_index = 1
    required_rows = start_row_index + len(items)
    ensure_table_row_count(table, required_rows)

    for row_index, item in enumerate(items, start=start_row_index):
        row = table.rows[row_index]
        write_cell(row.cells[0], str(item.get("label", "")))
        _write_chapter4_number_cell(row.cells[1], item.get("fx", ""))
        _write_chapter4_number_cell(row.cells[2], item.get("fy", ""))
        _write_chapter4_number_cell(row.cells[3], item.get("fz", ""))
        _write_chapter4_number_cell(row.cells[4], item.get("mx", ""))
        _write_chapter4_number_cell(row.cells[5], item.get("my", ""))
        _write_chapter4_number_cell(row.cells[6], item.get("mz", ""))
        _write_chapter4_number_cell(row.cells[7], item.get("dead_load", ""))
        _write_chapter4_number_cell(row.cells[8], item.get("buoyancy", ""))

    trim_table_row_count(table, required_rows)


def write_combo_case_desc_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    start_row_index = 1
    required_rows = start_row_index + len(items)
    ensure_table_row_count(table, required_rows)

    for row_index, item in enumerate(items, start=start_row_index):
        row = table.rows[row_index]
        write_cell(row.cells[0], str(item.get("case", "")))
        write_cell(row.cells[1], str(item.get("label", "")))
        write_cell(row.cells[2], str(item.get("category", "")))
        write_cell(row.cells[3], str(item.get("desc", "")))

    trim_table_row_count(table, required_rows)


def write_combo_case_loads_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    start_row_index = 1
    required_rows = start_row_index + len(items)
    ensure_table_row_count(table, required_rows)

    for row_index, item in enumerate(items, start=start_row_index):
        row = table.rows[row_index]
        write_cell(row.cells[0], str(item.get("case", "")))
        write_cell(row.cells[1], str(item.get("label", "")))
        _write_chapter4_number_cell(row.cells[2], item.get("fx", ""))
        _write_chapter4_number_cell(row.cells[3], item.get("fy", ""))
        _write_chapter4_number_cell(row.cells[4], item.get("fz", ""))
        _write_chapter4_number_cell(row.cells[5], item.get("mx", ""))
        _write_chapter4_number_cell(row.cells[6], item.get("my", ""))
        _write_chapter4_number_cell(row.cells[7], item.get("mz", ""))

    trim_table_row_count(table, required_rows)


def write_retrofit_history_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    # 1.2 节改造清单表直接对应“历史改造信息”页面顶部三列表格。
    start_row_index = 1
    required_rows = start_row_index + len(items)
    ensure_table_row_count(table, required_rows)

    for row_index, item in enumerate(items, start=start_row_index):
        row = table.rows[row_index]
        write_cell(row.cells[0], str(item.get("index", "")))
        write_cell(row.cells[1], str(item.get("name", "")))
        write_cell(row.cells[2], str(item.get("year", "")))

    trim_table_row_count(table, required_rows)


def write_environment_water_level_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    start_row_index = 2
    required_rows = start_row_index + len(items)
    ensure_table_row_count(table, required_rows)

    for row_index, item in enumerate(items, start=start_row_index):
        row = table.rows[row_index]
        write_cell(row.cells[0], str(item.get("group_name", "") or item.get("item_name", "")))
        write_cell(row.cells[1], str(item.get("item_name", "")))
        write_cell(row.cells[2], _protect_negative_number(str(item.get("value", ""))))

    trim_table_row_count(table, required_rows)


def write_environment_metric_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    start_row_index = 3
    required_rows = start_row_index + len(items)
    ensure_table_row_count(table, required_rows)

    period_keys = ["1", "10", "25", "50", "100"]
    for row_index, item in enumerate(items, start=start_row_index):
        row = table.rows[row_index]
        write_cell(row.cells[0], str(item.get("group_name", "")))
        write_cell(row.cells[1], str(item.get("item_name", "")))
        values_by_period = item.get("values_by_period", {})
        for column_offset, period_key in enumerate(period_keys, start=2):
            write_cell(
                row.cells[column_offset],
                _protect_negative_number(str(values_by_period.get(period_key, ""))),
            )

    trim_table_row_count(table, required_rows)


def write_environment_marine_growth_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    rows_by_layer = {}
    for item in items:
        raw_layer_no = str(item.get("layer_no", "")).strip()
        if not raw_layer_no:
            continue
        try:
            layer_no = int(float(raw_layer_no))
        except ValueError:
            continue
        if layer_no < 1:
            continue
        rows_by_layer[layer_no] = item

    max_layer_no = max(rows_by_layer.keys(), default=1)
    required_columns = 2 + max_layer_no
    ensure_table_column_count(table, required_columns)
    trim_table_column_count(table, required_columns)

    for layer_no in range(1, max_layer_no + 1):
        item = rows_by_layer.get(layer_no, {})
        column_index = layer_no + 1
        write_cell(table.rows[0].cells[column_index], str(layer_no))
        write_cell(table.rows[1].cells[column_index], _protect_negative_number(str(item.get("upper_limit_m", ""))))
        write_cell(table.rows[2].cells[column_index], _protect_negative_number(str(item.get("lower_limit_m", ""))))
        write_cell(table.rows[3].cells[column_index], _protect_negative_number(str(item.get("thickness_mm", ""))))

    density = ""
    for item in items:
        density = str(item.get("density_t_per_m3", "")).strip()
        if density:
            break
    for column_index in range(2, required_columns):
        write_cell(table.rows[4].cells[column_index], _protect_negative_number(density))


def write_environment_splash_zone_table(table: Table, items: Sequence[Mapping[str, Any]]) -> None:
    start_row_index = 1
    required_rows = start_row_index + len(items)
    ensure_table_row_count(table, required_rows)

    for row_index, item in enumerate(items, start=start_row_index):
        row = table.rows[row_index]
        write_cell(row.cells[0], _protect_negative_number(str(item.get("upper_limit_m", ""))))
        write_cell(row.cells[1], _protect_negative_number(str(item.get("lower_limit_m", ""))))
        write_cell(
            row.cells[2],
            _protect_negative_number(str(item.get("corrosion_allowance_mm_per_y", ""))),
        )

    trim_table_row_count(table, required_rows)
