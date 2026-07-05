import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "validate_release_starter_annotations.py"
SPEC = importlib.util.spec_from_file_location("validate_release_starter_annotations", MODULE_PATH)
validate_release_starter_annotations = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_release_starter_annotations)


class ValidateReleaseStarterAnnotationsTest(unittest.TestCase):
    fields = [
        "event_id",
        "formula",
        "release_blocking",
        "manual_review_status",
        "manual_review_cause",
        "manual_review_notes",
        "accepted_for_release",
        "reviewer",
        "reviewed_at",
    ]

    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fields, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in self.fields})

    def make_release_dir(self, root: Path, base_rows: list[dict[str, str]]) -> Path:
        release_dir = root / "release" / "latest"
        self.write_csv(release_dir / "release_blocking_review_starter.csv", base_rows)
        return release_dir

    def test_validates_complete_starter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_rows = [
                {"event_id": "event-a", "formula": "crowell_2016_gfast", "release_blocking": "yes"},
                {"event_id": "event-b", "formula": "crowell_2016_gfast", "release_blocking": "yes"},
            ]
            release_dir = self.make_release_dir(root, base_rows)
            completed = root / "completed.csv"
            self.write_csv(
                completed,
                [
                    {
                        "event_id": "event-a",
                        "formula": "crowell_2016_gfast",
                        "manual_review_status": "ACCEPTED",
                        "manual_review_cause": "data_quality_checked",
                        "accepted_for_release": "yes",
                        "reviewer": "reviewer-a",
                        "reviewed_at": "2026-07-04T00:00:00Z",
                    },
                    {
                        "event_id": "event-b",
                        "formula": "crowell_2016_gfast",
                        "manual_review_status": "EXCLUDED",
                        "manual_review_cause": "data_quality",
                        "accepted_for_release": "no",
                        "reviewer": "reviewer-a",
                        "reviewed_at": "2026-07-04T00:01:00Z",
                    },
                ],
            )

            rc = validate_release_starter_annotations.main(
                ["--release-dir", str(release_dir), "--completed-starter", str(completed), "--require-complete", "--strict"]
            )

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "release_starter_validation.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["completion_status"], "COMPLETE")
            self.assertEqual(payload["base_release_blocking_count"], 2)
            self.assertEqual(payload["complete_decision_count"], 2)
            self.assertEqual(payload["missing_decision_count"], 0)
            self.assertEqual(payload["invalid_count"], 0)
            self.assertEqual(payload["unknown_key_count"], 0)
            with (release_dir / "release_starter_validation.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual({row["validation_status"] for row in rows}, {"COMPLETE"})
            markdown = (release_dir / "release_starter_validation.md").read_text(encoding="utf-8")
            self.assertIn("COMPLETE", markdown)

    def test_reports_incomplete_and_invalid_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_rows = [
                {"event_id": "event-a", "formula": "crowell_2016_gfast", "release_blocking": "yes"},
                {"event_id": "event-b", "formula": "crowell_2016_gfast", "release_blocking": "yes"},
                {"event_id": "event-c", "formula": "crowell_2016_gfast", "release_blocking": "yes"},
            ]
            release_dir = self.make_release_dir(root, base_rows)
            completed = root / "completed.csv"
            self.write_csv(
                completed,
                [
                    {
                        "event_id": "event-a",
                        "formula": "crowell_2016_gfast",
                        "manual_review_status": "NEEDS_DATA_CHECK",
                        "accepted_for_release": "",
                    },
                    {
                        "event_id": "event-b",
                        "formula": "crowell_2016_gfast",
                        "manual_review_status": "ACCEPTED",
                        "accepted_for_release": "no",
                    },
                    {
                        "event_id": "event-x",
                        "formula": "crowell_2016_gfast",
                        "manual_review_status": "ACCEPTED",
                        "accepted_for_release": "yes",
                    },
                ],
            )

            rc = validate_release_starter_annotations.main(
                ["--release-dir", str(release_dir), "--completed-starter", str(completed), "--require-complete", "--strict"]
            )

            self.assertEqual(rc, 1)
            payload = json.loads((release_dir / "release_starter_validation.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertEqual(payload["completion_status"], "INCOMPLETE")
            self.assertEqual(payload["missing_decision_count"], 2)
            self.assertEqual(payload["invalid_count"], 1)
            self.assertEqual(payload["unknown_key_count"], 1)
            error_codes = {error["code"] for error in payload["errors"]}
            self.assertIn("INCOMPLETE_RELEASE_BLOCKING_DECISION", error_codes)
            self.assertIn("INCONSISTENT_ACCEPTED_FOR_RELEASE", error_codes)
            self.assertIn("UNKNOWN_STARTER_KEY", error_codes)

    def test_blank_starter_is_valid_but_incomplete_without_require_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_rows = [{"event_id": "event-a", "formula": "crowell_2016_gfast", "release_blocking": "yes"}]
            release_dir = self.make_release_dir(root, base_rows)
            completed = root / "blank.csv"
            self.write_csv(completed, base_rows)

            rc = validate_release_starter_annotations.main(["--release-dir", str(release_dir), "--completed-starter", str(completed)])

            self.assertEqual(rc, 0)
            payload = json.loads((release_dir / "release_starter_validation.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["completion_status"], "INCOMPLETE")
            self.assertEqual(payload["missing_decision_count"], 1)
            self.assertEqual(payload["invalid_count"], 0)


if __name__ == "__main__":
    unittest.main()
