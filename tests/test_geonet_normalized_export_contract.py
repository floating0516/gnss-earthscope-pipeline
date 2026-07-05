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


def write_rows(path: Path, rows: list[dict[str, str]], delimiter: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class GeoNetNormalizedExportContractTest(unittest.TestCase):
    def test_geonet_package_uses_standard_normalized_export_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            event_id = "geonet-202603040102"
            event_dir = "nz-geonet-202603040102-m7-1-20260304-test-event"
            package = root / event_dir
            package.mkdir(parents=True)
            (package / "event.json").write_text(
                json.dumps(
                    {
                        "schema_version": "normalized-event/v1",
                        "event_id": event_id,
                        "source": "geonet",
                        "source_label": "GeoNet PRIDE PPP-AR kin quality-passing stations",
                        "event_authority": "GeoNet",
                        "station_authority": "GeoNet",
                        "event_time": "2026-03-04T01:02:03Z",
                        "date": "2026-03-04T01:02:03Z",
                        "latitude": -42.0,
                        "longitude": 173.0,
                        "depth_km": 12.0,
                        "magnitude": 7.1,
                        "magnitude_type": "M",
                        "region": "New Zealand",
                        "network": "GeoNet",
                        "station_count": 1,
                        "waveform_rows": 3,
                        "stations": 1,
                        "event_grade": "C",
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
                        "waveform_rows": 3,
                        "workflow": {
                            "name": "geonet-event-1hz-pride",
                            "script": "scripts/workflows/run_geonet_event_1hz_pride_workflow.sh",
                            "started_at": "2026-03-04T01:02:03Z",
                            "completed_at": "2026-03-04T01:12:03Z",
                            "git_commit": "",
                            "command": "",
                        },
                        "source": {
                            "name": "geonet",
                            "event_authority": "GeoNet",
                            "station_authority": "GeoNet",
                            "downloader": "tools/geonet_downloader/",
                        },
                        "processing": {
                            "pride_processor": "tools/pride_processor/process_event_window.sh",
                            "pdp3": "pdp3",
                            "crx2rnx": "CRX2RNX",
                            "window_hours": None,
                            "sampling_hz": ["1.0"],
                        },
                        "quality": {
                            "quality_json": "/tmp/geonet-quality.json",
                            "thresholds": {"min_epochs": 60, "min_coverage_ratio": 0.8},
                            "summary_status": "OK",
                        },
                        "inputs": ["/tmp/kin_2026063_wgtn"],
                        "outputs": ["event.json", "stations.csv", "waveforms.csv.gz", "provenance.json"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            write_rows(
                package / "stations.csv",
                [
                    {
                        "Station": "WGTN",
                        "Latitude": "-41.2865",
                        "Longitude": "174.7762",
                        "Sampling_Hz": "1.0",
                        "Waveform_Rows": "3",
                        "Quality_Status": "OK",
                    }
                ],
            )
            with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz", "Source_File"],
                    lineterminator="\n",
                )
                writer.writeheader()
                for component in ["E", "N", "U"]:
                    writer.writerow(
                        {
                            "Station": "WGTN",
                            "Time_UTC": "2026-03-04T01:02:03Z",
                            "Time_Offset_s": "0.0",
                            "Component": component,
                            "Value_m": "0.0",
                            "Sampling_Hz": "1.0",
                            "Source_File": "kin_2026063_wgtn",
                        }
                    )
            write_rows(
                root / "manifest.tsv",
                [
                    {
                        "region": "New Zealand",
                        "network": "GeoNet",
                        "event_id": event_id,
                        "event_dir": event_dir,
                        "event_time": "2026-03-04T01:02:03Z",
                        "magnitude": "7.1",
                        "place": "Test event",
                        "stations_included": "1",
                        "waveform_rows": "3",
                        "event_grade": "C",
                    }
                ],
                delimiter="\t",
            )
            write_rows(
                root / "event_summary.csv",
                [
                    {
                        "event_id": event_id,
                        "event_dir": event_dir,
                        "origin_time": "2026-03-04T01:02:03Z",
                        "longitude": "173.0",
                        "latitude": "-42.0",
                        "depth_km": "12.0",
                        "magnitude": "7.1",
                        "place": "Test event",
                        "region": "New Zealand",
                        "country": "New Zealand",
                        "network": "GeoNet",
                        "station_count": "1",
                        "waveform_rows": "3",
                        "event_grade": "C",
                    }
                ],
            )
            write_rows(
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

            report = validate_export.validate_export(root, strict=True)

        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["packages"][0]["event_id"], event_id)


if __name__ == "__main__":
    unittest.main()
