import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_baseline_science_narrative.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_baseline_science_narrative", MODULE_PATH)
build_pgd_baseline_science_narrative = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_baseline_science_narrative)


class BuildPgdBaselineScienceNarrativeTest(unittest.TestCase):
    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0])
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_release_dir(self, root: Path, *, station_aggregation: str = "median") -> Path:
        release_dir = root / "release"
        self.write_json(
            release_dir / "release_package_summary.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "ready_event_count": 13,
                "pgd_event_count": 94,
                "requires_sensitivity_caveat": True,
                "sensitivity_switch_scenarios": ["horizontal", "calibrated"],
            },
        )
        self.write_json(
            release_dir / "pgd_baseline_narrative_handoff.json",
            {
                "status": "OK",
                "baseline_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "station_aggregation_method": "median",
                "formula_comparison_scope": "formula_only",
                "baseline_narrative_status": "READY_WITH_CAVEATS",
                "overall_release_readiness_status": "BLOCKED_ON_REVIEW",
                "comparison_formula_review_status": "NEEDS_COMPARISON_REVIEW",
                "ready_event_count": 13,
                "reviewed_release_count": 12,
                "recommended_formula_blocker_count": 0,
                "comparison_formula_blocker_count": 13,
                "manual_decisions_written": 0,
                "requires_sensitivity_caveat": True,
                "formulas": ["ruhl_2019", "melgar_2015", "crowell_2016_gfast"],
            },
        )
        self.write_json(
            release_dir / "pgd_release_readiness.json",
            {
                "status": "OK",
                "readiness_status": "BLOCKED_ON_REVIEW",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "ready_event_count": 13,
                "reviewed_release_count": 12,
                "blocker_count": 13,
                "requires_sensitivity_caveat": True,
            },
        )
        self.write_json(
            release_dir / "reviewed_release_summary.json",
            {
                "status": "OK",
                "completion_status": "INCOMPLETE",
                "reviewed_release_count": 12,
                "blocker_count": 13,
            },
        )
        self.write_csv(
            release_dir / "formula_comparison.csv",
            [
                {
                    "comparison_group": "all",
                    "comparison_value": "ALL",
                    "formula": "ruhl_2019",
                    "station_aggregation": station_aggregation,
                    "event_count": "94",
                    "mae_mw": "0.435870",
                    "rmse_mw": "0.534545",
                    "median_abs_error_mw": "0.352000",
                    "residual_outlier_count": "6",
                },
                {
                    "comparison_group": "all",
                    "comparison_value": "ALL",
                    "formula": "melgar_2015",
                    "station_aggregation": station_aggregation,
                    "event_count": "94",
                    "mae_mw": "0.530393",
                    "rmse_mw": "0.649305",
                    "median_abs_error_mw": "0.410000",
                    "residual_outlier_count": "11",
                },
                {
                    "comparison_group": "all",
                    "comparison_value": "ALL",
                    "formula": "crowell_2016_gfast",
                    "station_aggregation": station_aggregation,
                    "event_count": "94",
                    "mae_mw": "0.739891",
                    "rmse_mw": "0.863719",
                    "median_abs_error_mw": "0.620000",
                    "residual_outlier_count": "29",
                },
            ],
        )
        self.write_csv(
            release_dir / "sensitivity_recommendations.csv",
            [
                {
                    "scenario_id": "baseline",
                    "station_aggregation": station_aggregation,
                    "recommended_formula": "ruhl_2019",
                    "mae_mw": "0.435870",
                    "rmse_mw": "0.534545",
                    "matches_baseline": "yes",
                },
                {
                    "scenario_id": "horizontal",
                    "station_aggregation": station_aggregation,
                    "recommended_formula": "melgar_2015",
                    "mae_mw": "0.353619",
                    "rmse_mw": "0.434871",
                    "matches_baseline": "no",
                },
            ],
        )
        return release_dir

    def test_writes_release_level_baseline_science_narrative(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = build_pgd_baseline_science_narrative.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "pgd_baseline_science_narrative.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["baseline_formula"], "ruhl_2019")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["formula_comparison_scope"], "formula_only")
            self.assertEqual(payload["narrative_status"], "READY_WITH_CAVEATS")
            self.assertEqual(payload["pgd_event_count"], 94)
            self.assertEqual(payload["ready_event_count"], 13)
            self.assertEqual(payload["reviewed_release_count"], 12)
            self.assertEqual(payload["comparison_formula_blocker_count"], 13)
            self.assertEqual(payload["manual_decisions_written"], 0)
            self.assertTrue(payload["requires_sensitivity_caveat"])
            self.assertEqual(payload["baseline_metrics"]["mae_mw"], "0.435870")
            self.assertEqual(payload["formula_count"], 3)
            markdown = (release_dir / "pgd_baseline_science_narrative.md").read_text(encoding="utf-8")
            self.assertIn("Baseline Conclusion", markdown)
            self.assertIn("`ruhl_2019`", markdown)
            self.assertIn("one station aggregation method: `median`", markdown)
            self.assertIn("formula-only comparison", markdown)
            self.assertIn("sensitivity caveat", markdown)
            self.assertIn("comparison-formula review remains pending", markdown)
            self.assertIn("crowell_2016_gfast", markdown)
            self.assertIn("does not write manual decisions", markdown)
            self.assertNotIn("three methods", markdown.lower())

    def test_rejects_non_median_release_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), station_aggregation="mean")

            rc = build_pgd_baseline_science_narrative.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_baseline_science_narrative.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["narrative_status"], "INVALID_INPUTS")
            self.assertTrue(any(error["code"] == "INVALID_STATION_AGGREGATION" for error in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
