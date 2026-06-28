from __future__ import annotations

import argparse
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from gnss_eq import cli, preflight


class CompletedToken:
    returncode = 0
    stdout = "secret-token\n"
    stderr = ""


class FailedToken:
    returncode = 1
    stdout = ""
    stderr = "login required\ntraceback details"


class CliWorkflowCommandTest(unittest.TestCase):
    def test_run_batch_forwards_process_jobs(self):
        args = argparse.Namespace(
            csv="data/batches/example.csv",
            state_csv=None,
            timeout="120",
            hours="3",
            interval="1",
            run_root="runs",
            obs_root="data/obs",
            normalize_db="data/earthscope_availability/earthscope_nonconus_1hz.sqlite",
            verified_files_db="data/earthscope_availability/earthscope_nonconus_1hz.sqlite",
            post_seconds="200",
            process_jobs=5,
            summary=None,
            max_stations="0",
            skip_download=False,
            force_download=False,
            no_allow_partial=False,
            skip_process=False,
            skip_plot=False,
            cleanup_downloads=True,
            cleanup_pride_workdir=True,
            cleanup_obs=True,
            rerun_ok=True,
            dry_run=False,
        )
        with patch.object(cli, "run_command", return_value=0) as run_command:
            rc = cli.cmd_run_batch(args)

        self.assertEqual(rc, 0)
        command = run_command.call_args.args[0]
        self.assertIn("--process-jobs", command)
        self.assertEqual(command[command.index("--process-jobs") + 1], "5")
        self.assertIn("--normalize-db", command)
        self.assertTrue(command[command.index("--normalize-db") + 1].endswith("data/earthscope_availability/earthscope_nonconus_1hz.sqlite"))
        self.assertIn("--verified-files-db", command)
        self.assertTrue(command[command.index("--verified-files-db") + 1].endswith("data/earthscope_availability/earthscope_nonconus_1hz.sqlite"))


def create_monitor_earthscope_db(path: Path, event_table: str = "usgs_m6plus_events_usa") -> None:
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
        [("event-a", f"S{index:03d}", 1.0, 2.0, 3.0, 200.0) for index in range(6)]
        + [("event-a", "S300", 1.0, 2.0, 3.0, 300.0)],
    )
    conn.commit()
    conn.close()


def create_monitor_geonet_db(path: Path) -> None:
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
        ("geonet-a", 7.1, "2021-03-04", "GeoNet event", "", 0),
    )
    conn.execute(
        "INSERT INTO event_highrate_day_availability VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("geonet-a", 25, 40, 1, 100, 30, 25),
    )
    conn.commit()
    conn.close()


