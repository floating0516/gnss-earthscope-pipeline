import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "run_pgd_benchmark_bundle.py"
SPEC = importlib.util.spec_from_file_location("run_pgd_benchmark_bundle", MODULE_PATH)
run_pgd_benchmark_bundle = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_pgd_benchmark_bundle)


class RunPgdBenchmarkBundleTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_fake_report_outputs(self, report_dir: Path) -> None:
        self.write_rows(
            report_dir / "events.csv",
            [
                {
                    "event_id": "event-a",
                    "formula": "melgar_2015",
                    "station_aggregation": "median",
                    "usgs_magnitude": "6.4",
                    "estimated_mw_median": "6.2",
                    "residual_mw": "-0.2",
                    "abs_residual_mw": "0.2",
                    "usable_station_count": "3",
                    "median_pgd_snr": "5.0",
                    "median_distance_km": "25.0",
                },
                {
                    "event_id": "event-a",
                    "formula": "ruhl_2019",
                    "station_aggregation": "median",
                    "usgs_magnitude": "6.4",
                    "estimated_mw_median": "6.5",
                    "residual_mw": "0.1",
                    "abs_residual_mw": "0.1",
                    "usable_station_count": "3",
                    "median_pgd_snr": "5.0",
                    "median_distance_km": "25.0",
                },
            ],
        )
        self.write_rows(
            report_dir / "stations.csv",
            [
                {
                    "event_id": "event-a",
                    "station": "ABCD",
                    "formula": "melgar_2015",
                    "station_aggregation": "median",
                    "pgd_m": "0.12",
                    "pgd_snr": "5.0",
                    "hypocentral_distance_km": "25.0",
                    "estimated_mw": "6.2",
                    "residual_mw": "-0.2",
                }
            ],
        )
        self.write_rows(
            report_dir / "formula_comparison.csv",
            [
                {
                    "comparison_group": "all",
                    "comparison_value": "ALL",
                    "formula": "melgar_2015",
                    "station_aggregation": "median",
                    "event_count": "1",
                    "bias_mw": "-0.2",
                    "mae_mw": "0.2",
                    "rmse_mw": "0.2",
                    "median_abs_error_mw": "0.2",
                },
                {
                    "comparison_group": "all",
                    "comparison_value": "ALL",
                    "formula": "ruhl_2019",
                    "station_aggregation": "median",
                    "event_count": "1",
                    "bias_mw": "0.1",
                    "mae_mw": "0.1",
                    "rmse_mw": "0.1",
                    "median_abs_error_mw": "0.1",
                },
            ],
        )
        (report_dir / "summary.json").write_text(
            json.dumps(
                {
                    "status": "OK",
                    "counts": {"unique_events": 1, "event_rows": 2, "station_rows": 1, "formula_comparison_rows": 2},
                    "parameters": {"station_aggregation": "median", "pgd_component": "3d", "distance_mode": "hypocentral"},
                    "formula_recommendation": {"recommended_formula": "ruhl_2019", "station_aggregation": "median"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_fake_filter_outputs(self, filter_dir: Path) -> None:
        self.write_rows(
            filter_dir / "scenario_formula_summary.csv",
            [
                {
                    "scenario_id": "all",
                    "formula": "ruhl_2019",
                    "station_aggregation": "median",
                    "event_count": "1",
                    "excluded_event_count": "0",
                    "mae_mw": "0.100000",
                    "rmse_mw": "0.100000",
                    "median_abs_error_mw": "0.100000",
                    "rank_by_mae": "1",
                    "recommended_formula": "ruhl_2019",
                }
            ],
        )
        self.write_rows(
            filter_dir / "scenario_event_errors.csv",
            [
                {
                    "scenario_id": "all",
                    "formula": "ruhl_2019",
                    "station_aggregation": "median",
                    "event_id": "event-a",
                    "usgs_magnitude": "6.4",
                    "estimated_mw_median": "6.5",
                    "residual_mw": "0.1",
                    "abs_residual_mw": "0.1",
                }
            ],
        )
        self.write_rows(
            filter_dir / "scenario_exclusions.csv",
            [
                {
                    "scenario_id": "strict_snr5_time300_dist300_min3sta",
                    "event_id": "event-z",
                    "exclusion_reason": "TOO_FEW_FILTERED_STATIONS",
                }
            ],
        )
        (filter_dir / "summary.json").write_text(
            json.dumps({"status": "OK", "scenario_count": 10, "recommended_by_scenario": {"all": "ruhl_2019"}}) + "\n",
            encoding="utf-8",
        )
        (filter_dir / "README.md").write_text("# PGD Filter Benchmark\n", encoding="utf-8")

    def write_fake_interpretation_outputs(self, interpretation_dir: Path) -> None:
        figures = interpretation_dir / "figures"
        figures.mkdir(parents=True, exist_ok=True)
        for name in [
            "scenario_mae_rmse.svg",
            "event_count_vs_mae.svg",
            "estimated_vs_catalog_all.svg",
            "estimated_vs_catalog_quality.svg",
            "estimated_vs_catalog_strict.svg",
            "residual_diagnostics.svg",
        ]:
            (figures / name).write_text("<svg></svg>\n", encoding="utf-8")
        (interpretation_dir / "pgd_benchmark_interpretation.json").write_text(
            json.dumps(
                {
                    "status": "OK",
                    "highlights": {
                        "all": {"recommended_formula": "ruhl_2019", "event_count": 1},
                        "quality": {"recommended_formula": "melgar_2015", "event_count": 1},
                        "strict": {"recommended_formula": "melgar_2015", "event_count": 1},
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (interpretation_dir / "pgd_benchmark_interpretation.md").write_text("# PGD Benchmark Interpretation\n", encoding="utf-8")

    def fake_successful_run_command(self, commands: list[list[str]]):
        def fake_run(command: list[str]):
            commands.append(command)
            script = Path(command[1]).name
            out_dir = Path(command[command.index("--out-dir") + 1])
            if script == "run_pgd_report.py":
                self.write_fake_report_outputs(out_dir)
            elif script == "build_pgd_filter_benchmark.py":
                self.write_fake_filter_outputs(out_dir)
            elif script == "build_pgd_benchmark_interpretation.py":
                self.write_fake_interpretation_outputs(out_dir)
            else:
                raise AssertionError(f"unexpected command: {command}")
            return SimpleNamespace(returncode=0, stdout=f"{script} ok", stderr="")

        return fake_run

    def write_minimal_event_package(self, root: Path, dirname: str, event_id: str, country: str) -> None:
        package = root / dirname
        package.mkdir(parents=True)
        (package / "event.json").write_text(
            json.dumps({"event_id": event_id, "country": country, "magnitude": 6.4}) + "\n",
            encoding="utf-8",
        )
        (package / "stations.csv").write_text("Station\nABCD\n", encoding="utf-8")
        (package / "waveforms.csv.gz").write_bytes(b"placeholder")

    def test_runs_pgd_report_filter_and_interpretation_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "benchmark"
            work_dir = root / "work"
            out_json = root / "benchmark-summary.json"
            commands: list[list[str]] = []
            self.write_minimal_event_package(export_root, "us-event-a", "event-a", "United States")
            self.write_minimal_event_package(export_root, "pa-event-b", "event-b", "Panama")

            original_run_command = run_pgd_benchmark_bundle.run_command
            try:
                run_pgd_benchmark_bundle.run_command = self.fake_successful_run_command(commands)
                rc = run_pgd_benchmark_bundle.main(
                    [
                        "--export-root",
                        str(export_root),
                        "--out-dir",
                        str(out_dir),
                        "--work-dir",
                        str(work_dir),
                        "--out-json",
                        str(out_json),
                    ]
                )
            finally:
                run_pgd_benchmark_bundle.run_command = original_run_command

            self.assertEqual(rc, 0)
            self.assertEqual(
                [Path(command[1]).name for command in commands],
                ["run_pgd_report.py", "build_pgd_filter_benchmark.py", "build_pgd_benchmark_interpretation.py"],
            )
            self.assertNotIn("run_pgd_sensitivity.py", " ".join(commands[0]))
            self.assertIn("--countries", commands[0])
            countries = commands[0][commands[0].index("--countries") + 1 :]
            self.assertEqual(countries, ["Panama", "United States"])
            self.assertEqual(commands[1][commands[1].index("--benchmark-dir") + 1], str(out_dir))
            self.assertEqual(commands[1][commands[1].index("--out-dir") + 1], str(out_dir / "filter_benchmark"))
            self.assertEqual(commands[2][commands[2].index("--filter-dir") + 1], str(out_dir / "filter_benchmark"))
            self.assertEqual(commands[2][commands[2].index("--out-dir") + 1], str(out_dir / "filter_benchmark" / "interpretation"))
            self.assertEqual(
                sorted(path.name for path in out_dir.iterdir()),
                [
                    "README.md",
                    "events.csv",
                    "filter_benchmark",
                    "formula_errors.csv",
                    "formula_summary.csv",
                    "stations.csv",
                    "summary.json",
                ],
            )
            with (out_dir / "formula_errors.csv").open(newline="", encoding="utf-8") as handle:
                formula_errors = list(csv.DictReader(handle))
            self.assertEqual({row["formula"] for row in formula_errors}, {"melgar_2015", "ruhl_2019"})
            self.assertEqual({row["station_aggregation"] for row in formula_errors}, {"median"})
            with (out_dir / "formula_summary.csv").open(newline="", encoding="utf-8") as handle:
                formula_summary = list(csv.DictReader(handle))
            self.assertEqual({row["formula"] for row in formula_summary}, {"melgar_2015", "ruhl_2019"})
            self.assertEqual({row["station_aggregation"] for row in formula_summary}, {"median"})
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["workflow"], "pgd_benchmark_bundle")
            self.assertEqual(payload["stage_count"], 3)
            self.assertEqual([stage["stage"] for stage in payload["stages"]], ["pgd_report", "filter_benchmark", "benchmark_interpretation"])
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["country_scope"]["mode"], "all_normalized_export_countries")
            self.assertEqual(payload["country_scope"]["countries"], ["Panama", "United States"])
            self.assertEqual(payload["benchmark_outputs"]["formula_errors"], str(out_dir / "formula_errors.csv"))
            self.assertEqual(payload["filter_benchmark"]["summary"], str(out_dir / "filter_benchmark" / "summary.json"))
            self.assertEqual(
                payload["benchmark_interpretation"]["markdown"],
                str(out_dir / "filter_benchmark" / "interpretation" / "pgd_benchmark_interpretation.md"),
            )
            self.assertEqual(json.loads(out_json.read_text(encoding="utf-8"))["out_dir"], str(out_dir))
            readme = (out_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("PGD Benchmark Package", readme)
            self.assertIn("four-stage", readme)
            self.assertIn("filter_benchmark", readme)
            self.assertIn("PGD Benchmark Interpretation", readme)
            self.assertIn("one station aggregation method: `median`", readme)
            self.assertIn("Country scope: all normalized export countries", readme)
            self.assertNotIn("release blocker", readme.lower())

    def test_explicit_countries_override_default_export_country_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "benchmark"
            commands: list[list[str]] = []
            self.write_minimal_event_package(export_root, "us-event-a", "event-a", "United States")
            self.write_minimal_event_package(export_root, "pa-event-b", "event-b", "Panama")

            original_run_command = run_pgd_benchmark_bundle.run_command
            try:
                run_pgd_benchmark_bundle.run_command = self.fake_successful_run_command(commands)
                rc = run_pgd_benchmark_bundle.main(
                    [
                        "--export-root",
                        str(export_root),
                        "--out-dir",
                        str(out_dir),
                        "--countries",
                        "United States",
                    ]
                )
            finally:
                run_pgd_benchmark_bundle.run_command = original_run_command

            self.assertEqual(rc, 0)
            countries = commands[0][commands[0].index("--countries") + 1 :]
            self.assertEqual(countries, ["United States"])
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["country_scope"]["mode"], "explicit")
            self.assertEqual(payload["country_scope"]["countries"], ["United States"])

    def test_report_failure_stops_without_benchmark_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_json = root / "summary.json"
            self.write_minimal_event_package(root / "exports", "us-event-a", "event-a", "United States")

            def fake_run(_command: list[str]):
                return SimpleNamespace(returncode=2, stdout="", stderr="boom")

            original_run_command = run_pgd_benchmark_bundle.run_command
            try:
                run_pgd_benchmark_bundle.run_command = fake_run
                rc = run_pgd_benchmark_bundle.main(
                    [
                        "--export-root",
                        str(root / "exports"),
                        "--out-dir",
                        str(root / "benchmark"),
                        "--out-json",
                        str(out_json),
                    ]
                )
            finally:
                run_pgd_benchmark_bundle.run_command = original_run_command

            self.assertEqual(rc, 2)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "FAILED")
            self.assertEqual(payload["failed_stage"], "pgd_report")
            self.assertFalse((root / "benchmark" / "formula_errors.csv").exists())

    def test_default_work_dir_is_temporary_unless_explicitly_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "benchmark"
            commands: list[list[str]] = []
            self.write_minimal_event_package(root / "exports", "us-event-a", "event-a", "United States")

            original_run_command = run_pgd_benchmark_bundle.run_command
            try:
                run_pgd_benchmark_bundle.run_command = self.fake_successful_run_command(commands)
                rc = run_pgd_benchmark_bundle.main(["--export-root", str(root / "exports"), "--out-dir", str(out_dir)])
            finally:
                run_pgd_benchmark_bundle.run_command = original_run_command

            self.assertEqual(rc, 0)
            self.assertFalse((root / "benchmark-work").exists())
            self.assertTrue((out_dir / "formula_errors.csv").exists())
            report_dir = Path(commands[0][commands[0].index("--out-dir") + 1])
            self.assertFalse(report_dir.exists(), "implicit report work directory should be cleaned up")


if __name__ == "__main__":
    unittest.main()
