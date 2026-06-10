from __future__ import annotations

import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class DummyFastMCP:
    def __init__(self, name: str):
        self.name = name

    def tool(self):
        def decorator(func):
            return func

        return decorator

    def run(self):
        return None


mcp_module = types.ModuleType("mcp")
server_module = types.ModuleType("mcp.server")
fastmcp_module = types.ModuleType("mcp.server.fastmcp")
fastmcp_module.FastMCP = DummyFastMCP
sys.modules.setdefault("mcp", mcp_module)
sys.modules.setdefault("mcp.server", server_module)
sys.modules.setdefault("mcp.server.fastmcp", fastmcp_module)

from gnss_eq import mcp_server


class Completed:
    returncode = 0
    stdout = "out"
    stderr = ""


class CompletedEvents:
    returncode = 0
    stdout = (
        "event_id\tmagnitude\tevent_date\tplace\tstations_200km\tstations_300km\texisting_data_status\texisting_station_count\n"
        "ci38457511\t7.1\t2019-07-06\tRidgecrest Earthquake Sequence\t154\t376\tHAS_NORMALIZED\t490\n"
    )
    stderr = ""


class ExistingDataFailure:
    returncode = 1
    stdout = ""
    stderr = "event already has normalized data (HAS_NORMALIZED): ci38457511; use --include-existing to export it anyway\n"


class LongOutput:
    returncode = 0
    stdout = "\n".join(f"line-{index}" for index in range(205)) + "\n"
    stderr = ""


