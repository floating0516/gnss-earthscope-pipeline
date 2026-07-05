from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "workflows" / "classify_batch_status.py"
SPEC = importlib.util.spec_from_file_location("classify_batch_status", MODULE_PATH)
classifier = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(classifier)


class ClassifyBatchStatusTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]], delimiter: str = ",") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_batch(self, path: Path, event_ids: list[str]) -> None:
        self.write_rows(
            path,
            [
                {
                    "event_id": event_id,
                    "event_time": f"2020-01-0{index + 1}T00:00:00Z",
                    "stations": "ABCD",
                    "status": "",
                }
                for index, event_id in enumerate(event_ids)
            ],
        )

    def write_workflow_summary(
        self,
        runs: Path,
        event_id: str,
        tag: str,
        *,
        status: dict[str, str],
        counts: dict[str, int] | None = None,
    ) -> Path:
        reports = runs / event_id / f"workflow-{tag}" / "reports"
        reports.mkdir(parents=True)
        summary = {
            "status": status,
            "counts": counts or {},
            "paths": {"workflow_dir": str(reports.parent)},
        }
        path = reports / "workflow-summary.json"
        path.write_text(json.dumps(summary) + "\n", encoding="utf-8")
        return path

    def write_valid_export_package(self, root: Path, event_id: str, *, source: str = "earthscope") -> None:
        package = root / (f"nz-geonet-{event_id}" if source == "geonet" else f"us-{event_id}")
        package.mkdir(parents=True)
        source_label = (
            "GeoNet PRIDE PPP-AR kin quality-passing stations"
            if source == "geonet"
            else "EarthScope PRIDE PPP-AR kin quality-passing stations"
        )
        event_authority = "GeoNet" if source == "geonet" else "USGS"
        station_authority = "GeoNet" if source == "geonet" else "EarthScope/GAGE"
        (package / "event.json").write_text(
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
        (package / "provenance.json").write_text(
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
        self.write_rows(package / "stations.csv", [{"Station": "ABCD", "Quality_Status": "OK"}])
        with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["Station", "Time_UTC"], lineterminator="\n")
            writer.writeheader()
            writer.writerow({"Station": "ABCD", "Time_UTC": "2020-01-01T00:00:00Z"})

    def test_classifies_done_from_valid_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch.csv"
            out = root / "classified.csv"
            self.write_batch(batch, ["event-ok"])
            self.write_valid_export_package(root / "exports", "event-ok")

            rows = classifier.classify_batch(batch, root / "runs", root / "exports")
            rc = classifier.main(["--batch", str(batch), "--runs", str(root / "runs"), "--export-root", str(root / "exports"), "--out", str(out)])

        self.assertEqual(rows[0]["final_status"], "OK")
        self.assertEqual(rows[0]["next_action"], "DONE")
        self.assertEqual(rc, 0)

    def test_classifies_no_obs_quality_fail_plot_retry_and_repeated_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch.csv"
            out = root / "classified.csv"
            event_ids = ["event-no-obs", "event-quality", "event-plot", "event-timeout"]
            self.write_batch(batch, event_ids)
            runs = root / "runs"
            exports = root / "exports"

            self.write_workflow_summary(
                runs,
                "event-no-obs",
                "20200101T000000Z",
                status={"download": "OK", "obs_validation": "FAIL", "process": "BLOCKED_OBS_VALIDATION"},
                counts={"obs_files": 0, "kin_files": 0},
            )
            self.write_workflow_summary(
                runs,
                "event-quality",
                "20200102T000000Z",
                status={"quality": "FAIL", "process": "OK", "normalized": "SKIPPED_QUALITY_FAIL"},
                counts={"obs_files": 1, "kin_files": 1},
            )
            self.write_workflow_summary(
                runs,
                "event-plot",
                "20200103T000000Z",
                status={"normalized": "OK", "plot": "FAIL"},
                counts={"obs_files": 1, "kin_files": 1},
            )
            for index in range(3):
                self.write_workflow_summary(
                    runs,
                    "event-timeout",
                    f"20200104T00000{index}Z",
                    status={"process": "TIMEOUT"},
                    counts={"obs_files": 1, "kin_files": 0},
                )

            rc = classifier.main(["--batch", str(batch), "--runs", str(runs), "--export-root", str(exports), "--out", str(out)])

            with out.open(newline="", encoding="utf-8") as handle:
                rows = {row["event_id"]: row for row in csv.DictReader(handle)}

        self.assertEqual(rc, 0)
        self.assertEqual(rows["event-no-obs"]["final_status"], "CLASSIFIED_NO_OBS")
        self.assertEqual(rows["event-quality"]["final_status"], "CLASSIFIED_QUALITY_FAIL")
        self.assertEqual(rows["event-plot"]["final_status"], "RETRY_PLOT")
        self.assertEqual(rows["event-timeout"]["final_status"], "ABANDONED_REPEATED_TIMEOUT")
        self.assertEqual(rows["event-timeout"]["failure_class"], "TIMEOUT")

    def test_classifies_geonet_done_and_normalized_validation_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch.csv"
            event_ids = ["geonet-done", "geonet-validation-fail", "geonet-normalize-fail"]
            self.write_batch(batch, event_ids)
            runs = root / "runs"
            exports = root / "exports"
            self.write_valid_export_package(exports, "geonet-done", source="geonet")
            self.write_workflow_summary(
                runs,
                "geonet-validation-fail",
                "20200102T000000Z",
                status={"process": "OK", "quality": "OK", "normalized": "OK", "normalized_validation": "FAIL"},
                counts={"obs_files": 1, "kin_files": 1},
            )
            self.write_workflow_summary(
                runs,
                "geonet-normalize-fail",
                "20200103T000000Z",
                status={"process": "OK", "quality": "OK", "normalized": "FAIL"},
                counts={"obs_files": 1, "kin_files": 1},
            )

            rows = {row["event_id"]: row for row in classifier.classify_batch(batch, runs, exports)}

        self.assertEqual(rows["geonet-done"]["final_status"], "OK")
        self.assertEqual(rows["geonet-done"]["next_action"], "DONE")
        self.assertEqual(rows["geonet-validation-fail"]["final_status"], "RETRY_NORMALIZE")
        self.assertEqual(rows["geonet-validation-fail"]["failure_class"], "NORMALIZED_VALIDATION_FAIL")
        self.assertEqual(rows["geonet-normalize-fail"]["final_status"], "RETRY_NORMALIZE")
        self.assertEqual(rows["geonet-normalize-fail"]["failure_class"], "NORMALIZE_FAIL")


if __name__ == "__main__":
    unittest.main()
