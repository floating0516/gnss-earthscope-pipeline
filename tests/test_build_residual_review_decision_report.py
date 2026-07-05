import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_residual_review_decision_report.py"
SPEC = importlib.util.spec_from_file_location("build_residual_review_decision_report", MODULE_PATH)
build_residual_review_decision_report = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_residual_review_decision_report)


class BuildResidualReviewDecisionReportTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def dashboard_rows(self) -> list[dict[str, str]]:
        return [
            {
                "triage_priority": "1",
                "event_id": "event-accepted",
                "formula": "ruhl_2019",
                "review_dashboard_status": "REVIEWED",
                "manual_review_status": "ACCEPTED",
                "manual_review_cause": "formula_limitation",
                "accepted_for_release": "yes",
                "reviewer": "reviewer-a",
                "reviewed_at": "2026-07-04T01:00:00Z",
                "packet_path": "residual_review_packets/001-event-accepted-ruhl_2019.md",
                "abs_residual_mw": "1.2",
                "triage_status_suggestion": "NEEDS_FORMULA_REVIEW",
                "triage_cause_suggestion": "formula_limitation",
                "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                "release_status": "INCLUDED_RELEASE_SET",
                "release_failure_reasons": "",
                "release_review_reasons": "",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "3",
                "median_pgd_snr": "4.2",
                "median_distance_km": "120",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "1.2",
                "formula_residuals_for_event": "ruhl_2019=1.2",
                "manual_review_notes": "Accept after formula comparison.",
                "triage_reason": "formula residual exceeds threshold",
            },
            {
                "triage_priority": "2",
                "event_id": "event-excluded",
                "formula": "crowell_2016_gfast",
                "review_dashboard_status": "REVIEWED",
                "manual_review_status": "EXCLUDED",
                "manual_review_cause": "data_quality",
                "accepted_for_release": "no",
                "reviewer": "reviewer-a",
                "reviewed_at": "2026-07-04T01:05:00Z",
                "packet_path": "residual_review_packets/002-event-excluded-crowell_2016_gfast.md",
                "abs_residual_mw": "1.8",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "release_status": "EXCLUDED_RELEASE_SET",
                "release_failure_reasons": "insufficient_usable_stations",
                "release_review_reasons": "",
                "pgd_reliability": "UNUSABLE",
                "usable_station_count": "0",
                "median_pgd_snr": "",
                "median_distance_km": "",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "0.4",
                "formula_residuals_for_event": "crowell_2016_gfast=1.8;ruhl_2019=0.4",
                "manual_review_notes": "Exclude: no usable stations.",
                "triage_reason": "zero usable stations",
            },
            {
                "triage_priority": "3",
                "event_id": "event-pending",
                "formula": "melgar_2015",
                "review_dashboard_status": "PENDING_REVIEW",
                "manual_review_status": "",
                "manual_review_cause": "",
                "accepted_for_release": "",
                "reviewer": "",
                "reviewed_at": "",
                "packet_path": "residual_review_packets/003-event-pending-melgar_2015.md",
                "abs_residual_mw": "1.1",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "release_status": "EXCLUDED_RELEASE_SET",
                "release_failure_reasons": "low_reliability",
                "release_review_reasons": "",
                "pgd_reliability": "LOW",
                "usable_station_count": "1",
                "median_pgd_snr": "2.1",
                "median_distance_km": "90",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "0.5",
                "formula_residuals_for_event": "melgar_2015=1.1;ruhl_2019=0.5",
                "manual_review_notes": "",
                "triage_reason": "low reliability",
            },
        ]

    def test_builds_decision_report_from_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = Path(tmp) / "release" / "latest"
            self.write_csv(release_dir / "residual_review_dashboard.csv", self.dashboard_rows())

            rc = build_residual_review_decision_report.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            with (release_dir / "residual_review_decision_report.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["decision_status"] for row in rows], ["ACCEPTED_FOR_RELEASE", "EXCLUDED_BY_REVIEW", "PENDING_REVIEW"])
            self.assertEqual(rows[0]["decision_issue"], "")
            self.assertEqual(rows[1]["manual_review_cause"], "data_quality")
            self.assertEqual(rows[2]["next_decision_action"], "COMPLETE_REVIEW_DECISION")
            payload = json.loads((release_dir / "residual_review_decision_report.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["completion_status"], "INCOMPLETE")
            self.assertEqual(payload["row_count"], 3)
            self.assertEqual(payload["accepted_count"], 1)
            self.assertEqual(payload["excluded_count"], 1)
            self.assertEqual(payload["pending_count"], 1)
            self.assertEqual(payload["invalid_count"], 0)
            self.assertEqual(payload["decision_status_counts"], {"ACCEPTED_FOR_RELEASE": 1, "EXCLUDED_BY_REVIEW": 1, "PENDING_REVIEW": 1})
            markdown = (release_dir / "residual_review_decision_report.md").read_text(encoding="utf-8")
            self.assertIn("Residual Review Decision Report", markdown)
            self.assertIn("event-pending", markdown)

    def test_rejects_conflicting_manual_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = Path(tmp) / "release" / "latest"
            rows = self.dashboard_rows()
            rows[0]["manual_review_status"] = "ACCEPTED"
            rows[0]["accepted_for_release"] = "no"
            self.write_csv(release_dir / "residual_review_dashboard.csv", rows)

            rc = build_residual_review_decision_report.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "residual_review_decision_report.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["invalid_count"], 1)
            self.assertEqual(payload["errors"][0]["code"], "CONFLICTING_RELEASE_DECISION")


if __name__ == "__main__":
    unittest.main()
