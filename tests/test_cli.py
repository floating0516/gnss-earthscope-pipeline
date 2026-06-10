from __future__ import annotations

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
