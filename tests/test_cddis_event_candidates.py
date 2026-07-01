from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "availability" / "rebuild_cddis_event_station_candidates.py"
SPEC = importlib.util.spec_from_file_location("rebuild_cddis_event_station_candidates", SCRIPT_PATH)
rebuild_cddis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["rebuild_cddis_event_station_candidates"] = rebuild_cddis
SPEC.loader.exec_module(rebuild_cddis)


def seed_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE cddis_highrate_files (
                station4 TEXT NOT NULL,
                station9 TEXT NOT NULL,
                year INTEGER NOT NULL,
                doy INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                start_time_utc TEXT NOT NULL,
                end_time_utc TEXT NOT NULL,
                filename TEXT NOT NULL,
                url TEXT NOT NULL PRIMARY KEY,
                source TEXT NOT NULL,
                scan_id INTEGER NOT NULL,
                discovered_at TEXT NOT NULL
            );
            CREATE TABLE cddis_stations (
                station4 TEXT PRIMARY KEY,
                station9 TEXT NOT NULL,
                marker_name TEXT NOT NULL,
                marker_number TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                elevation_m REAL NOT NULL,
                x_m REAL NOT NULL,
                y_m REAL NOT NULL,
                z_m REAL NOT NULL,
                receiver_type TEXT NOT NULL,
                antenna_type TEXT NOT NULL,
                source_file TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE cddis_events (
                event_id TEXT PRIMARY KEY,
                event_time_utc TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                magnitude REAL,
                place TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO cddis_highrate_files VALUES (
                'DAEJ', 'DAEJ174X0', 2026, 174, 23,
                '2026-06-23T23:00:00Z', '2026-06-23T23:15:00Z',
                'daej174x00.26o.gz',
                'https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/daej174x00.26o.gz',
                'CDDIS highrate GNSS', 1, '2026-06-24T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO cddis_stations VALUES (
                'DAEJ', 'DAEJ174X0', 'DAEJ', '23902M002',
                36.3994271208407, 127.37449155786193, 116.08855598326772,
                -3120042.5551, 4084613.8142, 3764026.3252,
                'TRIMBLE NETR9', 'TRM59800.00     SCIS',
                'data/cddis_highrate/smoke/files/daej174x00.26o.gz',
                '2026-06-24T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO cddis_events VALUES (
                'db-event', '2026-06-23T23:07:30Z',
                36.3994271208407, 127.37449155786193, 6.5, 'test place', 'now'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class CddisEventCandidatesTest(unittest.TestCase):
    def test_haversine_zero_distance(self):
        distance = rebuild_cddis.haversine_km(36.3994271208407, 127.37449155786193, 36.3994271208407, 127.37449155786193)

        self.assertAlmostEqual(distance, 0.0, places=6)

    def test_main_writes_candidate_rows_by_radius(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_db(db)

            rc = rebuild_cddis.main(
                [
                    "--db",
                    str(db),
                    "--event-id",
                    "test-event",
                    "--event-time",
                    "2026-06-23T23:00:00Z",
                    "--latitude",
                    "36.3994271208407",
                    "--longitude",
                    "127.37449155786193",
                    "--radius-km",
                    "1",
                    "--radius-km",
                    "1000",
                    "--clear-event",
                ]
            )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                event = conn.execute("SELECT * FROM cddis_events WHERE event_id = 'test-event'").fetchone()
                rows = conn.execute("SELECT * FROM event_cddis_station_candidates ORDER BY radius_km").fetchall()
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(event["event_id"], "test-event")
        self.assertEqual(len(rows), 2)
        self.assertEqual([row["radius_km"] for row in rows], [1.0, 1000.0])
        self.assertEqual(rows[0]["station4"], "DAEJ")
        self.assertAlmostEqual(rows[0]["distance_km"], 0.0, places=6)
        self.assertEqual(rows[0]["available_file_count"], 1)
        self.assertIn("daej174x00.26o.gz", rows[0]["filenames"])

    def test_batch_rebuild_reads_events_from_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_db(db)

            rc = rebuild_cddis.main(
                [
                    "--db",
                    str(db),
                    "--radius-km",
                    "1",
                    "--clear-event",
                ]
            )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute("SELECT * FROM event_cddis_station_candidates").fetchall()
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_id"], "db-event")
        self.assertEqual(rows[0]["window_start_utc"], "2026-06-23T23:00:00Z")
        self.assertEqual(rows[0]["window_end_utc"], "2026-06-23T23:15:00Z")

    def test_candidate_window_can_exclude_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_db(db)

            rc = rebuild_cddis.main(
                [
                    "--db",
                    str(db),
                    "--event-id",
                    "late-event",
                    "--event-time",
                    "2026-06-23T23:30:00Z",
                    "--latitude",
                    "36.3994271208407",
                    "--longitude",
                    "127.37449155786193",
                    "--radius-km",
                    "1000",
                    "--clear-event",
                ]
            )
            conn = sqlite3.connect(db)
            try:
                count = conn.execute("SELECT COUNT(*) FROM event_cddis_station_candidates WHERE event_id = 'late-event'").fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(count, 0)

    def test_invalid_custom_window_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_db(db)
            with self.assertRaises(SystemExit):
                rebuild_cddis.main(
                    [
                        "--db",
                        str(db),
                        "--event-id",
                        "bad-event",
                        "--event-time",
                        "2026-06-23T23:00:00Z",
                        "--latitude",
                        "0",
                        "--longitude",
                        "0",
                        "--start-time",
                        "2026-06-23T23:15:00Z",
                        "--end-time",
                        "2026-06-23T23:00:00Z",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
