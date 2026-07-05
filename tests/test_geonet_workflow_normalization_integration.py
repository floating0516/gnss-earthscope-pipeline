from __future__ import annotations

import csv
import datetime as dt
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_normalize_geonet_pride_kin_event import write_geonet_db


ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
UNIX_EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
MJD_UNIX_EPOCH = 40587
SECONDS_PER_DAY = 86400


def mjd_sod_from_datetime(value: dt.datetime) -> tuple[int, float]:
    delta = value - UNIX_EPOCH
    total_seconds = delta.days * SECONDS_PER_DAY + delta.seconds + delta.microseconds / 1_000_000
    mjd = MJD_UNIX_EPOCH + int(total_seconds // SECONDS_PER_DAY)
    sod = total_seconds % SECONDS_PER_DAY
    return mjd, sod


def write_clean_kin(path: Path, event_time: dt.datetime) -> None:
    lines = ["END OF HEADER"]
    for offset in range(-60, 60):
        gpst = event_time + dt.timedelta(seconds=offset + 18)
        mjd, sod = mjd_sod_from_datetime(gpst)
        lines.append(f"{mjd} {sod:.0f} 1000.000000 2000.000000 3000.000000")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_key_value_tsv(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["key"]: row["value"] for row in csv.DictReader(handle, delimiter="\t")}


class GeoNetWorkflowNormalizationIntegrationTest(unittest.TestCase):
    def test_geonet_workflow_normalizes_valid_reused_kin_without_network(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            tmp_path = Path(tmp)
            event_id = "geonet-test-event"
            event_time = "2020-01-01T00:00:00Z"
            run_root = tmp_path / "runs"
            obs_root = tmp_path / "obs"
            normalized_root = tmp_path / "normalized"
            figure_root = tmp_path / "figure"
            db_path = tmp_path / "geonet.sqlite"
            workflow_dir = run_root / event_id / "workflow-20200101T000000Z"
            kin_file = workflow_dir / "pride" / "geonet-test-pdp3" / "wgtn" / "2020" / "001" / "kin_2020001_wgtn"
            fake_plot_python = tmp_path / "fake-plot-python"

            write_geonet_db(db_path)
            write_clean_kin(kin_file, dt.datetime(2020, 1, 1, tzinfo=UTC))
            fake_plot_python.write_text(
                "#!/usr/bin/env bash\n"
                "mkdir -p \"$FAKE_FIGURE_DIR\"\n"
                "plot=\"$FAKE_FIGURE_DIR/geonet-test-event.png\"\n"
                "printf plot > \"$plot\"\n"
                "printf '%s\\n' \"$plot\"\n",
                encoding="utf-8",
            )
            fake_plot_python.chmod(0o755)

            env = {
                **os.environ,
                "FINAL_PLOT_PYTHON": str(fake_plot_python),
                "FINAL_FIGURE_DIR": str(figure_root),
                "FAKE_FIGURE_DIR": str(figure_root),
            }
            result = subprocess.run(
                [
                    str(ROOT / "scripts" / "workflows" / "run_geonet_event_1hz_pride_workflow.sh"),
                    "--event-id",
                    event_id,
                    "--event-time",
                    event_time,
                    "--hours",
                    "0",
                    "--run-root",
                    str(run_root),
                    "--obs-root",
                    str(obs_root),
                    "--geonet-db",
                    str(db_path),
                    "--normalized-root",
                    str(normalized_root),
                    "--skip-download",
                    "--skip-process",
                ],
                cwd=str(ROOT),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            summary_tsv = workflow_dir / "reports" / "workflow-summary.tsv"
            summary_json = workflow_dir / "reports" / "workflow-summary.json"
            values = read_key_value_tsv(summary_tsv)
            payload = json.loads(summary_json.read_text(encoding="utf-8"))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(values["normalized_status"], "OK")
            self.assertEqual(values["normalized_export_valid"], "true")
            self.assertEqual(values["normalized_validation_status"], "OK")
            self.assertEqual(values["normalized_station_count"], "1")
            self.assertGreater(int(values["normalized_waveform_rows"]), 0)
            self.assertEqual(values["plot_status"], "OK")
            self.assertEqual(values["workflow_result"], "OK")
            self.assertEqual(values["next_action"], "DONE")
            self.assertEqual(payload["status"]["normalized"], "OK")
            self.assertTrue(Path(values["normalized_event_dir"], "event.json").exists())
            self.assertTrue((figure_root / "geonet-test-event.png").exists())


if __name__ == "__main__":
    unittest.main()
