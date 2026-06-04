# -*- coding: utf-8 -*-

from shiyou_db.document_code_parser import parse_document_code_from_name


def test_parse_detail_design_general_drawing_code():
    result = parse_document_code_from_name("DD-DWG-DPPA-GE-1001.pdf")

    assert result["recognition_status"] == "recognized"
    assert result["design_stage_code"] == "DD"
    assert result["discipline_code"] == "GE"
    assert result["file_class_code"] == "DWG"
    assert result["file_class_name"] == "图纸"
    assert result["asset_unit_code"] == "DPPA"
    assert result["asset_unit_name"] == "钻采平台"
    assert result["module_unit_code"] == "TS"
    assert result["module_unit_name"] == "上部组块"
    assert result["document_code"] == "DD-DWG-DPPA-GE-1001"
    assert result["document_title"] == ""


def test_parse_completion_stage_general_drawing_code():
    result = parse_document_code_from_name("AB-DWG-DPPA-GE-1001.pdf")

    assert result["recognition_status"] == "recognized"
    assert result["design_stage_code"] == "AB"
    assert result["design_stage_name"] == "完工"
    assert result["discipline_code"] == "GE"
    assert result["file_class_code"] == "DWG"


def test_parse_document_title_after_code():
    result = parse_document_code_from_name("DD-DWG-DPPA-GE-1001 平台总图.pdf")

    assert result["document_code"] == "DD-DWG-DPPA-GE-1001"
    assert result["document_title"] == "平台总图"


def test_parse_rebuild_structure_drawing_code_with_sub_sequence():
    result = parse_document_code_from_name("MD(DD)-DWG-DPPA(LQ)-ST-1001（01）.dwg")

    assert result["recognition_status"] == "recognized"
    assert result["design_stage_code"] == "MD(DD)"
    assert result["discipline_code"] == "ST"
    assert result["discipline_group"] == "结构专业"
    assert result["file_class_code"] == "DWG"
    assert result["asset_unit_name"] == "钻采平台"
    assert result["module_unit_code"] == "LQ"
    assert result["module_unit_name"] == "生活楼"
    assert result["drawing_no"] == "1001"
    assert result["sub_sequence"] == "01"


def test_parse_detail_design_jacket_structure_drawing_code():
    result = parse_document_code_from_name("DD-DWG-DPPA(JK)-ST-1001（01）.pdf")

    assert result["recognition_status"] == "recognized"
    assert result["discipline_code"] == "ST"
    assert result["discipline_group"] == "结构专业"
    assert result["module_unit_code"] == "JK"
    assert result["module_unit_name"] == "导管架"
    assert result["drawing_no"] == "1001"
    assert result["sub_sequence"] == "01"


def test_parse_other_discipline_report_code():
    result = parse_document_code_from_name("DD-RPT-DPPA-SA-1001.pdf")

    assert result["recognition_status"] == "recognized"
    assert result["discipline_code"] == "SA"
    assert result["discipline_name"] == "安全"
    assert result["discipline_group"] == "其它专业"
    assert result["file_class_name"] == "报告"


def test_parse_other_discipline_quality_control_code():
    result = parse_document_code_from_name("DD-QC-DPPA-CC-1001.pdf")

    assert result["recognition_status"] == "recognized"
    assert result["discipline_code"] == "CC"
    assert result["discipline_name"] == "防腐"
    assert result["discipline_group"] == "其它专业"
    assert result["file_class_code"] == "QC"
    assert result["file_class_name"] == "质量控制"


def test_general_discipline_rejects_structure_only_file_class():
    result = parse_document_code_from_name("DD-MAL-DPPA-GE-1001.pdf")

    assert result["recognition_status"] == "partial"
    assert "文件分类不适用于该专业" in result["recognition_message"]


def test_invalid_drawing_and_sub_sequence_are_partial():
    result = parse_document_code_from_name("DD-DWG-DPPA-GE-0000（00）.pdf")

    assert result["recognition_status"] == "partial"
    assert "图号超出范围" in result["recognition_message"]
    assert "次级序列号超出范围" in result["recognition_message"]


def test_unrecognized_model_file_goes_unclassified():
    result = parse_document_code_from_name("sacinp.JKnew")

    assert result["recognition_status"] == "unclassified"
    assert result["document_code"] == ""
    assert result["recognition_message"]
