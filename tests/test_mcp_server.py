from __future__ import annotations

import json
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


class PreflightFailure:
    returncode = 2
    stdout = "FAIL\tEarthScope auth\tlogin required; run: es login\nPREFLIGHT_FAILED\tEarthScope preflight\t1 blocking check(s); batch not started\n"
    stderr = ""


def create_earthscope_db(path: Path, event_table: str = "usgs_m6plus_events_usa") -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        f"CREATE TABLE {event_table} ("
        "event_id TEXT, magnitude REAL, event_date TEXT, time_utc TEXT, place TEXT, "
        "existing_data_status TEXT, existing_station_count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE event_earthscope_station_candidates ("
        "event_id TEXT, station TEXT, station_latitude REAL, station_longitude REAL, distance_km REAL, radius_km REAL)"
    )
    conn.execute(
        f"INSERT INTO {event_table} VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("event-a", 6.2, "2020-01-02", "2020-01-02T03:04:05Z", "Test event", "", 0),
    )
    conn.executemany(
        "INSERT INTO event_earthscope_station_candidates VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("event-a", "ABCD", 1.0, 2.0, 3.0, 200.0),
            ("event-a", "EFGH", 4.0, 5.0, 6.0, 200.0),
            ("event-a", "IJKL", 7.0, 8.0, 9.0, 300.0),
        ],
    )
    conn.commit()
    conn.close()


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
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "earthscope.sqlite"
            create_earthscope_db(db)
            conn = sqlite3.connect(db)
            conn.execute("UPDATE usgs_m6plus_events_usa SET existing_data_status = ?, existing_station_count = ?", ("HAS_NORMALIZED", 490))
            conn.commit()
            conn.close()
            with patch.object(mcp_server, "DEFAULT_DB", db):
                result = mcp_server.preview_batch("event-a", radius_km=200)

        self.assertTrue(result["ok"])
        self.assertEqual(result["station_count"], 2)
        self.assertTrue(result["has_existing_normalized"])
        self.assertTrue(result["would_fail_without_include_existing"])
        self.assertFalse(result["would_export"])

    def test_batch_preview_uses_unified_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "earthscope.sqlite"
            create_earthscope_db(db)
            with patch.object(mcp_server, "DEFAULT_DB", db):
                result = mcp_server.batch("event-a", mode="preview", radius_km=200)

        self.assertTrue(result["ok"])
        self.assertEqual(result["station_count"], 2)
        self.assertEqual(result["source"], "earthscope")

    def test_preview_batch_allows_include_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "earthscope.sqlite"
            create_earthscope_db(db)
            conn = sqlite3.connect(db)
            conn.execute("UPDATE usgs_m6plus_events_usa SET existing_data_status = ?", ("HAS_NORMALIZED",))
            conn.commit()
            conn.close()
            with patch.object(mcp_server, "DEFAULT_DB", db):
                result = mcp_server.preview_batch("event-a", radius_km=300, include_existing=True)

        self.assertTrue(result["would_export"])
        self.assertEqual(result["station_count"], 1)
        self.assertEqual(result["csv_path"], "data/batches/event-a-300km.csv")

    def test_preview_batch_returns_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "earthscope.sqlite"
            create_earthscope_db(db)
            with patch.object(mcp_server, "DEFAULT_DB", db):
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

    def test_batch_preview_accepts_nonconus_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "nonconus.sqlite"
            create_earthscope_db(db, event_table="usgs_m6plus_events_earthscope_nonconus")
            with patch.object(mcp_server, "NONCONUS_DB", db):
                result = mcp_server.batch("event-a", mode="preview", radius_km=300, source="earthscope_nonconus")

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "earthscope")
        self.assertEqual(result["requested_source"], "earthscope_nonconus")
        self.assertEqual(result["earthscope_subset"], "nonconus")
        self.assertEqual(result["db"], str(db))
        self.assertEqual(result["station_count"], 1)

    def test_batch_export_passes_nonconus_pipeline_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "nonconus.sqlite"
            create_earthscope_db(db, event_table="usgs_m6plus_events_earthscope_nonconus")
            with patch.object(mcp_server, "NONCONUS_DB", db):
                with patch.object(mcp_server.subprocess, "run", return_value=Completed) as run:
                    result = mcp_server.batch("event-a", mode="export", radius_km=300, source="earthscope_nonconus")

        self.assertEqual(
            run.call_args.args[0][1:],
            ["export-batch", "--event-id", "event-a", "--radius-km", "300"],
        )
        self.assertEqual(run.call_args.kwargs["env"]["PIPELINE_DB"], str(db))
        self.assertEqual(result["source"], "earthscope")
        self.assertEqual(result["requested_source"], "earthscope_nonconus")
        self.assertEqual(result["earthscope_subset"], "nonconus")

    def test_batch_default_earthscope_finds_nonconus_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            default_db = Path(tmp) / "earthscope.sqlite"
            nonconus_db = Path(tmp) / "nonconus.sqlite"
            create_earthscope_db(default_db)
            create_earthscope_db(nonconus_db, event_table="usgs_m6plus_events_earthscope_nonconus")
            conn = sqlite3.connect(nonconus_db)
            conn.execute("UPDATE usgs_m6plus_events_earthscope_nonconus SET event_id = ?", ("event-b",))
            conn.execute("UPDATE event_earthscope_station_candidates SET event_id = ?", ("event-b",))
            conn.commit()
            conn.close()
            with patch.object(mcp_server, "DEFAULT_DB", default_db):
                with patch.object(mcp_server, "NONCONUS_DB", nonconus_db):
                    result = mcp_server.batch("event-b", mode="preview", radius_km=300)

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "earthscope")
        self.assertEqual(result["requested_source"], "earthscope")
        self.assertEqual(result["earthscope_subset"], "nonconus")
        self.assertEqual(result["db"], str(nonconus_db))

    def test_batch_rejects_non_earthscope_sources(self):
        for source in ("geonet", "paper"):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    mcp_server.batch("event-a", source=source)

    def test_run_batch_rejects_mixed_earthscope_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch_root = Path(tmp) / "batches"
            batch_root.mkdir()
            csv_path = batch_root / "mixed.csv"
            csv_path.write_text(
                "event_id,event_time,stations,status\n"
                "event-a,2020-01-02T03:04:05Z,ABCD,PENDING\n"
                "event-b,2020-01-03T03:04:05Z,IJKL,PENDING\n",
                encoding="utf-8",
            )
            default_db = Path(tmp) / "earthscope.sqlite"
            nonconus_db = Path(tmp) / "nonconus.sqlite"
            create_earthscope_db(default_db)
            create_earthscope_db(nonconus_db, event_table="usgs_m6plus_events_earthscope_nonconus")
            conn = sqlite3.connect(nonconus_db)
            conn.execute("UPDATE usgs_m6plus_events_earthscope_nonconus SET event_id = ?", ("event-b",))
            conn.execute("UPDATE event_earthscope_station_candidates SET event_id = ?", ("event-b",))
            conn.commit()
            conn.close()
            with patch.object(mcp_server, "BATCH_ROOT", batch_root):
                with patch.object(mcp_server, "DEFAULT_DB", default_db):
                    with patch.object(mcp_server, "NONCONUS_DB", nonconus_db):
                        with self.assertRaisesRegex(ValueError, "MIXED_EARTHSCOPE_BATCH"):
                            mcp_server.run_batch(str(csv_path))

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
            mcp_server.export_batch("ci38457511", radius_km=750)

    def test_run_batch_limits_csv_to_batch_root(self):
        with self.assertRaises(ValueError):
            mcp_server.run_batch("../outside.csv")

    def test_run_batch_requires_csv_suffix(self):
        with self.assertRaises(ValueError):
            mcp_server.run_batch("data/batches/example.tsv")

    def test_run_batch_rejects_timeout_above_max(self):
        with self.assertRaises(ValueError):
            mcp_server.run_batch("data/batches/example.csv", timeout=mcp_server.MAX_RUN_BATCH_TIMEOUT + 1)

    def test_run_batch_rejects_invalid_process_jobs(self):
        for process_jobs in (0, -1, mcp_server.MAX_PROCESS_JOBS + 1):
            with self.subTest(process_jobs=process_jobs):
                with self.assertRaises(ValueError):
                    mcp_server.run_batch("data/batches/example.csv", process_jobs=process_jobs)

    def test_run_command_adds_tail_fields(self):
        with patch.object(mcp_server.subprocess, "run", return_value=LongOutput):
            result = mcp_server.check_env()

        self.assertTrue(result["stdout_truncated"])
        self.assertIn("line-204", result["stdout_tail"])
        self.assertNotIn("line-0", result["stdout_tail"])

    def test_run_command_strips_proxy_environment(self):
        with patch.dict(mcp_server.os.environ, {"http_proxy": "http://proxy", "HTTPS_PROXY": "http://proxy"}, clear=False):
            with patch.object(mcp_server.subprocess, "run", return_value=Completed) as run:
                mcp_server.check_env()

        run_env = run.call_args.kwargs["env"]
        self.assertNotIn("http_proxy", run_env)
        self.assertNotIn("HTTPS_PROXY", run_env)

    def test_run_batch_marks_preflight_failure(self):
        csv_path = Path("data/batches/example.csv")
        with patch.object(mcp_server.subprocess, "run", return_value=PreflightFailure):
            result = mcp_server.run_batch(str(csv_path), source="earthscope_nonconus")

        self.assertFalse(result["ok"])
        self.assertEqual(result["returncode"], 2)
        self.assertEqual(result["error_code"], "EARTHSCOPE_PREFLIGHT_FAILED")
        self.assertEqual(result["suggested_action"], "inspect_preflight_report")
        self.assertIn("PREFLIGHT_FAILED", result["stdout"])

    def test_run_batch_builds_flags(self):
        csv_path = Path("data/batches/example.csv")
        with patch.object(mcp_server.subprocess, "run", return_value=Completed) as run:
            result = mcp_server.run_batch(
                str(csv_path),
                timeout=120,
                process_jobs=5,
                cleanup_pride_workdir=True,
                cleanup_obs=True,
                rerun_ok=True,
                source="earthscope_nonconus",
                use_verified_files=True,
            )

        self.assertEqual(
            run.call_args.args[0][1:],
            [
                "run-batch",
                "--csv",
                "data/batches/example.csv",
                "--timeout",
                "120",
                "--process-jobs",
                "5",
                "--cleanup-pride-workdir",
                "--cleanup-obs",
                "--rerun-ok",
            ],
        )
        self.assertEqual(run.call_args.kwargs["timeout"], 150)
        self.assertEqual(run.call_args.kwargs["env"]["PIPELINE_DB"], str(mcp_server.NONCONUS_DB))
        self.assertEqual(run.call_args.kwargs["env"]["PIPELINE_VERIFIED_FILES_DB"], str(mcp_server.NONCONUS_DB))
        self.assertEqual(result["summary_hint"], "data/batches/batch-summary.tsv")
        self.assertEqual(result["process_jobs"], 5)
        self.assertEqual(result["source"], "earthscope")
        self.assertEqual(result["requested_source"], "earthscope_nonconus")
        self.assertEqual(result["earthscope_subset"], "earthscope_nonconus")
        self.assertEqual(result["db"], "data/earthscope_availability/earthscope_nonconus_1hz.sqlite")
        self.assertTrue(result["use_verified_files"])

    def test_get_batch_summary_reads_and_filters_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "batch-summary.tsv"
            legacy_summary = Path(tmp) / "legacy-batch-summary.tsv"
            summary.write_text(
                "event_id\tstatus\tstation_count\n"
                "event-a\tOK\t2\n"
                "event-b\tFAILED\t0\n",
                encoding="utf-8",
            )
            with patch.object(mcp_server, "BATCH_SUMMARY", summary):
                with patch.object(mcp_server, "LEGACY_BATCH_SUMMARY", legacy_summary):
                    result = mcp_server.get_batch_summary(event_id="event-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["path"], str(summary))
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["rows"][0]["station_count"], 2)

    def test_get_batch_summary_falls_back_to_legacy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "missing-batch-summary.tsv"
            legacy_summary = Path(tmp) / "legacy-batch-summary.tsv"
            legacy_summary.write_text(
                "event_id\tstatus\tstation_count\n"
                "event-a\tOK\t2\n",
                encoding="utf-8",
            )
            with patch.object(mcp_server, "BATCH_SUMMARY", summary):
                with patch.object(mcp_server, "LEGACY_BATCH_SUMMARY", legacy_summary):
                    result = mcp_server.get_batch_summary(event_id="event-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["path"], str(legacy_summary))
        self.assertEqual(result["count"], 1)

    def test_get_batch_summary_returns_empty_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mcp_server, "BATCH_SUMMARY", Path(tmp) / "missing.tsv"):
                with patch.object(mcp_server, "LEGACY_BATCH_SUMMARY", Path(tmp) / "legacy-missing.tsv"):
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
            legacy_summary = Path(tmp) / "legacy-batch-summary.tsv"
            summary.write_text(
                "event_id\tstatus\tstation_count\n"
                "event-a\tOK\t2\n",
                encoding="utf-8",
            )
            with patch.object(mcp_server, "BATCH_SUMMARY", summary):
                with patch.object(mcp_server, "LEGACY_BATCH_SUMMARY", legacy_summary):
                    result = mcp_server.overview(view="summary", event_id="event-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["batch_summary"]["count"], 1)
        self.assertEqual(result["batch_summary"]["rows"][0]["status"], "OK")

    def test_overview_summary_includes_latest_workflow_summary_for_earthscope_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch_summary = Path(tmp) / "batch-summary.tsv"
            legacy_summary = Path(tmp) / "legacy-batch-summary.tsv"
            batch_summary.write_text("event_id\tstatus\nevent-a\tOK\n", encoding="utf-8")
            workflow_reports = Path(tmp) / "event-a" / "workflow-20260101T000000Z" / "reports"
            workflow_reports.mkdir(parents=True)
            (workflow_reports / "workflow-summary.tsv").write_text(
                "key\tvalue\n"
                "event_id\tevent-a\n"
                "normalized_status\tOK\n"
                "normalized_station_count\t3\n",
                encoding="utf-8",
            )
            with patch.object(mcp_server, "BATCH_SUMMARY", batch_summary):
                with patch.object(mcp_server, "LEGACY_BATCH_SUMMARY", legacy_summary):
                    with patch.object(mcp_server, "RUNS_ROOT", Path(tmp)):
                        result = mcp_server.overview(view="summary", event_id="event-a", source="earthscope_nonconus")

        self.assertTrue(result["ok"])
        self.assertEqual(result["batch_summary"]["count"], 1)
        self.assertEqual(result["latest_workflow"]["values"]["normalized_status"], "OK")
        self.assertEqual(result["latest_workflow"]["values"]["normalized_station_count"], 3)

    def test_overview_summary_marks_geonet_as_not_applicable(self):
        result = mcp_server.overview(view="summary", event_id="nz-event", source="geonet")

        self.assertTrue(result["ok"])
        self.assertEqual(result["summary"]["status"], "NOT_APPLICABLE")
        self.assertEqual(result["summary"]["source"], "geonet")

    def test_overview_coverage_marks_workflow_and_collected_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "earthscope.sqlite"
            create_earthscope_db(db)
            conn = sqlite3.connect(db)
            conn.execute("UPDATE usgs_m6plus_events_usa SET existing_data_status = ?, existing_station_count = ?", ("HAS_NORMALIZED", 3))
            conn.commit()
            conn.close()
            workflow_dir = Path(tmp) / "event-a" / "workflow-20260101"
            workflow_dir.mkdir(parents=True)
            with patch.object(mcp_server, "DEFAULT_DB", db):
                with patch.object(mcp_server, "NONCONUS_DB", Path(tmp) / "missing-nonconus.sqlite"):
                    with patch.object(mcp_server, "RUNS_ROOT", Path(tmp)):
                        result = mcp_server.overview(view="coverage")

        self.assertTrue(result["ok"])
        self.assertEqual(result["events"][0]["coverage_status"], "BOTH")
        self.assertEqual(result["events"][0]["priority"], "SKIP")

    def test_overview_nonconus_events_and_stations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "nonconus.sqlite"
            create_earthscope_db(db, event_table="usgs_m6plus_events_earthscope_nonconus")
            with patch.object(mcp_server, "NONCONUS_DB", db):
                coverage = mcp_server.overview(view="coverage", source="earthscope_nonconus")
                stations = mcp_server.overview(view="stations", source="earthscope_nonconus", event_id="event-a")

        self.assertTrue(coverage["ok"])
        self.assertEqual(coverage["source"], "earthscope_nonconus")
        self.assertEqual(coverage["events"][0]["event_id"], "event-a")
        self.assertEqual(coverage["events"][0]["stations_200km"], 2)
        self.assertEqual(coverage["events"][0]["stations_300km"], 1)
        self.assertEqual(stations["stations"]["source"], "earthscope")
        self.assertEqual(stations["stations"]["requested_source"], "earthscope_nonconus")
        self.assertEqual(stations["stations"]["earthscope_subset"], "nonconus")
        self.assertEqual(stations["stations"]["count"], 3)

    def test_query_station_candidates_reports_missing_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mcp_server, "NONCONUS_DB", Path(tmp) / "missing.sqlite"):
                result = mcp_server.query_station_candidates("event-a", source="earthscope_nonconus")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "EVENT_NOT_FOUND")

    def test_query_station_candidates_reads_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "earthscope.sqlite"
            create_earthscope_db(db)
            with patch.object(mcp_server, "DEFAULT_DB", db):
                result = mcp_server.query_station_candidates("event-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["stations"][0]["station"], "ABCD")
        self.assertEqual(result["stations"][0]["distance_km"], 3.0)

    def test_overview_stations_uses_station_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "earthscope.sqlite"
            create_earthscope_db(db)
            with patch.object(mcp_server, "DEFAULT_DB", db):
                result = mcp_server.overview(view="stations", event_id="event-a")

        self.assertTrue(result["ok"])
        self.assertEqual(result["stations"]["count"], 3)
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

    def test_overview_paper_events_reads_normalized_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            event_dir = Path(tmp) / "kaikoura-2016-new-zealand"
            event_dir.mkdir()
            (event_dir / "event.json").write_text(
                json.dumps(
                    {
                        "event": "M 7.8 - Kaikoura",
                        "usgs_event_id": "us1000778i",
                        "date": "2016-11-13T11:02:56Z",
                        "magnitude": 7.8,
                        "stations": 36,
                        "country": "New Zealand",
                        "source": "Zenodo: Ruhl et al. 2018 / Kaikoura2016",
                        "data_type": "direct_waveform",
                        "paper_title": "High-rate GNSS displacement waveforms for large earthquakes version 2.0",
                        "paper_url": "https://zenodo.org/records/1434374",
                        "parse_status": "normalized",
                        "usgs_place": "53 km NNE of Amberley, New Zealand",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(mcp_server, "PAPER_COLLECTION_ROOT", Path(tmp)):
                result = mcp_server.overview(view="events", source="paper")

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "paper")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["format"], "normalized_directory")
        self.assertEqual(result["events"][0]["event_id"], "us1000778i")
        self.assertEqual(result["events"][0]["dataset_dir"], "kaikoura-2016-new-zealand")
        self.assertEqual(result["events"][0]["collection_status"], "PAPER_NORMALIZED")

    def test_overview_paper_coverage_marks_collection_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            event_dir = Path(tmp) / "ridgecrest-2019-california-m7-1"
            event_dir.mkdir()
            (event_dir / "event.json").write_text(
                json.dumps(
                    {
                        "usgs_event_id": "ci38457511",
                        "date": "2019-07-06T03:19:53Z",
                        "magnitude": 7.1,
                        "stations": 490,
                        "country": "USA",
                        "usgs_place": "Ridgecrest Earthquake Sequence",
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(mcp_server, "PAPER_COLLECTION_ROOT", Path(tmp)):
                result = mcp_server.overview(view="coverage", source="paper")

        self.assertTrue(result["ok"])
        self.assertEqual(result["events"][0]["coverage_status"], "COLLECTED_NORMALIZED")
        self.assertEqual(result["events"][0]["existing_data_status"], "HAS_NORMALIZED")
        self.assertEqual(result["events"][0]["collection_status"], "PAPER_NORMALIZED")


if __name__ == "__main__":
    unittest.main()
