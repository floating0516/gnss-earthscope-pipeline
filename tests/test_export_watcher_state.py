import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from gnss_eq import usgs_watcher


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "ops" / "export_watcher_state.py"


def load_module():
    spec = importlib.util.spec_from_file_location("export_watcher_state", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def create_state_db(path: Path, *, include_rows: bool = True) -> None:
    conn = sqlite3.connect(path)
    try:
        usgs_watcher.init_db(conn)
        if include_rows:
            conn.execute(
                """
                INSERT INTO usgs_watcher_events(
                    event_id, event_time_utc, first_seen_utc, last_seen_utc, usgs_updated_utc,
                    latitude, longitude, depth_km, magnitude, mag_type, place, title, usgs_url,
                    detail_url, scope, region, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "us-test",
                    "2026-06-24T22:05:11Z",
                    "2026-06-28T08:00:00Z",
                    "2026-06-28T08:00:00Z",
                    "2026-06-28T08:01:00Z",
                    40.4,
                    -124.5,
                    10.0,
                    7.5,
                    "mww",
                    "near the coast of northern California",
                    "M 7.5 - near the coast of northern California",
                    "https://earthquake.usgs.gov/earthquakes/eventpage/us-test",
                    "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us-test&format=geojson",
                    "americas,nz",
                    "americas",
                    '{"secret":"raw"}',
                ),
            )
            conn.execute(
                """
                INSERT INTO usgs_watcher_polls(started_utc, finished_utc, status, url_count, fetched_count, new_count, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("2026-06-28T08:00:00Z", "2026-06-28T08:01:00Z", "OK", 4, 1, 1, ""),
            )
            conn.execute("INSERT INTO usgs_watcher_state(key, value) VALUES (?, ?)", ("last_poll_end", "2026-06-28T08:01:00Z"))
        conn.commit()
    finally:
        conn.close()


class ExportWatcherStateTest(unittest.TestCase):
    def test_exports_events_polls_state_and_summary_without_raw_json_by_default(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "watcher.sqlite"
            out = root / "watcher.jsonl"
            create_state_db(db)

            summary = module.export_watcher_state(db, out)
            rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["counts"]["events"], 1)
        self.assertEqual(summary["counts"]["polls"], 1)
        self.assertEqual(summary["counts"]["state"], 1)
        event = next(row for row in rows if row["kind"] == "event")
        poll = next(row for row in rows if row["kind"] == "poll")
        state = next(row for row in rows if row["kind"] == "state")
        summary_row = rows[-1]
        self.assertEqual(event["event_id"], "us-test")
        self.assertNotIn("raw_json", event)
        self.assertEqual(poll["status"], "OK")
        self.assertEqual(state["key"], "last_poll_end")
        self.assertEqual(summary_row["kind"], "summary")
        self.assertEqual(summary_row["counts"]["events"], 1)

    def test_can_include_raw_json_when_requested(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "watcher.sqlite"
            out = root / "watcher.jsonl"
            create_state_db(db)

            module.export_watcher_state(db, out, include_raw_json=True)
            rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

        event = next(row for row in rows if row["kind"] == "event")
        self.assertEqual(event["raw_json"], '{"secret":"raw"}')

    def test_empty_db_writes_summary_only(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "watcher.sqlite"
            out = root / "watcher.jsonl"
            create_state_db(db, include_rows=False)

            summary = module.export_watcher_state(db, out)
            rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["counts"]["events"], 0)
        self.assertEqual(rows, [{"kind": "summary", **summary}])

    def test_cli_returns_nonzero_for_missing_or_bad_db(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing.sqlite"
            bad = root / "bad.sqlite"
            out = root / "watcher.jsonl"
            bad.write_text("not sqlite", encoding="utf-8")

            with redirect_stderr(io.StringIO()):
                missing_code = module.main(["--db", str(missing), "--out", str(out)])
                bad_code = module.main(["--db", str(bad), "--out", str(out)])

        self.assertEqual(missing_code, 1)
        self.assertEqual(bad_code, 1)


if __name__ == "__main__":
    unittest.main()