class CliMonitorCommandTest(unittest.TestCase):
    def test_monitor_tsv_reports_prioritized_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "earthscope.sqlite"
            create_monitor_earthscope_db(db)
            output = io.StringIO()
            with redirect_stdout(output):
                rc = cli.main(
                    [
                        "monitor",
                        "--source",
                        "earthscope",
                        "--earthscope-db",
                        str(db),
                        "--earthscope-nonconus-db",
                        str(root / "missing-nonconus.sqlite"),
                        "--runs-root",
                        str(root / "runs"),
                    ]
                )

        text = output.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("kind\tsource\tok", text)
        self.assertIn("SUMMARY\tearthscope\tTrue", text)
        self.assertIn("CANDIDATE\tearthscope\tTrue", text)
        self.assertIn("event-a", text)
        self.assertIn("MEDIUM\tMISSING", text)

    def test_monitor_json_reports_earthscope_and_geonet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            earthscope_db = root / "earthscope.sqlite"
            geonet_db = root / "geonet.sqlite"
            create_monitor_earthscope_db(earthscope_db)
            create_monitor_geonet_db(geonet_db)
            output = io.StringIO()
            with redirect_stdout(output):
                rc = cli.main(
                    [
                        "monitor",
                        "--source",
                        "all",
                        "--format",
                        "json",
                        "--earthscope-db",
                        str(earthscope_db),
                        "--earthscope-nonconus-db",
                        str(root / "missing-nonconus.sqlite"),
                        "--geonet-db",
                        str(geonet_db),
                        "--runs-root",
                        str(root / "runs"),
                    ]
                )

        report = json.loads(output.getvalue())
        self.assertEqual(rc, 0)
        self.assertTrue(report["read_only"])
        self.assertEqual([source["source"] for source in report["sources"]], ["earthscope", "geonet"])
        self.assertEqual(report["sources"][1]["candidates"][0]["event_id"], "geonet-a")
        self.assertEqual(report["sources"][1]["candidates"][0]["priority"], "HIGH")

    def test_monitor_handles_missing_dbs_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                rc = cli.main(
                    [
                        "monitor",
                        "--source",
                        "geonet",
                        "--geonet-db",
                        str(Path(tmp) / "missing.sqlite"),
                    ]
                )

        text = output.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("SUMMARY\tgeonet\tFalse", text)
        self.assertIn("ERROR\tgeonet\tFalse", text)
        self.assertIn("DATABASE_NOT_FOUND", text)

    def test_monitor_marks_workflow_done_from_runs_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "earthscope.sqlite"
            create_monitor_earthscope_db(db)
            (root / "runs" / "event-a" / "workflow-test").mkdir(parents=True)
            output = io.StringIO()
            with redirect_stdout(output):
                rc = cli.main(
                    [
                        "monitor",
                        "--source",
                        "earthscope",
                        "--format",
                        "json",
                        "--earthscope-db",
                        str(db),
                        "--earthscope-nonconus-db",
                        str(root / "missing-nonconus.sqlite"),
                        "--runs-root",
                        str(root / "runs"),
                    ]
                )

        report = json.loads(output.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(report["sources"][0]["counts"]["workflow_done"], 1)
        self.assertEqual(report["sources"][0]["counts"]["missing"], 0)
        self.assertEqual(report["sources"][0]["candidates"], [])

    def test_monitor_does_not_shell_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "earthscope.sqlite"
            create_monitor_earthscope_db(db)
            with patch.object(cli, "run_command", side_effect=AssertionError("run_command called")) as run_command:
                with patch.object(cli.subprocess, "run", side_effect=AssertionError("subprocess.run called")) as subprocess_run:
                    output = io.StringIO()
                    with redirect_stdout(output):
                        rc = cli.main(
                            [
                                "monitor",
                                "--source",
                                "earthscope",
                                "--earthscope-db",
                                str(db),
                                "--earthscope-nonconus-db",
                                str(root / "missing-nonconus.sqlite"),
                                "--runs-root",
                                str(root / "runs"),
                            ]
                        )

        self.assertEqual(rc, 0)
        run_command.assert_not_called()
        subprocess_run.assert_not_called()

    def test_watch_usgs_forwards_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_db = Path(tmp) / "watcher.sqlite"
            with patch.object(cli.usgs_watcher, "run_watch_loop", return_value=0) as run_watch_loop:
                rc = cli.main(
                    [
                        "watch-usgs",
                        "--once",
                        "--interval",
                        "123",
                        "--state-db",
                        str(state_db),
                        "--scope",
                        "nz",
                        "--min-magnitude",
                        "5.5",
                        "--lookback-minutes",
                        "60",
                        "--overlap-minutes",
                        "10",
                        "--limit",
                        "25",
                        "--timeout",
                        "9",
                        "--format",
                        "jsonl",
                    ]
                )

        self.assertEqual(rc, 0)
        args = run_watch_loop.call_args.args[0]
        self.assertTrue(args.once)
        self.assertEqual(args.interval, 123)
        self.assertEqual(args.state_db, str(state_db.resolve(strict=False)))
        self.assertEqual(args.scope, "nz")
        self.assertEqual(args.min_magnitude, 5.5)
        self.assertEqual(args.lookback_minutes, 60)
        self.assertEqual(args.overlap_minutes, 10)
        self.assertEqual(args.limit, 25)
        self.assertEqual(args.timeout, 9)
        self.assertEqual(args.format, "jsonl")

    def test_triage_usgs_forwards_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_db = root / "watcher.sqlite"
            earthscope_db = root / "earthscope.sqlite"
            earthscope_nonconus_db = root / "earthscope-nonconus.sqlite"
            geonet_db = root / "geonet.sqlite"
            runs_root = root / "runs"
            with patch.object(cli.usgs_triage, "build_triage_report", return_value={"ok": True, "counts": {}, "events": [], "errors": []}) as build_report:
                with patch.object(cli.usgs_triage, "write_triage_json") as write_json:
                    rc = cli.main(
                        [
                            "triage-usgs",
                            "--format",
                            "json",
                            "--source",
                            "geonet",
                            "--limit",
                            "7",
                            "--state-db",
                            str(state_db),
                            "--min-magnitude",
                            "5.5",
                            "--earthscope-db",
                            str(earthscope_db),
                            "--earthscope-nonconus-db",
                            str(earthscope_nonconus_db),
                            "--geonet-db",
                            str(geonet_db),
                            "--runs-root",
                            str(runs_root),
                        ]
                    )

        self.assertEqual(rc, 0)
        kwargs = build_report.call_args.kwargs
        self.assertEqual(kwargs["state_db"], state_db.resolve(strict=False))
        self.assertEqual(kwargs["source"], "geonet")
        self.assertEqual(kwargs["limit"], 7)
        self.assertEqual(kwargs["min_magnitude"], 5.5)
        self.assertEqual(kwargs["earthscope_db"], earthscope_db.resolve(strict=False))
        self.assertEqual(kwargs["earthscope_nonconus_db"], earthscope_nonconus_db.resolve(strict=False))
        self.assertEqual(kwargs["geonet_db"], geonet_db.resolve(strict=False))
        self.assertEqual(kwargs["runs_root"], runs_root.resolve(strict=False))
        write_json.assert_called_once()

    def test_triage_usgs_does_not_shell_out_or_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(cli, "run_command", side_effect=AssertionError("run_command called")) as run_command:
                with patch.object(cli.subprocess, "run", side_effect=AssertionError("subprocess.run called")) as subprocess_run:
                    with patch.object(cli.usgs_watcher, "poll_once", side_effect=AssertionError("poll_once called")) as poll_once:
                        with patch.object(cli.usgs_watcher, "run_watch_loop", side_effect=AssertionError("run_watch_loop called")) as run_watch_loop:
                            output = io.StringIO()
                            with redirect_stdout(output):
                                rc = cli.main(
                                    [
                                        "triage-usgs",
                                        "--state-db",
                                        str(root / "missing.sqlite"),
                                        "--earthscope-db",
                                        str(root / "missing-earthscope.sqlite"),
                                        "--earthscope-nonconus-db",
                                        str(root / "missing-nonconus.sqlite"),
                                        "--geonet-db",
                                        str(root / "missing-geonet.sqlite"),
                                    ]
                                )

        self.assertEqual(rc, 0)
        self.assertIn("DATABASE_NOT_FOUND", output.getvalue())
        run_command.assert_not_called()
        subprocess_run.assert_not_called()
        poll_once.assert_not_called()
        run_watch_loop.assert_not_called()

    def test_import_usgs_earthscope_events_forwards_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_db = root / "watcher.sqlite"
            earthscope_db = root / "earthscope.sqlite"
            earthscope_nonconus_db = root / "earthscope-nonconus.sqlite"
            with patch.object(cli.earthscope_event_import, "import_watched_events", return_value={"ok": True}) as importer:
                with patch.object(cli.earthscope_event_import, "write_import_json") as write_json:
                    rc = cli.main(
                        [
                            "import-usgs-earthscope-events",
                            "--format",
                            "json",
                            "--state-db",
                            str(state_db),
                            "--target",
                            "nonconus",
                            "--event-id",
                            "event-a",
                            "--event-id",
                            "event-b",
                            "--min-magnitude",
                            "5.5",
                            "--limit",
                            "8",
                            "--earthscope-db",
                            str(earthscope_db),
                            "--earthscope-nonconus-db",
                            str(earthscope_nonconus_db),
                            "--dry-run",
                            "--update-existing",
                        ]
                    )

        self.assertEqual(rc, 0)
        kwargs = importer.call_args.kwargs
        self.assertEqual(kwargs["state_db"], state_db.resolve(strict=False))
        self.assertEqual(kwargs["target"], "nonconus")
        self.assertEqual(kwargs["event_ids"], ["event-a", "event-b"])
        self.assertEqual(kwargs["min_magnitude"], 5.5)
        self.assertEqual(kwargs["limit"], 8)
        self.assertEqual(kwargs["earthscope_db"], earthscope_db.resolve(strict=False))
        self.assertEqual(kwargs["earthscope_nonconus_db"], earthscope_nonconus_db.resolve(strict=False))
        self.assertTrue(kwargs["dry_run"])
        self.assertTrue(kwargs["update_existing"])
        write_json.assert_called_once()

    def test_import_usgs_earthscope_events_does_not_shell_out_or_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(cli, "run_command", side_effect=AssertionError("run_command called")) as run_command:
                with patch.object(cli.subprocess, "run", side_effect=AssertionError("subprocess.run called")) as subprocess_run:
                    with patch.object(cli.usgs_watcher, "poll_once", side_effect=AssertionError("poll_once called")) as poll_once:
                        with patch.object(cli.usgs_watcher, "run_watch_loop", side_effect=AssertionError("run_watch_loop called")) as run_watch_loop:
                            output = io.StringIO()
                            with redirect_stdout(output):
                                rc = cli.main(
                                    [
                                        "import-usgs-earthscope-events",
                                        "--state-db",
                                        str(root / "missing.sqlite"),
                                        "--earthscope-db",
                                        str(root / "missing-earthscope.sqlite"),
                                        "--earthscope-nonconus-db",
                                        str(root / "missing-nonconus.sqlite"),
                                    ]
                                )

        self.assertEqual(rc, 1)
        self.assertIn("DATABASE_NOT_FOUND", output.getvalue())
        run_command.assert_not_called()
        subprocess_run.assert_not_called()
        poll_once.assert_not_called()
        run_watch_loop.assert_not_called()

    def test_review_usgs_runs_safe_steps_and_writes_triage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_db = root / "watcher.sqlite"
            earthscope_db = root / "earthscope.sqlite"
            earthscope_nonconus_db = root / "earthscope-nonconus.sqlite"
            geonet_db = root / "geonet.sqlite"
            runs_root = root / "runs"
            metadata_root = root / "metadata"
            triage_report = {"ok": True, "counts": {}, "events": [], "errors": []}
            with patch.object(cli, "run_no_proxy_command", return_value=0) as run_no_proxy:
                with patch.object(cli.earthscope_event_import, "import_watched_events", return_value={"ok": True}) as importer:
                    with patch.object(cli.usgs_triage, "build_triage_report", return_value=triage_report) as build_report:
                        with patch.object(cli.usgs_triage, "write_triage_json") as write_json:
                            rc = cli.main(
                                [
                                    "review-usgs",
                                    "--format",
                                    "json",
                                    "--source",
                                    "earthscope",
                                    "--state-db",
                                    str(state_db),
                                    "--target",
                                    "nonconus",
                                    "--event-id",
                                    "event-a",
                                    "--min-magnitude",
                                    "5.5",
                                    "--limit",
                                    "8",
                                    "--recent-days",
                                    "3",
                                    "--earthscope-db",
                                    str(earthscope_db),
                                    "--earthscope-nonconus-db",
                                    str(earthscope_nonconus_db),
                                    "--earthscope-metadata-root",
                                    str(metadata_root),
                                    "--geonet-db",
                                    str(geonet_db),
                                    "--runs-root",
                                    str(runs_root),
                                    "--dry-run",
                                    "--update-existing",
                                ]
                            )

        self.assertEqual(rc, 0)
        commands = [call.args[0] for call in run_no_proxy.call_args_list]
        self.assertEqual(len(commands), 4)
        self.assertTrue(commands[0][1].endswith("scripts/availability/update_earthscope_availability.py"))
        self.assertEqual(commands[0][commands[0].index("--db") + 1], str(earthscope_db.resolve(strict=False)))
        self.assertEqual(commands[0][commands[0].index("--recent-days") + 1], "3")
        self.assertTrue(commands[1][1].endswith("scripts/availability/update_earthscope_availability.py"))
        self.assertEqual(commands[1][commands[1].index("--db") + 1], str(earthscope_nonconus_db.resolve(strict=False)))
        self.assertTrue(commands[2][1].endswith("scripts/availability/rebuild_event_station_candidates.py"))
        self.assertEqual(commands[2][commands[2].index("--db") + 1], str(earthscope_db.resolve(strict=False)))
        self.assertEqual(commands[2][commands[2].index("--event-id") + 1], "event-a")
        self.assertIn("--dry-run", commands[2])
        self.assertTrue(commands[3][1].endswith("scripts/availability/rebuild_event_station_candidates.py"))
        kwargs = importer.call_args.kwargs
        self.assertEqual(kwargs["state_db"], state_db.resolve(strict=False))
        self.assertEqual(kwargs["target"], "nonconus")
        self.assertEqual(kwargs["event_ids"], ["event-a"])
        self.assertEqual(kwargs["min_magnitude"], 5.5)
        self.assertEqual(kwargs["limit"], 8)
        self.assertEqual(kwargs["earthscope_db"], earthscope_db.resolve(strict=False))
        self.assertEqual(kwargs["earthscope_nonconus_db"], earthscope_nonconus_db.resolve(strict=False))
        self.assertTrue(kwargs["dry_run"])
        self.assertTrue(kwargs["update_existing"])
        triage_kwargs = build_report.call_args.kwargs
        self.assertEqual(triage_kwargs["state_db"], state_db.resolve(strict=False))
        self.assertEqual(triage_kwargs["source"], "earthscope")
        self.assertEqual(triage_kwargs["earthscope_db"], earthscope_db.resolve(strict=False))
        self.assertEqual(triage_kwargs["earthscope_nonconus_db"], earthscope_nonconus_db.resolve(strict=False))
        self.assertEqual(triage_kwargs["geonet_db"], geonet_db.resolve(strict=False))
        self.assertEqual(triage_kwargs["runs_root"], runs_root.resolve(strict=False))
        write_json.assert_called_once_with(triage_report)

    def test_review_usgs_does_not_poll_or_run_processing_workflows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            commands: list[list[str]] = []

            def fake_run(command: list[str], stdout: object | None = None) -> int:
                commands.append(command)
                joined = " ".join(command)
                self.assertNotIn("run_event_1hz_pride_workflow.sh", joined)
                self.assertNotIn("run_event_batch_workflow.sh", joined)
                self.assertNotIn("run_geonet_event_1hz_pride_workflow.sh", joined)
                self.assertNotIn("run_geonet_batch_workflow.sh", joined)
                return 0

            with patch.object(cli, "run_command", side_effect=AssertionError("run_command called")) as run_command:
                with patch.object(cli, "run_no_proxy_command", side_effect=fake_run) as run_no_proxy:
                    with patch.object(cli.subprocess, "run", side_effect=AssertionError("subprocess.run called")) as subprocess_run:
                        with patch.object(cli.usgs_watcher, "poll_once", side_effect=AssertionError("poll_once called")) as poll_once:
                            with patch.object(cli.usgs_watcher, "run_watch_loop", side_effect=AssertionError("run_watch_loop called")) as run_watch_loop:
                                with patch.object(cli.earthscope_event_import, "import_watched_events", return_value={"ok": True}) as importer:
                                    output = io.StringIO()
                                    with redirect_stdout(output):
                                        rc = cli.main(
                                            [
                                                "review-usgs",
                                                "--source",
                                                "earthscope",
                                                "--state-db",
                                                str(root / "missing.sqlite"),
                                                "--earthscope-db",
                                                str(root / "earthscope.sqlite"),
                                                "--earthscope-nonconus-db",
                                                str(root / "earthscope-nonconus.sqlite"),
                                                "--geonet-db",
                                                str(root / "geonet.sqlite"),
                                            ]
                                        )

        self.assertEqual(rc, 0)
        self.assertIn("DATABASE_NOT_FOUND", output.getvalue())
        self.assertEqual(len(commands), 4)
        run_command.assert_not_called()
        run_no_proxy.assert_called()
        subprocess_run.assert_not_called()
        poll_once.assert_not_called()
        run_watch_loop.assert_not_called()
        importer.assert_called_once()


class CliCheckEnvTest(unittest.TestCase):
    def test_check_earthscope_auth_reports_ok_without_token(self):
        with patch.object(cli.shutil, "which", return_value="/usr/bin/es"):
            with patch.object(cli.subprocess, "run", return_value=CompletedToken):
                status, detail = cli.check_earthscope_auth()

        self.assertEqual(status, "OK")
        self.assertEqual(detail, "access token available")
        self.assertNotIn("secret-token", detail)
        self.assertNotIn("es login", detail)

    def test_check_earthscope_auth_reports_failure(self):
        with patch.object(cli.shutil, "which", return_value="/usr/bin/es"):
            with patch.object(cli.subprocess, "run", return_value=FailedToken):
                status, detail = cli.check_earthscope_auth()

        self.assertEqual(status, "FAIL")
        self.assertEqual(detail, "login required; run: es login")

    def test_check_env_includes_earthscope_auth(self):
        ok_checks = [preflight.CheckResult("OK", f"command {command}", f"/usr/bin/{command}") for command in preflight.REQUIRED_COMMANDS]
        ok_checks.extend(preflight.CheckResult("OK", name, str(path)) for name, path in preflight.REQUIRED_SCRIPTS)
        with patch.object(preflight, "command_checks", return_value=ok_checks[: len(preflight.REQUIRED_COMMANDS)]):
            with patch.object(preflight, "script_checks", return_value=ok_checks[len(preflight.REQUIRED_COMMANDS) :]):
                with patch.object(cli, "check_earthscope_auth", return_value=("OK", "access token available")):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        rc = cli.cmd_check_env(Mock())

        self.assertEqual(rc, 0)
        self.assertIn("OK\tEarthScope auth\taccess token available", output.getvalue())
        self.assertIn("OK\tcommand CRX2RNX\t/usr/bin/CRX2RNX", output.getvalue())

    def test_preflight_command_returns_report(self):
        results = [preflight.CheckResult("PREFLIGHT_OK", "EarthScope preflight", "all blocking checks passed", fatal=False)]
        args = Mock(db="db.sqlite", verified_files_db="", timeout=1.0, no_connectivity=False, no_database=False, format="tsv")
        with patch.object(preflight, "run_preflight", return_value=(results, 0)):
            output = io.StringIO()
            with redirect_stdout(output):
                rc = cli.cmd_preflight_earthscope(args)

        self.assertEqual(rc, 0)
        self.assertIn("PREFLIGHT_OK\tEarthScope preflight\tall blocking checks passed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
