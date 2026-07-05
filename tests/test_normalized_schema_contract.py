from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "summaries" / "validate_normalized_export.py"
SPEC = importlib.util.spec_from_file_location("validate_normalized_export", MODULE_PATH)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


SOURCES = {
    "earthscope": {
        "event_id": "us-earthscope-schema",
        "event_dir": "us-earthscope-schema-m6-5-20200101-test",
        "network": "EarthScope",
        "region": "US",
        "country": "United States",
        "event_authority": "USGS",
        "station_authority": "EarthScope/GAGE",
        "downloader": "tools/earthscope_downloader/download_event_window.py",
        "workflow": "scripts/workflows/run_event_1hz_pride_workflow.sh",
        "station": "P123",
    },
    "geonet": {
        "event_id": "geonet-schema",
        "event_dir": "nz-geonet-schema-m6-5-20200101-test",
        "network": "GeoNet",
        "region": "New Zealand",
        "country": "New Zealand",
        "event_authority": "GeoNet",
        "station_authority": "GeoNet",
        "downloader": "tools/geonet_downloader/",
        "workflow": "scripts/workflows/run_geonet_event_1hz_pride_workflow.sh",
        "station": "WGTN",
    },
    "cddis": {
        "event_id": "cddis-schema",
        "event_dir": "cddis-schema-m6-5-20200101-test",
        "network": "NASA CDDIS",
        "region": "Global CDDIS",
        "country": "Global",
        "event_authority": "USGS",
        "station_authority": "IGS/CDDIS",
        "downloader": "tools/cddis_downloader/download_cddis_event_window.py",
        "workflow": "scripts/workflows/run_cddis_event_1hz_pride_workflow.sh",
        "station": "ABMF",
    },
}


def write_rows(path: Path, rows: list[dict[str, str]], delimiter: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_source_package(root: Path, source_name: str, config: dict[str, str]) -> None:
    package = root / config["event_dir"]
    package.mkdir(parents=True)
    event_time = "2020-01-01T00:00:00Z"
    event_payload = {
        "schema_version": "normalized-event/v1",
        "event_id": config["event_id"],
        "source": source_name,
        "source_label": f"{config['network']} PRIDE PPP-AR kin quality-passing stations",
        "event_authority": config["event_authority"],
        "station_authority": config["station_authority"],
        "event_time": event_time,
        "date": event_time,
        "latitude": 1.0,
        "longitude": 2.0,
        "depth_km": 10.0,
        "magnitude": 6.5,
        "magnitude_type": "M",
        "region": config["region"],
        "country": config["country"],
        "network": config["network"],
        "station_count": 1,
        "waveform_rows": 3,
        "stations": 1,
        "event_grade": "C",
    }
    provenance_payload = {
        "schema_version": "provenance/v1",
        "event_id": config["event_id"],
        "station_count": 1,
        "waveform_rows": 3,
        "workflow": {
            "name": f"{source_name}-event-1hz-pride",
            "script": config["workflow"],
            "started_at": event_time,
            "completed_at": "2020-01-01T00:10:00Z",
            "git_commit": "",
            "command": "",
        },
        "source": {
            "name": source_name,
            "event_authority": config["event_authority"],
            "station_authority": config["station_authority"],
            "downloader": config["downloader"],
        },
        "processing": {
            "pride_processor": "tools/pride_processor/process_event_window.sh",
            "pdp3": "pdp3",
            "crx2rnx": "CRX2RNX",
            "window_hours": None,
            "sampling_hz": ["1.0"],
        },
        "quality": {
            "quality_json": f"/tmp/{source_name}-quality.json",
            "thresholds": {"min_epochs": 60, "min_coverage_ratio": 0.8},
            "summary_status": "OK",
        },
        "inputs": [f"/tmp/kin_2020001_{config['station'].lower()}"],
        "outputs": ["event.json", "stations.csv", "waveforms.csv.gz", "provenance.json"],
    }
    (package / "event.json").write_text(json.dumps(event_payload, indent=2) + "\n", encoding="utf-8")
    (package / "provenance.json").write_text(json.dumps(provenance_payload, indent=2) + "\n", encoding="utf-8")
    write_rows(
        package / "stations.csv",
        [
            {
                "Station": config["station"],
                "Latitude": "1.0",
                "Longitude": "2.0",
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
                    "Station": config["station"],
                    "Time_UTC": event_time,
                    "Time_Offset_s": "0.0",
                    "Component": component,
                    "Value_m": "0.0",
                    "Sampling_Hz": "1.0",
                    "Source_File": f"kin_2020001_{config['station'].lower()}",
                }
            )


class NormalizedSchemaContractTest(unittest.TestCase):
    def test_earthscope_geonet_and_cddis_packages_share_schema_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_rows = []
            summary_rows = []
            inventory_rows = []
            for source_name, config in SOURCES.items():
                write_source_package(root, source_name, config)
                manifest_rows.append(
                    {
                        "region": config["region"],
                        "network": config["network"],
                        "event_id": config["event_id"],
                        "event_dir": config["event_dir"],
                        "event_time": "2020-01-01T00:00:00Z",
                        "magnitude": "6.5",
                        "place": "Schema test",
                        "stations_included": "1",
                        "waveform_rows": "3",
                        "event_grade": "C",
                    }
                )
                summary_rows.append(
                    {
                        "event_id": config["event_id"],
                        "event_dir": config["event_dir"],
                        "origin_time": "2020-01-01T00:00:00Z",
                        "longitude": "2.0",
                        "latitude": "1.0",
                        "depth_km": "10.0",
                        "magnitude": "6.5",
                        "place": "Schema test",
                        "region": config["region"],
                        "country": config["country"],
                        "network": config["network"],
                        "station_count": "1",
                        "waveform_rows": "3",
                        "event_grade": "C",
                    }
                )
                inventory_rows.append(
                    {
                        "event_dir": config["event_dir"],
                        "event.json": "yes",
                        "stations.csv": "yes",
                        "provenance.json": "yes",
                        "waveforms.csv.gz": "yes",
                        "complete": "yes",
                    }
                )

            write_rows(root / "manifest.tsv", manifest_rows, delimiter="\t")
            write_rows(root / "event_summary.csv", summary_rows)
            write_rows(root / "file_inventory.tsv", inventory_rows, delimiter="\t")

            report = validator.validate_export(root, strict=True)

        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["event_count"], 3)
        self.assertEqual({package["event_schema_version"] for package in report["packages"]}, {"normalized-event/v1"})
        self.assertEqual({package["provenance_schema_version"] for package in report["packages"]}, {"provenance/v1"})


if __name__ == "__main__":
    unittest.main()
