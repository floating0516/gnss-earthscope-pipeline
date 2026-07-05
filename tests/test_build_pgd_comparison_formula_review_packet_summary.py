import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_comparison_formula_review_packet_summary.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_comparison_formula_review_packet_summary", MODULE_PATH)
build_pgd_comparison_formula_review_packet_summary = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_comparison_formula_review_packet_summary)


class BuildPgdComparisonFormulaReviewPacketSummaryTest(unittest.TestCase):
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

    def make_release_dir(self, root: Path, *, station_aggregation: str = "median", create_packet: bool = True) -> Path:
        release_dir = root / "release"
        guide_rows = [
            {
                "guide_priority": "1",
                "event_id": "event-a",
                "formula": "crowell_2016_gfast",
                "recommended_formula": "ruhl_2019",
                "formula_scope": "comparison_formula",
                "packet_path": "residual_review_packets/001-event-a-crowell_2016_gfast.md",
                "allowed_terminal_statuses": "REVIEWED;ACCEPTED;EXCLUDED",
                "accepted_for_release_rule": "ACCEPTED=>yes;EXCLUDED=>no;REVIEWED=>yes_or_no_with_notes",
                "suggested_review_status": "NEEDS_DATA_CHECK",
                "suggested_review_cause": "data_quality",
                "pre_decision_checks": "CHECK_WAVEFORM_AND_STATION_FILTERING;CHECK_FORMULA_CONTEXT",
                "review_focus": "Inspect waveform and station filtering before release decision.",
                "release_status": "EXCLUDED_RELEASE_SET",
                "release_failure_reasons": "insufficient_usable_stations;low_reliability",
                "formula_residuals_for_event": "crowell_2016_gfast=1.8;ruhl_2019=0.4",
                "manual_decision_written": "no",
                "manual_review_status": "",
                "manual_review_cause": "",
                "manual_review_notes": "",
                "accepted_for_release": "",
                "reviewer": "",
                "reviewed_at": "",
            },
            {
                "guide_priority": "2",
                "event_id": "event-b",
                "formula": "ruhl_2019",
                "recommended_formula": "ruhl_2019",
                "formula_scope": "recommended_formula",
                "packet_path": "residual_review_packets/002-event-b-ruhl_2019.md",
                "allowed_terminal_statuses": "REVIEWED;ACCEPTED;EXCLUDED",
                "accepted_for_release_rule": "ACCEPTED=>yes;EXCLUDED=>no;REVIEWED=>yes_or_no_with_notes",
                "suggested_review_status": "NEEDS_FORMULA_REVIEW",
                "suggested_review_cause": "formula_limitation",
                "pre_decision_checks": "CHECK_FORMULA_CONTEXT",
                "review_focus": "Recommended formula blocker example.",
                "release_status": "NEEDS_RESIDUAL_REVIEW",
                "release_failure_reasons": "",
                "formula_residuals_for_event": "ruhl_2019=1.2;melgar_2015=0.3",
                "manual_decision_written": "no",
                "manual_review_status": "",
                "manual_review_cause": "",
                "manual_review_notes": "",
                "accepted_for_release": "",
                "reviewer": "",
                "reviewed_at": "",
            },
        ]
        self.write_csv(release_dir / "pgd_release_blocker_decision_guide.csv", guide_rows)
        self.write_json(
            release_dir / "pgd_release_blocker_decision_guide.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "row_count": 2,
                "manual_decisions_written": 0,
                "comparison_formula_blocker_count": 1,
            },
        )
        self.write_json(
            release_dir / "pgd_release_blocker_analysis.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "blocker_count": 2,
                "comparison_formula_blocker_count": 1,
            },
        )
        self.write_json(
            release_dir / "pgd_release_readiness.json",
            {
                "status": "OK",
                "readiness_status": "BLOCKED_ON_REVIEW",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "release_blocking_count": 1,
            },
        )
        self.write_json(
            release_dir / "pgd_formula_test_matrix.json",
            {
                "status": "OK",
                "station_aggregation": station_aggregation,
                "recommended_formula": "ruhl_2019",
                "formula_count": 3,
            },
        )
        self.write_csv(
            release_dir / "pgd_formula_test_matrix.csv",
            [
                {
                    "formula": "ruhl_2019",
                    "station_aggregation": station_aggregation,
                    "baseline_rank_by_mae": "1",
                    "baseline_mae_mw": "0.43",
                    "baseline_rmse_mw": "0.53",
                    "sensitivity_winning_scenarios": "baseline;epicentral",
                    "test_status": "BASELINE_RECOMMENDED_REVIEW_BLOCKED",
                },
                {
                    "formula": "crowell_2016_gfast",
                    "station_aggregation": station_aggregation,
                    "baseline_rank_by_mae": "3",
                    "baseline_mae_mw": "0.74",
                    "baseline_rmse_mw": "0.86",
                    "sensitivity_winning_scenarios": "",
                    "test_status": "COMPARISON_NEEDS_REVIEW",
                },
            ],
        )
        self.write_csv(
            release_dir / "residual_review_packet_index.csv",
            [
                {
                    "triage_priority": "1",
                    "event_id": "event-a",
                    "formula": "crowell_2016_gfast",
                    "packet_path": "residual_review_packets/001-event-a-crowell_2016_gfast.md",
                    "abs_residual_mw": "1.8",
                    "triage_status_suggestion": "NEEDS_DATA_CHECK",
                    "triage_cause_suggestion": "data_quality",
                    "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING;COMPARE_FORMULA_RESIDUALS",
                    "release_status": "EXCLUDED_RELEASE_SET",
                    "manual_review_status": "",
                }
            ],
        )
        if create_packet:
            packet_path = release_dir / "residual_review_packets" / "001-event-a-crowell_2016_gfast.md"
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text("# Packet\n", encoding="utf-8")
        return release_dir

    def test_writes_comparison_formula_packet_summary_without_manual_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = build_pgd_comparison_formula_review_packet_summary.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            with (release_dir / "pgd_comparison_formula_review_packet_summary.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["event_id"], "event-a")
            self.assertEqual(row["formula"], "crowell_2016_gfast")
            self.assertEqual(row["recommended_formula"], "ruhl_2019")
            self.assertEqual(row["station_aggregation"], "median")
            self.assertEqual(row["formula_scope"], "comparison_formula")
            self.assertEqual(row["baseline_rank_by_mae"], "3")
            self.assertEqual(row["packet_exists"], "yes")
            self.assertEqual(row["manual_decision_state"], "blank")
            self.assertEqual(row["manual_review_status"], "")
            self.assertIn("CHECK_FORMULA_CONTEXT", row["pre_decision_checks"])
            payload = json.loads((release_dir / "pgd_comparison_formula_review_packet_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["row_count"], 1)
            self.assertEqual(payload["comparison_formula_blocker_count"], 1)
            self.assertEqual(payload["manual_decisions_written"], 0)
            self.assertEqual(payload["packet_exists_count"], 1)
            self.assertEqual(payload["missing_packet_count"], 0)
            self.assertEqual(payload["blockers_by_formula"], {"crowell_2016_gfast": 1})
            markdown = (release_dir / "pgd_comparison_formula_review_packet_summary.md").read_text(encoding="utf-8")
            self.assertIn("PGD Comparison-Formula Review Packet Summary", markdown)
            self.assertIn("one station aggregation method: `median`", markdown)
            self.assertIn("does not write manual decisions", markdown)
            self.assertIn("crowell_2016_gfast", markdown)
            self.assertNotIn("three methods", markdown.lower())

    def test_rejects_non_median_release_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), station_aggregation="mean")

            rc = build_pgd_comparison_formula_review_packet_summary.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_comparison_formula_review_packet_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(any(error["code"] == "INVALID_STATION_AGGREGATION" for error in payload["errors"]))

    def test_reports_missing_packet_as_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), create_packet=False)

            rc = build_pgd_comparison_formula_review_packet_summary.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_comparison_formula_review_packet_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["missing_packet_count"], 1)
            self.assertTrue(any(error["code"] == "MISSING_PACKET" for error in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
