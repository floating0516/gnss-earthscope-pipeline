import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_release_readiness_report.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_release_readiness_report", MODULE_PATH)
build_pgd_release_readiness_report = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_release_readiness_report)


class BuildPgdReleaseReadinessReportTest(unittest.TestCase):
    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0]) if rows else ["event_id", "formula"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_release_dir(self, root: Path, *, release_blocking_count: int = 2, completion_status: str = "INCOMPLETE") -> Path:
        release_dir = root / "release" / "latest"
        self.write_json(
            release_dir / "release_package_summary.json",
            {
                "status": "OK",
                "ready_event_count": 13,
                "recommended_formula": "ruhl_2019",
                "station_aggregation": "median",
                "requires_sensitivity_caveat": True,
            },
        )
        self.write_json(
            release_dir / "residual_review_decision_report.json",
            {"status": "OK", "completion_status": completion_status, "pending_count": release_blocking_count},
        )
        self.write_json(
            release_dir / "reviewed_release_summary.json",
            {
                "status": "OK",
                "completion_status": completion_status,
                "reviewed_release_count": 12 if release_blocking_count else 13,
                "blocker_count": release_blocking_count,
            },
        )
        self.write_json(
            release_dir / "residual_review_worklist.json",
            {
                "status": "OK",
                "completion_status": completion_status,
                "work_item_count": release_blocking_count + 1 if release_blocking_count else 0,
                "release_blocking_count": release_blocking_count,
            },
        )
        self.write_json(
            release_dir / "release_blocking_review_starter.json",
            {"status": "OK", "starter_row_count": release_blocking_count, "release_blocking_count": release_blocking_count},
        )
        blocker_rows = [
            {
                "event_id": f"event-{index}",
                "formula": "crowell_2016_gfast",
                "release_blocking": "yes",
                "blocker_reason": "Residual review decision is still pending.",
                "suggested_review_status": "NEEDS_DATA_CHECK",
                "suggested_review_cause": "data_quality",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING",
                "abs_residual_mw": str(1.2 + index / 10),
                "packet_path": f"residual_review_packets/event-{index}.md",
            }
            for index in range(1, release_blocking_count + 1)
        ]
        self.write_csv(release_dir / "residual_review_worklist.csv", blocker_rows)
        self.write_csv(release_dir / "reviewed_release_blockers.csv", blocker_rows)
        return release_dir

    def test_reports_blocked_on_review_with_next_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), release_blocking_count=2)

            rc = build_pgd_release_readiness_report.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "pgd_release_readiness.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["readiness_status"], "BLOCKED_ON_REVIEW")
            self.assertEqual(payload["recommended_formula"], "ruhl_2019")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["release_blocking_count"], 2)
            self.assertEqual(payload["reviewed_release_count"], 12)
            self.assertIn("release_blocking_review_starter.csv", payload["release_blocking_review_starter"])
            self.assertTrue(any("--starter-annotations" in action for action in payload["next_actions"]))
            self.assertEqual(len(payload["top_blockers"]), 2)
            self.assertEqual(payload["top_blockers"][0]["suggested_manual_status"], "NEEDS_DATA_CHECK")
            self.assertEqual(payload["top_blockers"][0]["suggested_manual_cause"], "data_quality")
            self.assertEqual(payload["top_blockers"][0]["next_action"], "CHECK_WAVEFORM_AND_STATION_FILTERING")
            markdown = (release_dir / "pgd_release_readiness.md").read_text(encoding="utf-8")
            self.assertIn("BLOCKED_ON_REVIEW", markdown)
            self.assertIn("ruhl_2019", markdown)
            self.assertIn("release_blocking_review_starter.csv", markdown)

    def test_reports_ready_when_review_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), release_blocking_count=0, completion_status="COMPLETE")

            rc = build_pgd_release_readiness_report.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "pgd_release_readiness.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["readiness_status"], "READY")
            self.assertEqual(payload["release_blocking_count"], 0)
            self.assertEqual(payload["reviewed_release_count"], 13)
            self.assertEqual(payload["next_actions"], ["PGD release review is complete; package can be used for downstream science reporting."])

    def test_reports_invalid_inputs_when_required_product_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = Path(tmp) / "release" / "latest"
            release_dir.mkdir(parents=True)

            rc = build_pgd_release_readiness_report.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_release_readiness.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["readiness_status"], "INVALID_INPUTS")
            self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()
