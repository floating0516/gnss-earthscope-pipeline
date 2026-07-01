from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "cddis_downloader"
COMMON_PATH = TOOLS / "cddis_common.py"
SCRIPT_PATH = TOOLS / "download_cddis_event_window.py"

COMMON_SPEC = importlib.util.spec_from_file_location("cddis_common", COMMON_PATH)
cddis_common = importlib.util.module_from_spec(COMMON_SPEC)
assert COMMON_SPEC.loader is not None
sys.modules["cddis_common"] = cddis_common
COMMON_SPEC.loader.exec_module(cddis_common)

SCRIPT_SPEC = importlib.util.spec_from_file_location("download_cddis_event_window", SCRIPT_PATH)
download_cddis_event_window = importlib.util.module_from_spec(SCRIPT_SPEC)
assert SCRIPT_SPEC.loader is not None
SCRIPT_SPEC.loader.exec_module(download_cddis_event_window)


def seed_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE event_cddis_station_candidates (
                event_id TEXT NOT NULL,
                station4 TEXT NOT NULL,
                radius_km REAL NOT NULL,
                distance_km REAL NOT NULL,
                event_time_utc TEXT NOT NULL,
                window_start_utc TEXT NOT NULL,
                window_end_utc TEXT NOT NULL,
                station_latitude REAL NOT NULL,
                station_longitude REAL NOT NULL,
                station_elevation_m REAL NOT NULL,
                available_file_count INTEGER NOT NULL,
                filenames TEXT NOT NULL,
                urls TEXT NOT NULL,
                metadata_source_file TEXT NOT NULL,
                availability_source TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(event_id, station4, radius_km)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO event_cddis_station_candidates VALUES (
                'event1', 'DAEJ', 1000.0, 12.5,
                '2026-06-23T23:00:00Z', '2026-06-23T23:00:00Z', '2026-06-23T23:15:00Z',
                36.4, 127.4, 116.0, 1,
                'daej174x00.26o.gz',
                'https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/daej174x00.26o.gz',
                'source.rnx', 'CDDIS', '2026-06-24T00:00:00Z'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class CddisEventDownloaderTest(unittest.TestCase):
    def test_dry_run_writes_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            out = Path(tmp) / "out"
            seed_db(db)

            rc = download_cddis_event_window.main(
                [
                    "--db",
                    str(db),
                    "--event-id",
                    "event1",
                    "--radius-km",
                    "1000",
                    "--out-dir",
                    str(out),
                    "--dry-run",
                ]
            )
            summary = json.loads((out / "manifests" / "cddis-event-summary.json").read_text(encoding="utf-8"))
            requested = (out / "manifests" / "cddis-event-requested.tsv").read_text(encoding="utf-8")
            downloaded = (out / "manifests" / "cddis-event-downloaded.tsv").read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(summary["requested_file_count"], 1)
        self.assertTrue(summary["dry_run"])
        self.assertIn("DAEJ", requested)
        self.assertIn("DRY_RUN", downloaded)

    def test_download_calls_curl_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            out = Path(tmp) / "out"
            seed_db(db)

            def fake_download(url, target, **kwargs):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"rinex")
                return "OK", ""

            with patch.object(download_cddis_event_window, "curl_download", side_effect=fake_download) as download:
                rc = download_cddis_event_window.main(
                    [
                        "--db",
                        str(db),
                        "--event-id",
                        "event1",
                        "--radius-km",
                        "1000",
                        "--out-dir",
                        str(out),
                    ]
                )
            summary = json.loads((out / "manifests" / "cddis-event-summary.json").read_text(encoding="utf-8"))
            downloaded_bytes = (out / "files" / "daej" / "daej174x00.26o.gz").read_bytes()

        self.assertEqual(rc, 0)
        download.assert_called_once()
        self.assertEqual(summary["downloaded_count"], 1)
        self.assertEqual(downloaded_bytes, b"rinex")

    def test_missing_candidates_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            out = Path(tmp) / "out"
            seed_db(db)

            rc = download_cddis_event_window.main(
                [
                    "--db",
                    str(db),
                    "--event-id",
                    "missing",
                    "--radius-km",
                    "1000",
                    "--out-dir",
                    str(out),
                    "--dry-run",
                ]
            )

        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
