from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "manage_residual_review.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing residual review manager: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("manage_residual_review", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE_FIELDS = [
    "event_id",
    "event_time",
    "country",
    "place",
    "formula",
    "usgs_magnitude",
    "estimated_mw_median",
    "residual_mw",
    "abs_residual_mw",
    "pgd_reliability",
    "usable_station_count",
    "median_pgd_snr",
    "median_distance_km",
    "review_status",
    "suspected_cause",
    "waveform_issue",
    "station_geometry_issue",
    "magnitude_metadata_issue",
    "formula_limitation",
    "reviewer_note",
]


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(fields or rows[0])
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def base_row(event_id: str, formula: str, abs_residual: str, status: str = "UNREVIEWED") -> dict[str, str]:
    return {
        "event_id": event_id,
        "event_time": "2020-01-01T00:00:00Z",
        "country": "United States",
        "place": "Synthetic event",
        "formula": formula,
        "usgs_magnitude": "6.4",
        "estimated_mw_median": "7.1",
        "residual_mw": "0.7",
        "abs_residual_mw": abs_residual,
        "pgd_reliability": "LOW",
        "usable_station_count": "1",
        "median_pgd_snr": "3.2",
        "median_distance_km": "25.0",
        "review_status": status,
        "suspected_cause": "",
        "waveform_issue": "",
        "station_geometry_issue": "",
        "magnitude_metadata_issue": "",
        "formula_limitation": "",
        "reviewer_note": "",
    }


