import unittest

from pages.platform_load_information_page import _normalise_chart_line_visibility


class PlatformLoadChartVisibilityTests(unittest.TestCase):
    def test_chart_lines_default_to_visible(self) -> None:
        visibility = _normalise_chart_line_visibility({}, ["Fx", "Fy"])

        self.assertEqual(visibility, {"Fx": True, "Fy": True})

    def test_chart_line_visibility_is_preserved_after_data_refresh(self) -> None:
        visibility = _normalise_chart_line_visibility({"Fx": False, "Old": False}, ["Fx", "Fy", "Fz"])

        self.assertEqual(visibility, {"Fx": False, "Fy": True, "Fz": True})


if __name__ == "__main__":
    unittest.main()
