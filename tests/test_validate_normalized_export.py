from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "summaries" / "validate_normalized_export.py"
SPEC = importlib.util.spec_from_file_location("validate_normalized_export", MODULE_PATH)
validate_export = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_export)


class ValidateNormalizedExportTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]], delimiter: str = ",") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_package(
        self,
        root: Path,
        event_id: str = "event-a",
        event_dir: str = "us-event-a",
        *,
        legacy_schema: bool = False,
        event_overrides: dict | None = None,
        provenance_overrides: dict | None = None,
    ) -> Path:
        package = root / event_dir
        package.mkdir(parents=True)
        event_payload = {
            "schema_version": "normalized-event/v1",
            "event_id": event_id,
            "source": "earthscope",
            "source_label": "EarthScope PRIDE PPP-AR kin quality-passing stations",
            "event_authority": "USGS",
            "station_authority": "EarthScope/GAGE",
            "event_time": "2020-01-01T00:00:00Z",
            "date": "2020-01-01T00:00:00Z",
            "latitude": 1.0,
            "longitude": 2.0,
            "depth_km": 10.0,
            "magnitude": 6.1,
            "magnitude_type": "",
            "region": "US",
            "network": "EarthScope",
            "station_count": 1,
            "waveform_rows": 2,
            "stations": 1,
            "event_grade": "C",
        }
        provenance_payload = {
            "schema_version": "provenance/v1",
            "event_id": event_id,
            "station_count": 1,
            "waveform_rows": 2,
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
                "thresholds": {"min_epochs": 60, "min_coverage_ratio": 0.8},
                "summary_status": "OK",
            },
            "quality_summary": {"status": "OK", "station_count": 1, "ok_station_count": 1},
            "inputs": ["/tmp/kin_2020001_abcd"],
            "outputs": ["event.json", "stations.csv", "waveforms.csv.gz", "provenance.json"],
        }
        if legacy_schema:
            event_payload = {
                "event_id": event_id,
                "date": "2020-01-01T00:00:00Z",
                "magnitude": 6.1,
                "stations": 1,
                "region": "US",
                "network": "EarthScope",
            }
            provenance_payload = {"event_id": event_id, "station_count": 1, "waveform_rows": 2}
        if event_overrides:
            event_payload.update(event_overrides)
        if provenance_overrides:
            provenance_payload.update(provenance_overrides)
        (package / "event.json").write_text(
            json.dumps(event_payload) + "\n",
            encoding="utf-8",
        )
        (package / "provenance.json").write_text(
            json.dumps(provenance_payload) + "\n",
            encoding="utf-8",
        )
        self.write_rows(
            package / "stations.csv",
            [
                {
                    "Station": "ABCD",
                    "Latitude": "1.0",
                    "Longitude": "2.0",
                    "Sampling_Hz": "1.0",
                    "Waveform_Rows": "2",
                    "Quality_Status": "OK",
                }
            ],
        )
        with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz"],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "Station": "ABCD",
                    "Time_UTC": "2020-01-01T00:00:00Z",
                    "Time_Offset_s": "0",
                    "Component": "E",
                    "Value_m": "0.0",
                    "Sampling_Hz": "1.0",
                }
            )
            writer.writerow(
                {
                    "Station": "ABCD",
                    "Time_UTC": "2020-01-01T00:00:01Z",
                    "Time_Offset_s": "1",
                    "Component": "N",
                    "Value_m": "0.0",
                    "Sampling_Hz": "1.0",
                }
            )
        return package

    def write_indexes(self, root: Path, event_id: str = "event-a", event_dir: str = "us-event-a") -> None:
        self.write_rows(
            root / "manifest.tsv",
            [
                {
                    "region": "US",
                    "network": "EarthScope",
                    "event_id": event_id,
                    "event_dir": event_dir,
                    "event_time": "2020-01-01T00:00:00Z",
                    "magnitude": "6.1",
                    "place": "Test event",
                    "stations_included": "1",
                    "ok_stations_included": "1",
                    "warn_stations_included": "0",
                    "waveform_rows": "2",
                    "event_grade": "C",
                    "quality_filter": "quality_status in OK,WARN",
                    "workflow_summary": "",
                    "stations": "ABCD",
                }
            ],
            delimiter="\t",
        )
        self.write_rows(
            root / "event_summary.csv",
            [
                {
                    "event_id": event_id,
                    "event_dir": event_dir,
                    "origin_time": "2020-01-01T00:00:00Z",
                    "longitude": "2.0",
                    "latitude": "1.0",
                    "depth_km": "10.0",
                    "magnitude": "6.1",
                    "place": "Test event",
                    "region": "US",
                    "country": "United States",
                    "network": "EarthScope",
                    "station_count": "1",
                    "ok_station_count": "1",
                    "warn_station_count": "0",
                    "waveform_rows": "2",
                    "event_grade": "C",
                }
            ],
        )
        self.write_rows(
            root / "file_inventory.tsv",
            [
                {
                    "event_dir": event_dir,
                    "event.json": "yes",
                    "stations.csv": "yes",
                    "provenance.json": "yes",
                    "waveforms.csv.gz": "yes",
                    "complete": "yes",
                }
            ],
            delimiter="\t",
        )

    def make_valid_export(self, root: Path) -> None:
        self.write_package(root)
        self.write_indexes(root)

    def test_valid_export_succeeds_and_reports_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_valid_export(root)

            report = validate_export.validate_export(root)

        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["error_count"], 0)

    def test_missing_package_file_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_valid_export(root)
            (root / "us-event-a" / "provenance.json").unlink()

            report = validate_export.validate_export(root)

        self.assertEqual(report["status"], "INVALID")
        self.assertGreater(report["error_count"], 0)
        self.assertTrue(any("provenance.json" in error["message"] for error in report["errors"]))

    def test_event_id_mode_validates_package_before_indexes_are_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_package(root, event_id="event-a", event_dir="us-event-a")

            report = validate_export.validate_export(root, event_id="event-a")

        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["packages"][0]["event_dir"], "us-event-a")

    def test_event_id_mode_rejects_legacy_event_and_provenance_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_package(root, event_id="event-a", event_dir="us-event-a", legacy_schema=True)

            report = validate_export.validate_export(root, event_id="event-a")

        self.assertEqual(report["status"], "INVALID")
        self.assertTrue(any(error["code"] == "EVENT_SCHEMA_INVALID" for error in report["errors"]))
        self.assertTrue(any(error["code"] == "PROVENANCE_SCHEMA_INVALID" for error in report["errors"]))

    def test_strict_dataset_validation_rejects_legacy_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_package(root, legacy_schema=True)
            self.write_indexes(root)

            report = validate_export.validate_export(root, strict=True)

        self.assertEqual(report["status"], "INVALID")
        self.assertTrue(any(error["code"] == "EVENT_SCHEMA_INVALID" for error in report["errors"]))

    def test_non_strict_dataset_validation_allows_legacy_schema_during_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_package(root, legacy_schema=True)
            self.write_indexes(root)

            report = validate_export.validate_export(root)

        self.assertEqual(report["status"], "OK")

    def test_schema_validation_requires_core_event_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_package(
                root,
                event_overrides={
                    "schema_version": "normalized-event/v1",
                    "source": "",
                    "event_time": "",
                    "station_count": "one",
                    "waveform_rows": -1,
                },
            )

            report = validate_export.validate_export(root, event_id="event-a")

        messages = "\n".join(error["message"] for error in report["errors"] if error["code"] == "EVENT_SCHEMA_INVALID")
        self.assertEqual(report["status"], "INVALID")
        self.assertIn("source", messages)
        self.assertIn("event_time", messages)
        self.assertIn("station_count", messages)
        self.assertIn("waveform_rows", messages)

    def test_schema_validation_requires_core_provenance_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_package(
                root,
                provenance_overrides={
                    "schema_version": "provenance/v1",
                    "workflow": {},
                    "source": {},
                    "processing": {},
                    "quality": {},
                    "inputs": "not-a-list",
                    "outputs": "not-a-list",
                },
            )

            report = validate_export.validate_export(root, event_id="event-a")

        messages = "\n".join(error["message"] for error in report["errors"] if error["code"] == "PROVENANCE_SCHEMA_INVALID")
        self.assertEqual(report["status"], "INVALID")
        self.assertIn("workflow.name", messages)
        self.assertIn("source.name", messages)
        self.assertIn("processing.sampling_hz", messages)
        self.assertIn("quality.thresholds", messages)
        self.assertIn("inputs", messages)
        self.assertIn("outputs", messages)

    def test_index_event_set_mismatch_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_valid_export(root)
            self.write_rows(
                root / "event_summary.csv",
                [{"event_id": "other-event", "event_dir": "us-event-a"}],
            )

            report = validate_export.validate_export(root)

        self.assertEqual(report["status"], "INVALID")
        self.assertTrue(any(error["code"] == "EVENT_SET_MISMATCH" for error in report["errors"]))

    def test_file_inventory_missing_reference_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_valid_export(root)
            self.write_rows(
                root / "file_inventory.tsv",
                [
                    {
                        "event_dir": "us-event-a",
                        "file": "us-event-a/missing-extra.txt",
                    }
                ],
                delimiter="\t",
            )

            report = validate_export.validate_export(root)

        self.assertEqual(report["status"], "INVALID")
        self.assertTrue(any(error["code"] == "FILE_INVENTORY_MISSING_FILE" for error in report["errors"]))

    def test_station_without_waveform_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_valid_export(root)
            with gzip.open(root / "us-event-a" / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz"],
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Station": "WXYZ",
                        "Time_UTC": "2020-01-01T00:00:00Z",
                        "Time_Offset_s": "0",
                        "Component": "E",
                        "Value_m": "0.0",
                        "Sampling_Hz": "1.0",
                    }
                )

            report = validate_export.validate_export(root)

        self.assertEqual(report["status"], "INVALID")
        self.assertTrue(any(error["code"] == "STATION_WITHOUT_WAVEFORM" for error in report["errors"]))

    def test_cli_writes_json_report_and_returns_nonzero_for_invalid_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_out = root / "report.json"
            self.make_valid_export(root)
            (root / "manifest.tsv").unlink()

            rc = validate_export.main(["--root", str(root), "--json-out", str(json_out)])

            payload = json.loads(json_out.read_text(encoding="utf-8"))

        self.assertEqual(rc, 1)
        self.assertEqual(payload["status"], "INVALID")
        self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()
