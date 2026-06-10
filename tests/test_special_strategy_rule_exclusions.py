import pandas as pd

from pages.output_special_strategy.inspection_tool import (
    _apply_joint_delete_rule,
    _apply_member_delete_rule,
)


def test_empty_popup_rules_do_not_apply_default_vba_member_exclusions():
    rows = pd.DataFrame(
        [
            {"JointA": "C001", "JointB": "A001"},
            {"JointA": "B001", "JointB": "B002"},
            {"JointA": "K001", "JointB": "K002"},
            {"JointA": "R001", "JointB": "A002"},
            {"JointA": "A003", "JointB": "A004"},
        ]
    )

    result = _apply_member_delete_rule(rows, user_rules={})

    assert result[["JointA", "JointB"]].to_dict("records") == rows.to_dict("records")


def test_empty_popup_rules_do_not_apply_default_vba_joint_exclusions():
    rows = pd.DataFrame(
        [
            {"JoitID": "C001"},
            {"JoitID": "B001"},
            {"JoitID": "K001"},
            {"JoitID": "R001"},
            {"JoitID": "A001"},
        ]
    )

    result = _apply_joint_delete_rule(rows, user_rules={})

    assert result["JoitID"].tolist() == rows["JoitID"].tolist()


def test_popup_rules_still_remove_matching_members_and_joints():
    member_rows = pd.DataFrame(
        [
            {"JointA": "C001", "JointB": "A001"},
            {"JointA": "A002", "JointB": "A003"},
        ]
    )
    joint_rows = pd.DataFrame([{"JoitID": "R001"}, {"JoitID": "A001"}])
    rules = {
        "member_exclusions": [{"a": "C001", "relation": "And", "b": "A001"}],
        "joint_exclusions": ["R001"],
    }

    member_result = _apply_member_delete_rule(member_rows, user_rules=rules)
    joint_result = _apply_joint_delete_rule(joint_rows, user_rules=rules)

    assert member_result[["JointA", "JointB"]].to_dict("records") == [
        {"JointA": "A002", "JointB": "A003"}
    ]
    assert joint_result["JoitID"].tolist() == ["A001"]
