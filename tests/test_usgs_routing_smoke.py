from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "ops" / "check_usgs_routing_smoke.py"

SPEC = importlib.util.spec_from_file_location("check_usgs_routing_smoke", SCRIPT_PATH)
check_usgs_routing_smoke = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["check_usgs_routing_smoke"] = check_usgs_routing_smoke
SPEC.loader.exec_module(check_usgs_routing_smoke)


class UsgsRoutingSmokeTest(unittest.TestCase):
    def test_run_smoke_checks_south_america_exclusion_from_earthscope(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = check_usgs_routing_smoke.run_smoke(Path(tmp))

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["source_by_event"]["smoke-mexico"], "earthscope")
        self.assertEqual(result["source_by_event"]["smoke-geonet"], "geonet")
        self.assertEqual(result["source_by_event"]["smoke-chile"], "unsupported_south_america")
        self.assertEqual(result["source_by_event"]["smoke-venezuela"], "unsupported_south_america")
        self.assertEqual(result["earthscope_event_ids"], ["smoke-mexico"])
        self.assertEqual(result["counts_by_source"]["unsupported_south_america"], 2)

    def test_main_prints_stable_ok_summary(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = check_usgs_routing_smoke.main([])

        self.assertEqual(rc, 0)
        text = stdout.getvalue()
        self.assertIn("USGS_ROUTING_SMOKE\tOK", text)
        self.assertIn("earthscope=1", text)
        self.assertIn("geonet=1", text)
        self.assertIn("unsupported_south_america=2", text)


if __name__ == "__main__":
    unittest.main()
