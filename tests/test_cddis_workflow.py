from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "workflows" / "run_cddis_event_1hz_pride_workflow.sh"


class CddisWorkflowTest(unittest.TestCase):
    def test_dry_run_prints_cddis_stage_commands(self):
        result = subprocess.run(
            [
                str(SCRIPT),
                "--event-id",
                "event1",
                "--event-time",
                "2026-06-23T23:00:00Z",
                "--process-event-time",
                "2026-06-23T23:07:30Z",
                "--radius-km",
                "1000",
                "--event-dir",
                str(ROOT / "data" / "cddis_highrate" / "events" / "event1"),
                "--dry-run",
            ],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("download_cddis_event_window.py", result.stdout)
        self.assertIn("prepare_cddis_event_obs.py", result.stdout)
        self.assertIn("process_event_window.sh", result.stdout)
        self.assertIn("compute_kin_quality.py", result.stdout)
        self.assertIn("normalize_cddis_pride_kin_event.py", result.stdout)
        self.assertIn("plot_completed_normalized_event.py", result.stdout)
        self.assertIn("data/cddis_highrate/events/event1", result.stdout)

    def test_radius_required_unless_download_skipped(self):
        result = subprocess.run(
            [
                str(SCRIPT),
                "--event-id",
                "event1",
                "--event-time",
                "2026-06-23T23:00:00Z",
                "--dry-run",
            ],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("--radius-km is required", result.stderr)

    def test_skip_download_allows_missing_radius(self):
        result = subprocess.run(
            [
                str(SCRIPT),
                "--event-id",
                "event1",
                "--event-time",
                "2026-06-23T23:00:00Z",
                "--skip-download",
                "--dry-run",
            ],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("download_cddis_event_window.py", result.stdout)
        self.assertIn("prepare_cddis_event_obs.py", result.stdout)

    def test_existing_portable_pride_summary_is_resolved_for_kin_inventory(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            tmp_path = Path(tmp)
            event_dir = tmp_path / "event"
            run_root = tmp_path / "pride"
            station_dir = run_root / "event1-pdp3-1h" / "daej"
            summary_dir = run_root / "event1-pdp3-1h"
            kin_file = station_dir / "kin_2026174_daej"
            summary = summary_dir / "event-window-summary.tsv"
            station_dir.mkdir(parents=True)
            kin_file.write_text("kin placeholder\n", encoding="utf-8")
            portable_station_dir = f"@ROOT@/{station_dir.relative_to(ROOT)}"
            summary.write_text(
                "\n".join(
                    [
                        "event_id\tevent1",
                        "station\tobs_file\tstatus\tstation_run_dir",
                        f"daej\t@ROOT@/data/obs/event1/daej.rnx\tOK\t{portable_station_dir}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(SCRIPT),
                    "--event-id",
                    "event1",
                    "--event-time",
                    "2026-06-23T23:00:00Z",
                    "--event-dir",
                    str(event_dir),
                    "--run-root",
                    str(run_root),
                    "--skip-download",
                    "--skip-prepare",
                    "--skip-process",
                    "--skip-quality",
                    "--skip-normalize",
                    "--skip-plot",
                ],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            workflow_dirs = sorted(event_dir.glob("workflow-*"))
            kin_manifest = workflow_dirs[-1] / "manifests" / "kin-files.txt"
            kin_manifest_text = kin_manifest.read_text(encoding="utf-8").strip()
            summary_json = json.loads((workflow_dirs[-1] / "reports" / "workflow-summary.json").read_text(encoding="utf-8"))
            with (workflow_dirs[-1] / "reports" / "workflow-summary.tsv").open(newline="", encoding="utf-8") as handle:
                summary_tsv = {row[0]: row[1] for row in csv.reader(handle, delimiter="\t") if len(row) >= 2}

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(kin_manifest_text, str(kin_file))
        self.assertEqual(summary_json["status"]["normalize"], "SKIPPED")
        self.assertEqual(summary_json["status"]["normalized"], "SKIPPED")
        self.assertEqual(summary_tsv["normalize_status"], "SKIPPED")
        self.assertEqual(summary_tsv["normalized_status"], "SKIPPED")


if __name__ == "__main__":
    unittest.main()
