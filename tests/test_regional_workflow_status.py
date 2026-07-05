from __future__ import annotations

import csv
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RegionalWorkflowStatusTest(unittest.TestCase):
    def read_key_value_tsv(self, path: Path) -> dict[str, str]:
        with path.open(newline="", encoding="utf-8") as handle:
            return {row["key"]: row["value"] for row in csv.DictReader(handle, delimiter="\t")}

    def test_regional_workflows_block_final_plot_without_normalized_output(self):
        cases = [
            (
                ROOT / "scripts" / "workflows" / "run_geonet_event_1hz_pride_workflow.sh",
                ["--skip-normalize"],
                "SKIPPED_NORMALIZE",
                "BLOCKED_NORMALIZE_SKIPPED",
            ),
            (
                ROOT / "scripts" / "workflows" / "run_ring_event_1hz_pride_workflow.sh",
                [],
                "SKIPPED_UNSUPPORTED_SOURCE",
                "BLOCKED_NORMALIZE_UNSUPPORTED",
            ),
        ]

        for script, extra_args, expected_normalized, expected_plot in cases:
            with self.subTest(script=script.name):
                with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                    tmp_path = Path(tmp)
                    fake_python = tmp_path / "fake-python"
                    plot_marker = tmp_path / "plot-called"
                    fake_python.write_text(
                        "#!/usr/bin/env bash\n"
                        "printf called > \"$FAKE_PLOT_MARKER\"\n"
                        "exit 0\n",
                        encoding="utf-8",
                    )
                    fake_python.chmod(0o755)

                    event_id = f"test-{script.stem}"
                    run_root = tmp_path / "runs"
                    obs_root = tmp_path / "obs"
                    env = {
                        **os.environ,
                        "FINAL_PLOT_PYTHON": str(fake_python),
                        "FAKE_PLOT_MARKER": str(plot_marker),
                    }

                    result = subprocess.run(
                        [
                            str(script),
                            "--event-id",
                            event_id,
                            "--event-time",
                            "2020-01-02T03:04:05Z",
                            "--run-root",
                            str(run_root),
                            "--obs-root",
                            str(obs_root),
                            "--skip-download",
                            "--skip-process",
                            *extra_args,
                        ],
                        cwd=str(ROOT),
                        env=env,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )

                    summary_tsv = run_root / event_id / "workflow-20200102T030405Z" / "reports" / "workflow-summary.tsv"
                    values = self.read_key_value_tsv(summary_tsv)

                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse(plot_marker.exists(), f"{script.name} unexpectedly called final plotter")
                    self.assertEqual(values["normalized_status"], expected_normalized)
                    self.assertEqual(values["plot_status"], expected_plot)


if __name__ == "__main__":
    unittest.main()
