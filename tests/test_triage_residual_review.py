from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "triage_residual_review.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing residual review triage script: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("triage_residual_review", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
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


def review_row(
    event_id: str,
    formula: str,
    *,
    abs_residual: str,
    status: str = "UNREVIEWED",
    usable_stations: str = "1",
    median_snr: str = "4.2",
    reliability: str = "LOW",
) -> dict[str, str]:
    return {
        "event_id": event_id,
        "event_time": "2020-01-01T00:00:00Z",
        "country": "United States",
        "place": "Synthetic event",
        "formula": formula,
        "usgs_magnitude": "6.4",
        "estimated_mw_median": "7.1",
        "residual_mw": abs_residual,
        "abs_residual_mw": abs_residual,
        "pgd_reliability": reliability,
        "usable_station_count": usable_stations,
        "median_pgd_snr": median_snr,
        "median_distance_km": "25.0",
        "review_status": status,
        "suspected_cause": "",
        "waveform_issue": "",
        "station_geometry_issue": "",
        "magnitude_metadata_issue": "",
        "formula_limitation": "",
        "reviewer_note": "",
    }


class TriageResidualReviewTest(unittest.TestCase):
    def test_cli_writes_triage_suggestions_without_mutating_manual_review_status(self):
        triage = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_csv = root / "residual_review_annotated.csv"
            events_csv = root / "events.csv"
            release_set_csv = root / "release_set.csv"
            out_csv = root / "residual_review_triage.csv"
            out_json = root / "residual_review_triage_summary.json"
            out_md = root / "residual_review_triage.md"
            write_rows(
                review_csv,
                [
                    review_row(
                        "event-a",
                        "crowell_2016_gfast",
                        abs_residual="1.5",
                        usable_stations="0",
                        median_snr="",
                        reliability="UNUSABLE",
                    ),
                    review_row("event-b", "melgar_2015", abs_residual="1.1", usable_stations="3", median_snr="5.0"),
                    review_row("event-c", "ruhl_2019", abs_residual="0.2", status="REVIEWED"),
                ],
            )
            write_rows(
                events_csv,
                [
                    {"event_id": "event-a", "formula": "melgar_2015", "abs_residual_mw": "0.4"},
                    {"event_id": "event-a", "formula": "crowell_2016_gfast", "abs_residual_mw": "1.5"},
                    {"event_id": "event-a", "formula": "ruhl_2019", "abs_residual_mw": "0.6"},
                    {"event_id": "event-b", "formula": "melgar_2015", "abs_residual_mw": "1.1"},
                    {"event_id": "event-b", "formula": "ruhl_2019", "abs_residual_mw": "0.5"},
                    {"event_id": "event-c", "formula": "ruhl_2019", "abs_residual_mw": "0.2"},
                ],
            )
            write_rows(
                release_set_csv,
                [
                    {
                        "event_id": "event-a",
                        "formula": "ruhl_2019",
                        "release_status": "EXCLUDED_RELEASE_SET",
                        "release_failure_reasons": "insufficient_usable_stations;low_reliability",
                        "release_review_reasons": "",
                    },
                    {
                        "event_id": "event-b",
                        "formula": "ruhl_2019",
                        "release_status": "NEEDS_RESIDUAL_REVIEW",
                        "release_failure_reasons": "",
                        "release_review_reasons": "large_residual",
                    },
                ],
            )

            rc = triage.main(
                [
                    "--review-csv",
                    str(review_csv),
                    "--events-csv",
                    str(events_csv),
                    "--release-set-csv",
                    str(release_set_csv),
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
            self.assertEqual([(row["event_id"], row["formula"]) for row in rows], [("event-a", "crowell_2016_gfast"), ("event-b", "melgar_2015"), ("event-c", "ruhl_2019")])
            first = rows[0]
            self.assertEqual(first["review_status"], "UNREVIEWED")
            self.assertEqual(first["triage_priority"], "1")
            self.assertEqual(first["triage_status_suggestion"], "NEEDS_DATA_CHECK")
            self.assertEqual(first["triage_cause_suggestion"], "data_quality")
            self.assertIn("zero usable stations", first["triage_reason"])
            self.assertIn("release gate", first["triage_reason"])
            self.assertEqual(first["best_formula_for_event"], "melgar_2015")
            self.assertEqual(first["formula_limitation_suggested"], "yes")
            self.assertEqual(first["release_status"], "EXCLUDED_RELEASE_SET")
            self.assertIn("CHECK_WAVEFORM_AND_STATION_FILTERING", first["next_review_action"])

            second = rows[1]
            self.assertEqual(second["review_status"], "UNREVIEWED")
            self.assertEqual(second["triage_status_suggestion"], "NEEDS_FORMULA_REVIEW")
            self.assertEqual(second["triage_cause_suggestion"], "formula_limitation")
            self.assertEqual(second["best_formula_for_event"], "ruhl_2019")
            self.assertIn("COMPARE_FORMULA_RESIDUALS", second["next_review_action"])

            third = rows[2]
            self.assertEqual(third["review_status"], "REVIEWED")
            self.assertEqual(third["triage_status_suggestion"], "REVIEWED")
            self.assertEqual(third["triage_cause_suggestion"], "already_reviewed")

            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["row_count"], 3)
            self.assertEqual(payload["suggested_status_counts"]["NEEDS_DATA_CHECK"], 1)
            self.assertEqual(payload["suggested_status_counts"]["NEEDS_FORMULA_REVIEW"], 1)
            self.assertEqual(payload["suggested_status_counts"]["REVIEWED"], 1)
            self.assertEqual(payload["top_priority_rows"][0]["event_id"], "event-a")
            report = out_md.read_text(encoding="utf-8")
            self.assertIn("Residual Review Triage", report)
            self.assertIn("NEEDS_DATA_CHECK", report)
            self.assertIn("event-a", report)


if __name__ == "__main__":
    unittest.main()
