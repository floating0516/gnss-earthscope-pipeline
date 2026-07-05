import csv
import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "run_pgd_sensitivity.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing sensitivity script: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("run_pgd_sensitivity", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunPgdSensitivityTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_event_package(
        self,
        root: Path,
        *,
        event_id: str,
        dirname: str,
        magnitude: float,
        signal_base: float,
        station_distances: list[tuple[str, str]],
    ) -> None:
        package = root / dirname
        package.mkdir(parents=True)
        (package / "event.json").write_text(
            json.dumps(
                {
                    "event_id": event_id,
                    "date": "2020-01-01T00:00:00Z",
                    "country": "United States",
                    "region": "US",
                    "source": "earthscope",
                    "place": "Synthetic sensitivity event",
                    "magnitude": magnitude,
                    "depth_km": 10.0,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (package / "provenance.json").write_text(
            json.dumps({"event_id": event_id, "station_count": len(station_distances)}) + "\n",
            encoding="utf-8",
        )
        self.write_rows(
            package / "stations.csv",
            [
                {
                    "Station": station,
                    "Latitude": "35.0",
                    "Longitude": "-120.0",
                    "Distance_Km": station_distance,
                    "Quality_Status": "OK",
                }
                for station, station_distance in station_distances
            ],
        )
        with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz", "Source_File"],
                lineterminator="\n",
            )
            writer.writeheader()
            for offset in range(-40, 11):
                base = 0.001 if offset < 0 else signal_base + offset * 0.001
                for station, _station_distance in station_distances:
                    for component, value in [("E", base), ("N", base / 2.0), ("U", base / 4.0)]:
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

    def test_cli_writes_default_sensitivity_report(self):
        run_pgd_sensitivity = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "reports" / "pgd_sensitivity"
            self.make_event_package(
                export_root,
                event_id="event-a",
                dirname="us-event-a",
                magnitude=6.4,
                signal_base=0.20,
                station_distances=[("ABCD", "20.0"), ("EFGH", "25.0"), ("IJKL", "30.0")],
            )
            self.make_event_package(
                export_root,
                event_id="event-b",
                dirname="us-event-b",
                magnitude=7.1,
                signal_base=0.55,
                station_distances=[("MNOP", "30.0"), ("QRST", "35.0"), ("UVWX", "40.0")],
            )

            rc = run_pgd_sensitivity.main(["--export-root", str(export_root), "--out-dir", str(out_dir)])

            self.assertEqual(rc, 0)
            for name in [
                "sensitivity_summary.csv",
                "sensitivity_recommendations.csv",
                "sensitivity_formula_deltas.csv",
                "sensitivity_interpretation.md",
                "summary.json",
                "summary.md",
            ]:
                self.assertTrue((out_dir / name).exists(), name)
            with (out_dir / "sensitivity_summary.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 12)
            self.assertEqual({row["scenario_id"] for row in rows}, {"baseline", "horizontal", "epicentral", "calibrated"})
            self.assertEqual({row["formula"] for row in rows}, {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            self.assertEqual({row["station_aggregation"] for row in rows}, {"median"})
            self.assertEqual({row["event_count"] for row in rows}, {"2"})
            calibrated = [row for row in rows if row["scenario_id"] == "calibrated"]
            self.assertEqual({row["calibration"] for row in calibrated}, {"leave-one-out-country-linear"})
            with (out_dir / "sensitivity_recommendations.csv").open(newline="", encoding="utf-8") as handle:
                recommendation_rows = list(csv.DictReader(handle))
            self.assertEqual(len(recommendation_rows), 4)
            self.assertEqual({row["station_aggregation"] for row in recommendation_rows}, {"median"})
            self.assertTrue(all(row["recommended_formula"] in {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"} for row in recommendation_rows))
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["counts"]["scenario_count"], 4)
            self.assertEqual(payload["counts"]["summary_rows"], 12)
            self.assertIn(payload["baseline_recommendation"]["recommended_formula"], {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            self.assertIn("recommendation_stable", payload)
            self.assertIn("formula_deltas", payload)
            delta_rows = payload["formula_deltas"]
            self.assertEqual(payload["counts"]["formula_delta_rows"], len(delta_rows))
            self.assertEqual(len(delta_rows), 12)
            self.assertEqual({row["station_aggregation"] for row in delta_rows}, {"median"})
            self.assertEqual({row["baseline_formula"] for row in delta_rows}, {payload["baseline_recommendation"]["recommended_formula"]})
            self.assertTrue(any(row["scenario_id"] == "baseline" and row["scenario_rank"] == 1 for row in delta_rows))
            with (out_dir / "sensitivity_formula_deltas.csv").open(newline="", encoding="utf-8") as handle:
                delta_csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(delta_csv_rows), 12)
            self.assertEqual({row["station_aggregation"] for row in delta_csv_rows}, {"median"})
            self.assertTrue(all("delta_mae_vs_baseline_scenario" in row for row in delta_csv_rows))
            interpretation_md = (out_dir / "sensitivity_interpretation.md").read_text(encoding="utf-8")
            self.assertIn("Formula Switches", interpretation_md)
            self.assertIn("baseline", interpretation_md)
            self.assertIn("median", interpretation_md)
            summary_md = (out_dir / "summary.md").read_text(encoding="utf-8")
            self.assertIn("PGD Sensitivity", summary_md)
            self.assertIn("Baseline formula", summary_md)
            self.assertIn("median", summary_md)

    def test_default_scenarios_reuse_raw_evaluation_when_only_calibration_differs(self):
        run_pgd_sensitivity = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            args = run_pgd_sensitivity.parse_args(
                [
                    "--export-root",
                    str(Path(tmp) / "exports"),
                    "--out-dir",
                    str(Path(tmp) / "reports" / "pgd_sensitivity"),
                ]
            )
            call_keys: list[tuple[str, str]] = []

            def fake_iter_event_dirs(_root: Path, _countries: set[str]):
                return [Path("event-a")]

            def fake_evaluate_event(_event_dir: Path, eval_args):
                call_keys.append((eval_args.pgd_component, eval_args.distance))
                event_rows = []
                for index, law in enumerate(run_pgd_sensitivity.pgd.SCALING_LAWS):
                    residual = float(index + 1) / 10.0
                    event_rows.append(
                        {
                            "event_id": "event-a",
                            "country": "United States",
                            "formula": law.name,
                            "usgs_magnitude": 6.4,
                            "estimated_mw_median": 6.4 + residual,
                            "residual_mw": residual,
                            "abs_residual_mw": abs(residual),
                            "pgd_reliability": "HIGH",
                        }
                    )
                return [], event_rows

            def fake_apply_leave_one_out_calibration(event_rows):
                calibrated = []
                for row in event_rows:
                    updated = dict(row)
                    updated["calibration"] = "leave_one_out_country_linear"
                    calibrated.append(updated)
                return calibrated

            original_iter_event_dirs = run_pgd_sensitivity.pgd.iter_event_dirs
            original_evaluate_event = run_pgd_sensitivity.pgd.evaluate_event
            original_apply_calibration = run_pgd_sensitivity.pgd.apply_leave_one_out_calibration
            try:
                run_pgd_sensitivity.pgd.iter_event_dirs = fake_iter_event_dirs
                run_pgd_sensitivity.pgd.evaluate_event = fake_evaluate_event
                run_pgd_sensitivity.pgd.apply_leave_one_out_calibration = fake_apply_leave_one_out_calibration

                payload = run_pgd_sensitivity.run_sensitivity(args)
            finally:
                run_pgd_sensitivity.pgd.iter_event_dirs = original_iter_event_dirs
                run_pgd_sensitivity.pgd.evaluate_event = original_evaluate_event
                run_pgd_sensitivity.pgd.apply_leave_one_out_calibration = original_apply_calibration

            self.assertEqual(payload["counts"]["scenario_count"], 4)
            self.assertEqual(call_keys.count(("3d", "hypocentral")), 1)
            self.assertEqual(sorted(call_keys), [("3d", "epicentral"), ("3d", "hypocentral"), ("horizontal", "hypocentral")])


if __name__ == "__main__":
    unittest.main()
