from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from gnss_eq import earthscope_event_import, usgs_watcher


def create_watcher_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        usgs_watcher.init_db(conn)
        conn.execute(
            """
            INSERT INTO usgs_watcher_events(
                event_id, event_time_utc, first_seen_utc, last_seen_utc, usgs_updated_utc,
                latitude, longitude, depth_km, magnitude, mag_type, place, title, usgs_url,
                detail_url, scope, region, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "us-venezuela",
                "2026-06-24T22:05:11Z",
                "2026-06-28T08:00:00Z",
                "2026-06-28T08:05:00Z",
                "2026-06-28T08:06:00Z",
                10.4351,
                -68.4716,
                10.0,
                7.5,
                "mww",
                "Yumare, Venezuela",
                "M 7.5 - Yumare, Venezuela",
                "https://earthquake.usgs.gov/earthquakes/eventpage/us-venezuela",
                "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us-venezuela&format=geojson",
                "americas,nz",
                "americas",
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO usgs_watcher_events(
                event_id, event_time_utc, first_seen_utc, last_seen_utc, usgs_updated_utc,
                latitude, longitude, depth_km, magnitude, mag_type, place, title, usgs_url,
                detail_url, scope, region, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "us-alaska",
                "2026-02-23T12:34:56Z",
                "2026-06-28T08:10:00Z",
                "2026-06-28T08:15:00Z",
                "2026-06-28T08:16:00Z",
                52.3259,
                -169.8682,
                10.0,
                6.0,
                "mww",
                "96 km SW of Nikolski, Alaska",
                "M 6.0 - 96 km SW of Nikolski, Alaska",
                "https://earthquake.usgs.gov/earthquakes/eventpage/us-alaska",
                "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us-alaska&format=geojson",
                "americas,nz",
                "americas",
                "{}",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def create_earthscope_db(path: Path, table: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            f"""
            CREATE TABLE {table} (
                event_id TEXT PRIMARY KEY,
                title TEXT,
                time_utc TEXT NOT NULL,
                event_date TEXT NOT NULL,
                year INTEGER NOT NULL,
                doy INTEGER NOT NULL,
                magnitude REAL NOT NULL,
                longitude REAL NOT NULL,
                latitude REAL NOT NULL,
                depth_km REAL,
                place TEXT,
                usgs_url TEXT,
                query_start TEXT NOT NULL,
                query_end TEXT NOT NULL,
                min_magnitude REAL NOT NULL,
                region_filter TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                existing_data_status TEXT NOT NULL DEFAULT '',
                existing_station_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class EarthScopeEventImportTest(unittest.TestCase):
    def test_auto_import_routes_watched_events_to_earthscope_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            usa_db = root / "earthscope.sqlite"
            nonconus_db = root / "earthscope-nonconus.sqlite"
            create_watcher_db(watcher_db)
            create_earthscope_db(usa_db, "usgs_m6plus_events_usa")
            create_earthscope_db(nonconus_db, "usgs_m6plus_events_earthscope_nonconus")

            report = earthscope_event_import.import_watched_events(
                state_db=watcher_db,
                target="auto",
                limit=10,
                earthscope_db=usa_db,
                earthscope_nonconus_db=nonconus_db,
            )

            usa_row = sqlite_row(usa_db, "usgs_m6plus_events_usa", "us-alaska")
            nonconus_row = sqlite_row(nonconus_db, "usgs_m6plus_events_earthscope_nonconus", "us-venezuela")

        self.assertTrue(report["ok"])
        self.assertEqual(report["counts"]["inserted"], 2)
        self.assertEqual(usa_row["event_date"], "2026-02-23")
        self.assertEqual(usa_row["year"], 2026)
        self.assertEqual(usa_row["doy"], 54)
        self.assertEqual(nonconus_row["event_date"], "2026-06-24")
        self.assertEqual(nonconus_row["region_filter"], "usgs_watcher_americas")

    def test_dry_run_does_not_write_event_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            nonconus_db = root / "earthscope-nonconus.sqlite"
            create_watcher_db(watcher_db)
            create_earthscope_db(nonconus_db, "usgs_m6plus_events_earthscope_nonconus")

            report = earthscope_event_import.import_watched_events(
                state_db=watcher_db,
                target="nonconus",
                event_ids=["us-venezuela"],
                earthscope_nonconus_db=nonconus_db,
                dry_run=True,
            )
            count = sqlite_count(nonconus_db, "usgs_m6plus_events_earthscope_nonconus")

        self.assertTrue(report["ok"])
        self.assertEqual(report["events"][0]["action"], "WOULD_INSERT")
        self.assertEqual(count, 0)

    def test_missing_watcher_db_is_graceful_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.sqlite"
            report = earthscope_event_import.import_watched_events(state_db=missing)

            self.assertFalse(report["ok"])
            self.assertFalse(missing.exists())
            self.assertEqual(report["errors"][0]["action"], "DATABASE_NOT_FOUND")

    def test_reimport_skips_existing_event_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            nonconus_db = root / "earthscope-nonconus.sqlite"
            create_watcher_db(watcher_db)
            create_earthscope_db(nonconus_db, "usgs_m6plus_events_earthscope_nonconus")

            earthscope_event_import.import_watched_events(
                state_db=watcher_db,
                target="nonconus",
                event_ids=["us-venezuela"],
                earthscope_nonconus_db=nonconus_db,
            )
            report = earthscope_event_import.import_watched_events(
                state_db=watcher_db,
                target="nonconus",
                event_ids=["us-venezuela"],
                earthscope_nonconus_db=nonconus_db,
            )
            count = sqlite_count(nonconus_db, "usgs_m6plus_events_earthscope_nonconus")

        self.assertTrue(report["ok"])
        self.assertEqual(report["counts"]["skipped"], 1)
        self.assertEqual(report["events"][0]["action"], "SKIPPED_EXISTS")
        self.assertEqual(count, 1)

    def test_update_existing_updates_existing_event_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            nonconus_db = root / "earthscope-nonconus.sqlite"
            create_watcher_db(watcher_db)
            create_earthscope_db(nonconus_db, "usgs_m6plus_events_earthscope_nonconus")

            earthscope_event_import.import_watched_events(
                state_db=watcher_db,
                target="nonconus",
                event_ids=["us-venezuela"],
                earthscope_nonconus_db=nonconus_db,
            )
            report = earthscope_event_import.import_watched_events(
                state_db=watcher_db,
                target="nonconus",
                event_ids=["us-venezuela"],
                earthscope_nonconus_db=nonconus_db,
                update_existing=True,
            )
            count = sqlite_count(nonconus_db, "usgs_m6plus_events_earthscope_nonconus")

        self.assertTrue(report["ok"])
        self.assertEqual(report["counts"]["updated"], 1)
        self.assertEqual(report["events"][0]["action"], "UPDATE")
        self.assertEqual(count, 1)


def sqlite_row(path: Path, table: str, event_id: str) -> sqlite3.Row:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(f"SELECT * FROM {table} WHERE event_id = ?", (event_id,)).fetchone()
        assert row is not None
        return row
    finally:
        conn.close()


def sqlite_count(path: Path, table: str) -> int:
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        conn.close()


if __name__ == "__main__":
    unittest.main()
