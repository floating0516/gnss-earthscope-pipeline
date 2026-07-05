import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_formula_test_matrix.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_formula_test_matrix", MODULE_PATH)
build_pgd_formula_test_matrix = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_formula_test_matrix)


class BuildPgdFormulaTestMatrixTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0]) if rows else ["formula"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def make_release_dir(self, root: Path, *, station_aggregation: str = "median") -> Path:
        release_dir = root / "reports" / "pgd_magnitude" / "release" / "latest"
        formulas = [
            ("melgar_2015", "0.530393", "0.649305", "0.542366", "11"),
            ("crowell_2016_gfast", "0.739891", "0.863719", "0.798946", "29"),
            ("ruhl_2019", "0.435870", "0.534545", "0.387517", "6"),
        ]
        self.write_csv(
            release_dir / "formula_comparison.csv",
            [
                {
                    "comparison_group": "all",
                    "comparison_value": "ALL",
                    "formula": formula,
                    "station_aggregation": station_aggregation,
                    "event_count": "94",
                    "high_medium_reliability_events": "13",
                    "low_reliability_events": "31",
                    "residual_outlier_count": outliers,
                    "bias_mw": "0.1",
                    "mae_mw": mae,
                    "rmse_mw": rmse,
                    "median_abs_error_mw": median_abs,
                }
                for formula, mae, rmse, median_abs, outliers in formulas
            ],
        )
        self.write_csv(
            release_dir / "sensitivity_recommendations.csv",
            [
                {
                    "scenario_id": "baseline",
                    "scenario_label": "3D PGD, hypocentral distance, no calibration",
                    "pgd_component": "3d",
                    "distance_mode": "hypocentral",
                    "calibration": "none",
                    "station_aggregation": station_aggregation,
                    "recommended_formula": "ruhl_2019",
                    "criterion": "lowest_mae_mw",
                    "event_count": "94",
                    "mae_mw": "0.435870",
                    "rmse_mw": "0.534545",
                    "median_abs_error_mw": "0.387517",
                    "residual_outlier_count": "6",
                    "matches_baseline": "yes",
                },
                {
                    "scenario_id": "horizontal",
                    "scenario_label": "Horizontal PGD",
                    "pgd_component": "horizontal",
                    "distance_mode": "hypocentral",
                    "calibration": "none",
                    "station_aggregation": station_aggregation,
                    "recommended_formula": "melgar_2015",
                    "criterion": "lowest_mae_mw",
                    "event_count": "94",
                    "mae_mw": "0.353619",
                    "rmse_mw": "0.434871",
                    "median_abs_error_mw": "0.296031",
                    "residual_outlier_count": "3",
                    "matches_baseline": "no",
                },
                {
                    "scenario_id": "epicentral",
                    "scenario_label": "3D PGD, epicentral distance",
                    "pgd_component": "3d",
                    "distance_mode": "epicentral",
                    "calibration": "none",
                    "station_aggregation": station_aggregation,
                    "recommended_formula": "ruhl_2019",
                    "criterion": "lowest_mae_mw",
                    "event_count": "94",
                    "mae_mw": "0.438786",
                    "rmse_mw": "0.534826",
                    "median_abs_error_mw": "0.387948",
                    "residual_outlier_count": "5",
                    "matches_baseline": "yes",
                },
            ],
        )
        self.write_csv(
            release_dir / "residual_review_worklist.csv",
            [
                {
                    "event_id": "event-1",
                    "formula": "crowell_2016_gfast",
                    "worklist_status": "PENDING_REVIEW",
                    "release_blocking": "yes",
                    "blocker_reason": "Residual review decision is still pending.",
                },
                {
                    "event_id": "event-2",
                    "formula": "crowell_2016_gfast",
                    "worklist_status": "PENDING_REVIEW",
                    "release_blocking": "yes",
                    "blocker_reason": "Residual review decision is still pending.",
                },
                {
                    "event_id": "event-3",
                    "formula": "ruhl_2019",
                    "worklist_status": "PENDING_REVIEW",
                    "release_blocking": "no",
                    "blocker_reason": "",
                },
            ],
        )
        self.write_json(
            release_dir / "release_package_summary.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "ready_event_count": 13,
                "requires_sensitivity_caveat": True,
                "sensitivity_switch_scenarios": ["horizontal"],
            },
        )
        self.write_json(
            release_dir / "pgd_release_readiness.json",
            {
                "status": "OK",
                "readiness_status": "BLOCKED_ON_REVIEW",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "release_blocking_count": 2,
                "ready_event_count": 13,
            },
        )
        return release_dir

    def test_builds_formula_test_matrix_from_release_products(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = build_pgd_formula_test_matrix.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            with (release_dir / "pgd_formula_test_matrix.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["formula"] for row in rows], ["ruhl_2019", "melgar_2015", "crowell_2016_gfast"])
            self.assertEqual({row["station_aggregation"] for row in rows}, {"median"})
            ruhl = rows[0]
            self.assertEqual(ruhl["baseline_rank_by_mae"], "1")
            self.assertEqual(ruhl["baseline_recommended"], "yes")
            self.assertEqual(ruhl["sensitivity_win_count"], "2")
            self.assertEqual(ruhl["sensitivity_winning_scenarios"], "baseline;epicentral")
            self.assertEqual(ruhl["release_role"], "recommended_baseline_formula")
            self.assertEqual(ruhl["test_status"], "BASELINE_RECOMMENDED_REVIEW_BLOCKED")
            crowell = rows[-1]
            self.assertEqual(crowell["baseline_rank_by_mae"], "3")
            self.assertEqual(crowell["release_blocking_work_items"], "2")
            self.assertEqual(crowell["test_status"], "COMPARISON_NEEDS_REVIEW")
            payload = json.loads((release_dir / "pgd_formula_test_matrix.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["recommended_formula"], "ruhl_2019")
            self.assertEqual(payload["formula_count"], 3)
            self.assertEqual(payload["sensitivity_scenario_count"], 3)
            self.assertEqual(payload["release_readiness_status"], "BLOCKED_ON_REVIEW")
            markdown = (release_dir / "pgd_formula_test_matrix.md").read_text(encoding="utf-8")
            self.assertIn("PGD Formula Test Matrix", markdown)
            self.assertIn("station aggregation method is fixed to `median`", markdown)
            self.assertIn("ruhl_2019", markdown)

    def test_rejects_non_median_formula_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), station_aggregation="mean")

            rc = build_pgd_formula_test_matrix.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_formula_test_matrix.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(any("station_aggregation" in error["message"] for error in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
