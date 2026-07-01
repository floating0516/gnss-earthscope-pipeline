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
SCRIPT_PATH = ROOT / "scripts" / "availability" / "update_cddis_highrate_availability.py"

COMMON_SPEC = importlib.util.spec_from_file_location("cddis_common", COMMON_PATH)
cddis_common = importlib.util.module_from_spec(COMMON_SPEC)
assert COMMON_SPEC.loader is not None
sys.modules["cddis_common"] = cddis_common
COMMON_SPEC.loader.exec_module(cddis_common)

SCRIPT_SPEC = importlib.util.spec_from_file_location("update_cddis_highrate_availability", SCRIPT_PATH)
update_cddis = importlib.util.module_from_spec(SCRIPT_SPEC)
assert SCRIPT_SPEC.loader is not None
SCRIPT_SPEC.loader.exec_module(update_cddis)


def granules() -> list[object]:
    return [
        cddis_common.CddisGranule(
            granule_id="G1",
            producer_granule_id="daej174x00.26o.gz",
            start_utc="2026-06-23T23:00:00Z",
            end_utc="2026-06-23T23:15:00Z",
            url="https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/daej174x00.26o.gz",
            filename="daej174x00.26o.gz",
            station4="DAEJ",
            station9="DAEJ174X0",
        ),
        cddis_common.CddisGranule(
            granule_id="G2",
            producer_granule_id="abcd174x00.26o.gz",
            start_utc="2026-06-23T23:00:00Z",
            end_utc="2026-06-23T23:15:00Z",
            url="https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/abcd174x00.26o.gz",
            filename="abcd174x00.26o.gz",
            station4="ABCD",
            station9="ABCD174X0",
        ),
    ]


class CddisAvailabilityTest(unittest.TestCase):
    def test_init_db_creates_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            conn = sqlite3.connect(db)
            try:
                update_cddis.init_db(conn)
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            finally:
                conn.close()

        self.assertIn("cddis_scan_runs", tables)
        self.assertIn("cddis_highrate_files", tables)

    def test_main_writes_selected_station_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            with patch.object(update_cddis, "query_granules", return_value=(granules(), "directory", ["fallback used"])):
                rc = update_cddis.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T23:00:00Z",
                        "--end-time",
                        "2026-06-23T23:15:00Z",
                        "--stations",
                        "DAEJ",
                    ]
                )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                runs = conn.execute("SELECT * FROM cddis_scan_runs").fetchall()
                files = conn.execute("SELECT * FROM cddis_highrate_files").fetchall()
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "OK")
        self.assertEqual(runs[0]["query_mode"], "directory")
        self.assertEqual(runs[0]["file_count"], 1)
        self.assertEqual(runs[0]["station_count"], 1)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["station4"], "DAEJ")
        self.assertEqual(files[0]["year"], 2026)
        self.assertEqual(files[0]["doy"], 174)
        self.assertEqual(files[0]["hour"], 23)

    def test_main_records_failed_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            with patch.object(update_cddis, "query_granules", side_effect=RuntimeError("CDDIS directory query failed")):
                rc = update_cddis.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T23:00:00Z",
                        "--end-time",
                        "2026-06-23T23:15:00Z",
                        "--query-mode",
                        "directory",
                    ]
                )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                runs = conn.execute("SELECT * FROM cddis_scan_runs").fetchall()
                files = conn.execute("SELECT * FROM cddis_highrate_files").fetchall()
            finally:
                conn.close()

        self.assertEqual(rc, 1)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "FAIL")
        self.assertIn("CDDIS directory query failed", runs[0]["reason"])
        self.assertEqual(len(files), 0)

    def test_clear_window_replaces_overlapping_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            with patch.object(update_cddis, "query_granules", return_value=(granules(), "directory", [])):
                rc1 = update_cddis.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T23:00:00Z",
                        "--end-time",
                        "2026-06-23T23:15:00Z",
                    ]
                )
            with patch.object(update_cddis, "query_granules", return_value=(granules()[:1], "directory", [])):
                rc2 = update_cddis.main(
                    [
                        "--db",
                        str(db),
                        "--start-time",
                        "2026-06-23T23:00:00Z",
                        "--end-time",
                        "2026-06-23T23:15:00Z",
                        "--clear-window",
                    ]
                )
            conn = sqlite3.connect(db)
            try:
                file_count = conn.execute("SELECT COUNT(*) FROM cddis_highrate_files").fetchone()[0]
                scan_count = conn.execute("SELECT COUNT(*) FROM cddis_scan_runs").fetchone()[0]
            finally:
                conn.close()

        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        self.assertEqual(file_count, 1)
        self.assertEqual(scan_count, 2)

    def test_invalid_time_window_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                update_cddis.main(
                    [
                        "--db",
                        str(Path(tmp) / "cddis.sqlite"),
                        "--start-time",
                        "2026-06-23T23:15:00Z",
                        "--end-time",
                        "2026-06-23T23:00:00Z",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
