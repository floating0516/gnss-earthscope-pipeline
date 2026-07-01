from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CDDIS_TOOLS = ROOT / "tools" / "cddis_downloader"
COMMON_PATH = CDDIS_TOOLS / "cddis_common.py"
SINGLE_PATH = ROOT / "scripts" / "availability" / "update_cddis_highrate_availability.py"
SCRIPT_PATH = ROOT / "scripts" / "availability" / "update_cddis_event_availability.py"

COMMON_SPEC = importlib.util.spec_from_file_location("cddis_common", COMMON_PATH)
cddis_common = importlib.util.module_from_spec(COMMON_SPEC)
assert COMMON_SPEC.loader is not None
sys.modules["cddis_common"] = cddis_common
COMMON_SPEC.loader.exec_module(cddis_common)

SINGLE_SPEC = importlib.util.spec_from_file_location("update_cddis_highrate_availability", SINGLE_PATH)
update_cddis_highrate_availability = importlib.util.module_from_spec(SINGLE_SPEC)
assert SINGLE_SPEC.loader is not None
sys.modules["update_cddis_highrate_availability"] = update_cddis_highrate_availability
SINGLE_SPEC.loader.exec_module(update_cddis_highrate_availability)

SCRIPT_SPEC = importlib.util.spec_from_file_location("update_cddis_event_availability", SCRIPT_PATH)
update_cddis_event_availability = importlib.util.module_from_spec(SCRIPT_SPEC)
assert SCRIPT_SPEC.loader is not None
sys.modules["update_cddis_event_availability"] = update_cddis_event_availability
SCRIPT_SPEC.loader.exec_module(update_cddis_event_availability)


def granule(start: str = "2026-06-23T23:00:00Z", station: str = "DAEJ", subdir: str = "26o") -> object:
    filename = f"{station.lower()}174x00.{subdir}.gz"
    return cddis_common.CddisGranule(
        granule_id=f"G-{station}-{subdir}",
        producer_granule_id=filename,
        start_utc=start,
        end_utc="2026-06-23T23:15:00Z",
        url=f"https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/{subdir}/23/{filename}",
        filename=filename,
        station4=station,
        station9=f"{station}174X0",
    )


def seed_events(db: Path) -> None:
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE cddis_events (
                event_id TEXT PRIMARY KEY,
                event_time_utc TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                magnitude REAL,
                place TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO cddis_events VALUES (?, ?, 0, 0, ?, '', 'now')",
            [
                ("event1", "2026-06-23T23:07:30Z", 6.5),
                ("event2", "2026-06-23T23:12:00Z", 6.6),
                ("small", "2026-06-23T23:30:00Z", 5.9),
            ],
        )
        conn.commit()
    finally:
        conn.close()


class CddisEventAvailabilityTest(unittest.TestCase):
    def test_reads_unique_15_minute_event_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_events(db)
            conn = sqlite3.connect(db)
            try:
                windows = update_cddis_event_availability.read_event_windows(
                    conn,
                    update_cddis_event_availability.parse_args(
                        [
                            "--db",
                            str(db),
                            "--start-time",
                            "2026-06-23T00:00:00Z",
                            "--end-time",
                            "2026-06-24T00:00:00Z",
                        ]
                    ),
                )
            finally:
                conn.close()

        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].start_utc, "2026-06-23T23:00:00Z")
        self.assertEqual(windows[0].end_utc, "2026-06-23T23:15:00Z")

    def test_main_writes_scans_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_events(db)
            with patch.object(update_cddis_event_availability, "query_granules", return_value=([granule()], "directory", [])):
                rc = update_cddis_event_availability.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T00:00:00Z",
                        "--end-time",
                        "2026-06-24T00:00:00Z",
                        "--jobs",
                        "1",
                        "--rinex-subdir",
                        "26o",
                        "--clear",
                    ]
                )
            conn = sqlite3.connect(db)
            try:
                scan_count = conn.execute("SELECT COUNT(*) FROM cddis_scan_runs").fetchone()[0]
                file_count = conn.execute("SELECT COUNT(*) FROM cddis_highrate_files").fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(scan_count, 1)
        self.assertEqual(file_count, 1)

    def test_default_directory_mode_scans_hatanaka_and_obs_subdirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_events(db)

            def query_directory(start, end, *, rinex_subdir, timeout, cookie_file):
                if rinex_subdir == "26d":
                    return [granule(station="ABMF", subdir="26d")]
                if rinex_subdir == "26o":
                    return [granule(station="DAEJ", subdir="26o")]
                return []

            with patch.object(update_cddis_event_availability, "query_directory_granules", side_effect=query_directory):
                rc = update_cddis_event_availability.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T00:00:00Z",
                        "--end-time",
                        "2026-06-24T00:00:00Z",
                        "--jobs",
                        "1",
                        "--clear",
                    ]
                )
            conn = sqlite3.connect(db)
            try:
                file_count = conn.execute("SELECT COUNT(*) FROM cddis_highrate_files").fetchone()[0]
                station_count = conn.execute("SELECT COUNT(DISTINCT station4) FROM cddis_highrate_files").fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(file_count, 2)
        self.assertEqual(station_count, 2)

    def test_records_missing_directory_as_empty_ok_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_events(db)
            error = "CDDIS directory query failed: curl: (22) The requested URL returned error: 404"
            with patch.object(update_cddis_event_availability, "query_granules", side_effect=RuntimeError(error)):
                rc = update_cddis_event_availability.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T00:00:00Z",
                        "--end-time",
                        "2026-06-24T00:00:00Z",
                        "--jobs",
                        "1",
                        "--rinex-subdir",
                        "26o",
                        "--clear",
                    ]
                )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT * FROM cddis_scan_runs").fetchone()
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(row["status"], "OK")
        self.assertEqual(row["file_count"], 0)
        self.assertEqual(row["reason"], "CDDIS directory not found")

    def test_retries_transient_directory_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_events(db)
            side_effects = [
                RuntimeError("CDDIS directory query failed: curl: (35) Recv failure: Connection reset by peer"),
                ([granule()], "directory", []),
            ]
            with patch.object(update_cddis_event_availability, "query_granules", side_effect=side_effects) as query:
                rc = update_cddis_event_availability.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T00:00:00Z",
                        "--end-time",
                        "2026-06-24T00:00:00Z",
                        "--jobs",
                        "1",
                        "--rinex-subdir",
                        "26o",
                        "--clear",
                    ]
                )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT * FROM cddis_scan_runs").fetchone()
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(query.call_count, 2)
        self.assertEqual(row["status"], "OK")
        self.assertEqual(row["file_count"], 1)

    def test_records_failed_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_events(db)
            with patch.object(update_cddis_event_availability, "query_granules", side_effect=RuntimeError("directory unavailable")):
                rc = update_cddis_event_availability.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T00:00:00Z",
                        "--end-time",
                        "2026-06-24T00:00:00Z",
                        "--jobs",
                        "1",
                        "--rinex-subdir",
                        "26o",
                        "--clear",
                    ]
                )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT * FROM cddis_scan_runs").fetchone()
            finally:
                conn.close()

        self.assertEqual(rc, 1)
        self.assertEqual(row["status"], "FAIL")
        self.assertIn("directory unavailable", row["reason"])

    def test_dry_run_does_not_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            seed_events(db)
            with patch.object(update_cddis_event_availability, "query_granules") as query:
                rc = update_cddis_event_availability.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T00:00:00Z",
                        "--end-time",
                        "2026-06-24T00:00:00Z",
                        "--dry-run",
                    ]
                )

        self.assertEqual(rc, 0)
        query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
