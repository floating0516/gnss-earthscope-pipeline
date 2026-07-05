import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_filter_benchmark.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_filter_benchmark", MODULE_PATH)
build_pgd_filter_benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = build_pgd_filter_benchmark
SPEC.loader.exec_module(build_pgd_filter_benchmark)


class BuildPgdFilterBenchmarkTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def station_row(
        self,
        *,
        event_id: str,
        station: str,
        formula: str,
        estimated_mw: str,
        magnitude: str = "6.0",
        pgd_cm: str = "3.0",
        snr: str = "6.0",
        time_offset: str = "120.0",
        distance: str = "100.0",
    ) -> dict[str, str]:
        return {
            "event_id": event_id,
            "event_time": "2020-01-01T00:00:00Z",
            "country": "United States" if event_id == "event-good" else "Panama",
            "region": "Test",
            "source": "synthetic",
            "place": "Synthetic",
            "usgs_magnitude": magnitude,
            "station": station,
            "formula": formula,
            "station_aggregation": "median",
            "pgd_cm": pgd_cm,
            "pgd_snr": snr,
            "pgd_time_offset_s": time_offset,
            "hypocentral_distance_km": distance,
            "estimated_mw": estimated_mw,
        }

    def test_builds_filter_benchmark_from_station_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark_dir = root / "benchmark"
            out_dir = root / "filters"
            formulas = ["melgar_2015", "crowell_2016_gfast", "ruhl_2019"]
            good_estimates = {"melgar_2015": "6.1", "crowell_2016_gfast": "6.2", "ruhl_2019": "6.0"}
            low_estimates = {"melgar_2015": "7.0", "crowell_2016_gfast": "7.2", "ruhl_2019": "7.4"}
            rows: list[dict[str, str]] = []
            for formula in formulas:
                rows.extend(
                    [
                        self.station_row(event_id="event-good", station="AAA", formula=formula, estimated_mw=good_estimates[formula]),
                        self.station_row(event_id="event-good", station="BBB", formula=formula, estimated_mw=good_estimates[formula]),
                        self.station_row(event_id="event-good", station="CCC", formula=formula, estimated_mw=good_estimates[formula]),
                        self.station_row(event_id="event-low-pgd", station="DDD", formula=formula, estimated_mw=low_estimates[formula], pgd_cm="1.5", snr="2.0"),
                        self.station_row(event_id="event-low-pgd", station="EEE", formula=formula, estimated_mw=low_estimates[formula], pgd_cm="1.5", snr="2.0"),
                        self.station_row(event_id="event-low-pgd", station="FFF", formula=formula, estimated_mw=low_estimates[formula], pgd_cm="1.5", snr="2.0"),
                    ]
                )
            self.write_rows(benchmark_dir / "stations.csv", rows)

            rc = build_pgd_filter_benchmark.main(["--benchmark-dir", str(benchmark_dir), "--out-dir", str(out_dir)])

            self.assertEqual(rc, 0)
            expected = [
                "README.md",
                "scenario_event_errors.csv",
                "scenario_exclusions.csv",
                "scenario_formula_summary.csv",
                "summary.json",
            ]
            self.assertEqual(sorted(path.name for path in out_dir.iterdir()), expected)
            with (out_dir / "scenario_formula_summary.csv").open(newline="", encoding="utf-8") as handle:
                summary_rows = list(csv.DictReader(handle))
            summary_by_key = {(row["scenario_id"], row["formula"]): row for row in summary_rows}
            self.assertEqual(summary_by_key[("all", "ruhl_2019")]["event_count"], "2")
            self.assertEqual(summary_by_key[("pgd_ge_2cm", "ruhl_2019")]["event_count"], "1")
            self.assertEqual(summary_by_key[("strict_snr5_time300_dist300_min3sta", "ruhl_2019")]["event_count"], "1")
            self.assertEqual(summary_by_key[("strict_snr5_time300_dist300_min3sta", "ruhl_2019")]["median_station_count"], "3.000000")
            self.assertEqual(summary_by_key[("strict_snr5_time300_dist300_min3sta", "ruhl_2019")]["mae_mw"], "0.000000")
            with (out_dir / "scenario_exclusions.csv").open(newline="", encoding="utf-8") as handle:
                exclusions = list(csv.DictReader(handle))
            self.assertTrue(
                any(
                    row["scenario_id"] == "pgd_ge_2cm"
                    and row["event_id"] == "event-low-pgd"
                    and row["exclusion_reason"] == "TOO_FEW_FILTERED_STATIONS"
                    for row in exclusions
                )
            )
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["scenario_count"], 10)
            self.assertEqual(payload["recommended_by_scenario"]["strict_snr5_time300_dist300_min3sta"], "ruhl_2019")
            readme = (out_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("PGD Filter Benchmark", readme)
            self.assertIn("strict_snr5_time300_dist300_min3sta", readme)


if __name__ == "__main__":
    unittest.main()
