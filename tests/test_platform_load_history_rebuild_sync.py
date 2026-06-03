import unittest


from pages.platform_load_information_page import _merge_history_rebuild_projects_into_load_rows


class PlatformLoadHistoryRebuildSyncTests(unittest.TestCase):
    def test_history_rebuild_projects_drive_name_date_and_content_columns(self) -> None:
        existing_rows = [
            ["0", "旧项目A", "旧日期", "旧内容", "100", "110"],
            ["1", "项目B", "旧日期B", "旧内容B", "200", "210"],
        ]
        history_projects = [
            {
                "project_name": "项目A",
                "directory_name": "目录A",
                "project_year": "2020",
                "summary_text": "项目A结论",
            },
            {
                "project_name": "项目B",
                "directory_name": "目录B",
                "project_year": "2021",
                "summary_text": "项目B结论",
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
                ["0", "项目A", "2020", "项目A结论", "100", "110"],
                ["1", "项目B", "2021", "项目B结论", "200", "210"],
            ],
        )

    def test_history_rebuild_project_name_falls_back_to_directory_name(self) -> None:
        merged = _merge_history_rebuild_projects_into_load_rows(
            [],
            [
                {
                    "project_name": "",
                    "directory_name": "历史改造项目1",
                    "project_year": "",
                    "summary_text": "",
                }
            ],
            column_count=5,
        )

        self.assertEqual(merged, [["0", "历史改造项目1", "", "", ""]])

    def test_history_rebuild_merge_preserves_saved_manual_project_rows(self) -> None:
        existing_rows = [
            ["0", "文件管理项目", "旧日期", "旧内容", "100", "110"],
            ["1", "手动项目", "2024", "手动内容", "200", "210"],
        ]
        history_projects = [
            {
                "project_name": "文件管理项目",
                "directory_name": "",
                "project_year": "2020",
                "summary_text": "文件管理内容",
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
                ["0", "文件管理项目", "2020", "文件管理内容", "100", "110"],
                ["1", "手动项目", "2024", "手动内容", "200", "210"],
            ],
        )

if __name__ == "__main__":
    unittest.main()
