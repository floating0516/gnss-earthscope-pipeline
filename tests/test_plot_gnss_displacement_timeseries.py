from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "plotting" / "plot_gnss_displacement_timeseries.py"


def load_script_module():
    if not SCRIPT.exists():
        raise AssertionError(f"missing plotting script: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("plot_gnss_displacement_timeseries", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load plotting script: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GnssDisplacementTimeseriesTest(unittest.TestCase):
    def test_parse_args_defaults_to_scale_bar_without_pgd_highlight(self):
        module = load_script_module()

        with patch("sys.argv", ["plot_gnss_displacement_timeseries.py", "event-dir"]):
            args = module.parse_args()

        self.assertFalse(args.highlight_max_pgd)
        self.assertEqual(args.scale_bar_cm, 5.0)

    def test_plot_default_scale_bar_is_single_5_cm_vertical_marker(self):
        module = load_script_module()
        trace = pd.DataFrame({"time_s": [0.0, 600.0], "value_cm": [0.0, 0.1]})
        plot_data = module.PlotData(
            stations=[module.StationPlotInfo(station="AAAA", distance_km=10.0)],
            traces={(station, component): trace.copy() for station in ["AAAA"] for component in module.COMPONENTS},
            time_start=0.0,
            time_end=600.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(module.plt, "close") as close_mock:
            module.plot_displacement_timeseries(
                plot_data,
                {"date": "2025-01-07T01:05:16Z"},
                Path(tmpdir) / "plot.png",
                dpi=72,
            )
            fig = close_mock.call_args.args[0]

        self.addCleanup(module.plt.close, fig)
        east_lines = fig.axes[0].lines
        vertical_5cm_lines = []
        horizontal_cap_lines = []
        for line in east_lines:
            x_data = [float(value) for value in line.get_xdata()]
            y_data = [float(value) for value in line.get_ydata()]
            if len(x_data) != 2 or len(y_data) != 2:
                continue
            x_span = abs(x_data[1] - x_data[0])
            y_span = abs(y_data[1] - y_data[0])
            if x_span < 1e-9 and abs(y_span - 5.0) < 1e-9:
                vertical_5cm_lines.append(line)
            if y_span < 1e-9 and 8.0 < x_span < 20.0:
                horizontal_cap_lines.append(line)

        self.assertEqual(len(vertical_5cm_lines), 1)
        self.assertEqual(horizontal_cap_lines, [])
        self.assertIn("5 cm", [text.get_text() for text in fig.axes[0].texts])

    def test_parse_args_can_enable_pgd_highlight_and_change_scale_bar(self):
        module = load_script_module()

        with patch(
            "sys.argv",
            [
                "plot_gnss_displacement_timeseries.py",
                "event-dir",
                "--highlight-max-pgd",
                "--scale-bar-cm",
                "5",
            ],
        ):
            args = module.parse_args()

        self.assertTrue(args.highlight_max_pgd)
        self.assertEqual(args.scale_bar_cm, 5.0)

    def test_prepare_plot_data_sorts_far_to_near_and_converts_to_cm(self):
        module = load_script_module()
        stations = pd.DataFrame(
            [
                {"Station": "NEAR", "Distance_Km": 20.0},
                {"Station": "FAR", "Distance_Km": 90.0},
                {"Station": "MID", "Distance_Km": 50.0},
            ]
        )
        waveforms = pd.DataFrame(
            [
                {"Station": "FAR", "Time_Offset_s": 0.0, "Component": "E", "Value_m": 0.01},
                {"Station": "FAR", "Time_Offset_s": 1.0, "Component": "E", "Value_m": 0.03},
                {"Station": "MID", "Time_Offset_s": 0.0, "Component": "E", "Value_m": -0.02},
                {"Station": "MID", "Time_Offset_s": 1.0, "Component": "E", "Value_m": -0.01},
                {"Station": "NEAR", "Time_Offset_s": 0.0, "Component": "E", "Value_m": 0.00},
                {"Station": "NEAR", "Time_Offset_s": 1.0, "Component": "E", "Value_m": 0.02},
                {"Station": "FAR", "Time_Offset_s": 700.0, "Component": "E", "Value_m": 1.00},
            ]
        )

        plot_data = module.prepare_plot_data(
            stations,
            waveforms,
            time_start=0.0,
            time_end=600.0,
            baseline_seconds=0.0,
        )

        self.assertEqual([row.station for row in plot_data.stations], ["FAR", "MID", "NEAR"])
        self.assertEqual([row.distance_km for row in plot_data.stations], [90.0, 50.0, 20.0])
        far_trace = plot_data.traces[("FAR", "E")]
        self.assertEqual(far_trace["time_s"].tolist(), [0.0, 1.0])
        self.assertEqual(far_trace["value_cm"].tolist(), [1.0, 3.0])
        self.assertNotIn(("FAR", "N"), plot_data.traces)

    def test_prepare_plot_data_removes_initial_baseline_per_trace(self):
        module = load_script_module()
        stations = pd.DataFrame([{"Station": "AAAA", "Distance_Km": 12.0}])
        waveforms = pd.DataFrame(
            [
                {"Station": "AAAA", "Time_Offset_s": 0.0, "Component": "U", "Value_m": 0.10},
                {"Station": "AAAA", "Time_Offset_s": 5.0, "Component": "U", "Value_m": 0.14},
                {"Station": "AAAA", "Time_Offset_s": 20.0, "Component": "U", "Value_m": 0.20},
            ]
        )

        plot_data = module.prepare_plot_data(
            stations,
            waveforms,
            time_start=0.0,
            time_end=600.0,
            baseline_seconds=10.0,
        )

        trace = plot_data.traces[("AAAA", "U")]
        for actual, expected in zip(trace["value_cm"].tolist(), [-2.0, 2.0, 8.0], strict=True):
            self.assertAlmostEqual(actual, expected)

    def test_selects_largest_usable_pgd_and_skips_low_snr(self):
        module = load_script_module()
        stations = [
            module.StationPlotInfo(station="NOIS", distance_km=10.0),
            module.StationPlotInfo(station="GOOD", distance_km=20.0),
        ]
        pgd_by_station = {
            "NOIS": {
                "pgd_cm": 20.0,
                "pgd_e_m": 0.10,
                "pgd_n_m": 0.10,
                "pgd_u_m": 0.10,
                "pgd_time_offset_s": 120.0,
                "pgd_snr": 1.5,
                "noise_sample_count": 100.0,
            },
            "GOOD": {
                "pgd_cm": 5.0,
                "pgd_e_m": 0.03,
                "pgd_n_m": 0.04,
                "pgd_u_m": 0.00,
                "pgd_time_offset_s": 80.0,
                "pgd_snr": 8.0,
                "noise_sample_count": 100.0,
            },
        }

        pgd = module.find_max_usable_station_pgd(
            stations,
            pgd_by_station,
            min_pgd_snr=3.0,
            quality_max_pgd_time_offset=300.0,
            quality_max_distance_km=0.0,
        )

        self.assertEqual(pgd.station, "GOOD")
        self.assertTrue(pgd.usable)
        self.assertEqual(pgd.quality_flags, "")
        self.assertEqual(module.pgd_label(pgd), "PGD = 5.00 cm")


if __name__ == "__main__":
    unittest.main()
