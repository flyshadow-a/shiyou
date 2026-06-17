import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QLabel

from pages.special_strategy_rule_dialogs import (
    RULE_MODE_JOINT_CLASSIFICATION,
    RULE_MODE_JOINT_EXCLUSION,
    RULE_MODE_MEMBER_CLASSIFICATION,
    RULE_MODE_MEMBER_EXCLUSION,
    SpecialStrategyRuleDialog,
    code_matches_pattern,
)

_QT_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _QT_APP
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _QT_APP = app
    return app


def test_rule_dialog_initial_preview_is_zero_until_manual_refresh():
    _ensure_app()
    dialog = SpecialStrategyRuleDialog(
        RULE_MODE_JOINT_EXCLUSION,
        {"joint_exclusions": ["A001"]},
        joint_ids=["A001"],
    )

    assert dialog.preview_label.text() == "命中数量预览：剔除节点 0。"

    dialog.refresh_preview_button.click()

    assert dialog.preview_label.text() == "命中数量预览：剔除节点 1。"


def test_rule_dialog_editing_cell_does_not_refresh_preview_automatically():
    _ensure_app()
    dialog = SpecialStrategyRuleDialog(
        RULE_MODE_JOINT_EXCLUSION,
        {"joint_exclusions": ["A001"]},
        joint_ids=["A001"],
    )
    calls: list[str] = []
    dialog._refresh_preview = lambda: calls.append("refresh")

    dialog.joint_exclusion_table.item(1, 0).setText("B")

    assert calls == []


def test_rule_dialog_append_node_row_does_not_refresh_preview_automatically():
    _ensure_app()
    dialog = SpecialStrategyRuleDialog(RULE_MODE_JOINT_EXCLUSION, {}, joint_ids=["A001"])
    calls: list[str] = []
    dialog._refresh_preview = lambda: calls.append("refresh")

    dialog._append_empty_node_row(dialog.joint_exclusion_table, dual=False)

    assert calls == []


def test_rule_dialog_append_member_row_does_not_refresh_preview_automatically():
    _ensure_app()
    dialog = SpecialStrategyRuleDialog(
        RULE_MODE_MEMBER_EXCLUSION,
        {},
        member_pairs=[("A001", "B001")],
    )
    calls: list[str] = []
    dialog._refresh_preview = lambda: calls.append("refresh")

    dialog._append_empty_member_row(dialog.member_exclusion_table)

    assert calls == []


def test_rule_dialogs_do_not_show_bottom_input_note():
    _ensure_app()
    for mode in (
        RULE_MODE_JOINT_CLASSIFICATION,
        RULE_MODE_MEMBER_CLASSIFICATION,
        RULE_MODE_MEMBER_EXCLUSION,
        RULE_MODE_JOINT_EXCLUSION,
    ):
        dialog = SpecialStrategyRuleDialog(mode, {})

        label_texts = [label.text() for label in dialog.findChildren(QLabel)]
        assert dialog.findChildren(QLabel, "RuleDialogNote") == []
        assert all("输入说明" not in text for text in label_texts)


def test_rule_pattern_supports_letter_and_digit_placeholders():
    assert code_matches_pattern("AB12", "##%%")
    assert code_matches_pattern("A912", "#%%%")
    assert not code_matches_pattern("1B12", "##%%")
    assert not code_matches_pattern("ABCD", "##%%")
    assert code_matches_pattern("AX12", "A*%%")


def test_rule_dialog_titles_and_hints_use_classification_identification_wording():
    _ensure_app()

    member_dialog = SpecialStrategyRuleDialog(RULE_MODE_MEMBER_CLASSIFICATION, {})
    member_texts = [label.text() for label in member_dialog.findChildren(QLabel)]
    assert member_dialog.windowTitle() == "构件分类识别"
    assert "构件分类识别" in member_texts
    assert any(
        "主腿构件与 X 撑构件分别录入。构件按无向匹配，A-B 与 B-A 视为同一构件。"
        "*为任意字符，#表示字母，%表示数字；全*行仅作占位，不参与匹配。"
        in text
        for text in member_texts
    )
    assert "若不输入，则根据软件模糊识别" in member_texts

    joint_dialog = SpecialStrategyRuleDialog(RULE_MODE_JOINT_CLASSIFICATION, {})
    joint_texts = [label.text() for label in joint_dialog.findChildren(QLabel)]
    assert joint_dialog.windowTitle() == "节点分类识别"
    assert "节点分类识别" in joint_texts
    assert any(
        "主腿节点与 X 撑节点分别录入。"
        "*为任意字符，#表示字母，%表示数字；全*行仅作占位，不参与匹配。"
        in text
        for text in joint_texts
    )
    assert "若不输入，则根据软件模糊识别" in joint_texts

    for mode in (RULE_MODE_MEMBER_EXCLUSION, RULE_MODE_JOINT_EXCLUSION):
        dialog = SpecialStrategyRuleDialog(mode, {})
        label_texts = [label.text() for label in dialog.findChildren(QLabel)]
        assert any(
            "*为任意字符，#表示字母，%表示数字；全*行仅作占位，不参与匹配。"
            in text
            for text in label_texts
        )
