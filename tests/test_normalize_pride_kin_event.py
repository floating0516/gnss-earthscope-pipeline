from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZE_DIR = ROOT / "scripts" / "normalize"
if str(NORMALIZE_DIR) not in sys.path:
    sys.path.insert(0, str(NORMALIZE_DIR))

import normalize_pride_kin_event as normalize


class NormalizePrideKinEventTest(unittest.TestCase):
    def test_read_event_supports_nonconus_event_table(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE usgs_m6plus_events_earthscope_nonconus (
                event_id TEXT PRIMARY KEY,
                title TEXT,
                time_utc TEXT,
                event_date TEXT,
                magnitude REAL,
                longitude REAL,
                latitude REAL,
                depth_km REAL,
                place TEXT,
                usgs_url TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO usgs_m6plus_events_earthscope_nonconus
            VALUES ('us7000i9bw', 'Mexico event', '2022-09-19T18:05:08Z', '2022-09-19', 7.6, -103.0, 18.0, 26.9, 'Mexico', 'https://example.invalid')
            """
        )

        event = normalize.read_event(conn, "us7000i9bw", "fallback")

        self.assertEqual(event["event_id"], "us7000i9bw")
        self.assertEqual(event["title"], "Mexico event")
        self.assertEqual(event["magnitude"], 7.6)

    def test_event_json_keeps_us_labels_for_usa_subset(self):
        payload = normalize.event_json(
            {
                "event_id": "nc123",
                "title": "US event",
                "time_utc": "2020-01-01T00:00:00Z",
                "longitude": -124.0,
                "latitude": 40.0,
                "depth_km": 10.0,
                "magnitude": 6.2,
                "place": "California",
                "usgs_url": "",
                "earthscope_subset": "usa",
            },
            1,
            Path("workflow-summary.json"),
            normalize.event_grade([{"Azimuth_Deg": ""}]),
            True,
        )

        self.assertEqual(payload["country"], "United States")
        self.assertEqual(payload["region"], "US")
        self.assertEqual(payload["earthscope_subset"], "usa")

    def test_event_json_uses_americas_labels_for_nonconus_subset(self):
        payload = normalize.event_json(
            {
                "event_id": "us7000irjd",
                "title": "Mexico event",
                "time_utc": "2022-11-22T16:39:05Z",
                "longitude": -116.4,
                "latitude": 30.8,
                "depth_km": 10.0,
                "magnitude": 6.2,
                "place": "Mexico",
                "usgs_url": "",
                "earthscope_subset": "nonconus",
            },
            1,
            Path("workflow-summary.json"),
            normalize.event_grade([{"Azimuth_Deg": ""}]),
            True,
        )

        self.assertEqual(payload["country"], "Americas")
        self.assertEqual(payload["region"], "Americas")
        self.assertEqual(payload["earthscope_subset"], "nonconus")

    def test_write_outputs_skips_quality_station_with_missing_coordinates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "events.sqlite"
            normalized_root = tmp_path / "normalized"
            workflow_summary = tmp_path / "workflow-summary.json"
            quality_json = tmp_path / "kin-quality.json"
            good_kin = tmp_path / "kin_2020001_good"
            missing_kin = tmp_path / "kin_2020001_miss"

            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE usgs_m6plus_events_earthscope_nonconus (
                    event_id TEXT PRIMARY KEY,
                    title TEXT,
                    time_utc TEXT,
                    event_date TEXT,
                    magnitude REAL,
                    longitude REAL,
                    latitude REAL,
                    depth_km REAL,
                    place TEXT,
                    usgs_url TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE event_earthscope_station_verified_files (
                    event_id TEXT,
                    station TEXT,
                    station_latitude REAL,
                    station_longitude REAL,
                    distance_km REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE event_earthscope_station_candidates (
                    event_id TEXT,
                    station TEXT,
                    station_latitude REAL,
                    station_longitude REAL,
                    distance_km REAL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO usgs_m6plus_events_earthscope_nonconus
                VALUES ('test-event', 'Test event', '2020-01-01T00:00:00Z', '2020-01-01', 6.1, -100.0, 20.0, 10.0, 'Test place', '')
                """
            )
            conn.execute(
                """
                INSERT INTO event_earthscope_station_candidates
                VALUES ('test-event', 'GOOD', 20.1, -100.1, 15.0)
                """
            )
            conn.commit()
            conn.close()

            kin_body = "END OF HEADER\n58849 86390 1000 2000 3000\n58850 10 1001 2001 3001\n"
            good_kin.write_text(kin_body, encoding="utf-8")
            missing_kin.write_text(kin_body, encoding="utf-8")
            workflow_summary.write_text(
                json.dumps(
                    {
                        "event": {"id": "test-event", "time_utc": "2020-01-01T00:00:00Z"},
                        "files": {"kin": [str(good_kin), str(missing_kin)]},
                    }
                ),
                encoding="utf-8",
            )
            quality_json.write_text(
                json.dumps(
                    {
                        "stations": [
                            {"station": "GOOD", "quality_status": "OK", "quality_flags": ""},
                            {"station": "MISS", "quality_status": "OK", "quality_flags": ""},
                        ],
                        "summary": {},
                    }
                ),
                encoding="utf-8",
            )

            args = type(
                "Args",
                (),
                {
                    "workflow_summary": workflow_summary,
                    "quality_json": quality_json,
                    "db": db_path,
                    "normalized_root": normalized_root,
                    "include_warn": True,
                },
            )()

            result = normalize.write_outputs(
                args,
                normalize.load_json(workflow_summary),
                normalize.load_json(quality_json),
            )

            self.assertEqual(result["normalized_status"], "OK")
            self.assertEqual(result["normalized_station_count"], 1)
            self.assertEqual(result["skipped_stations"], [{"station": "MISS", "reason": "missing_coordinates"}])
            stations_csv = Path(result["normalized_event_dir"]) / "stations.csv"
            self.assertIn("GOOD", stations_csv.read_text(encoding="utf-8"))
            event_json = json.loads((Path(result["normalized_event_dir"]) / "event.json").read_text(encoding="utf-8"))
            self.assertEqual(event_json["skipped_stations"], result["skipped_stations"])


if __name__ == "__main__":
    unittest.main()
