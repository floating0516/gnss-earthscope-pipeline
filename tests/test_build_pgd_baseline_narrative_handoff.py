import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_baseline_narrative_handoff.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_baseline_narrative_handoff", MODULE_PATH)
build_pgd_baseline_narrative_handoff = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_baseline_narrative_handoff)


class BuildPgdBaselineNarrativeHandoffTest(unittest.TestCase):
    def write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_release_dir(self, root: Path, *, station_aggregation: str = "median") -> Path:
        release_dir = root / "release"
        self.write_json(
            release_dir / "pgd_recommended_formula_release_status.json",
            {
                "status": "OK",
                "recommended_formula": "ruhl_2019",
                "station_aggregation": station_aggregation,
                "recommended_formula_release_status": "READY_FOR_BASELINE_NARRATIVE",
                "overall_release_readiness_status": "BLOCKED_ON_REVIEW",
                "comparison_formula_review_status": "NEEDS_COMPARISON_REVIEW",
                "ready_event_count": 13,
                "reviewed_release_count": 12,
                "recommended_formula_blocker_count": 0,
                "comparison_formula_blocker_count": 13,
                "manual_decisions_written": 0,
                "requires_sensitivity_caveat": True,
            },
        )
        self.write_csv(
            release_dir / "pgd_recommended_formula_release_status.csv",
            [
                {
                    "formula_scope": "recommended_formula",
                    "formula": "ruhl_2019",
                    "formula_release_status": "READY_FOR_BASELINE_NARRATIVE",
                    "station_aggregation": station_aggregation,
                    "blocker_count": "0",
                },
                {
                    "formula_scope": "comparison_formula",
                    "formula": "melgar_2015",
                    "formula_release_status": "COMPARISON_CLEAR",
                    "station_aggregation": station_aggregation,
                    "blocker_count": "0",
                },
                {
                    "formula_scope": "comparison_formula",
                    "formula": "crowell_2016_gfast",
                    "formula_release_status": "NEEDS_COMPARISON_REVIEW",
                    "station_aggregation": station_aggregation,
                    "blocker_count": "13",
                },
            ],
        )
        return release_dir

    def test_writes_median_only_baseline_handoff_with_pending_comparison_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp))

            rc = build_pgd_baseline_narrative_handoff.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "pgd_baseline_narrative_handoff.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["baseline_formula"], "ruhl_2019")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertEqual(payload["station_aggregation_method"], "median")
            self.assertEqual(payload["formula_comparison_scope"], "formula_only")
            self.assertEqual(payload["baseline_narrative_status"], "READY_WITH_CAVEATS")
            self.assertEqual(payload["comparison_formula_review_status"], "NEEDS_COMPARISON_REVIEW")
            self.assertEqual(payload["overall_release_readiness_status"], "BLOCKED_ON_REVIEW")
            self.assertEqual(payload["manual_decisions_written"], 0)
            self.assertEqual(payload["formula_count"], 3)
            self.assertEqual(set(payload["formulas"]), {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            self.assertTrue(payload["requires_sensitivity_caveat"])
            markdown = (release_dir / "pgd_baseline_narrative_handoff.md").read_text(encoding="utf-8")
            self.assertIn("one station aggregation method: `median`", markdown)
            self.assertIn("three PGD formulas", markdown)
            self.assertIn("ruhl_2019", markdown)
            self.assertIn("comparison-formula review remains pending", markdown)
            self.assertIn("crowell_2016_gfast", markdown)
            self.assertIn("sensitivity caveat", markdown)
            self.assertIn("does not write manual decisions", markdown)
            self.assertNotIn("three methods", markdown.lower())

    def test_rejects_non_median_station_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            release_dir = self.make_release_dir(Path(tmp), station_aggregation="mean")

            rc = build_pgd_baseline_narrative_handoff.main(["--release-dir", str(release_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "pgd_baseline_narrative_handoff.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["baseline_narrative_status"], "INVALID_INPUTS")
            self.assertTrue(any(error["code"] == "INVALID_STATION_AGGREGATION" for error in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
