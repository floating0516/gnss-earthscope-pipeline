from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_release_blocker_review_prompt.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_release_blocker_review_prompt", MODULE_PATH)
build_pgd_release_blocker_review_prompt = importlib.util.module_from_spec(SPEC)


class BuildPgdReleaseBlockerReviewPromptTest(unittest.TestCase):
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

    def load_module(self):
        assert SPEC.loader is not None
        SPEC.loader.exec_module(build_pgd_release_blocker_review_prompt)
        return build_pgd_release_blocker_review_prompt

    def make_release_dir(self, root: Path, *, station_aggregation: str = "median") -> Path:
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
                "pre_decision_checks": "CHECK_RELEASE_GATE;CHECK_FORMULA_CONTEXT",
                "review_focus": "Compare formula residuals and decide whether formula limitation is acceptable.",
                "release_status": "EXCLUDED_RELEASE_SET",
                "release_failure_reasons": "insufficient_usable_stations;low_reliability",
                "formula_residuals_for_event": "crowell_2016_gfast=1.8;melgar_2015=1.2;ruhl_2019=0.4",
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
                "formula": "crowell_2016_gfast",
                "recommended_formula": "ruhl_2019",
                "formula_scope": "comparison_formula",
                "packet_path": "residual_review_packets/002-event-b-crowell_2016_gfast.md",
                "allowed_terminal_statuses": "REVIEWED;ACCEPTED;EXCLUDED",
                "accepted_for_release_rule": "ACCEPTED=>yes;EXCLUDED=>no;REVIEWED=>yes_or_no_with_notes",
                "suggested_review_status": "NEEDS_FORMULA_REVIEW",
                "suggested_review_cause": "formula_limitation",
                "pre_decision_checks": "CHECK_FORMULA_CONTEXT",
                "review_focus": "Check whether comparison formula limitation explains the residual.",
                "release_status": "EXCLUDED_RELEASE_SET",
                "release_failure_reasons": "low_reliability",
                "formula_residuals_for_event": "crowell_2016_gfast=1.1;melgar_2015=0.7;ruhl_2019=0.5",
                "manual_decision_written": "no",
                "manual_review_status": "",
                "manual_review_cause": "",
                "manual_review_notes": "",
                "accepted_for_release": "",
                "reviewer": "",
                "reviewed_at": "",
            },
        ]
        starter_rows = []
        for row in guide_rows:
            starter_rows.append(
                {
                    "starter_priority": row["guide_priority"],
                    "event_id": row["event_id"],
                    "formula": row["formula"],
                    "release_blocking": "yes",
                    "packet_path": row["packet_path"],
                    "suggested_review_status": row["suggested_review_status"],
                    "suggested_review_cause": row["suggested_review_cause"],
                    "suggested_accepted_for_release": "",
                    "next_review_action": "CHECK_RELEASE_GATE;COMPARE_FORMULA_RESIDUALS",
                    "review_focus": row["review_focus"],
                    "release_status": row["release_status"],
                    "release_failure_reasons": row["release_failure_reasons"],
                    "best_formula_for_event": "ruhl_2019",
                    "formula_residuals_for_event": row["formula_residuals_for_event"],
                    "manual_review_status": "",
                    "manual_review_cause": "",
                    "manual_review_notes": "",
                    "accepted_for_release": "",
                    "reviewer": "",
                    "reviewed_at": "",
                }
            )
        self.write_csv(release_dir / "pgd_release_blocker_decision_guide.csv", guide_rows)
        self.write_csv(release_dir / "release_blocking_review_starter.csv", starter_rows)
        self.write_csv(
            release_dir / "pgd_comparison_formula_review_packet_summary.csv",
            [
                {
                    "review_priority": row["guide_priority"],
                    "event_id": row["event_id"],
                    "formula": row["formula"],
                    "recommended_formula": row["recommended_formula"],
                    "station_aggregation": station_aggregation,
                    "formula_scope": row["formula_scope"],
                    "packet_path": row["packet_path"],
                    "packet_exists": "yes",
                    "suggested_review_status": row["suggested_review_status"],
                    "suggested_review_cause": row["suggested_review_cause"],
                    "manual_decision_state": "blank",
                    "manual_review_status": "",
                    "accepted_for_release": "",
                }
                for row in guide_rows
            ],
        )
        self.write_json(
            release_dir / "pgd_release_blocker_decision_guide.json",
            {
                "status": "OK",
                "station_aggregation": station_aggregation,
                "recommended_formula": "ruhl_2019",
                "comparison_formula_blocker_count": 2,
                "manual_decisions_written": 0,
                "guide_by_formula_scope": {"comparison_formula": 2},
                "guide_by_suggested_review_status": {"NEEDS_DATA_CHECK": 1, "NEEDS_FORMULA_REVIEW": 1},
            },
        )
        self.write_json(
            release_dir / "release_blocking_review_starter.json",
            {
                "status": "OK",
                "starter_row_count": 2,
                "release_blocking_count": 2,
                "suggested_review_status_counts": {"NEEDS_DATA_CHECK": 1, "NEEDS_FORMULA_REVIEW": 1},
                "suggested_review_cause_counts": {"data_quality": 1, "formula_limitation": 1},
            },
        )
        self.write_json(
            release_dir / "pgd_comparison_formula_review_packet_summary.json",
            {
                "status": "OK",
                "station_aggregation": station_aggregation,
                "recommended_formula": "ruhl_2019",
                "row_count": 2,
                "comparison_formula_blocker_count": 2,
                "packet_exists_count": 2,
                "missing_packet_count": 0,
                "manual_decisions_written": 0,
                "blockers_by_formula": {"crowell_2016_gfast": 2},
            },
        )
        self.write_json(
            release_dir / "release_readme.json",
            {
                "status": "OK",
                "entrypoint_status": "BLOCKED_ON_REVIEW",
                "station_aggregation": station_aggregation,
                "baseline_formula": "ruhl_2019",
                "formula_comparison_scope": "formula_only",
                "formulas": ["melgar_2015", "crowell_2016_gfast", "ruhl_2019"],
                "ready_event_count": 13,
                "comparison_formula_blocker_count": 2,
                "manual_decisions_written": 0,
                "import_commands": ["validate command", "bundle import command"],
            },
        )
        self.write_json(
            release_dir / "pgd_review_briefing.json",
            {
                "status": "OK",
                "briefing_status": "BLOCKED_ON_REVIEW",
                "station_aggregation": station_aggregation,
                "baseline_formula": "ruhl_2019",
                "manual_decisions_written": 0,
                "allowed_manual_review_statuses": ["UNREVIEWED", "REVIEWED", "ACCEPTED", "EXCLUDED", "NEEDS_DATA_CHECK", "NEEDS_FORMULA_REVIEW"],
                "allowed_accepted_for_release_values": ["yes", "no"],
                "import_commands": ["validate command", "bundle import command"],
            },
        )
        return release_dir

    def test_writes_read_only_prompt_pack_for_release_blockers(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = module.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "pgd_release_blocker_review_prompt.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["prompt_status"], "BLOCKED_ON_REVIEW")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["baseline_formula"], "ruhl_2019")
            self.assertEqual(payload["formula_comparison_scope"], "formula_only")
            self.assertEqual(payload["blocker_count"], 2)
            self.assertEqual(payload["comparison_formula_blocker_count"], 2)
            self.assertEqual(payload["manual_decisions_written"], 0)
            self.assertEqual(payload["manual_fields"], ["manual_review_status", "manual_review_cause", "manual_review_notes", "accepted_for_release", "reviewer", "reviewed_at"])
            self.assertEqual(payload["allowed_terminal_statuses"], ["REVIEWED", "ACCEPTED", "EXCLUDED"])
            self.assertEqual(payload["accepted_for_release_rule"], "ACCEPTED=>yes;EXCLUDED=>no;REVIEWED=>yes_or_no_with_notes")
            self.assertEqual([row["event_id"] for row in payload["blocker_rows"]], ["event-a", "event-b"])
            self.assertTrue(all(row["packet_path"].startswith("residual_review_packets/") for row in payload["blocker_rows"]))
            self.assertTrue(all(row["manual_review_status"] == "" for row in payload["starter_rows"]))
            self.assertTrue(all(row["accepted_for_release"] == "" for row in payload["starter_rows"]))
            self.assertIn("melgar_2015", payload["formulas"])
            self.assertIn("crowell_2016_gfast", payload["formulas"])
            self.assertIn("ruhl_2019", payload["formulas"])
            markdown = (release_dir / "pgd_release_blocker_review_prompt.md").read_text(encoding="utf-8")
            self.assertIn("PGD Release Blocker Review Prompt", markdown)
            self.assertIn("one station aggregation method: `median`", markdown)
            self.assertIn("Do not edit generated evidence files", markdown)
            self.assertIn("Fill a copy of `release_blocking_review_starter.csv`", markdown)
            self.assertIn("validate_release_starter_annotations.py", markdown)
            self.assertIn("run_pgd_science_bundle.py", markdown)
            self.assertIn("event-a", markdown)
            self.assertNotIn("mean", markdown.lower())
            self.assertNotIn("trimmed", markdown.lower())

    def test_rejects_non_median_release_context(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), station_aggregation="mean")

            rc = module.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_release_blocker_review_prompt.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(any(error["code"] == "INVALID_STATION_AGGREGATION" for error in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
