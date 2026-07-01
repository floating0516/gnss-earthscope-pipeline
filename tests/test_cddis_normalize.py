from __future__ import annotations

import gzip
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "normalize" / "normalize_cddis_pride_kin_event.py"

SPEC = importlib.util.spec_from_file_location("normalize_cddis_pride_kin_event", SCRIPT_PATH)
normalize_cddis_pride_kin_event = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["normalize_cddis_pride_kin_event"] = normalize_cddis_pride_kin_event
SPEC.loader.exec_module(normalize_cddis_pride_kin_event)


def seed_db(path: Path) -> None:
    conn = sqlite3.connect(path)
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
            INSERT INTO cddis_events VALUES (
                'event1', '2026-06-23T23:07:30Z', 36.0, 127.0, 0.0,
                'CDDIS smoke event', '2026-06-24T00:00:00Z'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO event_cddis_station_candidates VALUES (
                'event1', 'DAEJ', 1000.0, 12.5,
                '2026-06-23T23:07:30Z', '2026-06-23T23:00:00Z', '2026-06-23T23:15:00Z',
                36.4, 127.4, 116.0, 1,
                'daej174x00.26o.gz', 'https://example.invalid/daej174x00.26o.gz',
                'source.rnx', 'CDDIS', '2026-06-24T00:00:00Z'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class CddisNormalizeTest(unittest.TestCase):
    def test_workflow_kin_files_resolves_portable_manifest_paths(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            workflow = root / "workflow"
            reports = workflow / "reports"
            manifests = workflow / "manifests"
            kin = root / "pride" / "daej" / "kin_2026174_daej"
            workflow_summary = reports / "workflow-summary.json"
            kin.parent.mkdir(parents=True)
            reports.mkdir(parents=True)
            manifests.mkdir(parents=True)
            kin.write_text("kin placeholder\n", encoding="utf-8")
            relative_kin = kin.relative_to(ROOT)
            (manifests / "kin-files.txt").write_text(
                "\n".join(
                    [
                        f"@ROOT@/{relative_kin}",
                        str(relative_kin),
                        f"/old/machine/gnss-earthscope-pipeline/{relative_kin}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            resolved = normalize_cddis_pride_kin_event.workflow_kin_files({}, workflow_summary)

        self.assertEqual(resolved, [kin])

    def test_normalizes_quality_passing_kin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "cddis.sqlite"
            workflow = root / "workflow"
            reports = workflow / "reports"
            manifests = workflow / "manifests"
            kin = root / "pride" / "daej" / "kin_2026174_daej"
            normalized_root = root / "normalized"
            seed_db(db)
            kin.parent.mkdir(parents=True, exist_ok=True)
            kin.write_text("kin placeholder\n", encoding="utf-8")
            (manifests).mkdir(parents=True, exist_ok=True)
            (manifests / "kin-files.txt").write_text(str(kin) + "\n", encoding="utf-8")
            workflow_summary = reports / "workflow-summary.json"
            quality_json = reports / "kin-quality.json"
            write_json(
                workflow_summary,
                {
                    "provider": "CDDIS",
                    "event_id": "event1",
                    "event_time_utc": "2026-06-23T23:07:30Z",
                    "process_event_time_utc": "2026-06-23T23:07:30Z",
                    "paths": {"run_root": str(root / "pride")},
                },
            )
            write_json(
                quality_json,
                {
                    "stations": [{"station": "DAEJ", "quality_status": "OK", "quality_flags": ""}],
                    "summary": {"event_quality_status": "OK"},
                },
            )

            series = [
                (normalize_cddis_pride_kin_event.parse_utc("2026-06-23T23:07:29Z"), -1.0, 1.0, 2.0, 3.0),
                (normalize_cddis_pride_kin_event.parse_utc("2026-06-23T23:07:30Z"), 0.0, 2.0, 3.0, 4.0),
            ]
            with patch.object(normalize_cddis_pride_kin_event, "kin_to_enu", return_value=series):
                rc = normalize_cddis_pride_kin_event.main(
                    [
                        "--workflow-summary",
                        str(workflow_summary),
                        "--quality-json",
                        str(quality_json),
                        "--db",
                        str(db),
                        "--normalized-root",
                        str(normalized_root),
                    ]
                )
            event_dirs = list(normalized_root.iterdir())
            event_json = json.loads((event_dirs[0] / "event.json").read_text(encoding="utf-8"))
            stations = (event_dirs[0] / "stations.csv").read_text(encoding="utf-8")
            with gzip.open(event_dirs[0] / "waveforms.csv.gz", "rt", encoding="utf-8") as handle:
                waveform_rows = handle.readlines()

        self.assertEqual(rc, 0)
        self.assertEqual(event_json["network"], "NASA CDDIS")
        self.assertEqual(event_json["stations"], 1)
        self.assertIn("kin epochs are interpreted as GPST", event_json["normalization"]["coordinate_frame"])
        self.assertIn("DAEJ", stations)
        self.assertEqual(len(waveform_rows), 7)

    def test_requires_quality_passing_stations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "cddis.sqlite"
            workflow_summary = root / "workflow" / "reports" / "workflow-summary.json"
            quality_json = root / "workflow" / "reports" / "kin-quality.json"
            seed_db(db)
            write_json(workflow_summary, {"event_id": "event1", "process_event_time_utc": "2026-06-23T23:07:30Z"})
            write_json(quality_json, {"stations": [{"station": "DAEJ", "quality_status": "FAIL"}]})

            with self.assertRaises(SystemExit) as exc:
                normalize_cddis_pride_kin_event.main(
                    [
                        "--workflow-summary",
                        str(workflow_summary),
                        "--quality-json",
                        str(quality_json),
                        "--db",
                        str(db),
                        "--normalized-root",
                        str(root / "normalized"),
                    ]
                )

        self.assertIn("No quality-passing stations", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