class ManageResidualReviewTest(unittest.TestCase):
    def test_cli_merges_annotations_and_writes_summaries(self):
        manager = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_csv = root / "residual_review.csv"
            annotations = root / "annotations.csv"
            out_csv = root / "residual_review_annotated.csv"
            out_json = root / "residual_review_summary.json"
            out_md = root / "residual_review_summary.md"
            write_rows(
                review_csv,
                [
                    base_row("event-a", "ruhl_2019", "1.4"),
                    base_row("event-b", "melgar_2015", "1.2"),
                    base_row("event-c", "crowell_2016_gfast", "1.1"),
                ],
                BASE_FIELDS,
            )
            write_rows(
                annotations,
                [
                    {
                        "event_id": "event-a",
                        "formula": "ruhl_2019",
                        "review_status": "REVIEWED",
                        "suspected_cause": "waveform",
                        "waveform_issue": "step-like transient",
                        "reviewer_note": "Keep but flag waveform.",
                    },
                    {
                        "event_id": "event-b",
                        "formula": "melgar_2015",
                        "review_status": "NEEDS_METADATA_CHECK",
                        "suspected_cause": "magnitude_metadata",
                        "magnitude_metadata_issue": "check authoritative Mw",
                        "reviewer_note": "Magnitude source needs confirmation.",
                    },
                ],
            )

            rc = manager.main(
                [
                    "--review-csv",
                    str(review_csv),
                    "--annotations",
                    str(annotations),
                    "--out-csv",
                    str(out_csv),
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                ]
            )

            self.assertEqual(rc, 0)
            with out_csv.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([(row["event_id"], row["formula"]) for row in rows], [("event-a", "ruhl_2019"), ("event-b", "melgar_2015"), ("event-c", "crowell_2016_gfast")])
            self.assertEqual(rows[0]["review_status"], "REVIEWED")
            self.assertEqual(rows[0]["waveform_issue"], "step-like transient")
            self.assertEqual(rows[1]["review_status"], "NEEDS_METADATA_CHECK")
            self.assertEqual(rows[1]["magnitude_metadata_issue"], "check authoritative Mw")
            self.assertEqual(rows[2]["review_status"], "UNREVIEWED")
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["row_count"], 3)
            self.assertEqual(payload["reviewed_count"], 2)
            self.assertEqual(payload["unreviewed_count"], 1)
            self.assertEqual(payload["status_counts"]["REVIEWED"], 1)
            self.assertEqual(payload["status_counts"]["NEEDS_METADATA_CHECK"], 1)
            self.assertEqual(payload["status_counts"]["UNREVIEWED"], 1)
            self.assertEqual(payload["suspected_cause_counts"]["waveform"], 1)
            self.assertEqual(payload["pending_review_rows"][0]["event_id"], "event-b")
            summary_md = out_md.read_text(encoding="utf-8")
            self.assertIn("Residual Review Summary", summary_md)
            self.assertIn("NEEDS_METADATA_CHECK", summary_md)
            self.assertIn("event-b", summary_md)

    def test_strict_rejects_invalid_status_and_unknown_annotation_key(self):
        manager = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_csv = root / "residual_review.csv"
            annotations = root / "annotations.csv"
            out_csv = root / "residual_review_annotated.csv"
            out_json = root / "residual_review_summary.json"
            out_md = root / "residual_review_summary.md"
            write_rows(review_csv, [base_row("event-a", "ruhl_2019", "1.4")], BASE_FIELDS)
            write_rows(
                annotations,
                [
                    {"event_id": "event-a", "formula": "ruhl_2019", "review_status": "BOGUS"},
                    {"event_id": "event-z", "formula": "melgar_2015", "review_status": "REVIEWED"},
                ],
            )

            rc = manager.main(
                [
                    "--review-csv",
                    str(review_csv),
                    "--annotations",
                    str(annotations),
                    "--out-csv",
                    str(out_csv),
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                    "--strict",
                ]
            )

            self.assertEqual(rc, 1)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual({error["code"] for error in payload["errors"]}, {"INVALID_REVIEW_STATUS", "UNKNOWN_ANNOTATION_KEY"})

    def test_cli_imports_release_annotation_starter_rows(self):
        manager = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_csv = root / "residual_review.csv"
            starter = root / "residual_review_annotations_starter.csv"
            out_csv = root / "residual_review_annotated.csv"
            out_json = root / "residual_review_summary.json"
            out_md = root / "residual_review_summary.md"
            write_rows(
                review_csv,
                [
                    base_row("event-a", "crowell_2016_gfast", "1.8"),
                    base_row("event-b", "ruhl_2019", "1.1"),
                ],
                BASE_FIELDS,
            )
            write_rows(
                starter,
                [
                    {
                        "triage_priority": "1",
                        "event_id": "event-a",
                        "formula": "crowell_2016_gfast",
                        "review_status": "UNREVIEWED",
                        "triage_status_suggestion": "NEEDS_DATA_CHECK",
                        "triage_cause_suggestion": "data_quality",
                        "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                        "manual_review_status": "EXCLUDED",
                        "manual_review_cause": "data_quality",
                        "manual_review_notes": "Zero usable stations after waveform review.",
                        "accepted_for_release": "no",
                        "reviewer": "analyst-a",
                        "reviewed_at": "2026-07-04T12:00:00Z",
                    },
                    {
                        "triage_priority": "2",
                        "event_id": "event-b",
                        "formula": "ruhl_2019",
                        "review_status": "UNREVIEWED",
                        "triage_status_suggestion": "NEEDS_FORMULA_REVIEW",
                        "triage_cause_suggestion": "formula_limitation",
                        "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                        "manual_review_status": "",
                        "manual_review_cause": "",
                        "manual_review_notes": "",
                        "accepted_for_release": "",
                        "reviewer": "",
                        "reviewed_at": "",
                    },
                ],
            )

            rc = manager.main(
                [
                    "--review-csv",
                    str(review_csv),
                    "--starter-annotations",
                    str(starter),
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
            with out_csv.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["review_status"], "EXCLUDED")
            self.assertEqual(rows[0]["suspected_cause"], "data_quality")
            self.assertEqual(rows[0]["reviewer_note"], "Zero usable stations after waveform review.")
            self.assertEqual(rows[0]["accepted_for_release"], "no")
            self.assertEqual(rows[0]["reviewer"], "analyst-a")
            self.assertEqual(rows[0]["reviewed_at"], "2026-07-04T12:00:00Z")
            self.assertEqual(rows[1]["review_status"], "UNREVIEWED")
            self.assertEqual(rows[1]["reviewer_note"], "")
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["annotation_count"], 1)
            self.assertEqual(payload["starter_annotations"], str(starter))
            self.assertEqual(payload["status_counts"]["EXCLUDED"], 1)
            self.assertEqual(payload["status_counts"]["UNREVIEWED"], 1)

    def test_strict_rejects_unknown_release_starter_key(self):
        manager = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_csv = root / "residual_review.csv"
            starter = root / "starter.csv"
            out_csv = root / "residual_review_annotated.csv"
            out_json = root / "residual_review_summary.json"
            out_md = root / "residual_review_summary.md"
            write_rows(review_csv, [base_row("event-a", "ruhl_2019", "1.4")], BASE_FIELDS)
            write_rows(
                starter,
                [
                    {
                        "event_id": "event-z",
                        "formula": "ruhl_2019",
                        "manual_review_status": "REVIEWED",
                    }
                ],
            )

            rc = manager.main(
                [
                    "--review-csv",
                    str(review_csv),
                    "--starter-annotations",
                    str(starter),
                    "--out-csv",
                    str(out_csv),
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                    "--strict",
                ]
            )

            self.assertEqual(rc, 1)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(any(error["code"] == "UNKNOWN_ANNOTATION_KEY" and error["event_id"] == "event-z" for error in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
