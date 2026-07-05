import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_benchmark_interpretation.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_benchmark_interpretation", MODULE_PATH)
build_pgd_benchmark_interpretation = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = build_pgd_benchmark_interpretation
SPEC.loader.exec_module(build_pgd_benchmark_interpretation)


class BuildPgdBenchmarkInterpretationTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def summary_row(self, scenario: str, formula: str, events: int, mae: float, rank: int, recommended: str) -> dict[str, str]:
        return {
            "scenario_id": scenario,
            "scenario_label": scenario,
            "tier": scenario.upper(),
            "formula": formula,
            "station_aggregation": "median",
            "event_count": str(events),
            "excluded_event_count": str(142 - events),
            "total_filtered_station_count": str(events * 3),
            "median_station_count": "3.0",
            "min_station_count": "3.0",
            "bias_mw": "0.1",
            "mae_mw": f"{mae:.3f}",
            "rmse_mw": f"{mae + 0.1:.3f}",
            "median_abs_error_mw": f"{mae - 0.05:.3f}",
            "within_0_3_count": "1",
            "within_0_5_count": "2",
            "within_1_0_count": str(events),
            "over_1_0_count": "0",
            "rank_by_mae": str(rank),
            "recommended_formula": recommended,
            "filters": "synthetic",
        }

    def event_row(self, scenario: str, formula: str, event_id: str, catalog: str, estimate: str) -> dict[str, str]:
        residual = float(estimate) - float(catalog)
        return {
            "scenario_id": scenario,
            "scenario_label": scenario,
            "tier": scenario.upper(),
            "formula": formula,
            "station_aggregation": "median",
            "event_id": event_id,
            "event_time": "2020-01-01T00:00:00Z",
            "country": "United States",
            "region": "Test",
            "source": "synthetic",
            "place": "Synthetic",
            "usgs_magnitude": catalog,
            "station_count": "3",
            "median_pgd_cm": "3.0",
            "median_pgd_snr": "6.0",
            "median_distance_km": "100.0",
            "median_pgd_time_offset_s": "120.0",
            "estimated_mw_median": estimate,
            "residual_mw": f"{residual:.3f}",
            "abs_residual_mw": f"{abs(residual):.3f}",
            "filters": "synthetic",
        }

    def test_builds_interpretation_report_and_figures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            filter_dir = root / "filter_benchmark"
            out_dir = root / "interpretation"
            formulas = ["melgar_2015", "crowell_2016_gfast", "ruhl_2019"]
            summary_rows: list[dict[str, str]] = []
            for scenario, events, recommended in [
                ("all", 142, "ruhl_2019"),
                ("quality_snr3_time300_dist300_min3sta", 14, "melgar_2015"),
                ("strict_snr5_time300_dist300_min3sta", 6, "melgar_2015"),
            ]:
                for index, formula in enumerate(formulas, start=1):
                    mae = {"melgar_2015": 0.20, "crowell_2016_gfast": 0.40, "ruhl_2019": 0.10}[formula]
                    if recommended == "melgar_2015":
                        mae = {"melgar_2015": 0.08, "crowell_2016_gfast": 0.20, "ruhl_2019": 0.18}[formula]
                    rank = 1 if formula == recommended else index + 1
                    summary_rows.append(self.summary_row(scenario, formula, events, mae, rank, recommended))
            self.write_rows(filter_dir / "scenario_formula_summary.csv", summary_rows)
            event_rows = []
            for scenario in ["all", "quality_snr3_time300_dist300_min3sta", "strict_snr5_time300_dist300_min3sta"]:
                for formula in formulas:
                    event_rows.append(self.event_row(scenario, formula, "event-a", "6.0", "6.1"))
                    event_rows.append(self.event_row(scenario, formula, "event-b", "7.0", "6.9"))
            self.write_rows(filter_dir / "scenario_event_errors.csv", event_rows)
            self.write_rows(
                filter_dir / "scenario_exclusions.csv",
                [
                    {
                        "scenario_id": "strict_snr5_time300_dist300_min3sta",
                        "scenario_label": "strict",
                        "tier": "STRICT",
                        "event_id": "event-z",
                        "event_time": "",
                        "country": "Panama",
                        "region": "",
                        "source": "",
                        "place": "",
                        "usgs_magnitude": "6.0",
                        "total_station_count": "1",
                        "filtered_station_count": "0",
                        "min_stations": "3",
                        "exclusion_reason": "TOO_FEW_FILTERED_STATIONS",
                        "filters": "synthetic",
                    }
                ],
            )
            (filter_dir / "summary.json").write_text(json.dumps({"status": "OK", "scenario_count": 3}) + "\n", encoding="utf-8")

            rc = build_pgd_benchmark_interpretation.main(["--filter-dir", str(filter_dir), "--out-dir", str(out_dir)])

            self.assertEqual(rc, 0)
            expected_files = {
                "pgd_benchmark_interpretation.md",
                "pgd_benchmark_interpretation.json",
            }
            self.assertTrue(expected_files.issubset({path.name for path in out_dir.iterdir()}))
            figure_names = {path.name for path in (out_dir / "figures").iterdir()}
            self.assertEqual(
                figure_names,
                {
                    "scenario_mae_rmse.svg",
                    "event_count_vs_mae.svg",
                    "estimated_vs_catalog_all.svg",
                    "estimated_vs_catalog_quality.svg",
                    "estimated_vs_catalog_strict.svg",
                    "residual_diagnostics.svg",
                },
            )
            for path in (out_dir / "figures").iterdir():
                self.assertIn("<svg", path.read_text(encoding="utf-8"))
            payload = json.loads((out_dir / "pgd_benchmark_interpretation.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["highlights"]["all"]["recommended_formula"], "ruhl_2019")
            self.assertEqual(payload["highlights"]["quality"]["recommended_formula"], "melgar_2015")
            self.assertEqual(payload["highlights"]["strict"]["event_count"], 6)
            self.assertIn("strict_snr5_time300_dist300_min3sta", payload["figures"]["estimated_vs_catalog_strict"]["scenario_id"])
            md = (out_dir / "pgd_benchmark_interpretation.md").read_text(encoding="utf-8")
            self.assertIn("PGD Benchmark Interpretation", md)
            self.assertIn("QUALITY", md)
            self.assertIn("STRICT", md)
            self.assertIn("melgar_2015", md)


if __name__ == "__main__":
    unittest.main()
