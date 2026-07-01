from __future__ import annotations

import gzip
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "database" / "update_cddis_station_metadata.py"
SPEC = importlib.util.spec_from_file_location("update_cddis_station_metadata", SCRIPT_PATH)
update_cddis_station_metadata = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["update_cddis_station_metadata"] = update_cddis_station_metadata
SPEC.loader.exec_module(update_cddis_station_metadata)


def rinex_header(station: str = "DAEJ", station9: str | None = None) -> str:
    marker = station9 or station
    lines = [
        "     2.11           OBSERVATION DATA    M (MIXED)           RINEX VERSION / TYPE",
        f"{marker:<60}MARKER NAME",
        "23902M002                                                   MARKER NUMBER",
        "5412K48145          TRIMBLE NETR9       5.44                REC # / TYPE / VERS",
        "4923363230          TRM59800.00     SCIS                    ANT # / TYPE",
        " -3120042.5551  4084613.8142  3764026.3252                  APPROX POSITION XYZ",
        "                                                            END OF HEADER",
    ]
    return "\n".join(lines) + "\n"


def seed_availability(db: Path) -> None:
    conn = sqlite3.connect(db)
    try:
        update_cddis_station_metadata.init_db(conn)
        conn.execute(
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
            )
            """
        )
        conn.execute(
            """
            INSERT INTO cddis_highrate_files VALUES (
                'ABMF', 'ABMF00GLP', 2026, 174, 23,
                '2026-06-23T23:00:00Z', '2026-06-23T23:15:00Z',
                'ABMF00GLP_S_20261742300_15M_01S_MO.crx.gz',
                'https://example.test/ABMF00GLP_S_20261742300_15M_01S_MO.crx.gz',
                'CDDIS highrate GNSS', 1, 'now'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class CddisStationMetadataTest(unittest.TestCase):
    def test_ecef_to_geodetic_converts_rinex_xyz(self):
        lat, lon, elevation = update_cddis_station_metadata.ecef_to_geodetic(
            -3120042.5551,
            4084613.8142,
            3764026.3252,
        )

        self.assertAlmostEqual(lat, 36.39942707, places=6)
        self.assertAlmostEqual(lon, 127.37449156, places=6)
        self.assertAlmostEqual(elevation, 116.089, places=3)

    def test_parse_rinex_header_from_gzip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daej174x00.26o.gz"
            with gzip.open(path, "wt", encoding="ascii") as handle:
                handle.write(rinex_header())

            metadata = update_cddis_station_metadata.parse_rinex_header(path)

        assert metadata is not None
        self.assertEqual(metadata.station4, "DAEJ")
        self.assertEqual(metadata.station9, "DAEJ174X0")
        self.assertEqual(metadata.marker_number, "23902M002")
        self.assertEqual(metadata.receiver_type, "TRIMBLE NETR9")
        self.assertEqual(metadata.antenna_type, "TRM59800.00     SCIS")
        self.assertAlmostEqual(metadata.latitude, 36.39942707, places=6)

    def test_main_writes_cddis_stations_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            rinex = Path(tmp) / "daej174x00.26o.gz"
            db = Path(tmp) / "cddis.sqlite"
            with gzip.open(rinex, "wt", encoding="ascii") as handle:
                handle.write(rinex_header())

            rc = update_cddis_station_metadata.main(["--db", str(db), "--file", str(rinex)])
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute("SELECT * FROM cddis_stations").fetchall()
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["station4"], "DAEJ")
        self.assertAlmostEqual(rows[0]["latitude"], 36.39942707, places=6)
        self.assertAlmostEqual(rows[0]["longitude"], 127.37449156, places=6)
        self.assertIn("daej174x00.26o.gz", rows[0]["source_file"])

    def test_from_availability_downloads_samples_and_writes_stations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "cddis.sqlite"
            sample_root = Path(tmp) / "samples"
            seed_availability(db)

            def download(row, root, cookie_file, timeout, overwrite=False):
                path = root / row["filename"]
                root.mkdir(parents=True, exist_ok=True)
                with gzip.open(path, "wt", encoding="ascii") as handle:
                    handle.write(rinex_header(station9="ABMF00GLP"))
                return path

            with patch.object(update_cddis_station_metadata, "download_sample", side_effect=download):
                rc = update_cddis_station_metadata.main(
                    [
                        "--db",
                        str(db),
                        "--from-availability",
                        "--sample-root",
                        str(sample_root),
                    ]
                )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute("SELECT * FROM cddis_stations WHERE station4 = 'ABMF'").fetchone()
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["station9"], "ABMF00GLP")
        self.assertIn("ABMF00GLP", row["source_file"])

    def test_missing_xyz_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            rinex = Path(tmp) / "bad.26o.gz"
            db = Path(tmp) / "cddis.sqlite"
            with gzip.open(rinex, "wt", encoding="ascii") as handle:
                handle.write("DAEJ                                                        MARKER NAME\n")

            rc = update_cddis_station_metadata.main(["--db", str(db), "--file", str(rinex)])

        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
