from __future__ import annotations

import argparse
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from gnss_eq import cli


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
        with patch.object(cli.shutil, "which", return_value="/usr/bin/tool"):
            with patch.object(cli.Path, "exists", return_value=True):
                with patch.object(cli, "check_earthscope_auth", return_value=("OK", "access token available")):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        rc = cli.cmd_check_env(Mock())

        self.assertEqual(rc, 0)
        self.assertIn("OK\tEarthScope auth\taccess token available", output.getvalue())


if __name__ == "__main__":
    unittest.main()
