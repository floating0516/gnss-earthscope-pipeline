import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_reviewed_release_set.py"
SPEC = importlib.util.spec_from_file_location("build_reviewed_release_set", MODULE_PATH)
build_reviewed_release_set = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_reviewed_release_set)


class BuildReviewedReleaseSetTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def release_rows(self) -> list[dict[str, str]]:
        return [
            {
                "event_id": "event-baseline",
                "event_time": "2020-01-01T00:00:00Z",
                "country": "United States",
                "region": "US",
                "place": "Baseline event",
                "formula": "ruhl_2019",
                "usgs_magnitude": "6.5",
                "estimated_mw_median": "6.4",
                "residual_mw": "-0.1",
                "abs_residual_mw": "0.1",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "4",
                "median_pgd_snr": "5.0",
                "median_distance_km": "100.0",
                "release_status": "INCLUDED_RELEASE_SET",
            },
            {
                "event_id": "event-excluded",
                "event_time": "2020-01-02T00:00:00Z",
                "country": "United States",
                "region": "US",
                "place": "Review excluded event",
                "formula": "ruhl_2019",
                "usgs_magnitude": "6.7",
                "estimated_mw_median": "6.6",
                "residual_mw": "-0.1",
                "abs_residual_mw": "0.1",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "5",
                "median_pgd_snr": "6.0",
                "median_distance_km": "90.0",
                "release_status": "INCLUDED_RELEASE_SET",
            },
            {
                "event_id": "event-pending",
                "event_time": "2020-01-03T00:00:00Z",
                "country": "United States",
                "region": "US",
                "place": "Pending review event",
                "formula": "ruhl_2019",
                "usgs_magnitude": "6.8",
                "estimated_mw_median": "6.9",
                "residual_mw": "0.1",
                "abs_residual_mw": "0.1",
                "pgd_reliability": "HIGH",
                "usable_station_count": "6",
                "median_pgd_snr": "7.0",
                "median_distance_km": "80.0",
                "release_status": "INCLUDED_RELEASE_SET",
            },
        ]

    def decision_rows(self) -> list[dict[str, str]]:
        return [
            {
                "triage_priority": "1",
                "event_id": "event-excluded",
                "formula": "ruhl_2019",
                "decision_status": "EXCLUDED_BY_REVIEW",
                "decision_issue": "",
                "next_decision_action": "KEEP_OUT_OF_REVIEWED_RELEASE_SET",
                "manual_review_status": "EXCLUDED",
                "accepted_for_release": "no",
                "manual_review_cause": "data_quality",
                "manual_review_notes": "Bad waveform.",
                "reviewer": "reviewer-a",
                "reviewed_at": "2026-07-04T01:00:00Z",
                "packet_path": "residual_review_packets/001-event-excluded-ruhl_2019.md",
                "abs_residual_mw": "1.8",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "release_status": "INCLUDED_RELEASE_SET",
                "release_failure_reasons": "",
                "release_review_reasons": "",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "5",
                "median_pgd_snr": "6.0",
                "median_distance_km": "90.0",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "1.8",
                "formula_residuals_for_event": "ruhl_2019=1.8",
            },
            {
                "triage_priority": "2",
                "event_id": "event-accepted",
                "formula": "ruhl_2019",
                "decision_status": "ACCEPTED_FOR_RELEASE",
                "decision_issue": "",
                "next_decision_action": "INCLUDE_IN_REVIEWED_RELEASE_SET",
                "manual_review_status": "ACCEPTED",
                "accepted_for_release": "yes",
                "manual_review_cause": "formula_limitation",
                "manual_review_notes": "Accept after packet review.",
                "reviewer": "reviewer-a",
                "reviewed_at": "2026-07-04T01:10:00Z",
                "packet_path": "residual_review_packets/002-event-accepted-ruhl_2019.md",
                "abs_residual_mw": "1.1",
                "triage_status_suggestion": "NEEDS_FORMULA_REVIEW",
                "triage_cause_suggestion": "formula_limitation",
                "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                "release_status": "EXCLUDED_RELEASE_SET",
                "release_failure_reasons": "residual_review_threshold",
                "release_review_reasons": "",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "3",
                "median_pgd_snr": "4.2",
                "median_distance_km": "120",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "1.1",
                "formula_residuals_for_event": "ruhl_2019=1.1",
            },
            {
                "triage_priority": "3",
                "event_id": "event-pending",
                "formula": "ruhl_2019",
                "decision_status": "PENDING_REVIEW",
                "decision_issue": "",
                "next_decision_action": "COMPLETE_REVIEW_DECISION",
                "manual_review_status": "",
                "accepted_for_release": "",
                "manual_review_cause": "",
                "manual_review_notes": "",
                "reviewer": "",
                "reviewed_at": "",
                "packet_path": "residual_review_packets/003-event-pending-ruhl_2019.md",
                "abs_residual_mw": "1.0",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "release_status": "INCLUDED_RELEASE_SET",
                "release_failure_reasons": "",
                "release_review_reasons": "",
                "pgd_reliability": "HIGH",
                "usable_station_count": "6",
                "median_pgd_snr": "7.0",
                "median_distance_km": "80.0",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "1.0",
                "formula_residuals_for_event": "ruhl_2019=1.0",
            },
        ]

    def test_builds_reviewed_release_set_from_baseline_and_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = Path(tmp) / "release" / "latest"
            self.write_csv(release_dir / "release_events.csv", self.release_rows())
            self.write_csv(release_dir / "residual_review_decision_report.csv", self.decision_rows())

            rc = build_reviewed_release_set.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            with (release_dir / "reviewed_release_events.csv").open(newline="", encoding="utf-8") as handle:
                release_rows = list(csv.DictReader(handle))
            self.assertEqual([row["event_id"] for row in release_rows], ["event-accepted", "event-baseline"])
            self.assertEqual(release_rows[0]["reviewed_release_status"], "INCLUDED_BY_REVIEW")
            self.assertEqual(release_rows[0]["reviewer"], "reviewer-a")
            self.assertEqual(release_rows[1]["reviewed_release_status"], "INCLUDED_BASELINE_RELEASE_SET")
            with (release_dir / "reviewed_release_blockers.csv").open(newline="", encoding="utf-8") as handle:
                blockers = list(csv.DictReader(handle))
            self.assertEqual([row["event_id"] for row in blockers], ["event-excluded", "event-pending"])
            self.assertEqual(blockers[0]["blocker_status"], "EXCLUDED_BY_REVIEW")
            self.assertEqual(blockers[1]["blocker_status"], "PENDING_REVIEW")
            payload = json.loads((release_dir / "reviewed_release_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["completion_status"], "INCOMPLETE")
            self.assertEqual(payload["baseline_ready_count"], 3)
            self.assertEqual(payload["reviewed_release_count"], 2)
            self.assertEqual(payload["included_from_baseline_count"], 1)
            self.assertEqual(payload["accepted_by_review_count"], 1)
            self.assertEqual(payload["excluded_by_review_count"], 1)
            self.assertEqual(payload["pending_review_count"], 1)
            self.assertEqual(payload["invalid_decision_count"], 0)
            markdown = (release_dir / "reviewed_release_summary.md").read_text(encoding="utf-8")
            self.assertIn("Reviewed Release Set", markdown)
            self.assertIn("event-pending", markdown)

    def test_invalid_decisions_make_reviewed_release_set_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = Path(tmp) / "release" / "latest"
            self.write_csv(release_dir / "release_events.csv", self.release_rows())
            decisions = self.decision_rows()
            decisions[0]["decision_status"] = "INVALID_DECISION"
            self.write_csv(release_dir / "residual_review_decision_report.csv", decisions)

            rc = build_reviewed_release_set.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "reviewed_release_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["invalid_decision_count"], 1)


if __name__ == "__main__":
    unittest.main()
