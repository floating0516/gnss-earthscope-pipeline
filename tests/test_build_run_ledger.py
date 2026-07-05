from __future__ import annotations

import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.summaries import build_run_ledger


class BuildRunLedgerTest(unittest.TestCase):
    def write_valid_package(self, package_dir: Path, event_id: str, *, source: str = "earthscope") -> None:
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "event.json").write_text(json.dumps({"event_id": event_id, "source": source}) + "\n", encoding="utf-8")
        (package_dir / "stations.csv").write_text("Station,Quality_Status\nABCD,OK\n", encoding="utf-8")
        with gzip.open(package_dir / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["Station", "time_utc", "component", "displacement_cm"])
            writer.writeheader()
            writer.writerow(
                {
                    "Station": "ABCD",
                    "time_utc": "2020-01-01T00:00:00Z",
                    "component": "E",
                    "displacement_cm": "0.0",
                }
            )
        (package_dir / "provenance.json").write_text(json.dumps({"event_id": event_id}) + "\n", encoding="utf-8")

    def write_workflow_summary(self, runs_root: Path, event_id: str, workflow_name: str, payload: dict[str, object]) -> None:
        reports = runs_root / event_id / workflow_name / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "workflow-summary.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def test_ledger_merges_export_only_and_latest_workflow_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            export_root = root / "exports" / "normalized-ok-stations-us-nz"
            out = root / "run-ledger.tsv"
            self.write_valid_package(export_root / "us-event-done", "event-done")
            self.write_workflow_summary(
                runs,
                "event-retry",
                "workflow-20200101T000000Z",
                {
                    "status": {"download": "OK", "obs_validation": "OK", "process": "OK", "quality": "OK"},
                    "counts": {"obs_files": 1, "kin_files": 1},
                },
            )
            self.write_workflow_summary(
                runs,
                "event-retry",
                "workflow-20200102T000000Z",
                {
                    "status": {"download": "OK", "obs_validation": "OK", "process": "FAIL", "quality": "WARN", "plot": ""},
                    "counts": {"obs_files": 1, "kin_files": 1},
                },
            )

            rc = build_run_ledger.main(["--runs", str(runs), "--export-root", str(export_root), "--out", str(out)])

            self.assertEqual(rc, 0)
            with out.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            by_event = {row["event_id"]: row for row in rows}
            self.assertEqual(by_event["event-done"]["workflow_count"], "0")
            self.assertEqual(by_event["event-done"]["latest_status"], "OK")
            self.assertEqual(by_event["event-done"]["export_status"], "OK")
            self.assertEqual(by_event["event-done"]["next_action"], "DONE")
            self.assertEqual(by_event["event-retry"]["workflow_count"], "2")
            self.assertTrue(by_event["event-retry"]["latest_workflow"].endswith("workflow-20200102T000000Z"))
            self.assertEqual(by_event["event-retry"]["latest_status"], "RETRY_PROCESS")
            self.assertEqual(by_event["event-retry"]["quality_status"], "WARN")
            self.assertEqual(by_event["event-retry"]["kin_count"], "1")
            self.assertEqual(by_event["event-retry"]["failure_class"], "PROCESS_FAIL")
            self.assertEqual(by_event["event-retry"]["next_action"], "RERUN_PROCESS")

    def test_ledger_does_not_call_deep_export_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports" / "normalized-ok-stations-us-nz"
            self.write_valid_package(export_root / "us-event-done", "event-done")

            with patch("gzip.open", side_effect=AssertionError("waveforms scanned")):
                rows = build_run_ledger.build_rows(root / "runs", export_root)

            self.assertEqual(rows[0]["event_id"], "event-done")
            self.assertEqual(rows[0]["export_status"], "OK")

    def test_ledger_classifies_geonet_done_and_normalized_validation_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            export_root = root / "exports" / "normalized-ok-stations-us-nz"
            out = root / "run-ledger.tsv"
            self.write_valid_package(export_root / "nz-geonet-geonet-done", "geonet-done", source="geonet")
            self.write_workflow_summary(
                runs,
                "geonet-validation-fail",
                "workflow-20200102T000000Z",
                {
                    "status": {"process": "OK", "quality": "OK", "normalized": "OK", "normalized_validation": "FAIL"},
                    "counts": {"obs_files": 1, "kin_files": 1},
                },
            )

            rc = build_run_ledger.main(["--runs", str(runs), "--export-root", str(export_root), "--out", str(out)])

            self.assertEqual(rc, 0)
            with out.open(newline="", encoding="utf-8") as handle:
                rows = {row["event_id"]: row for row in csv.DictReader(handle, delimiter="\t")}

        self.assertEqual(rows["geonet-done"]["latest_status"], "OK")
        self.assertEqual(rows["geonet-done"]["export_status"], "OK")
        self.assertEqual(rows["geonet-done"]["next_action"], "DONE")
        self.assertEqual(rows["geonet-validation-fail"]["latest_status"], "RETRY_NORMALIZE")
        self.assertEqual(rows["geonet-validation-fail"]["failure_class"], "NORMALIZED_VALIDATION_FAIL")
        self.assertEqual(rows["geonet-validation-fail"]["next_action"], "RERUN_NORMALIZE")


if __name__ == "__main__":
    unittest.main()
