from __future__ import annotations

import csv
import gzip
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from gnss_eq import cli


class CliWorklistTest(unittest.TestCase):
    def write_valid_package(self, package_dir: Path, event_id: str, *, source: str = "earthscope") -> None:
        package_dir.mkdir(parents=True, exist_ok=True)
        source_label = (
            "GeoNet PRIDE PPP-AR kin quality-passing stations"
            if source == "geonet"
            else "EarthScope PRIDE PPP-AR kin quality-passing stations"
        )
        event_authority = "GeoNet" if source == "geonet" else "USGS"
        station_authority = "GeoNet" if source == "geonet" else "EarthScope/GAGE"
        (package_dir / "event.json").write_text(
            json.dumps(
                {
                    "schema_version": "normalized-event/v1",
                    "event_id": event_id,
                    "source": source,
                    "source_label": source_label,
                    "event_authority": event_authority,
                    "station_authority": station_authority,
                    "event_time": "2020-01-01T00:00:00Z",
                    "latitude": 1.0,
                    "longitude": 2.0,
                    "depth_km": 10.0,
                    "magnitude": 6.1,
                    "magnitude_type": "",
                    "region": "New Zealand" if source == "geonet" else "US",
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
                        "name": source,
                        "event_authority": event_authority,
                        "station_authority": station_authority,
                        "downloader": "tools/geonet_downloader/" if source == "geonet" else "tools/earthscope_downloader/download_event_window.py",
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

    def write_workflow_summary(self, runs_root: Path, event_id: str, payload: dict[str, object]) -> None:
        reports = runs_root / event_id / "workflow-20200101T000000Z" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "workflow-summary.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def test_worklist_labels_ready_retry_and_done_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch.csv"
            runs = root / "runs"
            export_root = root / "exports" / "normalized-ok-stations-us-nz"
            export_root.mkdir(parents=True)
            batch.write_text(
                "\n".join(
                    [
                        "event_id,event_time,stations,status",
                        "event-ready,2020-01-01T00:00:00Z,ABCD,",
                        "event-retry,2020-01-02T00:00:00Z,ABCD,FAIL",
                        "event-done,2020-01-03T00:00:00Z,ABCD,OK",
                        "geonet-done,2020-01-04T00:00:00Z,WGTN,OK",
                        "geonet-validation-fail,2020-01-05T00:00:00Z,WGTN,FAIL",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.write_workflow_summary(
                runs,
                "event-retry",
                {
                    "status": {"download": "OK", "obs_validation": "OK", "process": "FAIL"},
                    "counts": {"obs_files": 1, "kin_files": 1},
                },
            )
            self.write_valid_package(export_root / "us-event-done", "event-done")
            self.write_valid_package(export_root / "nz-geonet-geonet-done", "geonet-done", source="geonet")
            self.write_workflow_summary(
                runs,
                "geonet-validation-fail",
                {
                    "status": {"download": "OK", "obs_validation": "OK", "process": "OK", "quality": "OK", "normalized": "OK", "normalized_validation": "FAIL"},
                    "counts": {"obs_files": 1, "kin_files": 1},
                },
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = cli.main(
                    [
                        "worklist",
                        "--batch",
                        str(batch),
                        "--runs",
                        str(runs),
                        "--export-root",
                        str(export_root),
                    ]
                )

            self.assertEqual(rc, 0)
            rows = list(csv.DictReader(io.StringIO(stdout.getvalue()), delimiter="\t"))
            by_event = {row["event_id"]: row for row in rows}
            self.assertEqual(by_event["event-ready"]["worklist_status"], "READY_TO_RUN")
            self.assertEqual(by_event["event-ready"]["next_action"], "RUN_WORKFLOW")
            self.assertEqual(by_event["event-retry"]["worklist_status"], "READY_TO_RETRY")
            self.assertEqual(by_event["event-retry"]["next_action"], "RERUN_PROCESS")
            self.assertEqual(by_event["event-done"]["worklist_status"], "DONE")
            self.assertEqual(by_event["event-done"]["next_action"], "DONE")
            self.assertEqual(by_event["geonet-done"]["worklist_status"], "DONE")
            self.assertEqual(by_event["geonet-done"]["next_action"], "DONE")
            self.assertEqual(by_event["geonet-validation-fail"]["worklist_status"], "READY_TO_RETRY")
            self.assertEqual(by_event["geonet-validation-fail"]["next_action"], "RERUN_NORMALIZE")


if __name__ == "__main__":
    unittest.main()
