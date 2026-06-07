import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from pages.platform_load_information_page import (
    MultiLineChart,
    _normalise_chart_line_visibility,
    _select_chart_xticks,
)


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class PlatformLoadChartVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = _ensure_app()

    def test_chart_lines_default_to_visible(self) -> None:
        visibility = _normalise_chart_line_visibility({}, ["Fx", "Fy"])

        self.assertEqual(visibility, {"Fx": True, "Fy": True})

    def test_chart_line_visibility_is_preserved_after_data_refresh(self) -> None:
        visibility = _normalise_chart_line_visibility({"Fx": False, "Old": False}, ["Fx", "Fy", "Fz"])

        self.assertEqual(visibility, {"Fx": False, "Fy": True, "Fz": True})

    def test_x_axis_ticks_are_thinned_when_sequence_count_grows(self) -> None:
        ticks = _select_chart_xticks(list(range(31)), max_tick_count=8)

        self.assertLessEqual(len(ticks), 8)
        self.assertEqual(0, ticks[0])
        self.assertEqual(30, ticks[-1])
        self.assertEqual(ticks, sorted(set(ticks)))

    def test_large_axis_values_keep_y_axis_labels_inside_canvas(self) -> None:
        chart = MultiLineChart(
            "Extreme Load",
            [0, 1, 2, 3, 4, 5],
            [
                ("Fx", [0, 1.4e4, 0, 1.4e4, 0, 0], "left"),
                ("Fy", [0, 3.7e4, 0, 3.7e4, 0, 0], "left"),
                ("Fz", [0, 5.6e4, 0, 5.6e4, 0, 0], "left"),
                ("Mx", [0, 6.5e5, 0, 6.5e5, 0, 0], "right"),
                ("My", [0, 7.8e5, 0, 7.8e5, 0, 0], "right"),
                ("Mz", [0, 6.3e5, 0, 6.3e5, 0, 0], "right"),
            ],
            left_ylabel="Fx,Fy,Fz(kN)",
            right_ylabel="Mx,My,Mz(kN*m)",
        )
        self.addCleanup(chart.deleteLater)

        chart.resize(680, 390)
        chart.draw()
        renderer = chart.figure.canvas.get_renderer()
        figure_width = chart.figure.bbox.width
        left_label_box = chart.ax.yaxis.label.get_window_extent(renderer)
        right_label_box = chart.ax_right.yaxis.label.get_window_extent(renderer)

        self.assertGreaterEqual(left_label_box.x0, 0)
        self.assertLessEqual(right_label_box.x1, figure_width)

    def test_axis_margins_expand_for_large_scientific_tick_labels(self) -> None:
        small_chart = MultiLineChart(
            "Small",
            [0, 1, 2, 3],
            [
                ("Fx", [0, 1, 2, 3], "left"),
                ("Mx", [0, 1, 2, 3], "right"),
            ],
            left_ylabel="Fx(kN)",
            right_ylabel="Mx(kN*m)",
        )
        large_chart = MultiLineChart(
            "Large",
            [0, 1, 2, 3],
            [
                ("Fx", [0, 1.0e8, 2.0e8, 3.0e8], "left"),
                ("Mx", [0, 1.0e9, 2.0e9, 3.0e9], "right"),
            ],
            left_ylabel="Fx(kN)",
            right_ylabel="Mx(kN*m)",
        )
        self.addCleanup(small_chart.deleteLater)
        self.addCleanup(large_chart.deleteLater)

        small_chart.resize(680, 390)
        large_chart.resize(680, 390)
        small_chart.draw()
        large_chart.draw()

        self.assertGreater(large_chart.figure.subplotpars.left, small_chart.figure.subplotpars.left)
        self.assertGreater(
            1 - large_chart.figure.subplotpars.right,
            1 - small_chart.figure.subplotpars.right,
        )

    def test_hover_text_includes_sequence_and_series_value(self) -> None:
        text = MultiLineChart._format_hover_text("Fx", 30, 123456.0)

        self.assertIn("30", text)
        self.assertIn("Fx", text)
        self.assertIn("123456", text)


if __name__ == "__main__":
    unittest.main()
