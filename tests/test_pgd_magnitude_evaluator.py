from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "evaluate_pgd_magnitude.py"
SPEC = importlib.util.spec_from_file_location("evaluate_pgd_magnitude", MODULE_PATH)
pgd = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = pgd
SPEC.loader.exec_module(pgd)


def write_waveforms(path: Path, station: str = "ABCD", peak_offset: int = 5) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz", "Source_File"],
            lineterminator="\n",
        )
        writer.writeheader()
        for offset in range(-35, 0):
            for component, value in [("E", 0.001), ("N", 0.0), ("U", 0.0)]:
                writer.writerow(
                    {
                        "Station": station,
                        "Time_UTC": "2020-01-01T00:00:00Z",
                        "Time_Offset_s": str(offset),
                        "Component": component,
                        "Value_m": f"{value:.6f}",
                        "Sampling_Hz": "1.0",
                        "Source_File": "synthetic",
                    }
                )
        samples = {
            peak_offset: {"E": 0.3, "N": 0.4, "U": 0.0},
            peak_offset + 1: {"E": 0.05, "N": 0.02},
            peak_offset + 2: {"E": 0.2, "N": 0.0, "U": 0.0},
        }
        for offset, components in samples.items():
            for component, value in components.items():
                writer.writerow(
                    {
                        "Station": station,
                        "Time_UTC": "2020-01-01T00:00:00Z",
                        "Time_Offset_s": str(offset),
                        "Component": component,
                        "Value_m": f"{value:.6f}",
                        "Sampling_Hz": "1.0",
                        "Source_File": "synthetic",
                    }
                )


