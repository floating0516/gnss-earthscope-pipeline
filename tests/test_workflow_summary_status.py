from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.workflows import update_workflow_summary_status as updater


class WorkflowSummaryStatusTest(unittest.TestCase):
    def test_updates_plot_status_and_plot_count_in_all_summary_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "runs" / "event-a" / "workflow-20200101T000000Z" / "reports"
            manifest_dir = report_dir.parent / "manifests"
            report_dir.mkdir(parents=True)
            manifest_dir.mkdir(parents=True)

            summary_json = report_dir / "workflow-summary.json"
            summary_tsv = report_dir / "workflow-summary.tsv"
            summary_md = report_dir / "workflow-summary.md"
            plot_manifest = manifest_dir / "plot-files.txt"

            summary_json.write_text(
                json.dumps(
                    {
                        "status": {"plot": "SKIPPED_DISABLED", "normalized": "OK"},
                        "counts": {"plot_files": 0},
                        "files": {"plots": []},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            summary_tsv.write_text("key\tvalue\nplot_status\tSKIPPED_DISABLED\nplot_file_count\t0\n", encoding="utf-8")
            summary_md.write_text("- Plot status: `SKIPPED_DISABLED`\n- Plot files: `0`\n", encoding="utf-8")
            plot_manifest.write_text("@ROOT@/figure/event-a-map.png\n@ROOT@/figure/event-a-record.png\n", encoding="utf-8")

            rc = updater.main(
                [
                    "--summary-json",
                    str(summary_json),
                    "--summary-tsv",
                    str(summary_tsv),
                    "--summary-md",
                    str(summary_md),
                    "--plot-status",
                    "OK",
                    "--plot-files",
                    str(plot_manifest),
                ]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(summary_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"]["plot"], "OK")
            self.assertEqual(payload["counts"]["plot_files"], 2)
            self.assertEqual(
                payload["files"]["plots"],
                ["@ROOT@/figure/event-a-map.png", "@ROOT@/figure/event-a-record.png"],
            )
            self.assertIn("plot_status\tOK\n", summary_tsv.read_text(encoding="utf-8"))
            self.assertIn("plot_file_count\t2\n", summary_tsv.read_text(encoding="utf-8"))
            self.assertIn("- Plot status: `OK`", summary_md.read_text(encoding="utf-8"))
            self.assertIn("- Plot files: `2`", summary_md.read_text(encoding="utf-8"))

    def test_extracts_png_paths_from_final_plot_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "plot-final-normalized.log"
            log.write_text(
                "rendering\n"
                "/mnt/data/gnss-earthscope-pipeline/figure/event-map.png\n"
                "figure/event-record.png\n"
                "not-a-plot.txt\n",
                encoding="utf-8",
            )
            self.assertEqual(
                updater.extract_plot_files_from_log(log),
                [
                    "/mnt/data/gnss-earthscope-pipeline/figure/event-map.png",
                    "figure/event-record.png",
                ],
            )

    def test_cli_can_write_plot_manifest_from_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "plot-final-normalized.log"
            manifest = root / "plot-files.txt"
            log.write_text(
                "rendering\n"
                "/tmp/repo/figure/event-map.png\n"
                "figure/event-record.png\n",
                encoding="utf-8",
            )

            rc = updater.main(
                [
                    "--extract-plot-files-from-log",
                    str(log),
                    "--write-plot-files",
                    str(manifest),
                ]
            )

            self.assertEqual(rc, 0)
            self.assertEqual(
                manifest.read_text(encoding="utf-8"),
                "/tmp/repo/figure/event-map.png\nfigure/event-record.png\n",
            )


if __name__ == "__main__":
    unittest.main()
