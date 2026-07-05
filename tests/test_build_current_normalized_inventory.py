from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "summaries" / "build_current_normalized_inventory.py"
SPEC = importlib.util.spec_from_file_location("build_current_normalized_inventory", MODULE_PATH)
inventory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(inventory)


class BuildCurrentNormalizedInventoryTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]], delimiter: str = ",") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_export(self, root: Path) -> Path:
        package = root / "us-event-a"
        package.mkdir(parents=True)
        (package / "event.json").write_text(
            json.dumps(
                {
                    "event_id": "event-a",
                    "source": "EarthScope PRIDE PPP-AR kin quality-passing stations",
                    "date": "2020-01-01T00:00:00Z",
                    "magnitude": 6.1,
                    "region": "US",
                    "network": "EarthScope",
                    "event_grade": "C",
                    "azimuth_bins_covered": 1,
                    "place": "Test place",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (package / "provenance.json").write_text(
            json.dumps(
                {
                    "event_id": "event-a",
                    "station_count": 1,
                    "waveform_rows": 2,
                    "quality_summary": {"status": "OK"},
                    "station_quality_counts": {"OK": 1},
                    "event_grade": {"grade": "C", "azimuth_bins_covered": 1},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.write_rows(
            package / "stations.csv",
            [
                {
                    "Station": "ABCD",
                    "Latitude": "1.0",
                    "Longitude": "2.0",
                    "Sampling_Hz": "1.0",
                    "Waveform_Rows": "2",
                    "Quality_Status": "OK",
                }
            ],
        )
        with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz"],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerow(
                {
                    "Station": "ABCD",
                    "Time_UTC": "2020-01-01T00:00:00Z",
                    "Time_Offset_s": "0",
                    "Component": "E",
                    "Value_m": "0.0",
                    "Sampling_Hz": "1.0",
                }
            )
            writer.writerow(
                {
                    "Station": "ABCD",
                    "Time_UTC": "2020-01-01T00:00:01Z",
                    "Time_Offset_s": "1",
                    "Component": "N",
                    "Value_m": "0.0",
                    "Sampling_Hz": "1.0",
                }
            )
        return package

    def test_build_inventory_rows_include_package_and_figure_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            figure_root = root / "figure"
            self.make_export(export_root)
            figure_root.mkdir()
            (figure_root / "event-a_station_map.png").write_bytes(b"png")

            rows = inventory.build_inventory_rows(export_root, figure_root)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["event_id"], "event-a")
        self.assertEqual(row["source"], "EarthScope")
        self.assertEqual(row["event_time"], "2020-01-01T00:00:00Z")
        self.assertEqual(row["magnitude"], "6.1")
        self.assertEqual(row["region"], "US")
        self.assertEqual(row["station_count"], "1")
        self.assertEqual(row["waveform_rows"], "2")
        self.assertEqual(row["quality_status"], "OK")
        self.assertEqual(row["event_grade"], "C")
        self.assertEqual(row["azimuth_bins"], "1")
        self.assertEqual(row["has_figure"], "yes")
        self.assertIn("event-a_station_map.png", row["figure_paths"])

    def test_cli_writes_tsv_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            figure_root = root / "figure"
            out_prefix = root / "summary"
            self.make_export(export_root)
            figure_root.mkdir()

            rc = inventory.main(
                [
                    "--root",
                    str(export_root),
                    "--figure-root",
                    str(figure_root),
                    "--out-prefix",
                    str(out_prefix),
                ]
            )

            tsv_path = root / "summary.tsv"
            json_path = root / "summary.json"
            md_path = root / "summary.md"

            self.assertEqual(rc, 0)
            self.assertTrue(tsv_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            with tsv_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(rows[0]["event_id"], "event-a")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total_events"], 1)
            self.assertIn("event-a", md_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
