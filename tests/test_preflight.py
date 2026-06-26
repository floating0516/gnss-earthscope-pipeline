from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gnss_eq import preflight


class CompletedToken:
    returncode = 0
    stdout = "secret-token\n"
    stderr = ""


class FailedToken:
    returncode = 1
    stdout = ""
    stderr = "login required\ntraceback details"


class CompletedCurl:
    returncode = 0
    stdout = "http_code=200"
    stderr = ""


class PreflightTest(unittest.TestCase):
    def test_missing_pdp3_is_fatal(self):
        def which(command, path=None):
            return None if command == "pdp3" else f"/usr/bin/{command}"

        with patch.object(preflight.shutil, "which", side_effect=which):
            with patch.object(preflight.subprocess, "run", return_value=CompletedToken):
                results, rc = preflight.run_preflight(include_connectivity=False, include_database=False)

        self.assertEqual(rc, 2)
        self.assertTrue(any(result.name == "command pdp3" and result.status == "MISSING" for result in results))
        self.assertTrue(any(result.status == "PREFLIGHT_FAILED" for result in results))

    def test_missing_crx2rnx_is_fatal(self):
        def which(command, path=None):
            return None if command == "CRX2RNX" else f"/usr/bin/{command}"

        with patch.object(preflight.shutil, "which", side_effect=which):
            with patch.object(preflight.subprocess, "run", return_value=CompletedToken):
                results, rc = preflight.run_preflight(include_connectivity=False, include_database=False)

        self.assertEqual(rc, 2)
        self.assertTrue(any(result.name == "command CRX2RNX" and result.status == "MISSING" for result in results))

    def test_auth_failure_reports_login_without_token(self):
        with patch.object(preflight.shutil, "which", return_value="/usr/bin/tool"):
            with patch.object(preflight.subprocess, "run", return_value=FailedToken):
                results, rc = preflight.run_preflight(include_connectivity=False, include_database=False)

        self.assertEqual(rc, 2)
        details = "\n".join(result.detail for result in results)
        self.assertIn("login required; run: es login", details)
        self.assertNotIn("secret-token", details)

    def test_proxy_variables_are_stripped_from_auth_and_connectivity(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(kwargs["env"])
            if command[0] == "es":
                return CompletedToken()
            return CompletedCurl()

        with patch.object(preflight.shutil, "which", return_value="/usr/bin/tool"):
            with patch.object(preflight.subprocess, "run", side_effect=fake_run):
                results, rc = preflight.run_preflight(
                    include_database=False,
                    environ={"PATH": os.environ.get("PATH", ""), "http_proxy": "http://proxy", "HTTPS_PROXY": "http://proxy"},
                )

        self.assertEqual(rc, 0)
        self.assertTrue(any(result.status == "PREFLIGHT_OK" for result in results))
        for env in calls:
            self.assertNotIn("http_proxy", env)
            self.assertNotIn("HTTPS_PROXY", env)


if __name__ == "__main__":
    unittest.main()
