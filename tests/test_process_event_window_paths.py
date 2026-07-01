from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "pride_processor" / "process_event_window.sh"


class ProcessEventWindowPathTest(unittest.TestCase):
    def test_reused_ok_station_status_is_refreshed_to_portable_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_root = tmp_path / "runs"
            obs_dir = tmp_path / "obs"
            obs_file = obs_dir / "abcd0010.20o"
            station_dir = run_root / "event-a-pdp3-1h-20200101T000000-010000" / "abcd"
            status_dir = run_root / "event-a-pdp3-1h-20200101T000000-010000" / ".station-status"
            kin_file = station_dir / "2020" / "001" / "kin_2020001_abcd"
            status_file = status_dir / "abcd.tsv"
            obs_dir.mkdir(parents=True)
            kin_file.parent.mkdir(parents=True)
            status_dir.mkdir(parents=True)
            obs_file.write_text("dummy obs\n", encoding="utf-8")
            kin_file.write_text("END OF HEADER\n", encoding="utf-8")
            status_file.write_text(
                "abcd\t/old/machine/gnss-earthscope-pipeline/data/obs/event-a/abcd0010.20o\tOK\t/old/machine/gnss-earthscope-pipeline/runs/event-a/workflow-old/pride/event-a-pdp3-1h-20200101T000000-010000/abcd\n",
                encoding="utf-8",
            )
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            pdp3 = fake_bin / "pdp3"
            pdp3.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            pdp3.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

            result = subprocess.run(
                [
                    str(SCRIPT),
                    "--event-id",
                    "event-a",
                    "--event-time",
                    "2020-01-01T00:00:00Z",
                    "--hours",
                    "1",
                    "--interval",
                    "1",
                    "--obs-dir",
                    str(obs_dir),
                    "--run-root",
                    str(run_root),
                    str(obs_file),
                ],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            status_parts = status_file.read_text(encoding="utf-8").strip().split("\t")
            self.assertEqual(status_parts[2], "OK")
            self.assertFalse(status_parts[1].startswith("/old/machine/"))
            self.assertFalse(status_parts[3].startswith("/old/machine/"))
            self.assertIn("runs/event-a-pdp3-1h-20200101T000000-010000/abcd", status_parts[3])


if __name__ == "__main__":
    unittest.main()
