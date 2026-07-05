from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "reports" / "build_event_inclusion_exclusion_report.py"
SPEC = importlib.util.spec_from_file_location("build_event_inclusion_exclusion_report", MODULE_PATH)
reporter = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(reporter)


class BuildEventInclusionExclusionReportTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_batch(self, path: Path) -> None:
        self.write_rows(
            path,
            [
                {"event_id": "event-done", "event_time": "2020-01-01T00:00:00Z", "source": "EarthScope", "status": ""},
                {"event_id": "event-no-obs", "event_time": "2020-01-02T00:00:00Z", "source": "EarthScope", "status": ""},
                {"event_id": "event-new", "event_time": "2020-01-03T00:00:00Z", "source": "EarthScope", "status": ""},
            ],
        )

    def write_valid_package(self, export_root: Path, event_id: str) -> None:
        package = export_root / f"us-{event_id}"
        package.mkdir(parents=True)
        (package / "event.json").write_text(json.dumps({"event_id": event_id}) + "\n", encoding="utf-8")
        (package / "provenance.json").write_text(json.dumps({"event_id": event_id}) + "\n", encoding="utf-8")
        (package / "stations.csv").write_text("Station,Quality_Status\nABCD,OK\n", encoding="utf-8")
        with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["Station", "Time_UTC"], lineterminator="\n")
            writer.writeheader()
            writer.writerow({"Station": "ABCD", "Time_UTC": "2020-01-01T00:00:00Z"})

    def write_workflow_summary(self, runs_root: Path, event_id: str, workflow_name: str, payload: dict[str, object]) -> None:
        reports = runs_root / event_id / workflow_name / "reports"
        reports.mkdir(parents=True)
        (reports / "workflow-summary.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def test_build_report_explains_included_excluded_retry_and_not_started_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch.csv"
            runs = root / "runs"
            export_root = root / "exports"
            self.write_batch(batch)
            self.write_valid_package(export_root, "event-done")
            self.write_workflow_summary(
                runs,
                "event-no-obs",
                "workflow-20200102T000000Z",
                {
                    "status": {"download": "OK", "obs_validation": "FAIL", "process": "BLOCKED_OBS_VALIDATION"},
                    "counts": {"obs_files": 0, "kin_files": 0},
                },
            )
            self.write_workflow_summary(
                runs,
                "event-retry",
                "workflow-20200104T000000Z",
                {
                    "status": {"download": "OK", "obs_validation": "OK", "process": "FAIL", "quality": "WARN"},
                    "counts": {"obs_files": 1, "kin_files": 1},
                },
            )

            rows = reporter.build_rows([batch], runs, export_root)

        by_event = {row["event_id"]: row for row in rows}
        self.assertEqual(by_event["event-done"]["final_status"], "INCLUDED_NORMALIZED")
        self.assertEqual(by_event["event-done"]["inclusion_stage"], "normalized_export")
        self.assertEqual(by_event["event-done"]["export_status"], "OK")
        self.assertEqual(by_event["event-no-obs"]["final_status"], "EXCLUDED_NO_OBS")
        self.assertEqual(by_event["event-no-obs"]["inclusion_stage"], "obs_validation")
        self.assertEqual(by_event["event-no-obs"]["exclusion_reason"], "NO_OBS")
        self.assertEqual(by_event["event-new"]["final_status"], "NOT_STARTED")
        self.assertEqual(by_event["event-new"]["next_action"], "SCHEDULE_WORKFLOW")
        self.assertEqual(by_event["event-retry"]["final_status"], "RETRY_PENDING")
        self.assertEqual(by_event["event-retry"]["batch_present"], "no")
        self.assertEqual(by_event["event-retry"]["failure_class"], "PROCESS_FAIL")

    def test_cli_writes_csv_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch.csv"
            runs = root / "runs"
            export_root = root / "exports"
            out_csv = root / "inclusion.csv"
            out_json = root / "inclusion.json"
            out_md = root / "inclusion.md"
            self.write_batch(batch)
            self.write_valid_package(export_root, "event-done")

            rc = reporter.main(
                [
                    "--batch",
                    str(batch),
                    "--runs",
                    str(runs),
                    "--export-root",
                    str(export_root),
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
            self.assertEqual({row["event_id"] for row in rows}, {"event-done", "event-new", "event-no-obs"})
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total_events"], 3)
            self.assertEqual(payload["summary"]["included_normalized"], 1)
            self.assertIn("event-done", out_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
