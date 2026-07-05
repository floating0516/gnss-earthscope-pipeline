import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_residual_review_dashboard.py"
SPEC = importlib.util.spec_from_file_location("build_residual_review_dashboard", MODULE_PATH)
build_residual_review_dashboard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_residual_review_dashboard)


class BuildResidualReviewDashboardTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_release_dir(self, root: Path) -> Path:
        release_dir = root / "release" / "latest"
        evidence_rows = [
            {
                "triage_priority": "1",
                "event_id": "event-a",
                "formula": "crowell_2016_gfast",
                "review_status": "UNREVIEWED",
                "abs_residual_mw": "1.8",
                "pgd_reliability": "UNUSABLE",
                "usable_station_count": "0",
                "median_pgd_snr": "",
                "median_distance_km": "",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "triage_reason": "zero usable stations",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "0.4",
                "formula_residuals_for_event": "crowell_2016_gfast=1.8;ruhl_2019=0.4",
                "formula_limitation_suggested": "yes",
                "release_status": "EXCLUDED_RELEASE_SET",
                "release_failure_reasons": "insufficient_usable_stations;low_reliability",
                "release_review_reasons": "",
            },
            {
                "triage_priority": "2",
                "event_id": "event-b",
                "formula": "ruhl_2019",
                "review_status": "UNREVIEWED",
                "abs_residual_mw": "1.1",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "3",
                "median_pgd_snr": "4.2",
                "median_distance_km": "120",
                "triage_status_suggestion": "NEEDS_FORMULA_REVIEW",
                "triage_cause_suggestion": "formula_limitation",
                "triage_reason": "formula residual exceeds threshold",
                "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                "best_formula_for_event": "melgar_2015",
                "best_formula_abs_residual_mw": "0.3",
                "formula_residuals_for_event": "melgar_2015=0.3;ruhl_2019=1.1",
                "formula_limitation_suggested": "yes",
                "release_status": "NEEDS_RESIDUAL_REVIEW",
                "release_failure_reasons": "",
                "release_review_reasons": "residual_review_threshold",
            },
        ]
        packet_rows = [
            {
                "triage_priority": "1",
                "event_id": "event-a",
                "formula": "crowell_2016_gfast",
                "packet_path": "residual_review_packets/001-event-a-crowell_2016_gfast.md",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "abs_residual_mw": "1.8",
                "release_status": "EXCLUDED_RELEASE_SET",
                "manual_review_status": "",
            },
            {
                "triage_priority": "2",
                "event_id": "event-b",
                "formula": "ruhl_2019",
                "packet_path": "residual_review_packets/002-event-b-ruhl_2019.md",
                "triage_status_suggestion": "NEEDS_FORMULA_REVIEW",
                "triage_cause_suggestion": "formula_limitation",
                "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                "abs_residual_mw": "1.1",
                "release_status": "NEEDS_RESIDUAL_REVIEW",
                "manual_review_status": "",
            },
        ]
        starter_rows = [
            {
                **evidence_rows[0],
                "manual_review_status": "EXCLUDED",
                "manual_review_cause": "data_quality",
                "manual_review_notes": "No usable stations after PGD filters.",
                "accepted_for_release": "no",
                "reviewer": "reviewer-a",
                "reviewed_at": "2026-07-04T00:00:00Z",
            },
            {
                **evidence_rows[1],
                "manual_review_status": "",
                "manual_review_cause": "",
                "manual_review_notes": "",
                "accepted_for_release": "",
                "reviewer": "",
                "reviewed_at": "",
            },
        ]
        self.write_csv(release_dir / "residual_review_evidence.csv", evidence_rows)
        self.write_csv(release_dir / "residual_review_packet_index.csv", packet_rows)
        self.write_csv(release_dir / "residual_review_annotations_starter.csv", starter_rows)
        return release_dir

    def test_builds_dashboard_from_release_review_products(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))
            out_csv = release_dir / "residual_review_dashboard.csv"
            out_json = release_dir / "residual_review_dashboard.json"
            out_md = release_dir / "residual_review_dashboard.md"

            rc = build_residual_review_dashboard.main(
                [
                    "--release-dir",
                    str(release_dir),
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
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["review_dashboard_status"], "REVIEWED")
            self.assertEqual(rows[0]["manual_review_status"], "EXCLUDED")
            self.assertEqual(rows[0]["accepted_for_release"], "no")
            self.assertEqual(rows[0]["packet_path"], "residual_review_packets/001-event-a-crowell_2016_gfast.md")
            self.assertEqual(rows[1]["review_dashboard_status"], "PENDING_REVIEW")
            self.assertEqual(rows[1]["manual_review_status"], "")
            self.assertEqual(rows[1]["triage_status_suggestion"], "NEEDS_FORMULA_REVIEW")
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["row_count"], 2)
            self.assertEqual(payload["reviewed_count"], 1)
            self.assertEqual(payload["pending_count"], 1)
            self.assertEqual(payload["manual_status_counts"], {"EXCLUDED": 1, "UNFILLED": 1})
            self.assertEqual(payload["triage_status_counts"], {"NEEDS_DATA_CHECK": 1, "NEEDS_FORMULA_REVIEW": 1})
            self.assertEqual(payload["accepted_for_release_counts"], {"no": 1, "unfilled": 1})
            markdown = out_md.read_text(encoding="utf-8")
            self.assertIn("Residual Review Dashboard", markdown)
            self.assertIn("PENDING_REVIEW", markdown)
            self.assertIn("event-b", markdown)

    def test_fails_when_packet_index_is_missing_an_evidence_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))
            rows = []
            with (release_dir / "residual_review_packet_index.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))[:1]
            self.write_csv(release_dir / "residual_review_packet_index.csv", rows)

            rc = build_residual_review_dashboard.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "residual_review_dashboard.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["errors"][0]["code"], "MISSING_PACKET_INDEX_ROW")


if __name__ == "__main__":
    unittest.main()
