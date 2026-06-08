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

    def test_scaled_large_axis_values_do_not_need_extra_scientific_label_margin(self) -> None:
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

        self.assertLessEqual(large_chart.figure.subplotpars.left, small_chart.figure.subplotpars.left)
        self.assertLessEqual(
            1 - large_chart.figure.subplotpars.right,
            1 - small_chart.figure.subplotpars.right,
        )

    def test_large_and_small_series_are_scaled_for_display_without_changing_raw_points(self) -> None:
        chart = MultiLineChart(
            "Operation Load",
            [0, 1, 2],
            [
                ("Fx", [120000.0, 130000.0, 140000.0], "left"),
                ("Fz", [2.2e6, 2.3e6, 2.4e6], "left"),
            ],
            left_ylabel="Fx,Fz(kN)",
        )
        self.addCleanup(chart.deleteLater)

        fx_plotted = list(chart._lines["Fx"].get_ydata())
        fz_plotted = list(chart._lines["Fz"].get_ydata())

        self.assertEqual([1.2, 1.3, 1.4], fx_plotted)
        self.assertEqual([2.2, 2.3, 2.4], fz_plotted)
        self.assertEqual([120000.0, 130000.0, 140000.0], chart._points["Fx"][1])
        self.assertEqual([2.2e6, 2.3e6, 2.4e6], chart._points["Fz"][1])

    def test_legend_labels_show_display_scale(self) -> None:
        chart = MultiLineChart(
            "Operation Load",
            [0, 1],
            [
                ("Fx", [100000.0, 120000.0], "left"),
                ("Fz", [2100000.0, 2300000.0], "left"),
            ],
            left_ylabel="Fx,Fz(kN)",
        )
        self.addCleanup(chart.deleteLater)

        self.assertEqual("Fx (×1e5)", chart._display_labels["Fx"])
        self.assertEqual("Fz (×1e6)", chart._display_labels["Fz"])

    def test_center_chart_can_show_raw_large_coordinates_without_display_scale(self) -> None:
        chart = MultiLineChart(
            "Center",
            [0, 1],
            [
                ("干重心Gx", [123456.0, 123556.0], "left"),
                ("操作重心Gy", [223456.0, 223556.0], "left"),
            ],
            left_ylabel="Gx,Gy(m)",
            scale_values=False,
        )
        self.addCleanup(chart.deleteLater)

        self.assertEqual([123456.0, 123556.0], list(chart._lines["干重心Gx"].get_ydata()))
        self.assertEqual([223456.0, 223556.0], list(chart._lines["操作重心Gy"].get_ydata()))
        self.assertEqual("干重心Gx", chart._display_labels["干重心Gx"])
        self.assertEqual("操作重心Gy", chart._display_labels["操作重心Gy"])

    def test_hover_text_includes_sequence_and_series_value(self) -> None:
        text = MultiLineChart._format_hover_text("Fx", 30, 123456.0)

        self.assertIn("30", text)
        self.assertIn("Fx", text)
        self.assertIn("123456", text)


if __name__ == "__main__":
    unittest.main()
