import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_release_blocker_analysis.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_release_blocker_analysis", MODULE_PATH)
build_pgd_release_blocker_analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_release_blocker_analysis)


class BuildPgdReleaseBlockerAnalysisTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0]) if rows else ["event_id", "formula"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def make_release_dir(self, root: Path, *, matrix_status: str = "OK") -> Path:
        release_dir = root / "reports" / "pgd_magnitude" / "release" / "latest"
        self.write_csv(
            release_dir / "pgd_formula_test_matrix.csv",
            [
                {
                    "formula": "ruhl_2019",
                    "station_aggregation": "median",
                    "baseline_rank_by_mae": "1",
                    "baseline_recommended": "yes",
                    "sensitivity_win_count": "2",
                    "release_blocking_work_items": "0",
                    "test_status": "BASELINE_RECOMMENDED_REVIEW_BLOCKED",
                },
                {
                    "formula": "crowell_2016_gfast",
                    "station_aggregation": "median",
                    "baseline_rank_by_mae": "3",
                    "baseline_recommended": "no",
                    "sensitivity_win_count": "0",
                    "release_blocking_work_items": "2",
                    "test_status": "COMPARISON_NEEDS_REVIEW",
                },
            ],
        )
        self.write_json(
            release_dir / "pgd_formula_test_matrix.json",
            {
                "status": matrix_status,
                "station_aggregation": "median",
                "recommended_formula": "ruhl_2019",
                "release_readiness_status": "BLOCKED_ON_REVIEW",
            },
        )
        self.write_json(
            release_dir / "release_package_summary.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": "median",
                "ready_event_count": 13,
            },
        )
        self.write_json(
            release_dir / "pgd_release_readiness.json",
            {
                "status": "OK",
                "readiness_status": "BLOCKED_ON_REVIEW",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": "median",
                "release_blocking_count": 2,
            },
        )
        self.write_csv(
            release_dir / "residual_review_worklist.csv",
            [
                {
                    "worklist_priority": "1",
                    "event_id": "event-a",
                    "formula": "crowell_2016_gfast",
                    "worklist_status": "PENDING_REVIEW",
                    "release_blocking": "yes",
                    "blocker_status": "PENDING_REVIEW",
                    "blocker_reason": "Residual review decision is still pending.",
                    "packet_path": "residual_review_packets/event-a.md",
                    "abs_residual_mw": "1.8",
                    "suggested_review_status": "NEEDS_DATA_CHECK",
                    "suggested_review_cause": "data_quality",
                    "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING;CHECK_RELEASE_GATE",
                    "review_focus": "Inspect waveform and station filtering before release decision.",
                    "release_status": "EXCLUDED_RELEASE_SET",
                    "release_failure_reasons": "insufficient_usable_stations;low_reliability",
                    "pgd_reliability": "UNUSABLE",
                    "usable_station_count": "0",
                    "median_pgd_snr": "",
                    "median_distance_km": "120",
                    "best_formula_for_event": "ruhl_2019",
                    "best_formula_abs_residual_mw": "0.4",
                    "formula_residuals_for_event": "crowell_2016_gfast=1.8;ruhl_2019=0.4",
                    "manual_review_status": "",
                    "accepted_for_release": "",
                },
                {
                    "worklist_priority": "2",
                    "event_id": "event-b",
                    "formula": "crowell_2016_gfast",
                    "worklist_status": "PENDING_REVIEW",
                    "release_blocking": "yes",
                    "blocker_status": "PENDING_REVIEW",
                    "blocker_reason": "Residual review decision is still pending.",
                    "packet_path": "residual_review_packets/event-b.md",
                    "abs_residual_mw": "1.5",
                    "suggested_review_status": "NEEDS_FORMULA_REVIEW",
                    "suggested_review_cause": "formula_limitation",
                    "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                    "review_focus": "Compare formula residuals and decide whether formula limitation is acceptable.",
                    "release_status": "EXCLUDED_RELEASE_SET",
                    "release_failure_reasons": "insufficient_usable_stations",
                    "pgd_reliability": "LOW",
                    "usable_station_count": "1",
                    "median_pgd_snr": "3.5",
                    "median_distance_km": "180",
                    "best_formula_for_event": "ruhl_2019",
                    "best_formula_abs_residual_mw": "0.6",
                    "formula_residuals_for_event": "crowell_2016_gfast=1.5;ruhl_2019=0.6",
                    "manual_review_status": "",
                    "accepted_for_release": "",
                },
                {
                    "worklist_priority": "3",
                    "event_id": "event-c",
                    "formula": "ruhl_2019",
                    "worklist_status": "PENDING_REVIEW",
                    "release_blocking": "no",
                    "blocker_status": "",
                    "blocker_reason": "",
                    "packet_path": "residual_review_packets/event-c.md",
                    "abs_residual_mw": "1.1",
                    "suggested_review_status": "NEEDS_DATA_CHECK",
                    "suggested_review_cause": "data_quality",
                    "next_review_action": "CHECK_RELEASE_GATE",
                    "review_focus": "Nonblocking example.",
                    "release_status": "NEEDS_RESIDUAL_REVIEW",
                    "release_failure_reasons": "",
                    "pgd_reliability": "MEDIUM",
                    "usable_station_count": "4",
                    "median_pgd_snr": "5.0",
                    "median_distance_km": "90",
                    "best_formula_for_event": "melgar_2015",
                    "best_formula_abs_residual_mw": "0.3",
                    "formula_residuals_for_event": "melgar_2015=0.3;ruhl_2019=1.1",
                    "manual_review_status": "",
                    "accepted_for_release": "",
                },
            ],
        )
        return release_dir

    def test_builds_blocker_analysis_without_manual_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = build_pgd_release_blocker_analysis.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            with (release_dir / "pgd_release_blocker_analysis.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["formula_scope"] for row in rows}, {"comparison_formula"})
            self.assertEqual({row["manual_decision_written"] for row in rows}, {"no"})
            self.assertEqual(rows[0]["recommended_formula"], "ruhl_2019")
            self.assertIn("comparison formula", rows[0]["analysis_note"])
            payload = json.loads((release_dir / "pgd_release_blocker_analysis.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["recommended_formula"], "ruhl_2019")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["blocker_count"], 2)
            self.assertEqual(payload["recommended_formula_blocker_count"], 0)
            self.assertEqual(payload["comparison_formula_blocker_count"], 2)
            self.assertEqual(payload["blockers_by_formula"], {"crowell_2016_gfast": 2})
            self.assertTrue(any("comparison formula blockers" in action for action in payload["next_actions"]))
            markdown = (release_dir / "pgd_release_blocker_analysis.md").read_text(encoding="utf-8")
            self.assertIn("PGD Release Blocker Analysis", markdown)
            self.assertIn("does not write manual review decisions", markdown)
            self.assertIn("crowell_2016_gfast", markdown)

    def test_invalid_when_formula_matrix_is_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), matrix_status="INVALID")

            rc = build_pgd_release_blocker_analysis.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_release_blocker_analysis.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()
