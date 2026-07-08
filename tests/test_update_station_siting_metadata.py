from __future__ import annotations

import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "database" / "update_station_siting_metadata.py"

SPEC = importlib.util.spec_from_file_location("update_station_siting_metadata", SCRIPT)
update_station_siting_metadata = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["update_station_siting_metadata"] = update_station_siting_metadata
SPEC.loader.exec_module(update_station_siting_metadata)


class UpdateStationSitingMetadataTest(unittest.TestCase):
    def test_parse_dai_station_rows_finds_monument_style_table(self):
        html = """
        <html><body>
          <table><tr><td>not the result table</td></tr></table>
          <table>
            <tr>
              <th>Station Code</th><th>Latitude</th><th>Longitude</th>
              <th>Station Name</th><th>Monument Style</th>
            </tr>
            <tr>
              <td>CN57</td><td>10.837</td><td>-60.938</td>
              <td>CN57Toco_TTO2021</td><td>BUILDING WALL</td>
            </tr>
            <tr>
              <td>CN04</td><td>14.024</td><td>-60.974</td>
              <td>Castries_LCA2014</td><td>BUILDING ROOF</td>
            </tr>
          </table>
        </body></html>
        """

        rows = update_station_siting_metadata.parse_dai_station_rows(html)

        self.assertEqual(rows["CN57"]["monument_style"], "BUILDING WALL")
        self.assertEqual(rows["CN57"]["station_name"], "CN57Toco_TTO2021")
        self.assertEqual(rows["CN04"]["monument_style"], "BUILDING ROOF")

    def test_sync_geonet_station_siting_populates_unknown_rows(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE geonet_gnss_stations (
                station TEXT PRIMARY KEY,
                station9 TEXT,
                network TEXT,
                name TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                start TEXT,
                end TEXT,
                sensor_type TEXT,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO geonet_gnss_stations VALUES (
                'AHTI', 'AHTI00NZL', 'CG', 'Ahititi',
                -38.411447554, 178.046002897,
                '2009-01-01T00:00:00Z', '9999-01-01T00:00:00Z',
                'GNSS/GPS', 'GeoNet', '2026-07-09T00:00:00Z'
            )
            """
        )

        count = update_station_siting_metadata.sync_geonet_station_siting(conn, "2026-07-09T00:00:00Z")
        row = conn.execute(
            """
            SELECT station, monument_style, station_siting_type, station_siting_type_zh, siting_source
            FROM station_siting_metadata
            WHERE provider = 'GeoNet' AND station = 'AHTI'
            """
        ).fetchone()

        self.assertEqual(count, 1)
        self.assertEqual(row["monument_style"], "UNKNOWN")
        self.assertEqual(row["station_siting_type"], "unknown")
        self.assertEqual(row["station_siting_type_zh"], "未知")
        self.assertEqual(row["siting_source"], "GeoNet station inventory")


if __name__ == "__main__":
    unittest.main()
