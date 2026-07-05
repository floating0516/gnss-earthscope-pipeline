from __future__ import annotations

import csv
import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.workflows import build_event_batch_summary


class EventBatchSummaryTest(unittest.TestCase):
    def write_valid_package(self, package_dir: Path, event_id: str) -> None:
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "event.json").write_text(
            json.dumps(
                {
                    "schema_version": "normalized-event/v1",
                    "event_id": event_id,
                    "source": "earthscope",
                    "source_label": "EarthScope PRIDE PPP-AR kin quality-passing stations",
                    "event_authority": "USGS",
                    "station_authority": "EarthScope/GAGE",
                    "event_time": "2020-01-01T00:00:00Z",
                    "latitude": 1.0,
                    "longitude": 2.0,
                    "depth_km": 10.0,
                    "magnitude": 6.1,
                    "magnitude_type": "",
                    "region": "US",
                    "station_count": 1,
                    "waveform_rows": 1,
                }
            )
            + "\n",
            encoding="utf-8",
        )
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
        (package_dir / "provenance.json").write_text(
            json.dumps(
                {
                    "schema_version": "provenance/v1",
                    "event_id": event_id,
                    "station_count": 1,
                    "waveform_rows": 1,
                    "workflow": {
                        "name": "earthscope-event-1hz-pride",
                        "script": "scripts/workflows/run_event_1hz_pride_workflow.sh",
                        "started_at": "2020-01-01T00:00:00Z",
                        "completed_at": "2020-01-01T00:10:00Z",
                        "git_commit": "",
                        "command": "",
                    },
                    "source": {
                        "name": "earthscope",
                        "event_authority": "USGS",
                        "station_authority": "EarthScope/GAGE",
                        "downloader": "tools/earthscope_downloader/download_event_window.py",
                    },
                    "processing": {
                        "pride_processor": "tools/pride_processor/process_event_window.sh",
                        "pdp3": "pdp3",
                        "crx2rnx": "CRX2RNX",
                        "window_hours": None,
                        "sampling_hz": ["1.0"],
                    },
                    "quality": {
                        "quality_json": "/tmp/quality.json",
                        "thresholds": {"min_epochs": 60},
                        "summary_status": "OK",
                    },
                    "inputs": ["/tmp/kin_2020001_abcd"],
                    "outputs": ["event.json", "stations.csv", "waveforms.csv.gz", "provenance.json"],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_summary_includes_normalized_and_export_package_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_csv = root / "data" / "batches" / "batch.csv"
            summary_tsv = root / "data" / "batches" / "batch-summary.tsv"
            workflow_reports = root / "runs" / "event-a" / "workflow-20200101T000000Z" / "reports"
            export_dir = root / "exports" / "normalized-ok-stations-us-nz" / "us-event-a"
            batch_csv.parent.mkdir(parents=True)
            workflow_reports.mkdir(parents=True)

            batch_csv.write_text("event_id,event_time,stations,status\nevent-a,2020-01-01T00:00:00Z,ABCD,OK\n", encoding="utf-8")
            self.write_valid_package(export_dir, "event-a")
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
            self.assertEqual(rows[0]["normalized_exists"], "yes")
            self.assertEqual(rows[0]["export_valid"], "yes")
            self.assertEqual(rows[0]["waveform_rows"], "120")
            self.assertEqual(rows[0]["event_grade"], "C")
            self.assertEqual(rows[0]["kin_count"], "1")
            self.assertEqual(rows[0]["latest_failure_reason"], "")
            self.assertEqual(rows[0]["suggested_next_action"], "DONE")

    def test_summary_suggests_classification_for_missing_obs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_csv = root / "data" / "batches" / "batch.csv"
            summary_tsv = root / "data" / "batches" / "batch-summary.tsv"
            workflow_reports = root / "runs" / "event-a" / "workflow-20200101T000000Z" / "reports"
            batch_csv.parent.mkdir(parents=True)
            workflow_reports.mkdir(parents=True)

            batch_csv.write_text("event_id,event_time,stations,status\nevent-a,2020-01-01T00:00:00Z,ABCD,FAIL\n", encoding="utf-8")
            (workflow_reports / "workflow-summary.json").write_text(
                json.dumps(
                    {
                        "status": {
                            "download": "OK",
                            "obs_validation": "FAIL",
                            "process": "BLOCKED_OBS_VALIDATION",
                            "quality": "",
                            "normalized": "",
                            "plot": "",
                        },
                        "counts": {"requested_stations": 1, "obs_files": 0, "kin_files": 0},
                        "paths": {"workflow_dir": "@ROOT@/runs/event-a/workflow-20200101T000000Z"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

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
            self.assertEqual(rows[0]["normalized_exists"], "")
            self.assertEqual(rows[0]["export_valid"], "no")
            self.assertEqual(rows[0]["kin_count"], "0")
            self.assertEqual(rows[0]["latest_failure_reason"], "NO_OBS")
            self.assertEqual(rows[0]["suggested_next_action"], "CLASSIFY_NO_OBS")

    def test_summary_accepts_cddis_normalize_status_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch_csv = root / "data" / "batches" / "batch.csv"
            summary_tsv = root / "data" / "batches" / "batch-summary.tsv"
            workflow_reports = root / "runs" / "event-a" / "workflow-20200101T000000Z" / "reports"
            batch_csv.parent.mkdir(parents=True)
            workflow_reports.mkdir(parents=True)

            batch_csv.write_text("event_id,event_time,stations,status\nevent-a,2020-01-01T00:00:00Z,ABCD,OK\n", encoding="utf-8")
            (workflow_reports / "workflow-summary.json").write_text(
                json.dumps(
                    {
                        "status": {
                            "download": "OK",
                            "process": "OK",
                            "quality": "OK",
                            "normalize": "OK",
                            "plot": "OK",
                        },
                        "counts": {},
                        "paths": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

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
            self.assertEqual(rows[0]["normalized_status"], "OK")

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
