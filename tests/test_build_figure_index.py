from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "plotting" / "build_figure_index.py"
SPEC = importlib.util.spec_from_file_location("build_figure_index", MODULE_PATH)
figure_index = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(figure_index)


class BuildFigureIndexTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_event_package(self, root: Path) -> None:
        package = root / "us-event-a"
        package.mkdir(parents=True)
        (package / "event.json").write_text(
            json.dumps(
                {
                    "event_id": "event-a",
                    "source": "EarthScope PRIDE PPP-AR kin quality-passing stations",
                    "event_time": "2020-01-01T00:00:00Z",
                    "country": "United States",
                    "place": "Synthetic Ridge",
                    "magnitude": 6.1,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (package / "provenance.json").write_text(json.dumps({"event_id": "event-a", "station_count": 2, "waveform_rows": 6}) + "\n", encoding="utf-8")
        self.write_rows(
            package / "stations.csv",
            [
                {"Station": "ABCD", "Latitude": "1.0", "Longitude": "2.0"},
                {"Station": "EFGH", "Latitude": "3.0", "Longitude": "4.0"},
            ],
        )
        with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m"], lineterminator="\n")
            writer.writeheader()
            writer.writerow({"Station": "ABCD", "Time_UTC": "2020-01-01T00:00:00Z", "Time_Offset_s": "0", "Component": "E", "Value_m": "0"})

    def test_build_index_matches_event_figures_and_keeps_unmatched_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            figure_root = root / "figure"
            self.make_event_package(export_root)
            (figure_root / "record_sections").mkdir(parents=True)
            (figure_root / "event-a_station_map.png").write_bytes(b"png")
            (figure_root / "record_sections" / "20200101_synthetic_ridge_record_section.svg").write_text("<svg/>\n", encoding="utf-8")
            (figure_root / "misc_unmatched.png").write_bytes(b"png")

            rows = figure_index.build_index(export_root, figure_root)

        self.assertEqual(len(rows), 3)
        by_path = {row["path"]: row for row in rows}
        self.assertEqual(by_path["event-a_station_map.png"]["event_id"], "event-a")
        self.assertEqual(by_path["event-a_station_map.png"]["figure_type"], "station_map")
        self.assertEqual(by_path["event-a_station_map.png"]["source"], "EarthScope")
        self.assertEqual(by_path["event-a_station_map.png"]["station_count"], "2")
        self.assertEqual(by_path["record_sections/20200101_synthetic_ridge_record_section.svg"]["event_id"], "event-a")
        self.assertEqual(by_path["record_sections/20200101_synthetic_ridge_record_section.svg"]["figure_type"], "record_section")
        self.assertEqual(by_path["misc_unmatched.png"]["event_id"], "")
        self.assertEqual(by_path["misc_unmatched.png"]["figure_type"], "unknown")
        self.assertTrue(by_path["misc_unmatched.png"]["created_at"])

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            figure_root = root / "figure"
            out_json = root / "figure_index.json"
            out_md = root / "figure_index.md"
            self.make_event_package(export_root)
            figure_root.mkdir()
            (figure_root / "event-a_station_map.png").write_bytes(b"png")

            rc = figure_index.main(
                [
                    "--export-root",
                    str(export_root),
                    "--figure-root",
                    str(figure_root),
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                ]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total_figures"], 1)
            self.assertEqual(payload["summary"]["matched_figures"], 1)
            self.assertEqual(payload["figures"][0]["event_id"], "event-a")
            self.assertIn("event-a_station_map.png", out_md.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
