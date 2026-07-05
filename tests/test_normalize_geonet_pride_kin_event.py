from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "normalize" / "normalize_geonet_pride_kin_event.py"
VALIDATOR_PATH = ROOT / "scripts" / "summaries" / "validate_normalized_export.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


validate_export = load_module(VALIDATOR_PATH, "validate_normalized_export")


def write_geonet_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE geonet_m6plus_events_nz (
                event_id TEXT PRIMARY KEY,
                title TEXT,
                time_utc TEXT NOT NULL,
                event_date TEXT NOT NULL,
                year INTEGER NOT NULL,
                doy INTEGER NOT NULL,
                magnitude REAL NOT NULL,
                mag_type TEXT,
                longitude REAL NOT NULL,
                latitude REAL NOT NULL,
                depth_km REAL,
                place TEXT,
                geonet_url TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE event_geonet_station_candidates (
                event_id TEXT NOT NULL,
                station TEXT NOT NULL,
                event_date TEXT NOT NULL,
                radius_km REAL NOT NULL,
                distance_km REAL NOT NULL,
                station_latitude REAL NOT NULL,
                station_longitude REAL NOT NULL,
                station9 TEXT,
                network TEXT,
                station_active_at_event INTEGER NOT NULL,
                availability_source TEXT NOT NULL,
                metadata_file TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO geonet_m6plus_events_nz
            VALUES (
                'geonet-test-event',
                'M6.1 - Test event',
                '2020-01-01T00:00:00Z',
                '2020-01-01',
                2020,
                1,
                6.1,
                'M',
                173.0,
                -42.0,
                12.0,
                'Test event',
                'https://www.geonet.org.nz/earthquake/geonet-test-event'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO event_geonet_station_candidates
            VALUES (
                'geonet-test-event',
                'WGTN',
                '2020-01-01',
                300.0,
                42.5,
                -41.2865,
                174.7762,
                'WGTN00NZL',
                'NZ',
                1,
                'test',
                'test.csv',
                '2020-01-01T00:00:00Z'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def write_workflow_summary(path: Path, kin_file: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent.parent / "manifests").mkdir(parents=True, exist_ok=True)
    (path.parent.parent / "manifests" / "kin-files.txt").write_text(f"{kin_file}\n", encoding="utf-8")
    path.write_text(
        json.dumps(
            {
                "source": "GeoNet",
                "event": {"id": "geonet-test-event", "time_utc": "2020-01-01T00:00:00Z"},
                "parameters": {"process_window_hours_each_side": 3.0, "interval_seconds": 1},
                "status": {"quality": "OK"},
                "files": {"kin": [str(kin_file)]},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def write_quality_json(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "kin-quality/v1",
                "thresholds": {"min_epochs": 60, "min_coverage_ratio": 0.8},
                "policy": {"allow_partial_failures": False},
                "summary": {"status": "OK", "station_count": 1, "ok_station_count": 1},
                "stations": [{"station": "WGTN", "quality_status": "OK", "quality_flags": ""}],
            }
        )
        + "\n",
        encoding="utf-8",
    )


class NormalizeGeoNetPrideKinEventTest(unittest.TestCase):
    def test_write_outputs_creates_strict_geonet_normalized_package(self):
        self.assertTrue(MODULE_PATH.exists(), f"missing normalizer: {MODULE_PATH}")
        normalize = load_module(MODULE_PATH, "normalize_geonet_pride_kin_event")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "geonet.sqlite"
            normalized_root = tmp_path / "normalized"
            workflow_summary = tmp_path / "workflow" / "reports" / "workflow-summary.json"
            quality_json = tmp_path / "workflow" / "reports" / "kin-quality.json"
            kin_file = tmp_path / "kin_2020001_wgtn"

            write_geonet_db(db_path)
            kin_file.write_text(
                "END OF HEADER\n"
                "58849 18 1000 2000 3000\n"
                "58849 19 1001 2001 3001\n",
                encoding="utf-8",
            )
            write_workflow_summary(workflow_summary, kin_file)
            write_quality_json(quality_json)

            args = type(
                "Args",
                (),
                {
                    "workflow_summary": workflow_summary,
                    "quality_json": quality_json,
                    "db": db_path,
                    "normalized_root": normalized_root,
                    "include_warn": True,
                    "overwrite": False,
                },
            )()

            result = normalize.write_outputs(
                args,
                normalize.load_json(workflow_summary),
                normalize.load_json(quality_json),
            )

            self.assertEqual(result["normalized_status"], "OK")
            self.assertEqual(result["normalized_station_count"], 1)
            self.assertEqual(result["normalized_waveform_rows"], 6)
            event_dir = Path(result["normalized_event_dir"])
            event = json.loads((event_dir / "event.json").read_text(encoding="utf-8"))
            provenance = json.loads((event_dir / "provenance.json").read_text(encoding="utf-8"))

            self.assertEqual(event["schema_version"], "normalized-event/v1")
            self.assertEqual(event["event_id"], "geonet-test-event")
            self.assertEqual(event["source"], "geonet")
            self.assertEqual(event["event_authority"], "GeoNet")
            self.assertEqual(event["station_authority"], "GeoNet")
            self.assertEqual(event["region"], "New Zealand")
            self.assertEqual(event["network"], "GeoNet")
            self.assertEqual(event["station_count"], 1)
            self.assertEqual(event["waveform_rows"], 6)

            self.assertEqual(provenance["schema_version"], "provenance/v1")
            self.assertEqual(provenance["source"]["name"], "geonet")
            self.assertEqual(provenance["source"]["event_authority"], "GeoNet")
            self.assertEqual(provenance["source"]["station_authority"], "GeoNet")
            self.assertIn("tools/geonet_downloader", provenance["source"]["downloader"])
            self.assertEqual(provenance["quality"]["summary_status"], "OK")
            self.assertEqual(provenance["quality"]["thresholds"]["min_epochs"], 60)

            with (event_dir / "stations.csv").open(newline="", encoding="utf-8") as handle:
                stations = list(csv.DictReader(handle))
            self.assertEqual(stations[0]["Station"], "WGTN")
            self.assertEqual(stations[0]["Distance_Km"], "42.500")

            with gzip.open(event_dir / "waveforms.csv.gz", "rt", newline="", encoding="utf-8") as handle:
                waveforms = list(csv.DictReader(handle))
            self.assertEqual(waveforms[0]["Station"], "WGTN")
            self.assertEqual(waveforms[0]["Time_UTC"], "2020-01-01T00:00:00Z")

            report = validate_export.validate_export(normalized_root, event_id="geonet-test-event")
            self.assertEqual(report["status"], "OK")
            self.assertEqual(report["event_count"], 1)


if __name__ == "__main__":
    unittest.main()
