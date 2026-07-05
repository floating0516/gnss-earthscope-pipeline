from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pgd_magnitude" / "build_release_blocking_review_starter.py"
MANAGER_PATH = ROOT / "scripts" / "pgd_magnitude" / "manage_residual_review.py"


def load_module(path: Path, name: str):
    if not path.exists():
        raise AssertionError(f"missing module: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class BuildReleaseBlockingReviewStarterTest(unittest.TestCase):
    def worklist_rows(self) -> list[dict[str, str]]:
        base = {
            "decision_issue": "",
            "blocker_status": "",
            "blocker_reason": "",
            "release_failure_reasons": "",
            "release_review_reasons": "",
            "manual_review_status": "",
            "manual_review_cause": "",
            "accepted_for_release": "",
            "reviewer": "",
            "reviewed_at": "",
        }
        return [
            {
                **base,
                "worklist_priority": "1",
                "event_id": "event-invalid",
                "formula": "melgar_2015",
                "worklist_status": "INVALID_DECISION",
                "decision_issue": "ACCEPTED requires accepted_for_release=yes.",
                "release_blocking": "yes",
                "blocker_status": "INVALID_DECISION",
                "blocker_reason": "Residual review decision is invalid and must be corrected.",
                "packet_path": "residual_review_packets/001-event-invalid-melgar_2015.md",
                "abs_residual_mw": "1.4",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "suggested_review_status": "FIX_INVALID_DECISION",
                "suggested_review_cause": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "next_decision_action": "FIX_MANUAL_REVIEW_FIELDS",
                "review_focus": "Fix inconsistent manual decision fields before scientific release review.",
                "release_status": "INCLUDED_RELEASE_SET",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "4",
                "median_pgd_snr": "4.0",
                "median_distance_km": "90",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "0.5",
                "formula_residuals_for_event": "melgar_2015=1.4;ruhl_2019=0.5",
            },
            {
                **base,
                "worklist_priority": "2",
                "event_id": "event-blocking",
                "formula": "crowell_2016_gfast",
                "worklist_status": "PENDING_REVIEW",
                "release_blocking": "yes",
                "blocker_status": "PENDING_REVIEW",
                "blocker_reason": "Residual review decision is still pending.",
                "packet_path": "residual_review_packets/002-event-blocking-crowell_2016_gfast.md",
                "abs_residual_mw": "1.8",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "suggested_review_status": "NEEDS_DATA_CHECK",
                "suggested_review_cause": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "next_decision_action": "COMPLETE_REVIEW_DECISION",
                "review_focus": "Inspect waveform and station filtering before release decision.",
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
                "worklist_priority": "3",
                "event_id": "event-nonblocking",
                "formula": "ruhl_2019",
                "worklist_status": "PENDING_REVIEW",
                "release_blocking": "no",
                "packet_path": "residual_review_packets/003-event-nonblocking-ruhl_2019.md",
                "abs_residual_mw": "1.1",
                "triage_status_suggestion": "NEEDS_FORMULA_REVIEW",
                "triage_cause_suggestion": "formula_limitation",
                "suggested_review_status": "NEEDS_FORMULA_REVIEW",
                "suggested_review_cause": "formula_limitation",
                "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                "next_decision_action": "COMPLETE_REVIEW_DECISION",
                "review_focus": "Compare formula residuals and decide whether formula limitation is acceptable.",
                "release_status": "EXCLUDED_RELEASE_SET",
                "pgd_reliability": "LOW",
                "usable_station_count": "1",
                "median_pgd_snr": "2.1",
                "median_distance_km": "140",
                "best_formula_for_event": "melgar_2015",
                "best_formula_abs_residual_mw": "0.3",
                "formula_residuals_for_event": "melgar_2015=0.3;ruhl_2019=1.1",
            },
        ]

    def make_release_dir(self, root: Path) -> Path:
        release_dir = root / "release" / "latest"
        write_csv(release_dir / "residual_review_worklist.csv", self.worklist_rows())
        return release_dir

    def test_builds_release_blocking_starter_with_blank_manual_fields(self):
        starter = load_module(MODULE_PATH, "build_release_blocking_review_starter")
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = starter.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            rows = read_csv(release_dir / "release_blocking_review_starter.csv")
            self.assertEqual([row["event_id"] for row in rows], ["event-invalid", "event-blocking"])
            self.assertEqual({row["release_blocking"] for row in rows}, {"yes"})
            self.assertEqual(rows[0]["starter_priority"], "1")
            self.assertEqual(rows[0]["suggested_review_status"], "FIX_INVALID_DECISION")
            self.assertEqual(rows[1]["suggested_review_status"], "NEEDS_DATA_CHECK")
            for field in ["manual_review_status", "manual_review_cause", "manual_review_notes", "accepted_for_release", "reviewer", "reviewed_at"]:
                with self.subTest(field=field):
                    self.assertIn(field, rows[0])
                    self.assertEqual(rows[0][field], "")
            payload = json.loads((release_dir / "release_blocking_review_starter.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["mode"], "release_blocking")
            self.assertEqual(payload["worklist_input_count"], 3)
            self.assertEqual(payload["starter_row_count"], 2)
            self.assertEqual(payload["release_blocking_count"], 2)
            self.assertEqual(payload["suggested_review_status_counts"]["FIX_INVALID_DECISION"], 1)
            markdown = (release_dir / "release_blocking_review_starter.md").read_text(encoding="utf-8")
            self.assertIn("Release-Blocking Review Starter", markdown)
            self.assertIn("event-blocking", markdown)
            self.assertIn("manual fields are blank", markdown)

    def test_can_include_nonblocking_rows_when_requested(self):
        starter = load_module(MODULE_PATH, "build_release_blocking_review_starter")
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = starter.main(["--release-dir", str(release_dir), "--include-nonblocking"])

            self.assertEqual(rc, 0)
            rows = read_csv(release_dir / "release_blocking_review_starter.csv")
            self.assertEqual([row["event_id"] for row in rows], ["event-invalid", "event-blocking", "event-nonblocking"])
            payload = json.loads((release_dir / "release_blocking_review_starter.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "all_worklist_rows")
            self.assertEqual(payload["nonblocking_count"], 1)

    def test_output_can_be_used_as_completed_starter_annotations(self):
        starter = load_module(MODULE_PATH, "build_release_blocking_review_starter")
        manager = load_module(MANAGER_PATH, "manage_residual_review_for_release_blocking_starter_test")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release_dir = self.make_release_dir(root)
            review_csv = root / "residual_review.csv"
            write_csv(
                review_csv,
                [
                    {
                        "event_id": "event-invalid",
                        "formula": "melgar_2015",
                        "abs_residual_mw": "1.4",
                        "review_status": "UNREVIEWED",
                        "suspected_cause": "",
                    },
                    {
                        "event_id": "event-blocking",
                        "formula": "crowell_2016_gfast",
                        "abs_residual_mw": "1.8",
                        "review_status": "UNREVIEWED",
                        "suspected_cause": "",
                    },
                ],
            )

            self.assertEqual(starter.main(["--release-dir", str(release_dir)]), 0)
            starter_csv = release_dir / "release_blocking_review_starter.csv"
            rows = read_csv(starter_csv)
            rows[0]["manual_review_status"] = "EXCLUDED"
            rows[0]["manual_review_cause"] = "data_quality"
            rows[0]["manual_review_notes"] = "Reject after packet review."
            rows[0]["accepted_for_release"] = "no"
            rows[0]["reviewer"] = "analyst-a"
            rows[0]["reviewed_at"] = "2026-07-04T12:00:00Z"
            write_csv(starter_csv, rows)

            out_csv = root / "residual_review_annotated.csv"
            out_json = root / "residual_review_summary.json"
            out_md = root / "residual_review_summary.md"
            rc = manager.main(
                [
                    "--review-csv",
                    str(review_csv),
                    "--starter-annotations",
                    str(starter_csv),
                    "--out-csv",
                    str(out_csv),
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                    "--strict",
                ]
            )

            self.assertEqual(rc, 0)
            merged = read_csv(out_csv)
            self.assertEqual(merged[0]["review_status"], "EXCLUDED")
            self.assertEqual(merged[0]["suspected_cause"], "data_quality")
            self.assertEqual(merged[0]["reviewer_note"], "Reject after packet review.")
            self.assertEqual(merged[1]["review_status"], "UNREVIEWED")
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["annotation_count"], 1)
            self.assertEqual(payload["starter_row_count"], 2)


if __name__ == "__main__":
    unittest.main()
