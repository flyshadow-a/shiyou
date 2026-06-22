import pandas as pd

from pages.output_special_strategy.inspection_tool import classify_structure


def test_classify_structure_defaults_do_not_run_sheet2_sheet3_overwrites():
    joints = pd.DataFrame(
        [
            {"Joint": "001L", "X": 0.0, "Y": 0.0, "Z": 0.0, "JointType": None},
            {"Joint": "002X", "X": 1.0, "Y": 0.0, "Z": 0.0, "JointType": None},
            {"Joint": "A001", "X": 2.0, "Y": 0.0, "Z": 0.0, "JointType": None},
        ]
    )
    members = pd.DataFrame(
        [
            {
                "A": "001L",
                "B": "002L",
                "ID": "M1",
                "OD": 100.0,
                "MemberType": None,
                "Z1": 0.0,
                "Z2": 0.0,
            },
            {
                "A": "002X",
                "B": "A001",
                "ID": "M2",
                "OD": 100.0,
                "MemberType": None,
                "Z1": 0.0,
                "Z2": 0.0,
            },
        ]
    )

    result_joints, result_members = classify_structure(
        joints=joints,
        members=members,
        work_points_xy=[],
        wp_z=10.0,
        min_leg_od=610.0,
    )

    assert result_joints["JointType"].isna().all()
    assert result_members["MemberType"].isna().all()
