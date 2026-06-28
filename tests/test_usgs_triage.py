from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from gnss_eq import usgs_triage, usgs_watcher


def create_watcher_db(path: Path) -> None:
    conn = sqlite3.connect(path)
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
            "us-americas",
            "2026-06-24T22:05:11Z",
            "2026-06-28T08:00:00Z",
            "2026-06-28T08:00:00Z",
            "2026-06-28T08:01:00Z",
            10.4351,
            -68.4716,
            10.0,
            7.5,
            "mww",
            "Yumare, Venezuela",
            "M 7.5 - Yumare, Venezuela",
            "https://earthquake.usgs.gov/earthquakes/eventpage/us-americas",
            "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us-americas&format=geojson",
            "americas,nz",
            "americas",
            '{"secret":"raw"}',
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
            "us-geonet",
            "2026-06-23T02:26:20Z",
            "2026-06-28T08:05:00Z",
            "2026-06-28T08:05:00Z",
            "2026-06-28T08:06:00Z",
            -27.1921,
            -177.7691,
            140.331,
            6.3,
            "mww",
            "Kermadec Islands region",
            "M 6.3 - Kermadec Islands region",
            "https://earthquake.usgs.gov/earthquakes/eventpage/us-geonet",
            "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us-geonet&format=geojson",
            "americas,nz",
            "new_zealand",
            '{"secret":"raw"}',
        ),
    )
    conn.execute(
        """
        INSERT INTO usgs_watcher_polls(started_utc, finished_utc, status, url_count, fetched_count, new_count, error)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-06-28T08:00:00Z", "2026-06-28T08:01:00Z", "OK", 4, 2, 2, ""),
    )
    conn.commit()
    conn.close()


def create_earthscope_db(path: Path, event_id: str = "us-americas", station_count: int = 20) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE usgs_m6plus_events_usa ("
        "event_id TEXT, magnitude REAL, event_date TEXT, place TEXT, existing_data_status TEXT, existing_station_count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE event_earthscope_station_candidates ("
        "event_id TEXT, station TEXT, station_latitude REAL, station_longitude REAL, distance_km REAL, radius_km REAL)"
    )
    conn.execute(
        "INSERT INTO usgs_m6plus_events_usa VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, 7.5, "2026-06-24", "Yumare", "", 0),
    )
    conn.executemany(
        "INSERT INTO event_earthscope_station_candidates VALUES (?, ?, ?, ?, ?, ?)",
        [(event_id, f"E{index:03d}", 1.0, 2.0, 3.0, 200.0) for index in range(station_count)]
        + [(event_id, "E300", 1.0, 2.0, 3.0, 300.0)],
    )
    conn.commit()
    conn.close()


def create_geonet_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE geonet_m6plus_events_nz ("
        "event_id TEXT, magnitude REAL, event_date TEXT, place TEXT, existing_data_status TEXT, existing_station_count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE event_highrate_day_availability ("
        "event_id TEXT, candidate_200km_station_count INTEGER, candidate_300km_station_count INTEGER, "
        "has_1hz INTEGER, file_count INTEGER, station_count INTEGER, candidate_300km_with_data_count INTEGER)"
    )
    conn.execute(
        "INSERT INTO geonet_m6plus_events_nz VALUES (?, ?, ?, ?, ?, ?)",
        ("us-geonet", 6.3, "2026-06-23", "Kermadec", "", 0),
    )
    conn.execute(
        "INSERT INTO event_highrate_day_availability VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("us-geonet", 6, 12, 1, 50, 7, 6),
    )
    conn.commit()
    conn.close()


class UsgsTriageTest(unittest.TestCase):
    def test_triage_reports_earthscope_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            earthscope_db = root / "earthscope.sqlite"
            create_watcher_db(watcher_db)
            create_earthscope_db(earthscope_db, station_count=20)

            report = usgs_triage.build_triage_report(
                state_db=watcher_db,
                source="earthscope",
                earthscope_db=earthscope_db,
                earthscope_nonconus_db=root / "missing-nonconus.sqlite",
                geonet_db=root / "missing-geonet.sqlite",
                runs_root=root / "runs",
            )

        self.assertTrue(report["read_only"])
        self.assertEqual(report["events"][0]["event_id"], "us-americas")
        self.assertEqual(report["events"][0]["priority"], "HIGH")
        self.assertEqual(report["events"][0]["suggested_action"], "REVIEW_PREPARE_BATCH")
        self.assertIn("export-batch --event-id us-americas", "\n".join(report["events"][0]["suggested_commands"]))

    def test_triage_reports_geonet_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            geonet_db = root / "geonet.sqlite"
            create_watcher_db(watcher_db)
            create_geonet_db(geonet_db)

            report = usgs_triage.build_triage_report(
                state_db=watcher_db,
                source="geonet",
                earthscope_db=root / "missing-earthscope.sqlite",
                earthscope_nonconus_db=root / "missing-nonconus.sqlite",
                geonet_db=geonet_db,
                runs_root=root / "runs",
            )

        self.assertEqual(report["events"][0]["event_id"], "us-geonet")
        self.assertEqual(report["events"][0]["source"], "geonet")
        self.assertEqual(report["events"][0]["priority"], "MEDIUM")
        self.assertEqual(report["events"][0]["suggested_action"], "REVIEW_PREPARE_BATCH")
        self.assertIn("run_geonet_batch_workflow.sh --help", "\n".join(report["events"][0]["suggested_commands"]))

    def test_missing_watcher_db_is_graceful_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.sqlite"
            report = usgs_triage.build_triage_report(state_db=missing)

            output = io.StringIO()
            with redirect_stdout(output):
                usgs_triage.write_triage_tsv(report)

            self.assertFalse(report["ok"])
            self.assertFalse(missing.exists())
            self.assertIn("DATABASE_NOT_FOUND", output.getvalue())

    def test_existing_workflow_skips_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            earthscope_db = root / "earthscope.sqlite"
            create_watcher_db(watcher_db)
            create_earthscope_db(earthscope_db)
            (root / "runs" / "us-americas" / "workflow-test").mkdir(parents=True)

            report = usgs_triage.build_triage_report(
                state_db=watcher_db,
                source="earthscope",
                earthscope_db=earthscope_db,
                earthscope_nonconus_db=root / "missing-nonconus.sqlite",
                geonet_db=root / "missing-geonet.sqlite",
                runs_root=root / "runs",
            )

        self.assertEqual(report["events"][0]["priority"], "SKIP")
        self.assertEqual(report["events"][0]["suggested_action"], "SKIP_WORKFLOW_EXISTS")

    def test_json_omits_raw_json_and_tsv_has_stable_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            earthscope_db = root / "earthscope.sqlite"
            create_watcher_db(watcher_db)
            create_earthscope_db(earthscope_db, station_count=5)
            report = usgs_triage.build_triage_report(
                state_db=watcher_db,
                source="earthscope",
                earthscope_db=earthscope_db,
                earthscope_nonconus_db=root / "missing-nonconus.sqlite",
                geonet_db=root / "missing-geonet.sqlite",
                runs_root=root / "runs",
            )

            json_output = io.StringIO()
            with redirect_stdout(json_output):
                usgs_triage.write_triage_json(report)
            payload = json.loads(json_output.getvalue())

            tsv_output = io.StringIO()
            with redirect_stdout(tsv_output):
                usgs_triage.write_triage_tsv(report)

        self.assertTrue(payload["read_only"])
        self.assertNotIn("raw_json", payload["events"][0])
        self.assertIn("kind\tok\tsource", tsv_output.getvalue())
        self.assertIn("SUMMARY\tTrue\tearthscope", tsv_output.getvalue())
        self.assertIn("EVENT\tTrue\tearthscope\tMEDIUM", tsv_output.getvalue())

    def test_build_report_does_not_modify_watcher_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            watcher_db = root / "watcher.sqlite"
            earthscope_db = root / "earthscope.sqlite"
            create_watcher_db(watcher_db)
            create_earthscope_db(earthscope_db)
            before = sqlite_counts(watcher_db)

            usgs_triage.build_triage_report(
                state_db=watcher_db,
                source="earthscope",
                earthscope_db=earthscope_db,
                earthscope_nonconus_db=root / "missing-nonconus.sqlite",
                geonet_db=root / "missing-geonet.sqlite",
                runs_root=root / "runs",
            )
            after = sqlite_counts(watcher_db)

        self.assertEqual(before, after)


def sqlite_counts(path: Path) -> tuple[int, int]:
    conn = sqlite3.connect(path)
    try:
        event_count = conn.execute("SELECT COUNT(*) FROM usgs_watcher_events").fetchone()[0]
        poll_count = conn.execute("SELECT COUNT(*) FROM usgs_watcher_polls").fetchone()[0]
    finally:
        conn.close()
    return event_count, poll_count


if __name__ == "__main__":
    unittest.main()
