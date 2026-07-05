from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "reports" / "build_dataset_report.py"
SPEC = importlib.util.spec_from_file_location("build_dataset_report", MODULE_PATH)
dataset_report = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(dataset_report)


class BuildDatasetReportTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]], delimiter: str = ",") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def write_package(
        self,
        root: Path,
        *,
        event_id: str,
        event_dir: str,
        source: str,
        region: str,
        magnitude: float,
        station_count: int,
        waveform_rows: int | None,
        quality_status: str,
        event_grade: str,
    ) -> None:
        package = root / event_dir
        package.mkdir(parents=True)
        (package / "event.json").write_text(
            json.dumps(
                {
                    "event_id": event_id,
                    "source": source,
                    "network": source,
                    "date": "2020-01-01T00:00:00Z",
                    "magnitude": magnitude,
                    "region": region,
                    "event_grade": event_grade,
                    "place": f"{event_id} test place",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        provenance = {
            "event_id": event_id,
            "station_count": station_count,
            "quality_summary": {"status": quality_status},
            "event_grade": {"grade": event_grade},
        }
        if waveform_rows is not None:
            provenance["waveform_rows"] = waveform_rows
        (package / "provenance.json").write_text(json.dumps(provenance) + "\n", encoding="utf-8")
        stations = [
            {
                "Station": f"S{index:03d}",
                "Latitude": "1.0",
                "Longitude": "2.0",
                "Sampling_Hz": "1.0",
                "Waveform_Rows": "3",
                "Quality_Status": quality_status,
            }
            for index in range(station_count)
        ]
        self.write_rows(package / "stations.csv", stations)
        with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz"],
                lineterminator="\n",
            )
            writer.writeheader()
            for index, station in enumerate(stations):
                writer.writerow(
                    {
                        "Station": station["Station"],
                        "Time_UTC": "2020-01-01T00:00:00Z",
                        "Time_Offset_s": str(index),
                        "Component": "E",
                        "Value_m": "0.0",
                        "Sampling_Hz": "1.0",
                    }
                )

    def make_export(self, root: Path, figure_root: Path) -> None:
        self.write_package(
            root,
            event_id="event-a",
            event_dir="us-event-a",
            source="EarthScope",
            region="US",
            magnitude=6.4,
            station_count=1,
            waveform_rows=3,
            quality_status="OK",
            event_grade="C",
        )
        self.write_package(
            root,
            event_id="event-b",
            event_dir="nz-event-b",
            source="GeoNet",
            region="New Zealand",
            magnitude=7.2,
            station_count=3,
            waveform_rows=None,
            quality_status="WARN",
            event_grade="B",
        )
        figure_root.mkdir(parents=True)
        (figure_root / "event-a_station_map.png").write_bytes(b"png")

    def test_build_report_summarizes_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            figure_root = root / "figure"
            self.make_export(export_root, figure_root)

            report = dataset_report.build_report(export_root, figure_root)

        summary = report["summary"]
        self.assertEqual(summary["total_events"], 2)
        self.assertEqual(summary["events_by_source"], {"EarthScope": 1, "GeoNet": 1})
        self.assertEqual(summary["events_by_region"], {"New Zealand": 1, "US": 1})
        self.assertEqual(summary["events_by_magnitude_bin"], {"6.0-6.9": 1, "7.0-7.9": 1})
        self.assertEqual(summary["station_count_distribution"], {"1": 1, "2-3": 1})
        self.assertEqual(summary["quality_status_distribution"], {"OK": 1, "WARN": 1})
        self.assertEqual(summary["event_grade_distribution"], {"B": 1, "C": 1})
        self.assertEqual(summary["events_missing_figures"], 1)
        self.assertEqual(report["top_station_count_events"][0]["event_id"], "event-b")
        self.assertEqual(report["missing_figure_events"][0]["event_id"], "event-b")
        event_b = next(row for row in report["events"] if row["event_id"] == "event-b")
        self.assertEqual(event_b["waveform_rows"], "3")

    def test_cli_writes_markdown_csv_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            figure_root = root / "figure"
            out_md = root / "reports" / "dataset_report.md"
            out_csv = root / "reports" / "dataset_report_events.csv"
            out_json = root / "reports" / "dataset_report.json"
            self.make_export(export_root, figure_root)

            rc = dataset_report.main(
                [
                    "--export-root",
                    str(export_root),
                    "--figure-root",
                    str(figure_root),
                    "--out-md",
                    str(out_md),
                    "--out-csv",
                    str(out_csv),
                    "--out-json",
                    str(out_json),
                ]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total_events"], 2)
            with out_csv.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["event_id"] for row in rows], ["event-a", "event-b"])
            markdown = out_md.read_text(encoding="utf-8")
            self.assertIn("# Normalized Dataset Report", markdown)
            self.assertIn("Top Station-count Events", markdown)
            self.assertIn("Missing Figure Events", markdown)
            self.assertIn("event-b", markdown)


if __name__ == "__main__":
    unittest.main()
