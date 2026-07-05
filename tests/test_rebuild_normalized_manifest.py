from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REBUILD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "normalize" / "rebuild_normalized_manifest.py"
REBUILD_SPEC = importlib.util.spec_from_file_location("rebuild_normalized_manifest", REBUILD_PATH)
rebuild = importlib.util.module_from_spec(REBUILD_SPEC)
assert REBUILD_SPEC.loader is not None
REBUILD_SPEC.loader.exec_module(rebuild)

VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "scripts" / "summaries" / "validate_normalized_export.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("validate_normalized_export", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(validator)


class RebuildNormalizedManifestTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]], delimiter: str = ",") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_package(
        self,
        root: Path,
        event_id: str,
        event_dir: str,
        event_time: str,
        stations: list[tuple[str, str]],
    ) -> None:
        package = root / event_dir
        package.mkdir(parents=True)
        ok_count = sum(1 for _, status in stations if status == "OK")
        warn_count = sum(1 for _, status in stations if status == "WARN")
        waveform_rows = len(stations) * 2

        (package / "event.json").write_text(
            json.dumps(
                {
                    "event_id": event_id,
                    "date": event_time,
                    "longitude": 2.0,
                    "latitude": 1.0,
                    "depth_km": 10.0,
                    "magnitude": 6.1,
                    "place": f"Test event {event_id}",
                    "region": "US",
                    "country": "United States",
                    "network": "EarthScope",
                    "quality_filter": "quality_status in OK,WARN",
                    "workflow_summary": f"/tmp/runs/{event_id}/workflow-summary.json",
                    "event_grade": "C",
                    "event_grade_description": "test grade",
                    "azimuth_bins_covered": 1,
                    "azimuth_bin_count": 8,
                    "single_station_allowed": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (package / "provenance.json").write_text(
            json.dumps(
                {
                    "event_id": event_id,
                    "station_count": len(stations),
                    "waveform_rows": waveform_rows,
                    "quality_summary": {
                        "status": "OK" if warn_count == 0 else "WARN",
                        "station_count": len(stations),
                        "ok_station_count": ok_count,
                        "warn_station_count": warn_count,
                        "fail_station_count": 0,
                    },
                    "station_quality_counts": {"OK": ok_count, "WARN": warn_count},
                    "event_grade": {
                        "grade": "C",
                        "description": "test grade",
                        "azimuth_bins_covered": 1,
                        "azimuth_bin_count": 8,
                        "azimuth_coverage_fraction": 0.125,
                        "single_station_allowed": True,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.write_rows(
            package / "stations.csv",
            [
                {
                    "Station": station,
                    "Latitude": "1.0",
                    "Longitude": "2.0",
                    "Sampling_Hz": "1.0",
                    "Waveform_Rows": "2",
                    "Quality_Status": status,
                }
                for station, status in stations
            ],
        )
        with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz"],
                lineterminator="\n",
            )
            writer.writeheader()
            for station, _ in stations:
                writer.writerow(
                    {
                        "Station": station,
                        "Time_UTC": event_time,
                        "Time_Offset_s": "0",
                        "Component": "E",
                        "Value_m": "0.0",
                        "Sampling_Hz": "1.0",
                    }
                )
                writer.writerow(
                    {
                        "Station": station,
                        "Time_UTC": event_time,
                        "Time_Offset_s": "1",
                        "Component": "N",
                        "Value_m": "0.0",
                        "Sampling_Hz": "1.0",
                    }
                )

    def make_export(self, root: Path) -> None:
        self.write_package(
            root,
            event_id="event-b",
            event_dir="us-event-b",
            event_time="2020-01-02T00:00:00Z",
            stations=[("WXYZ", "OK"), ("LMNO", "WARN")],
        )
        self.write_package(
            root,
            event_id="event-a",
            event_dir="us-event-a",
            event_time="2020-01-01T00:00:00Z",
            stations=[("ABCD", "OK")],
        )

    def test_build_indexes_from_packages_in_stable_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_export(root)

            indexes = rebuild.build_indexes(root)

        self.assertEqual([row["event_id"] for row in indexes.manifest_rows], ["event-a", "event-b"])
        self.assertEqual(indexes.manifest_rows[0]["event_dir"], "us-event-a")
        self.assertEqual(indexes.manifest_rows[1]["stations"], "LMNO WXYZ")
        self.assertEqual(indexes.event_summary_rows[1]["warn_station_count"], "1")
        self.assertEqual(indexes.file_inventory_rows[0]["complete"], "yes")

    def test_default_dry_run_does_not_write_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_export(root)

            rc = rebuild.main(["--root", str(root)])

            self.assertEqual(rc, 0)
            self.assertFalse((root / "manifest.tsv").exists())
            self.assertFalse((root / "event_summary.csv").exists())
            self.assertFalse((root / "file_inventory.tsv").exists())

    def test_incomplete_package_like_dirs_are_not_indexed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_export(root)
            leftover = root / "scratch-waveforms-only"
            leftover.mkdir()
            with gzip.open(leftover / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Station"], lineterminator="\n")
                writer.writeheader()
                writer.writerow({"Station": "LEFT"})

            indexes = rebuild.build_indexes(root)

        self.assertEqual([row["event_id"] for row in indexes.manifest_rows], ["event-a", "event-b"])

    def test_write_generates_validator_compatible_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_export(root)

            rc = rebuild.main(["--root", str(root), "--write"])
            report = validator.validate_export(root)

        self.assertEqual(rc, 0)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["event_count"], 2)

    def test_repeated_write_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_export(root)

            self.assertEqual(rebuild.main(["--root", str(root), "--write"]), 0)
            first = {
                name: (root / name).read_text(encoding="utf-8")
                for name in ["manifest.tsv", "event_summary.csv", "file_inventory.tsv"]
            }
            self.assertEqual(rebuild.main(["--root", str(root), "--write"]), 0)
            second = {
                name: (root / name).read_text(encoding="utf-8")
                for name in ["manifest.tsv", "event_summary.csv", "file_inventory.tsv"]
            }

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
