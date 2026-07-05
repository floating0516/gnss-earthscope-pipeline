import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_release_blocker_decision_guide.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_release_blocker_decision_guide", MODULE_PATH)
build_pgd_release_blocker_decision_guide = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_release_blocker_decision_guide)


class BuildPgdReleaseBlockerDecisionGuideTest(unittest.TestCase):
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

    def make_release_dir(self, root: Path, *, analysis_status: str = "OK") -> Path:
        release_dir = root / "reports" / "pgd_magnitude" / "release" / "latest"
        analysis_rows = [
            {
                "blocker_priority": "1",
                "worklist_priority": "1",
                "event_id": "event-a",
                "formula": "crowell_2016_gfast",
                "recommended_formula": "ruhl_2019",
                "formula_scope": "comparison_formula",
                "manual_decision_written": "no",
                "worklist_status": "PENDING_REVIEW",
                "blocker_status": "PENDING_REVIEW",
                "blocker_reason": "Residual review decision is still pending.",
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
                "packet_path": "residual_review_packets/event-a.md",
                "analysis_note": "comparison formula blocker",
            },
            {
                "blocker_priority": "2",
                "worklist_priority": "2",
                "event_id": "event-b",
                "formula": "ruhl_2019",
                "recommended_formula": "ruhl_2019",
                "formula_scope": "recommended_formula",
                "manual_decision_written": "no",
                "worklist_status": "PENDING_REVIEW",
                "blocker_status": "PENDING_REVIEW",
                "blocker_reason": "Residual review decision is still pending.",
                "abs_residual_mw": "1.2",
                "suggested_review_status": "NEEDS_FORMULA_REVIEW",
                "suggested_review_cause": "formula_limitation",
                "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                "review_focus": "Recommended formula blocker example.",
                "release_status": "NEEDS_RESIDUAL_REVIEW",
                "release_failure_reasons": "",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "4",
                "median_pgd_snr": "5.0",
                "median_distance_km": "90",
                "best_formula_for_event": "melgar_2015",
                "best_formula_abs_residual_mw": "0.3",
                "formula_residuals_for_event": "melgar_2015=0.3;ruhl_2019=1.2",
                "packet_path": "residual_review_packets/event-b.md",
                "analysis_note": "recommended formula blocker",
            },
        ]
        self.write_csv(release_dir / "pgd_release_blocker_analysis.csv", analysis_rows)
        self.write_json(
            release_dir / "pgd_release_blocker_analysis.json",
            {
                "status": analysis_status,
                "recommended_formula": "ruhl_2019",
                "station_aggregation": "median",
                "blocker_count": 2,
                "recommended_formula_blocker_count": 1,
                "comparison_formula_blocker_count": 1,
            },
        )
        starter_rows = []
        for row in analysis_rows:
            starter_rows.append(
                {
                    "starter_priority": row["blocker_priority"],
                    "worklist_priority": row["worklist_priority"],
                    "event_id": row["event_id"],
                    "formula": row["formula"],
                    "release_blocking": "yes",
                    "packet_path": row["packet_path"],
                    "suggested_review_status": row["suggested_review_status"],
                    "suggested_review_cause": row["suggested_review_cause"],
                    "next_review_action": row["next_review_action"],
                    "review_focus": row["review_focus"],
                    "manual_review_status": "",
                    "manual_review_cause": "",
                    "manual_review_notes": "",
                    "accepted_for_release": "",
                    "reviewer": "",
                    "reviewed_at": "",
                }
            )
        self.write_csv(release_dir / "release_blocking_review_starter.csv", starter_rows)
        return release_dir

    def test_builds_decision_guide_without_writing_manual_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = build_pgd_release_blocker_decision_guide.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            with (release_dir / "pgd_release_blocker_decision_guide.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["manual_decision_written"] for row in rows}, {"no"})
            self.assertEqual({row["manual_review_status"] for row in rows}, {""})
            self.assertEqual(rows[0]["allowed_terminal_statuses"], "REVIEWED;ACCEPTED;EXCLUDED")
            self.assertIn("ACCEPTED=>yes", rows[0]["accepted_for_release_rule"])
            self.assertIn("CHECK_WAVEFORM_AND_STATION_FILTERING", rows[0]["pre_decision_checks"])
            self.assertIn("CHECK_FORMULA_CONTEXT", rows[1]["pre_decision_checks"])
            payload = json.loads((release_dir / "pgd_release_blocker_decision_guide.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["row_count"], 2)
            self.assertEqual(payload["manual_decisions_written"], 0)
            self.assertEqual(payload["recommended_formula_blocker_count"], 1)
            self.assertEqual(payload["comparison_formula_blocker_count"], 1)
            self.assertEqual(payload["required_completed_starter"], str(release_dir / "release_blocking_review_starter.csv"))
            markdown = (release_dir / "pgd_release_blocker_decision_guide.md").read_text(encoding="utf-8")
            self.assertIn("PGD Release Blocker Decision Guide", markdown)
            self.assertIn("does not fill manual review fields", markdown)
            self.assertIn("REVIEWED;ACCEPTED;EXCLUDED", markdown)

    def test_invalid_when_blocker_analysis_is_not_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), analysis_status="INVALID")

            rc = build_pgd_release_blocker_decision_guide.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_release_blocker_decision_guide.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()
