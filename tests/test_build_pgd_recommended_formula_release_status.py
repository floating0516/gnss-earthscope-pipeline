import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_recommended_formula_release_status.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_recommended_formula_release_status", MODULE_PATH)
build_pgd_recommended_formula_release_status = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_recommended_formula_release_status)


class BuildPgdRecommendedFormulaReleaseStatusTest(unittest.TestCase):
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

    def make_release_dir(
        self,
        root: Path,
        *,
        station_aggregation: str = "median",
        recommended_blockers: int = 0,
        comparison_blockers: int = 2,
    ) -> Path:
        release_dir = root / "reports" / "pgd_magnitude" / "release" / "latest"
        self.write_json(
            release_dir / "release_package_summary.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "ready_event_count": 13,
                "requires_sensitivity_caveat": True,
            },
        )
        self.write_json(
            release_dir / "pgd_release_readiness.json",
            {
                "status": "OK",
                "readiness_status": "BLOCKED_ON_REVIEW",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "release_blocking_count": recommended_blockers + comparison_blockers,
                "ready_event_count": 13,
            },
        )
        self.write_json(
            release_dir / "reviewed_release_summary.json",
            {
                "status": "OK",
                "completion_status": "INCOMPLETE",
                "reviewed_release_count": 12,
                "blocker_count": recommended_blockers + comparison_blockers,
            },
        )
        self.write_json(
            release_dir / "pgd_release_blocker_analysis.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "blocker_count": recommended_blockers + comparison_blockers,
                "recommended_formula_blocker_count": recommended_blockers,
                "comparison_formula_blocker_count": comparison_blockers,
                "blockers_by_formula": {
                    "ruhl_2019": recommended_blockers,
                    "crowell_2016_gfast": comparison_blockers,
                },
                "manual_decisions_written": 0,
            },
        )
        self.write_json(
            release_dir / "pgd_formula_test_matrix.json",
            {
                "status": "OK",
                "station_aggregation": station_aggregation,
                "recommended_formula": "ruhl_2019",
                "formula_count": 3,
                "release_readiness_status": "BLOCKED_ON_REVIEW",
            },
        )
        self.write_csv(
            release_dir / "pgd_formula_test_matrix.csv",
            [
                {
                    "formula": "ruhl_2019",
                    "station_aggregation": station_aggregation,
                    "baseline_rank_by_mae": "1",
                    "baseline_recommended": "yes",
                    "sensitivity_win_count": "2",
                    "release_blocking_work_items": str(recommended_blockers),
                    "release_role": "recommended_baseline_formula",
                    "test_status": "BASELINE_RECOMMENDED_REVIEW_BLOCKED",
                },
                {
                    "formula": "melgar_2015",
                    "station_aggregation": station_aggregation,
                    "baseline_rank_by_mae": "2",
                    "baseline_recommended": "no",
                    "sensitivity_win_count": "2",
                    "release_blocking_work_items": "0",
                    "release_role": "comparison_formula",
                    "test_status": "COMPARISON_NEEDS_REVIEW",
                },
                {
                    "formula": "crowell_2016_gfast",
                    "station_aggregation": station_aggregation,
                    "baseline_rank_by_mae": "3",
                    "baseline_recommended": "no",
                    "sensitivity_win_count": "0",
                    "release_blocking_work_items": str(comparison_blockers),
                    "release_role": "comparison_formula",
                    "test_status": "COMPARISON_NEEDS_REVIEW",
                },
            ],
        )
        return release_dir

    def test_separates_recommended_formula_status_from_comparison_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), recommended_blockers=0, comparison_blockers=2)

            rc = build_pgd_recommended_formula_release_status.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "pgd_recommended_formula_release_status.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["recommended_formula"], "ruhl_2019")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["recommended_formula_release_status"], "READY_FOR_BASELINE_NARRATIVE")
            self.assertEqual(payload["overall_release_readiness_status"], "BLOCKED_ON_REVIEW")
            self.assertEqual(payload["recommended_formula_blocker_count"], 0)
            self.assertEqual(payload["comparison_formula_blocker_count"], 2)
            self.assertEqual(payload["manual_decisions_written"], 0)
            self.assertTrue(payload["requires_sensitivity_caveat"])
            with (release_dir / "pgd_recommended_formula_release_status.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            by_formula = {row["formula"]: row for row in rows}
            self.assertEqual(by_formula["ruhl_2019"]["formula_scope"], "recommended_formula")
            self.assertEqual(by_formula["ruhl_2019"]["formula_release_status"], "READY_FOR_BASELINE_NARRATIVE")
            self.assertEqual(by_formula["crowell_2016_gfast"]["formula_release_status"], "NEEDS_COMPARISON_REVIEW")
            self.assertEqual(by_formula["melgar_2015"]["formula_release_status"], "COMPARISON_CLEAR")
            markdown = (release_dir / "pgd_recommended_formula_release_status.md").read_text(encoding="utf-8")
            self.assertIn("READY_FOR_BASELINE_NARRATIVE", markdown)
            self.assertIn("comparison-formula blockers", markdown)
            self.assertIn("does not write manual decisions", markdown)

    def test_blocks_baseline_narrative_when_recommended_formula_has_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), recommended_blockers=1, comparison_blockers=2)

            rc = build_pgd_recommended_formula_release_status.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "pgd_recommended_formula_release_status.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["recommended_formula_release_status"], "BLOCKED_ON_RECOMMENDED_FORMULA_REVIEW")
            self.assertTrue(any("recommended formula" in action for action in payload["next_actions"]))

    def test_rejects_non_median_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), station_aggregation="mean")

            rc = build_pgd_recommended_formula_release_status.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_recommended_formula_release_status.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["recommended_formula_release_status"], "INVALID_INPUTS")
            self.assertTrue(any(error["code"] == "INVALID_STATION_AGGREGATION" for error in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
