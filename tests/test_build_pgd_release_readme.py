import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_release_readme.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_release_readme", MODULE_PATH)
build_pgd_release_readme = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_release_readme)


class BuildPgdReleaseReadmeTest(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def make_release_dir(self, root: Path) -> Path:
        release_dir = root / "reports" / "pgd_magnitude" / "release" / "latest"
        release_dir.mkdir(parents=True)
        self.write_json(
            release_dir / "release_package_summary.json",
            {
                "status": "OK",
                "ready_event_count": 13,
                "recommended_formula": "ruhl_2019",
                "station_aggregation": "median",
                "requires_sensitivity_caveat": True,
                "residual_review_evidence": {"row_count": 20},
            },
        )
        self.write_json(
            release_dir / "pgd_review_briefing.json",
            {
                "status": "OK",
                "briefing_status": "BLOCKED_ON_REVIEW",
                "baseline_formula": "ruhl_2019",
                "station_aggregation": "median",
                "formula_comparison_scope": "formula_only",
                "pgd_event_count": 94,
                "ready_event_count": 13,
                "comparison_formula_blocker_count": 13,
                "review_packet_count": 13,
                "manual_decisions_written": 0,
                "next_actions": ["Fill a copy of release_blocking_review_starter.csv."],
            },
        )
        self.write_json(
            release_dir / "pgd_release_readiness.json",
            {
                "status": "OK",
                "readiness_status": "BLOCKED_ON_REVIEW",
                "station_aggregation": "median",
                "ready_event_count": 13,
                "release_blocking_count": 13,
                "reviewed_release_count": 12,
                "work_item_count": 13,
            },
        )
        self.write_json(
            release_dir / "pgd_recommended_formula_release_status.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": "median",
                "recommended_formula_release_status": "READY_FOR_BASELINE_NARRATIVE",
                "overall_release_readiness_status": "BLOCKED_ON_REVIEW",
                "comparison_formula_blocker_count": 13,
                "manual_decisions_written": 0,
            },
        )
        self.write_json(
            release_dir / "reviewed_release_summary.json",
            {
                "status": "OK",
                "completion_status": "INCOMPLETE",
                "reviewed_release_count": 12,
                "blocker_count": 13,
            },
        )
        self.write_json(
            release_dir / "release_blocking_review_starter.json",
            {
                "status": "OK",
                "mode": "release_blocking",
                "starter_row_count": 13,
                "release_blocking_count": 13,
            },
        )
        return release_dir

    def test_builds_release_readme_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = build_pgd_release_readme.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "release_readme.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["entrypoint_status"], "BLOCKED_ON_REVIEW")
            self.assertEqual(payload["baseline_formula"], "ruhl_2019")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["manual_decisions_written"], 0)
            self.assertEqual(payload["comparison_formula_blocker_count"], 13)
            start_here = next(row for row in payload["key_files"] if row["path"] == "README.md")
            self.assertTrue(start_here["exists"])
            readme = (release_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("# PGD Magnitude Release", readme)
            self.assertIn("Station aggregation: `median`", readme)
            self.assertIn("Baseline formula: `ruhl_2019`", readme)
            self.assertIn("`melgar_2015`", readme)
            self.assertIn("`crowell_2016_gfast`", readme)
            self.assertIn("`ruhl_2019`", readme)
            self.assertIn("pgd_review_briefing.md", readme)
            self.assertIn("release_blocking_review_starter.csv", readme)
            self.assertIn("residual_review_packet_index.md", readme)
            self.assertIn("| Start here | README.md | True |", readme)
            self.assertIn("validate_release_starter_annotations.py", readme)
            self.assertIn("run_pgd_science_bundle.py", readme)
            self.assertIn("does not write manual decisions", readme)

    def test_rejects_non_median_release_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))
            briefing = json.loads((release_dir / "pgd_review_briefing.json").read_text(encoding="utf-8"))
            briefing["station_aggregation"] = "mean"
            self.write_json(release_dir / "pgd_review_briefing.json", briefing)

            rc = build_pgd_release_readme.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "release_readme.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["entrypoint_status"], "INVALID_INPUTS")
            self.assertEqual(payload["errors"][0]["code"], "INVALID_STATION_AGGREGATION")


if __name__ == "__main__":
    unittest.main()
