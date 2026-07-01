from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "cddis_downloader"
COMMON_PATH = TOOLS / "cddis_common.py"
SCRIPT_PATH = TOOLS / "prepare_cddis_event_obs.py"

COMMON_SPEC = importlib.util.spec_from_file_location("cddis_common", COMMON_PATH)
cddis_common = importlib.util.module_from_spec(COMMON_SPEC)
assert COMMON_SPEC.loader is not None
sys.modules["cddis_common"] = cddis_common
COMMON_SPEC.loader.exec_module(cddis_common)

SCRIPT_SPEC = importlib.util.spec_from_file_location("prepare_cddis_event_obs", SCRIPT_PATH)
prepare_cddis_event_obs = importlib.util.module_from_spec(SCRIPT_SPEC)
assert SCRIPT_SPEC.loader is not None
SCRIPT_SPEC.loader.exec_module(prepare_cddis_event_obs)


def rinex_text(interval: float = 1.0) -> str:
    return "\n".join(
        [
            "     2.11           OBSERVATION DATA    M                   RINEX VERSION / TYPE",
            "DAEJ                                                        MARKER NAME",
            f"{interval:10.3f}                                                  INTERVAL",
            "                                                            END OF HEADER",
            " 26  6 23 23  0  0.0000000  0  1G01",
            "      1.0",
            "",
        ]
    )


def write_downloaded_manifest(event_dir: Path, source: Path, status: str = "OK") -> None:
    manifest = event_dir / "manifests" / "cddis-event-downloaded.tsv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["event_id", "station4", "filename", "url", "local_file", "status", "size_bytes", "reason"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(
            {
                "event_id": "event1",
                "station4": "DAEJ",
                "filename": source.name,
                "url": "https://cddis.nasa.gov/archive/gnss/data/highrate/2026/174/26o/23/daej174x00.26o.gz",
                "local_file": str(source),
                "status": status,
                "size_bytes": str(source.stat().st_size) if source.exists() else "",
                "reason": "",
            }
        )


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


class CddisPrepareObsTest(unittest.TestCase):
    def test_prepare_gzip_rinex_writes_obs_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            event_dir = Path(tmp) / "event"
            source = event_dir / "files" / "daej" / "daej174x00.26o.gz"
            source.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(source, "wt", encoding="ascii") as handle:
                handle.write(rinex_text(1.0))
            write_downloaded_manifest(event_dir, source)

            rc = prepare_cddis_event_obs.main(["--event-id", "event1", "--event-dir", str(event_dir)])
            summary = json.loads((event_dir / "manifests" / "cddis-prepare-summary.json").read_text(encoding="utf-8"))
            prepared_rows = read_tsv(event_dir / "manifests" / "cddis-event-prepared.tsv")
            obs_rows = read_tsv(event_dir / "manifests" / "cddis-event-obs.tsv")
            obs_file = Path(obs_rows[0]["obs_file"])
            obs_text = obs_file.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(summary["prepared_count"], 1)
        self.assertEqual(summary["obs_count"], 1)
        self.assertEqual(prepared_rows[0]["status"], "OK")
        self.assertEqual(prepared_rows[0]["interval_seconds"], "1")
        self.assertTrue(obs_file.name.endswith("_event1_cddis.rnx"))
        self.assertIn("END OF HEADER", obs_text)

    def test_non_one_second_rinex_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            event_dir = Path(tmp) / "event"
            source = event_dir / "files" / "daej" / "daej174x00.26o.gz"
            source.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(source, "wt", encoding="ascii") as handle:
                handle.write(rinex_text(30.0))
            write_downloaded_manifest(event_dir, source)

            rc = prepare_cddis_event_obs.main(["--event-id", "event1", "--event-dir", str(event_dir)])
            prepared_rows = read_tsv(event_dir / "manifests" / "cddis-event-prepared.tsv")
            obs_rows = read_tsv(event_dir / "manifests" / "cddis-event-obs.tsv")

        self.assertEqual(rc, 1)
        self.assertEqual(prepared_rows[0]["status"], "INVALID")
        self.assertEqual(prepared_rows[0]["interval_seconds"], "30")
        self.assertEqual(obs_rows[0]["status"], "MISSING")

    def test_missing_downloaded_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            event_dir = Path(tmp) / "event"
            source = event_dir / "files" / "daej" / "missing.26o.gz"
            write_downloaded_manifest(event_dir, source, status="FAIL")

            rc = prepare_cddis_event_obs.main(["--event-id", "event1", "--event-dir", str(event_dir)])
            prepared_rows = read_tsv(event_dir / "manifests" / "cddis-event-prepared.tsv")

        self.assertEqual(rc, 1)
        self.assertEqual(prepared_rows[0]["status"], "MISSING")
        self.assertIn("download status=FAIL", prepared_rows[0]["reason"])

    def test_hatanaka_conversion_invokes_crx2rnx(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "daej174x00.26d"
            work.write_text("compressed", encoding="utf-8")

            def fake_run(command, **kwargs):
                self.assertEqual(command[0], "/usr/bin/CRX2RNX")
                work.with_name("daej174x00.26o").write_text(rinex_text(1.0), encoding="utf-8")
                return None

            with patch.object(prepare_cddis_event_obs.shutil, "which", return_value="/usr/bin/CRX2RNX"):
                with patch.object(prepare_cddis_event_obs.subprocess, "run", side_effect=fake_run):
                    converted = prepare_cddis_event_obs.convert_hatanaka(work)

        self.assertEqual(converted.name, "daej174x00.26o")


if __name__ == "__main__":
    unittest.main()
