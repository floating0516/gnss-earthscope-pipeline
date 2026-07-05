import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_review_briefing.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_review_briefing", MODULE_PATH)
build_pgd_review_briefing = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_review_briefing)


class BuildPgdReviewBriefingTest(unittest.TestCase):
    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0]) if rows else ["event_id", "formula"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_release_dir(self, root: Path, *, station_aggregation: str = "median") -> Path:
        release_dir = root / "reports" / "pgd_magnitude" / "release" / "latest"
        self.write_json(
            release_dir / "pgd_baseline_science_narrative.json",
            {
                "status": "OK",
                "baseline_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "station_aggregation_method": station_aggregation,
                "formula_comparison_scope": "formula_only",
                "narrative_status": "READY_WITH_CAVEATS",
                "pgd_event_count": 94,
                "ready_event_count": 13,
                "reviewed_release_count": 12,
                "comparison_formula_blocker_count": 2,
                "recommended_formula_blocker_count": 0,
                "manual_decisions_written": 0,
                "requires_sensitivity_caveat": True,
                "sensitivity_switch_scenarios": ["horizontal", "calibrated"],
                "formulas": ["crowell_2016_gfast", "melgar_2015", "ruhl_2019"],
            },
        )
        self.write_json(
            release_dir / "pgd_comparison_formula_review_packet_summary.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "release_readiness_status": "BLOCKED_ON_REVIEW",
                "row_count": 2,
                "comparison_formula_blocker_count": 2,
                "packet_exists_count": 2,
                "missing_packet_count": 0,
                "manual_decisions_written": 0,
                "blockers_by_formula": {"crowell_2016_gfast": 2},
                "suggested_review_status_counts": {"NEEDS_DATA_CHECK": 1, "NEEDS_FORMULA_REVIEW": 1},
                "suggested_review_cause_counts": {"data_quality": 1, "formula_limitation": 1},
                "manual_decision_state_counts": {"blank": 2},
            },
        )
        self.write_csv(
            release_dir / "pgd_comparison_formula_review_packet_summary.csv",
            [
                {
                    "review_priority": "1",
                    "event_id": "event-a",
                    "formula": "crowell_2016_gfast",
                    "recommended_formula": "ruhl_2019",
                    "station_aggregation": station_aggregation,
                    "formula_scope": "comparison_formula",
                    "packet_path": "residual_review_packets/001-event-a-crowell_2016_gfast.md",
                    "packet_exists": "yes",
                    "abs_residual_mw": "1.8",
                    "suggested_review_status": "NEEDS_DATA_CHECK",
                    "suggested_review_cause": "data_quality",
                    "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                    "manual_decision_state": "blank",
                    "manual_review_status": "",
                    "accepted_for_release": "",
                },
                {
                    "review_priority": "2",
                    "event_id": "event-b",
                    "formula": "crowell_2016_gfast",
                    "recommended_formula": "ruhl_2019",
                    "station_aggregation": station_aggregation,
                    "formula_scope": "comparison_formula",
                    "packet_path": "residual_review_packets/002-event-b-crowell_2016_gfast.md",
                    "packet_exists": "yes",
                    "abs_residual_mw": "1.3",
                    "suggested_review_status": "NEEDS_FORMULA_REVIEW",
                    "suggested_review_cause": "formula_limitation",
                    "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                    "manual_decision_state": "blank",
                    "manual_review_status": "",
                    "accepted_for_release": "",
                },
            ],
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
                "release_blocking_count": 2,
                "starter_row_count": 2,
                "work_item_count": 20,
                "release_blocking_review_starter": str(release_dir / "release_blocking_review_starter.csv"),
                "requires_sensitivity_caveat": True,
            },
        )
        self.write_json(
            release_dir / "pgd_recommended_formula_release_status.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "recommended_formula_release_status": "READY_FOR_BASELINE_NARRATIVE",
                "overall_release_readiness_status": "BLOCKED_ON_REVIEW",
                "recommended_formula_blocker_count": 0,
                "comparison_formula_blocker_count": 2,
                "manual_decisions_written": 0,
                "requires_sensitivity_caveat": True,
            },
        )
        self.write_json(
            release_dir / "release_blocking_review_starter.json",
            {
                "status": "OK",
                "mode": "release_blocking",
                "starter_row_count": 2,
                "release_blocking_count": 2,
                "out_csv": str(release_dir / "release_blocking_review_starter.csv"),
            },
        )
        (release_dir / "release_blocking_review_starter.csv").write_text("event_id,formula\n", encoding="utf-8")
        return release_dir

    def test_builds_read_only_review_briefing(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = build_pgd_review_briefing.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "pgd_review_briefing.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["briefing_status"], "BLOCKED_ON_REVIEW")
            self.assertEqual(payload["baseline_formula"], "ruhl_2019")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["formula_comparison_scope"], "formula_only")
            self.assertEqual(payload["comparison_formula_blocker_count"], 2)
            self.assertEqual(payload["manual_decisions_written"], 0)
            self.assertEqual(payload["review_packet_count"], 2)
            self.assertEqual(payload["review_files"]["starter_csv"], str(release_dir / "release_blocking_review_starter.csv"))
            self.assertTrue(any("validate_release_starter_annotations.py" in command for command in payload["import_commands"]))
            self.assertTrue(any("run_pgd_science_bundle.py" in command for command in payload["import_commands"]))
            self.assertIn("NEEDS_DATA_CHECK", payload["allowed_manual_review_statuses"])
            self.assertIn("ACCEPTED", payload["allowed_manual_review_statuses"])
            self.assertEqual(payload["review_packets"][0]["packet_path"], "residual_review_packets/001-event-a-crowell_2016_gfast.md")

            markdown = (release_dir / "pgd_review_briefing.md").read_text(encoding="utf-8")
            self.assertIn("PGD Review Briefing", markdown)
            self.assertIn("ruhl_2019", markdown)
            self.assertIn("Station aggregation: `median`", markdown)
            self.assertIn("crowell_2016_gfast", markdown)
            self.assertIn("release_blocking_review_starter.csv", markdown)
            self.assertIn("does not write manual decisions", markdown)

    def test_rejects_non_median_release_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), station_aggregation="mean")

            rc = build_pgd_review_briefing.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_review_briefing.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(any(error["code"] == "INVALID_STATION_AGGREGATION" for error in payload["errors"]))

    def test_reports_missing_required_products(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = Path(tmp) / "release" / "latest"
            release_dir.mkdir(parents=True)

            rc = build_pgd_review_briefing.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_review_briefing.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()
