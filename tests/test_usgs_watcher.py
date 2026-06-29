from __future__ import annotations

import argparse
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from gnss_eq import usgs_watcher


def make_payload(event_id: str, *, latitude: float = -35.0, longitude: float = 175.0, updated: int = 1600000300000) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": event_id,
                "properties": {
                    "mag": 6.4,
                    "magType": "mww",
                    "place": "test place",
                    "time": 1600000000000,
                    "updated": updated,
                    "url": f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}",
                    "detail": f"https://earthquake.usgs.gov/fdsnws/event/1/query?eventid={event_id}&format=geojson",
                    "title": "M 6.4 - test place",
                },
                "geometry": {"type": "Point", "coordinates": [longitude, latitude, 12.3]},
            }
        ],
    }


class IncrementingClock:
    def __init__(self) -> None:
        self.index = 0

    def __call__(self) -> str:
        self.index += 1
        return f"2024-01-01T00:00:{self.index:02d}Z"


class UsgsWatcherTest(unittest.TestCase):
    def test_parse_events_extracts_usgs_geojson_fields(self):
        events = usgs_watcher.parse_events(make_payload("us-test"))

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event_id"], "us-test")
        self.assertEqual(event["event_time_utc"], "2020-09-13T12:26:40Z")
        self.assertEqual(event["usgs_updated_utc"], "2020-09-13T12:31:40Z")
        self.assertEqual(event["mag_type"], "mww")
        self.assertEqual(event["latitude"], -35.0)
        self.assertEqual(event["longitude"], 175.0)
        self.assertEqual(event["depth_km"], 12.3)
        self.assertIn("raw_json", event)

    def test_classify_region_covers_americas_and_new_zealand_antimeridian(self):
        self.assertEqual(usgs_watcher.classify_region(34.0, -118.0), "americas")
        self.assertEqual(usgs_watcher.classify_region(55.0, 175.0), "americas")
        self.assertEqual(usgs_watcher.classify_region(-35.0, 175.0), "new_zealand")
        self.assertEqual(usgs_watcher.classify_region(-35.0, -175.0), "new_zealand")
        self.assertIsNone(usgs_watcher.classify_region(10.0, 20.0))

    def test_build_usgs_urls_uses_requested_scope(self):
        urls = usgs_watcher.build_usgs_urls(
            scope="americas",
            starttime="2024-01-01T00:00:00Z",
            endtime="2024-01-02T00:00:00Z",
            min_magnitude=6.0,
            limit=100,
        )

        self.assertEqual(len(urls), 2)
        self.assertTrue(all("format=geojson" in url for url in urls))
        self.assertTrue(all("minmagnitude=6.0" in url for url in urls))
        self.assertTrue(all("limit=100" in url for url in urls))

    def test_poll_once_deduplicates_across_bbox_fetches_and_second_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "watcher.sqlite"
            clock = IncrementingClock()

            def fetcher(_url: str, _timeout: int) -> dict:
                return make_payload("us-dedupe")

            first = usgs_watcher.poll_once(state_db=db, fetcher=fetcher, now=clock)
            second = usgs_watcher.poll_once(state_db=db, fetcher=fetcher, now=clock)

            self.assertEqual(first["status"], "OK")
            self.assertEqual(first["new_count"], 1)
            self.assertEqual(len(first["events"]), 1)
            self.assertEqual(second["status"], "OK")
            self.assertEqual(second["new_count"], 0)
            self.assertEqual(second["events"], [])

            conn = sqlite3.connect(db)
            try:
                count = conn.execute("SELECT COUNT(*) FROM usgs_watcher_events").fetchone()[0]
                last_finished = conn.execute("SELECT value FROM usgs_watcher_state WHERE key = 'last_poll_finished_utc'").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(count, 1)
            self.assertEqual(last_finished, "2024-01-01T00:00:04Z")

    def test_existing_event_updates_last_seen_and_usgs_updated_without_alerting(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "watcher.sqlite"
            payloads = [make_payload("us-update", updated=1600000300000), make_payload("us-update", updated=1600000600000)]

            def fetcher(_url: str, _timeout: int) -> dict:
                return payloads.pop(0) if payloads else make_payload("us-update", updated=1600000600000)

            usgs_watcher.poll_once(state_db=db, scope="nz", fetcher=fetcher, now=IncrementingClock())
            second_clock = IncrementingClock()
            second = usgs_watcher.poll_once(state_db=db, scope="nz", fetcher=fetcher, now=second_clock)

            self.assertEqual(second["new_count"], 0)
            conn = sqlite3.connect(db)
            try:
                row = conn.execute(
                    "SELECT first_seen_utc, last_seen_utc, usgs_updated_utc FROM usgs_watcher_events WHERE event_id = 'us-update'"
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(row[0], "2024-01-01T00:00:02Z")
            self.assertEqual(row[1], "2024-01-01T00:00:02Z")
            self.assertEqual(row[2], "2020-09-13T12:36:40Z")

    def test_ignore_state_uses_lookback_window_with_existing_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "watcher.sqlite"

            first = usgs_watcher.poll_once(state_db=db, scope="nz", fetcher=lambda _url, _timeout: make_payload("us-old"), now=IncrementingClock())
            second = usgs_watcher.poll_once(
                state_db=db,
                scope="nz",
                lookback_minutes=10080,
                ignore_state=True,
                fetcher=lambda _url, _timeout: make_payload("us-old"),
                now=IncrementingClock(),
            )

            self.assertEqual(first["query_mode"], "lookback")
            self.assertEqual(second["query_mode"], "lookback")
            self.assertEqual(second["query_start_utc"], "2023-12-25T00:00:01Z")

    def test_run_watch_loop_once_does_not_sleep(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                state_db=str(Path(tmp) / "watcher.sqlite"),
                scope="nz",
                min_magnitude=6.0,
                lookback_minutes=1440,
                overlap_minutes=30,
                limit=2000,
                timeout=30,
                format="jsonl",
                once=True,
                interval=300,
                ignore_state=False,
            )

            def sleeper(_seconds: int) -> None:
                raise AssertionError("sleep called")

            output = io.StringIO()
            with redirect_stdout(output):
                rc = usgs_watcher.run_watch_loop(args, fetcher=lambda _url, _timeout: make_payload("us-once"), sleeper=sleeper, now=IncrementingClock())

            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(output.getvalue())["new_count"], 1)

    def test_run_watch_loop_calls_hook_for_new_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                state_db=str(Path(tmp) / "watcher.sqlite"),
                scope="nz",
                min_magnitude=6.0,
                lookback_minutes=1440,
                overlap_minutes=30,
                limit=2000,
                timeout=30,
                format="jsonl",
                once=True,
                interval=300,
                ignore_state=False,
            )
            calls: list[dict] = []

            def sleeper(_seconds: int) -> None:
                raise AssertionError("sleep called")

            output = io.StringIO()
            with redirect_stdout(output):
                rc = usgs_watcher.run_watch_loop(
                    args,
                    fetcher=lambda _url, _timeout: make_payload("us-hook"),
                    sleeper=sleeper,
                    now=IncrementingClock(),
                    on_new_events=lambda result: calls.append(result),
                )

            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["new_count"], 1)
            self.assertEqual(calls[0]["events"][0]["event_id"], "us-hook")

    def test_run_watch_loop_skips_hook_when_no_new_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "watcher.sqlite"
            usgs_watcher.poll_once(state_db=db, scope="nz", fetcher=lambda _url, _timeout: make_payload("us-old"), now=IncrementingClock())
            args = argparse.Namespace(
                state_db=str(db),
                scope="nz",
                min_magnitude=6.0,
                lookback_minutes=1440,
                overlap_minutes=30,
                limit=2000,
                timeout=30,
                format="jsonl",
                once=True,
                interval=300,
                ignore_state=False,
            )
            calls: list[dict] = []

            output = io.StringIO()
            with redirect_stdout(output):
                rc = usgs_watcher.run_watch_loop(
                    args,
                    fetcher=lambda _url, _timeout: make_payload("us-old"),
                    sleeper=lambda _seconds: None,
                    now=IncrementingClock(),
                    on_new_events=lambda result: calls.append(result),
                )

            self.assertEqual(rc, 0)
            self.assertEqual(calls, [])
            self.assertEqual(json.loads(output.getvalue())["new_count"], 0)

    def test_run_watch_loop_skips_hook_on_poll_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                state_db=str(Path(tmp) / "watcher.sqlite"),
                scope="nz",
                min_magnitude=6.0,
                lookback_minutes=1440,
                overlap_minutes=30,
                limit=2000,
                timeout=30,
                format="jsonl",
                once=True,
                interval=300,
                ignore_state=False,
            )

            def fetcher(_url: str, _timeout: int) -> dict:
                raise RuntimeError("network down")

            output = io.StringIO()
            with redirect_stdout(output):
                rc = usgs_watcher.run_watch_loop(
                    args,
                    fetcher=fetcher,
                    sleeper=lambda _seconds: None,
                    now=IncrementingClock(),
                    on_new_events=lambda _result: self.fail("hook should not run"),
                )

            self.assertEqual(rc, 1)
            self.assertEqual(json.loads(output.getvalue())["status"], "ERROR")

    def test_write_tsv_and_jsonl_have_stable_fields(self):
        result = {
            "status": "OK",
            "started_utc": "2024-01-01T00:00:00Z",
            "finished_utc": "2024-01-01T00:00:01Z",
            "query_start_utc": "2023-12-31T00:00:00Z",
            "query_end_utc": "2024-01-01T00:00:00Z",
            "scope": "americas,nz",
            "url_count": 4,
            "fetched_count": 1,
            "new_count": 1,
            "events": [
                {
                    "event_id": "us-output",
                    "event_time_utc": "2024-01-01T00:00:00Z",
                    "first_seen_utc": "2024-01-01T00:00:01Z",
                    "magnitude": 6.1,
                    "latitude": -35.0,
                    "longitude": 175.0,
                    "depth_km": 10.0,
                    "mag_type": "mww",
                    "region": "new_zealand",
                    "scope": "americas,nz",
                    "place": "test",
                    "title": "M 6.1 - test",
                    "usgs_url": "https://example.invalid/event",
                    "detail_url": "https://example.invalid/detail",
                    "raw_json": "{}",
                }
            ],
            "error": "",
            "urls": [],
        }

        tsv = io.StringIO()
        with redirect_stdout(tsv):
            usgs_watcher.write_tsv(result)
        self.assertIn("kind\tstatus\tevent_id", tsv.getvalue())
        self.assertIn("POLL\tOK", tsv.getvalue())
        self.assertIn("EVENT\tOK\tus-output", tsv.getvalue())

        jsonl = io.StringIO()
        with redirect_stdout(jsonl):
            usgs_watcher.write_json_lines(result)
        payload = json.loads(jsonl.getvalue())
        self.assertEqual(payload["events"][0]["event_id"], "us-output")
        self.assertNotIn("raw_json", payload["events"][0])

    def test_fetch_failure_records_failed_poll_and_error_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "watcher.sqlite"

            def fetcher(_url: str, _timeout: int) -> dict:
                raise RuntimeError("network down")

            result = usgs_watcher.poll_once(state_db=db, fetcher=fetcher, now=IncrementingClock())
            self.assertEqual(result["status"], "ERROR")
            self.assertIn("network down", result["error"])

            conn = sqlite3.connect(db)
            try:
                row = conn.execute("SELECT status, error FROM usgs_watcher_polls").fetchone()
            finally:
                conn.close()
            self.assertEqual(row[0], "ERROR")
            self.assertIn("network down", row[1])

            output = io.StringIO()
            with redirect_stdout(output):
                usgs_watcher.write_tsv(result)
            self.assertIn("ERROR", output.getvalue())
            self.assertIn("network down", output.getvalue())


if __name__ == "__main__":
    unittest.main()
