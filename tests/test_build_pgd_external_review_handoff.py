import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_external_review_handoff.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_external_review_handoff", MODULE_PATH)
build_pgd_external_review_handoff = importlib.util.module_from_spec(SPEC)


class BuildPgdExternalReviewHandoffTest(unittest.TestCase):
    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0]) if rows else ["event_id", "formula"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def load_module(self):
        assert SPEC.loader is not None
        SPEC.loader.exec_module(build_pgd_external_review_handoff)
        return build_pgd_external_review_handoff

    def make_release_dir(self, root: Path, *, station_aggregation: str = "median", omit_prompt: bool = False) -> Path:
        release_dir = root / "release"
        release_dir.mkdir(parents=True)
        for relative_path in [
            "README.md",
            "pgd_review_briefing.md",
            "pgd_release_blocker_review_prompt.md",
            "pgd_release_readiness.md",
            "pgd_release_blocker_decision_guide.md",
            "pgd_comparison_formula_review_packet_summary.md",
            "release_blocking_review_starter.csv",
            "residual_review_packet_index.md",
            "residual_review_packets/001-event-a-crowell_2016_gfast.md",
        ]:
            path = release_dir / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {relative_path}\n", encoding="utf-8")
        if omit_prompt:
            (release_dir / "pgd_release_blocker_review_prompt.md").unlink()

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
                "comparison_formula_blocker_count": 1,
                "manual_decisions_written": 0,
            },
        )
        self.write_json(
            release_dir / "pgd_release_blocker_review_prompt.json",
            {
                "status": "OK",
                "prompt_status": "BLOCKED_ON_REVIEW",
                "station_aggregation": station_aggregation,
                "baseline_formula": "ruhl_2019",
                "formula_comparison_scope": "formula_only",
                "blocker_count": 1,
                "manual_decisions_written": 0,
            },
        )
        self.write_json(
            release_dir / "pgd_review_briefing.json",
            {
                "status": "OK",
                "briefing_status": "BLOCKED_ON_REVIEW",
                "station_aggregation": station_aggregation,
                "baseline_formula": "ruhl_2019",
                "review_packet_count": 1,
                "manual_decisions_written": 0,
            },
        )
        self.write_json(
            release_dir / "pgd_release_readiness.json",
            {
                "status": "OK",
                "readiness_status": "BLOCKED_ON_REVIEW",
                "station_aggregation": station_aggregation,
                "ready_event_count": 13,
                "release_blocking_count": 1,
            },
        )
        self.write_json(
            release_dir / "release_package_summary.json",
            {
                "status": "OK",
                "station_aggregation": station_aggregation,
                "recommended_formula": "ruhl_2019",
                "ready_event_count": 13,
            },
        )
        self.write_json(
            release_dir / "pgd_comparison_formula_review_packet_summary.json",
            {
                "status": "OK",
                "station_aggregation": station_aggregation,
                "recommended_formula": "ruhl_2019",
                "comparison_formula_blocker_count": 1,
                "packet_exists_count": 1,
                "missing_packet_count": 0,
                "manual_decisions_written": 0,
            },
        )
        self.write_csv(
            release_dir / "pgd_comparison_formula_review_packet_summary.csv",
            [
                {
                    "review_priority": "1",
                    "event_id": "event-a",
                    "formula": "crowell_2016_gfast",
                    "recommended_formula": "ruhl_2019",
                    "station_aggregation": station_aggregation,
                    "packet_path": "residual_review_packets/001-event-a-crowell_2016_gfast.md",
                    "packet_exists": "yes",
                    "suggested_review_status": "NEEDS_DATA_CHECK",
                    "manual_decision_state": "blank",
                }
            ],
        )
        return release_dir

    def test_writes_manifest_and_handoff_markdown_for_external_reviewers(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = module.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "pgd_external_review_handoff_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["handoff_status"], "BLOCKED_ON_REVIEW")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["baseline_formula"], "ruhl_2019")
            self.assertEqual(payload["formula_comparison_scope"], "formula_only")
            self.assertEqual(payload["blocker_count"], 1)
            self.assertEqual(payload["manual_decisions_written"], 0)
            self.assertEqual(payload["missing_required_count"], 0)
            self.assertEqual(payload["included_file_count"], len(payload["files"]))
            paths = {row["path"]: row for row in payload["files"]}
            self.assertEqual(paths["README.md"]["role"], "start_here")
            self.assertEqual(paths["pgd_release_blocker_review_prompt.md"]["role"], "review_prompt")
            self.assertEqual(paths["release_blocking_review_starter.csv"]["editable"], "copy_only")
            self.assertEqual(paths["residual_review_packets/001-event-a-crowell_2016_gfast.md"]["role"], "review_packet")
            self.assertTrue(all(row["exists"] for row in payload["files"]))
            self.assertEqual(payload["blocker_rows"][0]["event_id"], "event-a")

            with (release_dir / "pgd_external_review_handoff_manifest.csv").open(newline="", encoding="utf-8") as handle:
                manifest_rows = list(csv.DictReader(handle))
            self.assertEqual(len(manifest_rows), payload["included_file_count"])
            self.assertIn("sha256", manifest_rows[0])
            self.assertTrue(manifest_rows[0]["sha256"])

            markdown = (release_dir / "pgd_external_review_handoff.md").read_text(encoding="utf-8")
            self.assertIn("PGD External Review Handoff", markdown)
            self.assertIn("one station aggregation method: `median`", markdown)
            self.assertIn("three formulas", markdown)
            self.assertIn("Do not edit generated evidence files", markdown)
            self.assertIn("Fill a copy of `release_blocking_review_starter.csv`", markdown)
            self.assertIn("pgd_release_blocker_review_prompt.md", markdown)
            self.assertIn("residual_review_packets/001-event-a-crowell_2016_gfast.md", markdown)
            self.assertNotIn("three methods", markdown.lower())

    def test_reports_invalid_when_required_handoff_file_is_missing(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), omit_prompt=True)

            rc = module.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_external_review_handoff_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["handoff_status"], "INVALID_INPUTS")
            self.assertEqual(payload["missing_required_count"], 1)
            self.assertTrue(any(error["code"] == "MISSING_HANDOFF_FILE" for error in payload["errors"]))

    def test_rejects_non_median_release_context(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), station_aggregation="mean")

            rc = module.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_external_review_handoff_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(any(error["code"] == "INVALID_STATION_AGGREGATION" for error in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
