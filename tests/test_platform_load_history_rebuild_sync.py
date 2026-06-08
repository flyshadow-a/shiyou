import unittest

from pages.platform_load_information_page import (
    DETAIL_DESIGN_PROJECT_NAME,
    _merge_history_rebuild_projects_into_load_rows,
)


class PlatformLoadHistoryRebuildSyncTests(unittest.TestCase):
    def test_rebuild_id_merge_keeps_detail_design_first_and_drops_deleted_projects(self) -> None:
        existing_rows = [
            ["0", "OriginalDesign", "", "", "100", "110", ""],
            ["1", "OldName", "2019", "OldContent", "200", "210", "10"],
            ["2", "DeletedProject", "2018", "DeletedContent", "300", "310", "20"],
            ["3", "ManualProject", "2024", "ManualContent", "400", "410", ""],
        ]
        history_projects = [
            {
                "id": 10,
                "project_name": "RenamedProject",
                "directory_name": "",
                "project_year": "2020",
                "summary_text": "RenamedContent",
            }
        ]

        merged = _merge_history_rebuild_projects_into_load_rows(
            existing_rows,
            history_projects,
            column_count=6,
        )

        self.assertEqual(
            merged,
            [
                ["0", DETAIL_DESIGN_PROJECT_NAME, "", "", "100", "110", ""],
                ["1", "RenamedProject", "2020", "RenamedContent", "200", "210", "10"],
                ["2", "ManualProject", "2024", "ManualContent", "400", "410", ""],
            ],
        )

    def test_history_rebuild_projects_start_after_detail_design_row(self) -> None:
        existing_rows = [
            ["0", "OriginalDesign", "", "", "100", "110"],
            ["1", "ProjectB", "OldDateB", "OldContentB", "200", "210"],
        ]
        history_projects = [
            {
                "project_name": "ProjectA",
                "directory_name": "DirA",
                "project_year": "2020",
                "summary_text": "ProjectAContent",
            },
            {
                "project_name": "ProjectB",
                "directory_name": "DirB",
                "project_year": "2021",
                "summary_text": "ProjectBContent",
            },
        ]

        merged = _merge_history_rebuild_projects_into_load_rows(
            existing_rows,
            history_projects,
            column_count=6,
        )

        self.assertEqual(
            merged,
            [
                ["0", DETAIL_DESIGN_PROJECT_NAME, "", "", "100", "110", ""],
                ["1", "ProjectA", "2020", "ProjectAContent", "", "", ""],
                ["2", "ProjectB", "2021", "ProjectBContent", "200", "210", ""],
            ],
        )

    def test_history_rebuild_project_name_falls_back_to_directory_name(self) -> None:
        merged = _merge_history_rebuild_projects_into_load_rows(
            [],
            [
                {
                    "project_name": "",
                    "directory_name": "HistoryProject1",
                    "project_year": "",
                    "summary_text": "",
                }
            ],
            column_count=5,
        )

        self.assertEqual(
            merged,
            [
                ["0", DETAIL_DESIGN_PROJECT_NAME, "", "", "", ""],
                ["1", "HistoryProject1", "", "", "", ""],
            ],
        )

    def test_history_rebuild_merge_preserves_saved_manual_project_rows(self) -> None:
        existing_rows = [
            ["0", "OriginalDesign", "", "", "100", "110"],
            ["1", "ManagedProject", "OldDate", "OldContent", "200", "210"],
            ["2", "ManualProject", "2024", "ManualContent", "300", "310"],
        ]
        history_projects = [
            {
                "project_name": "ManagedProject",
                "directory_name": "",
                "project_year": "2020",
                "summary_text": "ManagedContent",
            }
        ]

        merged = _merge_history_rebuild_projects_into_load_rows(
            existing_rows,
            history_projects,
            column_count=6,
        )

        self.assertEqual(
            merged,
            [
                ["0", DETAIL_DESIGN_PROJECT_NAME, "", "", "100", "110", ""],
                ["1", "ManagedProject", "2020", "ManagedContent", "200", "210", ""],
                ["2", "ManualProject", "2024", "ManualContent", "300", "310", ""],
            ],
        )

    def test_unmatched_history_project_does_not_overwrite_manual_row_by_position(self) -> None:
        existing_rows = [
            ["0", "OriginalDesign", "", "", "100", "110"],
            ["1", "ManualProject", "2024", "ManualContent", "200", "210"],
        ]
        history_projects = [
            {
                "project_name": "HistoryProject",
                "directory_name": "",
                "project_year": "2020",
                "summary_text": "HistoryContent",
            }
        ]

        merged = _merge_history_rebuild_projects_into_load_rows(
            existing_rows,
            history_projects,
            column_count=6,
        )

        self.assertEqual(
            merged,
            [
                ["0", DETAIL_DESIGN_PROJECT_NAME, "", "", "100", "110", ""],
                ["1", "HistoryProject", "2020", "HistoryContent", "", "", ""],
                ["2", "ManualProject", "2024", "ManualContent", "200", "210", ""],
            ],
        )


if __name__ == "__main__":
    unittest.main()