def write_event_package(root: Path) -> Path:
    package = root / "event-a"
    package.mkdir(parents=True)
    (package / "event.json").write_text(
        json.dumps(
            {
                "schema_version": "normalized-event/v1",
                "event_id": "event-a",
                "event_time": "2020-01-01T00:00:00Z",
                "country": "United States",
                "region": "Synthetic Region",
                "magnitude": 6.4,
                "depth_km": 10.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with (package / "stations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Station", "Distance_Km", "Quality_Status"], lineterminator="\n")
        writer.writeheader()
        writer.writerow({"Station": "ABCD", "Distance_Km": "20.0", "Quality_Status": "OK"})
    write_waveforms(package / "waveforms.csv.gz")
    return package


def evaluator_args(**overrides: object) -> SimpleNamespace:
    args = {
        "pgd_window_start": 0.0,
        "pgd_window_end": 30.0,
        "min_pgd_m": 1e-6,
        "pgd_component": "3d",
        "noise_window_start": -40.0,
        "noise_window_end": 0.0,
        "distance": "hypocentral",
        "min_distance_km": 1.0,
        "max_distance_km": 0.0,
        "max_pgd_time_offset": 0.0,
        "min_pgd_snr": 3.0,
        "quality_max_distance_km": 500.0,
        "quality_max_pgd_time_offset": 300.0,
        "near_distance_km": 300.0,
        "min_stations": 1,
        "station_aggregation": "median",
        "trim_fraction": 0.2,
    }
    args.update(overrides)
    return SimpleNamespace(**args)


class PgdMagnitudeEvaluatorTest(unittest.TestCase):
    def test_read_pgd_by_station_uses_complete_components_and_noise_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            waveform_path = Path(tmp) / "waveforms.csv.gz"
            write_waveforms(waveform_path)

            by_station = pgd.read_pgd_by_station(waveform_path, 0.0, 30.0, 1e-6, "3d", -40.0, 0.0)

        station = by_station["ABCD"]
        self.assertAlmostEqual(station["pgd_m"], 0.5)
        self.assertEqual(station["pgd_time_offset_s"], 5.0)
        self.assertEqual(station["pgd_sample_count"], 2.0)
        self.assertEqual(station["noise_sample_count"], 35.0)
        self.assertAlmostEqual(station["pre_event_rms_m"], 0.001)
        self.assertGreater(station["pgd_snr"], 400.0)

    def test_evaluate_event_uses_normalized_event_time_and_region_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            event_dir = write_event_package(Path(tmp))

            station_rows, event_rows = pgd.evaluate_event(event_dir, evaluator_args())

        self.assertEqual(len(station_rows), 3)
        self.assertEqual(len(event_rows), 3)
        self.assertEqual({row["event_time"] for row in station_rows + event_rows}, {"2020-01-01T00:00:00Z"})
        self.assertEqual({row["place"] for row in station_rows + event_rows}, {"Synthetic Region"})
        melgar = next(row for row in event_rows if row["formula"] == "melgar_2015")
        self.assertEqual(melgar["usable_station_count"], 1)
        self.assertEqual(melgar["pgd_reliability"], "LOW")
        self.assertTrue(math.isfinite(float(melgar["estimated_mw_median"])))

    def test_station_quality_flags_report_low_snr_far_and_late_peak(self):
        usable, flags = pgd.station_quality_flags(
            {
                "pgd_snr": 1.2,
                "pgd_time_offset_s": 350.0,
                "noise_sample_count": 10.0,
            },
            650.0,
            evaluator_args(),
        )

        self.assertFalse(usable)
        self.assertEqual(set(flags.split(",")), {"low_pgd_snr", "far_station", "late_pgd_peak", "short_noise_window"})

    def test_station_aggregation_is_always_median(self):
        values = [1.0, 3.0, 100.0]

        self.assertEqual(pgd.aggregate_station_estimates(values), 3.0)
        with self.assertRaises(TypeError):
            pgd.aggregate_station_estimates(values, "median")
        with self.assertRaises(TypeError):
            pgd.aggregate_station_estimates(values, "mean")
        with self.assertRaises(TypeError):
            pgd.aggregate_station_estimates(values, "trimmed-mean", 0.2)

    def test_leave_one_out_calibration_records_raw_values_and_fit_metadata(self):
        rows = [
            {"country": "United States", "formula": "melgar_2015", "estimated_mw_median": 5.0, "usgs_magnitude": 6.0, "residual_mw": -1.0},
            {"country": "United States", "formula": "melgar_2015", "estimated_mw_median": 6.0, "usgs_magnitude": 8.0, "residual_mw": -2.0},
            {"country": "United States", "formula": "melgar_2015", "estimated_mw_median": 7.0, "usgs_magnitude": 10.0, "residual_mw": -3.0},
        ]

        calibrated = pgd.apply_leave_one_out_calibration(rows)

        self.assertEqual(len(calibrated), 3)
        for row in calibrated:
            self.assertEqual(row["calibration"], "leave_one_out_country_linear")
            self.assertAlmostEqual(float(row["calibration_intercept"]), -4.0)
            self.assertAlmostEqual(float(row["calibration_slope"]), 2.0)
            self.assertAlmostEqual(float(row["residual_mw"]), 0.0)
            self.assertIn("raw_estimated_mw_median", row)
            self.assertIn("raw_residual_mw", row)

    def test_cli_rejects_non_median_station_aggregation(self):
        original_argv = sys.argv
        try:
            sys.argv = ["evaluate_pgd_magnitude.py", "--station-aggregation", "mean"]
            with self.assertRaises(SystemExit):
                pgd.parse_args()
        finally:
            sys.argv = original_argv

    def test_cli_rejects_trim_fraction_without_trimmed_mean_method(self):
        original_argv = sys.argv
        try:
            sys.argv = ["evaluate_pgd_magnitude.py", "--trim-fraction", "0.1"]
            with self.assertRaises(SystemExit):
                pgd.parse_args()
        finally:
            sys.argv = original_argv

    def test_main_writes_formula_summary_products_as_canonical_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "normalized"
            write_event_package(root)
            out_root = Path(tmp) / "pgd"
            figure_root = Path(tmp) / "figures"
            out_root.mkdir(parents=True)
            for stale_name in [
                "method_summary_raw.tsv",
                "method_summary.tsv",
                "method_summary_by_magnitude_bin.tsv",
                "method_summary_quality_filtered_by_magnitude_bin.tsv",
            ]:
                (out_root / stale_name).write_text("stale\n", encoding="utf-8")
            original_argv = sys.argv
            try:
                sys.argv = [
                    "evaluate_pgd_magnitude.py",
                    "--normalized-root",
                    str(root),
                    "--out-root",
                    str(out_root),
                    "--figure-root",
                    str(figure_root),
                    "--countries",
                    "United States",
                ]

                exit_code = pgd.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            canonical_outputs = [
                "formula_summary_raw.tsv",
                "formula_summary.tsv",
                "formula_summary_by_magnitude_bin.tsv",
                "formula_summary_quality_filtered_by_magnitude_bin.tsv",
            ]
            for canonical in canonical_outputs:
                with self.subTest(canonical=canonical):
                    canonical_path = out_root / canonical
                    self.assertTrue(canonical_path.exists())
            legacy_aliases = [
                "method_summary_raw.tsv",
                "method_summary.tsv",
                "method_summary_by_magnitude_bin.tsv",
                "method_summary_quality_filtered_by_magnitude_bin.tsv",
            ]
            for legacy_alias in legacy_aliases:
                with self.subTest(legacy_alias=legacy_alias):
                    self.assertFalse((out_root / legacy_alias).exists())
            figure_text = (figure_root / "formula_mae_by_region.svg").read_text(encoding="utf-8")
            self.assertIn("PGD formula MAE by region", figure_text)
            self.assertNotIn("PGD method MAE by region", figure_text)


if __name__ == "__main__":
    unittest.main()
