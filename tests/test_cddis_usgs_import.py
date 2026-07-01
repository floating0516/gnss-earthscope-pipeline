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
SCRIPT_PATH = ROOT / "scripts" / "database" / "import_usgs_events_to_cddis.py"

SPEC = importlib.util.spec_from_file_location("import_usgs_events_to_cddis", SCRIPT_PATH)
import_usgs_events_to_cddis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["import_usgs_events_to_cddis"] = import_usgs_events_to_cddis
SPEC.loader.exec_module(import_usgs_events_to_cddis)


def usgs_payload() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "us-test-1",
                "properties": {
                    "mag": 6.7,
                    "magType": "mww",
                    "place": "test place",
                    "time": 1262304000000,
                    "updated": 1262307600000,
                    "title": "M 6.7 - test place",
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us-test-1",
                },
                "geometry": {"type": "Point", "coordinates": [127.0, 36.0, 10.0]},
            }
        ],
    }


class CddisUsgsImportTest(unittest.TestCase):
    def test_imports_usgs_events_into_cddis_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            with patch.object(import_usgs_events_to_cddis, "fetch_json", return_value=usgs_payload()):
                rc = import_usgs_events_to_cddis.main(
                    [
                        "--db",
                        str(db),
                        "--starttime",
                        "2010-01-01T00:00:00Z",
                        "--endtime",
                        "2010-01-02T00:00:00Z",
                    ]
                )

            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT * FROM cddis_events WHERE event_id = 'us-test-1'").fetchone()
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["event_time_utc"], "2010-01-01T00:00:00.000Z")
        self.assertEqual(row["latitude"], 36.0)
        self.assertEqual(row["longitude"], 127.0)
        self.assertEqual(row["magnitude"], 6.7)
        self.assertEqual(row["depth_km"], 10.0)
        self.assertEqual(row["mag_type"], "mww")
        self.assertEqual(row["event_source"], "USGS")

    def test_dry_run_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            with patch.object(import_usgs_events_to_cddis, "fetch_json", return_value=usgs_payload()):
                rc = import_usgs_events_to_cddis.main(["--db", str(db), "--dry-run"])

        self.assertEqual(rc, 0)
        self.assertFalse(db.exists())

    def test_builds_usgs_url_with_global_magnitude_query(self):
        args = import_usgs_events_to_cddis.parse_args(
            [
                "--starttime",
                "2010-01-01T00:00:00Z",
                "--endtime",
                "2026-06-27T00:00:00Z",
                "--min-magnitude",
                "6",
                "--limit",
                "123",
            ]
        )

        url = import_usgs_events_to_cddis.build_usgs_url(args)

        self.assertIn("format=geojson", url)
        self.assertIn("starttime=2010-01-01T00%3A00%3A00Z", url)
        self.assertIn("endtime=2026-06-27T00%3A00%3A00Z", url)
        self.assertIn("minmagnitude=6.0", url)
        self.assertIn("orderby=time-asc", url)
        self.assertIn("limit=123", url)
        self.assertNotIn("minlatitude", url)


if __name__ == "__main__":
    unittest.main()
