from __future__ import annotations

import csv
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "workflows" / "run_cddis_event_batch_workflow.sh"


class CddisBatchWorkflowTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        fieldnames = list(rows[0].keys())
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_dry_run_prints_cddis_event_workflow_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "events.csv"
            event_root = Path(tmp) / "events"
            self.write_csv(
                batch,
                [
                    {
                        "event_id": "event1",
                        "event_time": "2026-06-23T23:00:00Z",
                        "process_event_time": "2026-06-23T23:07:30Z",
                        "radius_km": "1000",
                        "status": "",
                    }
                ],
            )

            result = subprocess.run(
                [
                    str(SCRIPT),
                    "--csv",
                    str(batch),
                    "--event-root",
                    str(event_root),
                    "--dry-run",
                ],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run_cddis_event_1hz_pride_workflow.sh", result.stdout)
        self.assertIn("--event-id event1", result.stdout)
        self.assertIn("--process-event-time", result.stdout)
        self.assertIn("--radius-km 1000", result.stdout)
        self.assertIn("CDDIS batch summary:", result.stdout)

    def test_radius_required_unless_default_or_skip_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "events.csv"
            self.write_csv(
                batch,
                [
                    {
                        "event_id": "event1",
                        "event_time": "2026-06-23T23:00:00Z",
                        "status": "",
                    }
                ],
            )

            result = subprocess.run(
                [str(SCRIPT), "--csv", str(batch), "--dry-run"],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            default_radius = subprocess.run(
                [str(SCRIPT), "--csv", str(batch), "--radius-km", "1000", "--dry-run"],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("radius_km is required", result.stderr)
        self.assertEqual(default_radius.returncode, 0, default_radius.stderr)
        self.assertIn("--radius-km 1000", default_radius.stdout)

    def test_dry_run_skips_ok_rows_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "events.csv"
            self.write_csv(
                batch,
                [
                    {
                        "event_id": "event1",
                        "event_time": "2026-06-23T23:00:00Z",
                        "radius_km": "1000",
                        "status": "OK",
                    }
                ],
            )

            result = subprocess.run(
                [str(SCRIPT), "--csv", str(batch), "--dry-run"],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Runnable events processed: 0", result.stdout)
        self.assertNotIn("run_cddis_event_1hz_pride_workflow.sh", result.stdout)

    def test_summary_includes_normalized_status_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "events.csv"
            event_root = root / "events"
            summary = root / "summary.tsv"
            reports = event_root / "event1" / "workflow-20260702T000000Z" / "reports"
            reports.mkdir(parents=True)
            self.write_csv(
                batch,
                [
                    {
                        "event_id": "event1",
                        "event_time": "2026-06-23T23:00:00Z",
                        "process_event_time": "2026-06-23T23:07:30Z",
                        "radius_km": "1000",
                        "status": "OK",
                    }
                ],
            )
            (reports / "workflow-summary.json").write_text(
                '{"status":{"normalize":"OK","plot":"OK"},"counts":{},"paths":{}}\n',
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(SCRIPT),
                    "--csv",
                    str(batch),
                    "--event-root",
                    str(event_root),
                    "--summary",
                    str(summary),
                    "--dry-run",
                ],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            with summary.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(rows[0]["normalize_status"], "OK")
        self.assertEqual(rows[0]["normalized_status"], "OK")


if __name__ == "__main__":
    unittest.main()
