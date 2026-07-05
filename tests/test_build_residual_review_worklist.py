import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_residual_review_worklist.py"
SPEC = importlib.util.spec_from_file_location("build_residual_review_worklist", MODULE_PATH)
build_residual_review_worklist = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_residual_review_worklist)


class BuildResidualReviewWorklistTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def dashboard_rows(self) -> list[dict[str, str]]:
        base = {
            "manual_review_status": "",
            "manual_review_cause": "",
            "accepted_for_release": "",
            "reviewer": "",
            "reviewed_at": "",
            "release_failure_reasons": "",
            "release_review_reasons": "",
            "manual_review_notes": "",
            "triage_reason": "",
        }
        return [
            {
                **base,
                "triage_priority": "1",
                "event_id": "event-a",
                "formula": "crowell_2016_gfast",
                "review_dashboard_status": "PENDING_REVIEW",
                "packet_path": "residual_review_packets/001-event-a-crowell_2016_gfast.md",
                "abs_residual_mw": "1.8",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "release_status": "INCLUDED_RELEASE_SET",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "5",
                "median_pgd_snr": "6.0",
                "median_distance_km": "100",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "0.4",
                "formula_residuals_for_event": "crowell_2016_gfast=1.8;ruhl_2019=0.4",
            },
            {
                **base,
                "triage_priority": "2",
                "event_id": "event-b",
                "formula": "ruhl_2019",
                "review_dashboard_status": "PENDING_REVIEW",
                "packet_path": "residual_review_packets/002-event-b-ruhl_2019.md",
                "abs_residual_mw": "1.1",
                "triage_status_suggestion": "NEEDS_FORMULA_REVIEW",
                "triage_cause_suggestion": "formula_limitation",
                "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                "release_status": "EXCLUDED_RELEASE_SET",
                "release_failure_reasons": "low_reliability",
                "pgd_reliability": "LOW",
                "usable_station_count": "1",
                "median_pgd_snr": "2.1",
                "median_distance_km": "140",
                "best_formula_for_event": "melgar_2015",
                "best_formula_abs_residual_mw": "0.3",
                "formula_residuals_for_event": "melgar_2015=0.3;ruhl_2019=1.1",
            },
            {
                **base,
                "triage_priority": "3",
                "event_id": "event-c",
                "formula": "melgar_2015",
                "review_dashboard_status": "REVIEWED",
                "manual_review_status": "ACCEPTED",
                "accepted_for_release": "no",
                "packet_path": "residual_review_packets/003-event-c-melgar_2015.md",
                "abs_residual_mw": "1.4",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "release_status": "INCLUDED_RELEASE_SET",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "4",
                "median_pgd_snr": "4.0",
                "median_distance_km": "90",
            },
            {
                **base,
                "triage_priority": "4",
                "event_id": "event-d",
                "formula": "ruhl_2019",
                "review_dashboard_status": "REVIEWED",
                "manual_review_status": "ACCEPTED",
                "accepted_for_release": "yes",
                "packet_path": "residual_review_packets/004-event-d-ruhl_2019.md",
                "abs_residual_mw": "0.9",
                "triage_status_suggestion": "NEEDS_FORMULA_REVIEW",
                "triage_cause_suggestion": "formula_limitation",
                "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                "release_status": "EXCLUDED_RELEASE_SET",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "3",
                "median_pgd_snr": "3.8",
                "median_distance_km": "120",
            },
        ]

    def decision_rows(self) -> list[dict[str, str]]:
        rows = []
        for row in self.dashboard_rows():
            decision = dict(row)
            if row["event_id"] == "event-c":
                decision["decision_status"] = "INVALID_DECISION"
                decision["decision_issue"] = "ACCEPTED requires accepted_for_release=yes."
                decision["next_decision_action"] = "FIX_MANUAL_REVIEW_FIELDS"
            elif row["event_id"] == "event-d":
                decision["decision_status"] = "ACCEPTED_FOR_RELEASE"
                decision["decision_issue"] = ""
                decision["next_decision_action"] = "INCLUDE_IN_REVIEWED_RELEASE_SET"
            else:
                decision["decision_status"] = "PENDING_REVIEW"
                decision["decision_issue"] = ""
                decision["next_decision_action"] = "COMPLETE_REVIEW_DECISION"
            rows.append(decision)
        return rows

    def blocker_rows(self) -> list[dict[str, str]]:
        return [
            {
                "event_id": "event-a",
                "formula": "crowell_2016_gfast",
                "blocker_status": "PENDING_REVIEW",
                "blocker_reason": "Residual review decision is still pending.",
                "review_source": "residual_review_decision",
                "decision_status": "PENDING_REVIEW",
                "packet_path": "residual_review_packets/001-event-a-crowell_2016_gfast.md",
                "release_status": "INCLUDED_RELEASE_SET",
                "abs_residual_mw": "1.8",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "next_decision_action": "COMPLETE_REVIEW_DECISION",
            },
            {
                "event_id": "event-c",
                "formula": "melgar_2015",
                "blocker_status": "INVALID_DECISION",
                "blocker_reason": "Residual review decision is invalid and must be corrected.",
                "review_source": "residual_review_decision",
                "decision_status": "INVALID_DECISION",
                "packet_path": "residual_review_packets/003-event-c-melgar_2015.md",
                "release_status": "INCLUDED_RELEASE_SET",
                "abs_residual_mw": "1.4",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "next_decision_action": "FIX_MANUAL_REVIEW_FIELDS",
            },
        ]

    def make_release_dir(self, root: Path) -> Path:
        release_dir = root / "release" / "latest"
        self.write_csv(release_dir / "residual_review_dashboard.csv", self.dashboard_rows())
        self.write_csv(release_dir / "residual_review_decision_report.csv", self.decision_rows())
        self.write_csv(release_dir / "reviewed_release_blockers.csv", self.blocker_rows())
        return release_dir

    def test_builds_pending_and_invalid_review_worklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = build_residual_review_worklist.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            with (release_dir / "residual_review_worklist.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["event_id"] for row in rows], ["event-c", "event-a", "event-b"])
            self.assertEqual(rows[0]["worklist_status"], "INVALID_DECISION")
            self.assertEqual(rows[0]["release_blocking"], "yes")
            self.assertEqual(rows[0]["suggested_review_status"], "FIX_INVALID_DECISION")
            self.assertEqual(rows[1]["suggested_review_status"], "NEEDS_DATA_CHECK")
            self.assertEqual(rows[1]["suggested_review_cause"], "data_quality")
            self.assertEqual(rows[1]["suggested_accepted_for_release"], "")
            self.assertEqual(rows[1]["release_blocking"], "yes")
            self.assertIn("waveform", rows[1]["review_focus"].lower())
            self.assertEqual(rows[2]["release_blocking"], "no")
            self.assertIn("formula", rows[2]["review_focus"].lower())
            payload = json.loads((release_dir / "residual_review_worklist.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["completion_status"], "INCOMPLETE")
            self.assertEqual(payload["work_item_count"], 3)
            self.assertEqual(payload["pending_count"], 2)
            self.assertEqual(payload["invalid_count"], 1)
            self.assertEqual(payload["release_blocking_count"], 2)
            markdown = (release_dir / "residual_review_worklist.md").read_text(encoding="utf-8")
            self.assertIn("Residual Review Worklist", markdown)
            self.assertIn("event-a", markdown)
            self.assertIn("release-blocking", markdown)

    def test_returns_ok_when_no_pending_or_invalid_decisions_remain(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = Path(tmp) / "release" / "latest"
            accepted = [row for row in self.decision_rows() if row["event_id"] == "event-d"]
            self.write_csv(release_dir / "residual_review_dashboard.csv", [self.dashboard_rows()[-1]])
            self.write_csv(release_dir / "residual_review_decision_report.csv", accepted)
            self.write_csv(release_dir / "reviewed_release_blockers.csv", self.blocker_rows()[:1])

            rc = build_residual_review_worklist.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "residual_review_worklist.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["completion_status"], "COMPLETE")
            self.assertEqual(payload["work_item_count"], 0)


if __name__ == "__main__":
    unittest.main()
