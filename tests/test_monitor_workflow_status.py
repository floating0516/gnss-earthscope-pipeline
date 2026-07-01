from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gnss_eq import monitor


class MonitorWorkflowStatusTest(unittest.TestCase):
    def test_failed_workflow_is_retryable_candidate_not_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "earthscope.sqlite"
            runs_root = root / "runs"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE usgs_m6plus_events_usa ("
                "event_id TEXT, magnitude REAL, event_date TEXT, time_utc TEXT, place TEXT, "
                "existing_data_status TEXT, existing_station_count INTEGER)"
            )
            conn.execute(
                "CREATE TABLE event_earthscope_station_candidates ("
                "event_id TEXT, station TEXT, station_latitude REAL, station_longitude REAL, distance_km REAL, radius_km REAL)"
            )
            conn.execute(
                "INSERT INTO usgs_m6plus_events_usa VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("event-a", 6.5, "2020-01-01", "2020-01-01T00:00:00Z", "Test", "", 0),
            )
            for index in range(6):
                conn.execute(
                    "INSERT INTO event_earthscope_station_candidates VALUES (?, ?, ?, ?, ?, ?)",
                    ("event-a", f"S{index:03d}", 1.0, 2.0, 3.0, 200.0),
                )
            conn.commit()
            conn.close()

            report_dir = runs_root / "event-a" / "workflow-20200101T000000Z" / "reports"
            report_dir.mkdir(parents=True)
            (report_dir / "workflow-summary.json").write_text(
                json.dumps({"status": {"download": "FAIL", "process": "SKIPPED", "normalized": "SKIPPED_WORKFLOW_FAILED"}}),
                encoding="utf-8",
            )

            report = monitor.build_monitor_report(
                source="earthscope",
                limit=20,
                earthscope_db=db,
                earthscope_nonconus_db=root / "missing.sqlite",
                geonet_db=root / "missing-geonet.sqlite",
                runs_root=runs_root,
            )

        source = report["sources"][0]
        self.assertEqual(source["counts"]["failed_retryable"], 1)
        self.assertEqual(source["candidates"][0]["coverage_status"], "FAILED_RETRYABLE")
        self.assertEqual(source["candidates"][0]["priority"], "MEDIUM")


if __name__ == "__main__":
    unittest.main()