class McpServerTest(unittest.TestCase):
    def test_check_env_runs_gnss_eq(self):
        with patch.object(mcp_server.subprocess, "run", return_value=Completed) as run:
            result = mcp_server.check_env()

        self.assertTrue(result["ok"])
        self.assertEqual(result["stdout"], "out")
        command = run.call_args.args[0]
        self.assertEqual(command, ["gnss-eq", "check-env"])
        self.assertEqual(run.call_args.kwargs["cwd"], mcp_server.ROOT)

    def test_list_events_returns_structured_records(self):
        with patch.object(mcp_server.subprocess, "run", return_value=CompletedEvents):
            result = mcp_server.list_events()

        self.assertEqual(result["format"], "tsv")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["events"][0]["event_id"], "ci38457511")
        self.assertEqual(result["events"][0]["magnitude"], 7.1)
        self.assertEqual(result["events"][0]["stations_200km"], 154)

    def test_preview_batch_reports_existing_data(self):
        with patch.object(mcp_server.subprocess, "run", return_value=CompletedEvents):
            result = mcp_server.preview_batch("ci38457511", radius_km=200)

        self.assertTrue(result["ok"])
        self.assertEqual(result["station_count"], 154)
        self.assertTrue(result["has_existing_normalized"])
        self.assertTrue(result["would_fail_without_include_existing"])
        self.assertFalse(result["would_export"])

    def test_batch_preview_uses_unified_entrypoint(self):
        with patch.object(mcp_server.subprocess, "run", return_value=CompletedEvents):
            result = mcp_server.batch("ci38457511", mode="preview", radius_km=200)

        self.assertTrue(result["ok"])
        self.assertEqual(result["station_count"], 154)
        self.assertTrue(result["has_existing_normalized"])

    def test_preview_batch_allows_include_existing(self):
        with patch.object(mcp_server.subprocess, "run", return_value=CompletedEvents):
            result = mcp_server.preview_batch("ci38457511", radius_km=300, include_existing=True)

        self.assertTrue(result["would_export"])
        self.assertEqual(result["station_count"], 376)
        self.assertEqual(result["csv_path"], "data/batches/ci38457511-300km.csv")

    def test_preview_batch_returns_not_found(self):
        with patch.object(mcp_server.subprocess, "run", return_value=CompletedEvents):
            result = mcp_server.preview_batch("missing-event")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "EVENT_NOT_FOUND")

    def test_export_batch_adds_include_existing_and_csv_path(self):
        with patch.object(mcp_server.subprocess, "run", return_value=Completed) as run:
            result = mcp_server.export_batch("ci38457511", radius_km=300, include_existing=True)

        self.assertEqual(
            run.call_args.args[0][1:],
            ["export-batch", "--event-id", "ci38457511", "--radius-km", "300", "--include-existing"],
        )
        self.assertEqual(result["csv_path"], "data/batches/ci38457511-300km.csv")

    def test_batch_export_uses_unified_entrypoint(self):
        with patch.object(mcp_server.subprocess, "run", return_value=Completed) as run:
            result = mcp_server.batch("ci38457511", mode="export", radius_km=300, include_existing=True)

        self.assertEqual(
            run.call_args.args[0][1:],
            ["export-batch", "--event-id", "ci38457511", "--radius-km", "300", "--include-existing"],
        )
        self.assertEqual(result["csv_path"], "data/batches/ci38457511-300km.csv")

    def test_export_batch_adds_existing_data_error_code(self):
        with patch.object(mcp_server.subprocess, "run", return_value=ExistingDataFailure):
            result = mcp_server.export_batch("ci38457511")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "EVENT_ALREADY_HAS_NORMALIZED")
        self.assertEqual(result["suggested_action"], "retry_with_include_existing")

    def test_export_batch_rejects_invalid_event_id_and_radius(self):
        with self.assertRaises(ValueError):
            mcp_server.export_batch("bad/event")
        with self.assertRaises(ValueError):
            mcp_server.export_batch("ci38457511", radius_km=250)

    def test_run_batch_limits_csv_to_batch_root(self):
        with self.assertRaises(ValueError):
            mcp_server.run_batch("../outside.csv")

    def test_run_batch_requires_csv_suffix(self):
        with self.assertRaises(ValueError):
            mcp_server.run_batch("data/batches/example.tsv")

    def test_run_batch_rejects_timeout_above_max(self):
        with self.assertRaises(ValueError):
            mcp_server.run_batch("data/batches/example.csv", timeout=mcp_server.MAX_RUN_BATCH_TIMEOUT + 1)

    def test_run_command_adds_tail_fields(self):
        with patch.object(mcp_server.subprocess, "run", return_value=LongOutput):
            result = mcp_server.check_env()

        self.assertTrue(result["stdout_truncated"])
        self.assertIn("line-204", result["stdout_tail"])
        self.assertNotIn("line-0", result["stdout_tail"])

    def test_run_batch_builds_flags(self):
        csv_path = Path("data/batches/example.csv")
        with patch.object(mcp_server.subprocess, "run", return_value=Completed) as run:
            result = mcp_server.run_batch(
                str(csv_path),
                timeout=120,
                cleanup_pride_workdir=True,
                cleanup_obs=True,
                rerun_ok=True,
            )

        self.assertEqual(
            run.call_args.args[0][1:],
            [
                "run-batch",
                "--csv",
                "data/batches/example.csv",
                "--timeout",
                "120",
                "--cleanup-pride-workdir",
                "--cleanup-obs",
                "--rerun-ok",
            ],
        )
        self.assertEqual(run.call_args.kwargs["timeout"], 150)
        self.assertEqual(result["summary_hint"], "runs/batch-summary.tsv")

    def test_get_batch_summary_reads_and_filters_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "batch-summary.tsv"
            summary.write_text(
                "event_id\tstatus\tstation_count\n"
                "event-a\tOK\t2\n"
                "event-b\tFAILED\t0\n",
                encoding="utf-8",
            )
            with patch.object(mcp_server, "BATCH_SUMMARY", summary):
                result = mcp_server.get_batch_summary(event_id="event-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["rows"][0]["station_count"], 2)

    def test_get_batch_summary_returns_empty_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mcp_server, "BATCH_SUMMARY", Path(tmp) / "missing.tsv"):
                result = mcp_server.get_batch_summary()

        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"], [])

    def test_get_batch_summary_rejects_large_limit_and_invalid_event_id(self):
        with self.assertRaises(ValueError):
            mcp_server.get_batch_summary(limit=mcp_server.MAX_LIMIT + 1)
        with self.assertRaises(ValueError):
            mcp_server.get_batch_summary(event_id="bad/event")

    def test_overview_summary_reads_batch_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "batch-summary.tsv"
            summary.write_text(
                "event_id\tstatus\tstation_count\n"
                "event-a\tOK\t2\n",
                encoding="utf-8",
            )
            with patch.object(mcp_server, "BATCH_SUMMARY", summary):
                result = mcp_server.overview(view="summary", event_id="event-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["batch_summary"]["count"], 1)
        self.assertEqual(result["batch_summary"]["rows"][0]["status"], "OK")

    def test_overview_coverage_marks_workflow_and_collected_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            workflow_dir = Path(tmp) / "ci38457511" / "workflow-20260101"
            workflow_dir.mkdir(parents=True)
            with patch.object(mcp_server, "RUNS_ROOT", Path(tmp)):
                with patch.object(mcp_server.subprocess, "run", return_value=CompletedEvents):
                    result = mcp_server.overview(view="coverage")

        self.assertTrue(result["ok"])
        self.assertEqual(result["events"][0]["coverage_status"], "BOTH")
        self.assertEqual(result["events"][0]["priority"], "SKIP")

    def test_query_station_candidates_reports_missing_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mcp_server, "DEFAULT_DB", Path(tmp) / "missing.sqlite"):
                result = mcp_server.query_station_candidates("event-a")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "DATABASE_NOT_FOUND")

    def test_query_station_candidates_reads_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "earthscope.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE event_earthscope_station_candidates ("
                "event_id TEXT, station TEXT, station_latitude REAL, station_longitude REAL, distance_km REAL)"
            )
            conn.execute(
                "INSERT INTO event_earthscope_station_candidates VALUES (?, ?, ?, ?, ?)",
                ("event-a", "ABCD", 1.0, 2.0, 3.0),
            )
            conn.execute(
                "INSERT INTO event_earthscope_station_candidates VALUES (?, ?, ?, ?, ?)",
                ("event-a", "ABCD", 1.0, 2.0, 4.0),
            )
            conn.commit()
            conn.close()
            with patch.object(mcp_server, "DEFAULT_DB", db):
                result = mcp_server.query_station_candidates("event-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["stations"][0]["station"], "ABCD")
        self.assertEqual(result["stations"][0]["distance_km"], 3.0)

    def test_overview_stations_uses_station_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "earthscope.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE event_earthscope_station_candidates ("
                "event_id TEXT, station TEXT, station_latitude REAL, station_longitude REAL, distance_km REAL)"
            )
            conn.execute(
                "INSERT INTO event_earthscope_station_candidates VALUES (?, ?, ?, ?, ?)",
                ("event-a", "ABCD", 1.0, 2.0, 3.0),
            )
            conn.commit()
            conn.close()
            with patch.object(mcp_server, "DEFAULT_DB", db):
                result = mcp_server.overview(view="stations", event_id="event-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["stations"]["count"], 1)
        self.assertEqual(result["stations"]["stations"][0]["station"], "ABCD")

    def test_overview_geonet_events_and_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "geonet.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE geonet_m6plus_events_nz ("
                "event_id TEXT, magnitude REAL, event_date TEXT, place TEXT, "
                "existing_data_status TEXT, existing_station_count INTEGER)"
            )
            conn.execute(
                "CREATE TABLE event_highrate_day_availability ("
                "event_id TEXT, candidate_200km_station_count INTEGER, candidate_300km_station_count INTEGER, "
                "has_1hz INTEGER, file_count INTEGER, station_count INTEGER, candidate_300km_with_data_count INTEGER)"
            )
            conn.execute(
                "INSERT INTO geonet_m6plus_events_nz VALUES (?, ?, ?, ?, ?, ?)",
                ("nz-event", 6.5, "2020-01-01", "New Zealand", "", 0),
            )
            conn.execute(
                "INSERT INTO event_highrate_day_availability VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("nz-event", 25, 40, 1, 10, 8, 7),
            )
            conn.commit()
            conn.close()
            with patch.object(mcp_server, "GEONET_DB", db):
                result = mcp_server.overview(view="coverage", source="geonet")

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "geonet")
        self.assertEqual(result["events"][0]["event_id"], "nz-event")
        self.assertEqual(result["events"][0]["stations_200km"], 25)
        self.assertEqual(result["events"][0]["coverage_status"], "MISSING")
        self.assertEqual(result["events"][0]["priority"], "HIGH")

    def test_overview_geonet_stations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "geonet.sqlite"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE event_geonet_station_candidates ("
                "event_id TEXT, station TEXT, station_latitude REAL, station_longitude REAL, distance_km REAL, "
                "station9 TEXT, network TEXT, station_active_at_event INTEGER)"
            )
            conn.execute(
                "INSERT INTO event_geonet_station_candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("nz-event", "ABCD", -1.0, 2.0, 3.0, "ABCD00NZL", "NZ", 1),
            )
            conn.commit()
            conn.close()
            with patch.object(mcp_server, "GEONET_DB", db):
                result = mcp_server.overview(view="stations", source="geonet", event_id="nz-event")

        self.assertTrue(result["ok"])
        self.assertEqual(result["stations"]["count"], 1)
        self.assertEqual(result["stations"]["stations"][0]["station9"], "ABCD00NZL")


if __name__ == "__main__":
    unittest.main()
