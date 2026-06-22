from core.model_file_classifier import classify_model_file_name, is_single_current_model_code


def test_model_file_classifier_matches_prefixes_case_insensitively() -> None:
    result = classify_model_file_name("SACINP.demo01")

    assert result is not None
    assert result.code == "sacinp"
    assert result.model_type == "SACS input data"
    assert result.match_kind == "prefix"
    assert result.category == "结构模型文件"
    assert is_single_current_model_code(result.code)


def test_model_file_classifier_matches_seainp_variants_by_prefix() -> None:
    for filename in ("seainp.demo01", "seainp.static.demo02", "seainp.ldf.demo02"):
        result = classify_model_file_name(filename)

        assert result is not None
        assert result.code == "seainp"
        assert result.category == "海况文件"
        assert is_single_current_model_code(result.code)


def test_model_file_classifier_matches_runx_by_suffix() -> None:
    for filename in ("psi.demo03.runx", "rundemo01.RUNX", "static.demo02.runx"):
        result = classify_model_file_name(filename)

        assert result is not None
        assert result.code == "runx"
        assert result.model_type == "SACS run file"
        assert result.match_kind == "suffix"
        assert result.category == "其他"
        assert not is_single_current_model_code(result.code)


def test_model_file_classifier_maps_current_model_single_codes() -> None:
    expected = {
        "sacinp.demo01": "结构模型文件",
        "seainp.demo01": "海况文件",
        "psiinp.demo03": "桩基文件",
        "jcninp.demo01": "冲剪节点文件",
    }

    for filename, category in expected.items():
        result = classify_model_file_name(filename)

        assert result is not None
        assert result.category == category
        assert is_single_current_model_code(result.code)


def test_model_file_classifier_maps_listings_and_unknowns() -> None:
    assert classify_model_file_name("ftglst.demo05a.std").category == "疲劳分析结果文件"
    assert classify_model_file_name("clplog.demo13").category == "倒塌分析日志文件"
    assert classify_model_file_name("unknown-file.txt") is None
