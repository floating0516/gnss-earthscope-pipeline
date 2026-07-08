from __future__ import annotations

import csv
import gzip
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

VALIDATOR_PATH = ROOT / "scripts" / "summaries" / "validate_normalized_export.py"
VALIDATOR_SPEC = __import__("importlib.util").util.spec_from_file_location("validate_normalized_export", VALIDATOR_PATH)
validator = __import__("importlib.util").util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(validator)


class NormalizePrideKinEventTest(unittest.TestCase):
    def make_write_fixture(self, tmp_path: Path, overwrite: bool = False):
        db_path = tmp_path / "events.sqlite"
        normalized_root = tmp_path / "normalized"
        workflow_root = tmp_path / "workflow"
        reports_dir = workflow_root / "reports"
        manifests_dir = workflow_root / "manifests"
        workflow_summary = reports_dir / "workflow-summary.json"
        quality_json = reports_dir / "kin-quality.json"
        kin_file = tmp_path / "kin_2020001_good"

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

        kin_file.write_text("END OF HEADER\n58849 18 1000 2000 3000\n58849 19 1001 2001 3001\n", encoding="utf-8")
        manifests_dir.mkdir(parents=True)
        reports_dir.mkdir(parents=True)
        (manifests_dir / "kin-files.txt").write_text(f"{kin_file}\n", encoding="utf-8")
        workflow_summary.write_text(
            json.dumps({"event": {"id": "test-event", "time_utc": "2020-01-01T00:00:00Z"}}),
            encoding="utf-8",
        )
        quality_json.write_text(
            json.dumps(
                {
                    "schema_version": "kin-quality/v1",
                    "thresholds": {"min_epochs": 60, "min_coverage_ratio": 0.8},
                    "policy": {"allow_partial_failures": False},
                    "stations": [{"station": "GOOD", "quality_status": "OK", "quality_flags": ""}],
                    "summary": {"status": "OK", "station_count": 1, "ok_station_count": 1},
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
                "overwrite": overwrite,
            },
        )()
        expected_dir = normalized_root / "us-test-event-m6-1-20200101-test-place"
        return args, normalize.load_json(workflow_summary), normalize.load_json(quality_json), expected_dir

    def test_workflow_kin_files_resolves_relative_root_token_and_legacy_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workflow_root = tmp_path / "runs" / "event-a" / "workflow-20200101T000000Z"
            reports_dir = workflow_root / "reports"
            manifests_dir = workflow_root / "manifests"
            kin_dir = workflow_root / "pride" / "event-a-pdp3-1h" / "abcd" / "2020" / "001"
            workflow_summary = reports_dir / "workflow-summary.json"
            kin_file = kin_dir / "kin_2020001_abcd"
            reports_dir.mkdir(parents=True)
            manifests_dir.mkdir(parents=True)
            kin_dir.mkdir(parents=True)
            kin_file.write_text("END OF HEADER\n", encoding="utf-8")

            summary = {
                "paths": {"root": str(tmp_path)},
                "files": {
                    "kin": [
                        "@ROOT@/runs/event-a/workflow-20200101T000000Z/pride/event-a-pdp3-1h/abcd/2020/001/kin_2020001_abcd",
                        "runs/event-a/workflow-20200101T000000Z/pride/event-a-pdp3-1h/abcd/2020/001/kin_2020001_abcd",
                        "/old/machine/gnss-earthscope-pipeline/runs/event-a/workflow-20200101T000000Z/pride/event-a-pdp3-1h/abcd/2020/001/kin_2020001_abcd",
                    ]
                },
            }
            workflow_summary.write_text(json.dumps(summary), encoding="utf-8")

            resolved = normalize.workflow_kin_files(summary, workflow_summary)

            self.assertEqual(resolved, [kin_file])

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
            3,
            Path("workflow-summary.json"),
            normalize.event_grade([{"Azimuth_Deg": ""}]),
            True,
        )

        self.assertEqual(payload["schema_version"], "normalized-event/v1")
        self.assertEqual(payload["source"], "earthscope")
        self.assertEqual(payload["source_label"], "EarthScope PRIDE PPP-AR kin quality-passing stations")
        self.assertEqual(payload["event_authority"], "USGS")
        self.assertEqual(payload["station_authority"], "EarthScope/GAGE")
        self.assertEqual(payload["event_time"], "2020-01-01T00:00:00Z")
        self.assertEqual(payload["station_count"], 1)
        self.assertEqual(payload["waveform_rows"], 3)
        self.assertEqual(payload["country"], "United States")
        self.assertEqual(payload["region"], "US")
        self.assertEqual(payload["earthscope_subset"], "usa")

    def test_event_json_uses_country_and_americas_region_for_nonconus_subset(self):
        payload = normalize.event_json(
            {
                "event_id": "us7000irjd",
                "title": "Mexico event",
                "time_utc": "2022-11-22T16:39:05Z",
                "longitude": -116.4,
                "latitude": 30.8,
                "depth_km": 10.0,
                "magnitude": 6.2,
                "place": "28 km SW of Las Brisas, Mexico",
                "usgs_url": "",
                "earthscope_subset": "nonconus",
            },
            1,
            3,
            Path("workflow-summary.json"),
            normalize.event_grade([{"Azimuth_Deg": ""}]),
            True,
        )

        self.assertEqual(payload["country"], "Mexico")
        self.assertEqual(payload["region"], "Americas")
        self.assertEqual(payload["earthscope_subset"], "nonconus")

    def test_earthscope_country_derives_known_nonconus_countries(self):
        cases = [
            ("28 km SW of Las Brisas, Mexico", "Mexico"),
            ("Nippes, Haiti", "Haiti"),
            ("40 km WSW of Pointe-Noire, Guadeloupe", "Guadeloupe"),
            ("42 km SSW of Bartolomé Masó, Cuba", "Cuba"),
            ("Unknown offshore event", "Americas"),
        ]
        for place, expected in cases:
            with self.subTest(place=place):
                self.assertEqual(
                    normalize.earthscope_country({"place": place, "earthscope_subset": "nonconus"}),
                    expected,
                )

    def test_write_outputs_skips_quality_station_with_missing_coordinates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "events.sqlite"
            normalized_root = tmp_path / "normalized"
            workflow_root = tmp_path / "workflow"
            reports_dir = workflow_root / "reports"
            manifests_dir = workflow_root / "manifests"
            workflow_summary = reports_dir / "workflow-summary.json"
            quality_json = reports_dir / "kin-quality.json"
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
            manifests_dir.mkdir(parents=True)
            reports_dir.mkdir(parents=True)
            (manifests_dir / "kin-files.txt").write_text(f"{good_kin}\n{missing_kin}\n", encoding="utf-8")
            workflow_summary.write_text(
                json.dumps({"event": {"id": "test-event", "time_utc": "2020-01-01T00:00:00Z"}}),
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
            event_dir = Path(result["normalized_event_dir"])
            stations_csv = event_dir / "stations.csv"
            self.assertIn("GOOD", stations_csv.read_text(encoding="utf-8"))
            event_json = json.loads((event_dir / "event.json").read_text(encoding="utf-8"))
            self.assertEqual(event_json["skipped_stations"], result["skipped_stations"])
            self.assertIn("kin epochs are interpreted as GPST", event_json["normalization"]["coordinate_frame"])
            with gzip.open(event_dir / "waveforms.csv.gz", "rt", encoding="utf-8", newline="") as handle:
                waveform_rows = list(csv.DictReader(handle))
            self.assertEqual(waveform_rows[0]["Time_UTC"], "2020-01-01T23:59:32Z")
            self.assertEqual(waveform_rows[0]["Time_Offset_s"], "86372.000000")
            self.assertEqual(waveform_rows[3]["Time_UTC"], "2020-01-01T23:59:52Z")
            self.assertEqual(waveform_rows[3]["Time_Offset_s"], "86392.000000")

    def test_write_outputs_uses_catalog_fractional_event_time_for_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "events.sqlite"
            normalized_root = tmp_path / "normalized"
            workflow_root = tmp_path / "workflow"
            reports_dir = workflow_root / "reports"
            manifests_dir = workflow_root / "manifests"
            workflow_summary = reports_dir / "workflow-summary.json"
            quality_json = reports_dir / "kin-quality.json"
            kin_file = tmp_path / "kin_2020001_good"

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
                VALUES ('test-event', 'Test event', '2020-01-01T00:00:00.500000Z', '2020-01-01', 6.1, -100.0, 20.0, 10.0, 'Test place', '')
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

            kin_file.write_text("END OF HEADER\n58849 18 1000 2000 3000\n", encoding="utf-8")
            manifests_dir.mkdir(parents=True)
            reports_dir.mkdir(parents=True)
            (manifests_dir / "kin-files.txt").write_text(f"{kin_file}\n", encoding="utf-8")
            workflow_summary.write_text(
                json.dumps({"event": {"id": "test-event", "time_utc": "2020-01-01T00:00:00Z"}}),
                encoding="utf-8",
            )
            quality_json.write_text(
                json.dumps({"stations": [{"station": "GOOD", "quality_status": "OK", "quality_flags": ""}], "summary": {}}),
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

            with gzip.open(Path(result["normalized_event_dir"]) / "waveforms.csv.gz", "rt", encoding="utf-8", newline="") as handle:
                waveform_rows = list(csv.DictReader(handle))
            self.assertEqual(waveform_rows[0]["Time_UTC"], "2020-01-01T00:00:00Z")
            self.assertEqual(waveform_rows[0]["Time_Offset_s"], "-0.500000")
    def test_write_outputs_failure_does_not_leave_partial_event_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, summary, quality, expected_dir = self.make_write_fixture(Path(tmp), overwrite=True)
            original = normalize.kin_to_enu

            def fail_kin_to_enu(*_args, **_kwargs):
                raise RuntimeError("synthetic normalization failure")

            normalize.kin_to_enu = fail_kin_to_enu
            try:
                with self.assertRaises(RuntimeError):
                    normalize.write_outputs(args, summary, quality)
            finally:
                normalize.kin_to_enu = original

            self.assertFalse(expected_dir.exists())
            self.assertFalse(list(args.normalized_root.glob(".tmp-*")))

    def test_write_outputs_refuses_existing_package_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, summary, quality, expected_dir = self.make_write_fixture(Path(tmp), overwrite=False)
            expected_dir.mkdir(parents=True)
            (expected_dir / "sentinel.txt").write_text("keep\n", encoding="utf-8")

            with self.assertRaises(SystemExit) as context:
                normalize.write_outputs(args, summary, quality)

            self.assertIn("already exists", str(context.exception))
            self.assertEqual((expected_dir / "sentinel.txt").read_text(encoding="utf-8"), "keep\n")

    def test_write_outputs_overwrite_replaces_existing_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, summary, quality, expected_dir = self.make_write_fixture(Path(tmp), overwrite=True)
            expected_dir.mkdir(parents=True)
            (expected_dir / "sentinel.txt").write_text("remove\n", encoding="utf-8")

            result = normalize.write_outputs(args, summary, quality)

            self.assertEqual(Path(result["normalized_event_dir"]), expected_dir)
            self.assertFalse((expected_dir / "sentinel.txt").exists())
            self.assertTrue((expected_dir / "event.json").exists())

    def test_write_outputs_writes_schema_v1_event_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, summary, quality, _expected_dir = self.make_write_fixture(Path(tmp), overwrite=False)

            result = normalize.write_outputs(args, summary, quality)
            event_dir = Path(result["normalized_event_dir"])
            event_payload = json.loads((event_dir / "event.json").read_text(encoding="utf-8"))
            provenance = json.loads((event_dir / "provenance.json").read_text(encoding="utf-8"))
            validation = validator.validate_export(args.normalized_root, event_id="test-event")

        self.assertEqual(event_payload["schema_version"], "normalized-event/v1")
        self.assertEqual(event_payload["event_id"], "test-event")
        self.assertEqual(event_payload["source"], "earthscope")
        self.assertEqual(event_payload["event_authority"], "USGS")
        self.assertEqual(event_payload["station_authority"], "EarthScope/GAGE")
        self.assertEqual(event_payload["event_time"], "2020-01-01T00:00:00Z")
        self.assertEqual(event_payload["station_count"], 1)
        self.assertEqual(event_payload["waveform_rows"], 6)
        self.assertEqual(provenance["schema_version"], "provenance/v1")
        self.assertEqual(provenance["source"]["name"], "earthscope")
        self.assertEqual(provenance["source"]["event_authority"], "USGS")
        self.assertEqual(provenance["source"]["station_authority"], "EarthScope/GAGE")
        self.assertEqual(provenance["quality"]["thresholds"]["min_epochs"], 60)
        self.assertEqual(provenance["quality"]["summary_status"], "OK")
        self.assertIn("event.json", provenance["outputs"])
        self.assertEqual(validation["status"], "OK")

    def test_write_outputs_adds_station_siting_fields_from_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "events.sqlite"
            normalized_root = tmp_path / "normalized"
            workflow_root = tmp_path / "workflow"
            reports_dir = workflow_root / "reports"
            manifests_dir = workflow_root / "manifests"
            workflow_summary = reports_dir / "workflow-summary.json"
            quality_json = reports_dir / "kin-quality.json"
            kin_file = tmp_path / "kin_2020001_good"

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
                CREATE TABLE station_siting_metadata (
                    provider TEXT NOT NULL,
                    station TEXT NOT NULL,
                    station9 TEXT NOT NULL DEFAULT '',
                    station_name TEXT NOT NULL DEFAULT '',
                    latitude REAL,
                    longitude REAL,
                    monument_style TEXT NOT NULL DEFAULT '',
                    station_siting_type TEXT NOT NULL,
                    station_siting_type_zh TEXT NOT NULL,
                    siting_category TEXT NOT NULL,
                    rooftop_status TEXT NOT NULL,
                    bedrock_bolted_mast_status TEXT NOT NULL,
                    siting_source TEXT NOT NULL,
                    siting_source_url TEXT NOT NULL DEFAULT '',
                    raw_metadata_json TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (provider, station)
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
            conn.execute(
                """
                INSERT INTO station_siting_metadata (
                    provider, station, monument_style, station_siting_type, station_siting_type_zh,
                    siting_category, rooftop_status, bedrock_bolted_mast_status, siting_source, updated_at
                ) VALUES (
                    'EarthScope', 'GOOD', 'BUILDING ROOF', 'roof', '楼顶',
                    'roof/building', 'yes', 'not classified as bedrock-bolted in DAI',
                    'EarthScope DAI', '2026-07-09T00:00:00Z'
                )
                """
            )
            conn.commit()
            conn.close()

            kin_file.write_text("END OF HEADER\n58849 0 1000 2000 3000\n", encoding="utf-8")
            manifests_dir.mkdir(parents=True)
            reports_dir.mkdir(parents=True)
            (manifests_dir / "kin-files.txt").write_text(f"{kin_file}\n", encoding="utf-8")
            workflow_summary.write_text(
                json.dumps({"event": {"id": "test-event", "time_utc": "2020-01-01T00:00:00Z"}}),
                encoding="utf-8",
            )
            quality_json.write_text(
                json.dumps({"stations": [{"station": "GOOD", "quality_status": "OK", "quality_flags": ""}], "summary": {}}),
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

            with (Path(result["normalized_event_dir"]) / "stations.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(rows[0]["Monument_Style"], "BUILDING ROOF")
            self.assertEqual(rows[0]["Station_Siting_Type"], "roof")
            self.assertEqual(rows[0]["Station_Siting_Type_Zh"], "楼顶")
            self.assertEqual(rows[0]["Siting_Source"], "EarthScope DAI")


if __name__ == "__main__":
    unittest.main()
