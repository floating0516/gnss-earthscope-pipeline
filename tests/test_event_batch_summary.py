from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.workflows import build_event_batch_summary


class EventBatchSummaryTest(unittest.TestCase):
    def test_summary_includes_normalized_and_export_package_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_csv = root / "data" / "batches" / "batch.csv"
            summary_tsv = root / "data" / "batches" / "batch-summary.tsv"
            workflow_reports = root / "runs" / "event-a" / "workflow-20200101T000000Z" / "reports"
            export_dir = root / "exports" / "normalized-ok-stations-us-nz" / "us-event-a"
            batch_csv.parent.mkdir(parents=True)
            workflow_reports.mkdir(parents=True)
            export_dir.mkdir(parents=True)

            batch_csv.write_text("event_id,event_time,stations,status\nevent-a,2020-01-01T00:00:00Z,ABCD,OK\n", encoding="utf-8")
            for name in ["event.json", "stations.csv", "waveforms.csv.gz"]:
                (export_dir / name).write_text("x", encoding="utf-8")
            (workflow_reports / "workflow-summary.json").write_text(
                json.dumps(
                    {
                        "status": {
                            "download": "OK",
                            "obs_validation": "OK",
                            "process": "OK",
                            "plot": "OK",
                            "quality": "WARN",
                            "cleanup": "OK",
                            "pride_cleanup": "OK",
                            "obs_cleanup": "OK",
                            "normalized": "OK",
                        },
                        "counts": {
                            "requested_stations": 1,
                            "obs_files": 1,
                            "kin_files": 1,
                            "plot_files": 2,
                            "normalized_stations": 1,
                            "normalized_waveform_rows": 120,
                        },
                        "paths": {
                            "workflow_dir": "@ROOT@/runs/event-a/workflow-20200101T000000Z",
                            "normalized_event_dir": "@ROOT@/exports/normalized-ok-stations-us-nz/us-event-a",
                            "normalized_event_grade": "C",
                        },
                        "duration_seconds": 10,
                        "quality": {"summary": {"ok_station_count": 1, "warn_station_count": 0, "fail_station_count": 0}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                rc = build_event_batch_summary.main(
                    [
                        "--csv",
                        str(batch_csv),
                        "--summary",
                        str(summary_tsv),
                        "--run-root",
                        str(root / "runs"),
                        "--pipeline-root",
                        str(root),
                    ]
                )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(rc, 0)
            with summary_tsv.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(rows[0]["normalized_status"], "OK")
            self.assertEqual(rows[0]["normalized_station_count"], "1")
            self.assertEqual(rows[0]["normalized_waveform_rows"], "120")
            self.assertEqual(rows[0]["normalized_event_grade"], "C")
            self.assertEqual(rows[0]["normalized_event_dir"], "@ROOT@/exports/normalized-ok-stations-us-nz/us-event-a")
            self.assertEqual(rows[0]["export_package_status"], "COMPLETE")

    def test_summary_leaves_export_status_blank_without_workflow_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_csv = root / "data" / "batches" / "batch.csv"
            summary_tsv = root / "data" / "batches" / "batch-summary.tsv"
            batch_csv.parent.mkdir(parents=True)
            batch_csv.write_text("event_id,event_time,stations,status\nevent-a,2020-01-01T00:00:00Z,ABCD,\n", encoding="utf-8")

            rc = build_event_batch_summary.main(
                [
                    "--csv",
                    str(batch_csv),
                    "--summary",
                    str(summary_tsv),
                    "--run-root",
                    str(root / "runs"),
                    "--pipeline-root",
                    str(root),
                ]
            )

            self.assertEqual(rc, 0)
            with summary_tsv.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(rows[0]["normalized_event_dir"], "")
            self.assertEqual(rows[0]["export_package_status"], "")


if __name__ == "__main__":
    unittest.main()
