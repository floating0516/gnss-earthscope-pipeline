from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "summaries" / "build_current_event_completion.py"
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_current_event_completion", MODULE_PATH)
build_completion = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_completion)


class BuildCurrentEventCompletionTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]], delimiter: str = "\t") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_manifest_export_is_added_and_legacy_current_row_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current_path = root / "current.tsv"
            manifest_path = root / "manifest.tsv"
            event_summary_path = root / "event_summary.csv"

            self.write_rows(
                current_path,
                [
                    {
                        "region": "US",
                        "network": "EarthScope",
                        "event_id": "legacy-only",
                        "magnitude": "6.4",
                        "event_date": "2019-07-06",
                        "event_time": "2019-07-06T03:19:53Z",
                        "place": "Legacy event",
                        "stations_200km": "10",
                        "stations_300km": "12",
                        "existing_data_status": "HAS_NORMALIZED",
                        "workflow_status": "",
                        "download_status": "",
                        "obs_validation_status": "",
                        "process_status": "",
                        "plot_status": "",
                        "quality_status": "",
                        "quality_station_count": "",
                        "quality_ok_stations": "",
                        "quality_warn_stations": "",
                        "quality_fail_stations": "",
                        "station_health_ratio": "",
                        "requested_stations": "",
                        "obs_files": "",
                        "kin_files": "",
                        "plot_files": "",
                        "cleanup_status": "",
                        "pride_cleanup_status": "",
                        "obs_cleanup_status": "",
                        "duration_seconds": "",
                        "workflow_dir": "",
                        "summary_json": "",
                    }
                ],
            )
            self.write_rows(
                manifest_path,
                [
                    {
                        "region": "US",
                        "network": "EarthScope",
                        "event_id": "manifest-only",
                        "event_dir": "us-manifest-only",
                        "event_time": "2020-01-02T03:04:05Z",
                        "magnitude": "6.1",
                        "place": "Manifest only event",
                        "stations_included": "3",
                        "ok_stations_included": "2",
                        "warn_stations_included": "1",
                        "waveform_rows": "42",
                        "event_grade": "B",
                        "quality_filter": "quality_status in OK,WARN",
                        "workflow_summary": str(root / "runs" / "manifest-only" / "workflow-20200102T030405Z" / "reports" / "workflow-summary.json"),
                        "stations": "AAA BBB CCC",
                    }
                ],
            )
            self.write_rows(
                event_summary_path,
                [
                    {
                        "event_id": "manifest-only",
                        "event_dir": "us-manifest-only",
                        "origin_time": "2020-01-02T03:04:05Z",
                        "longitude": "-124.0",
                        "latitude": "40.0",
                        "depth_km": "10.0",
                        "magnitude": "6.1",
                        "place": "Manifest only event",
                        "region": "US",
                        "country": "United States",
                        "network": "EarthScope",
                        "station_count": "3",
                        "ok_station_count": "2",
                        "warn_station_count": "1",
                        "waveform_rows": "42",
                        "event_grade": "B",
                        "event_grade_description": "multi-station event",
                        "azimuth_bins_covered": "2",
                        "azimuth_bin_count": "8",
                        "azimuth_coverage_fraction": "0.25",
                        "single_station_allowed": "True",
                        "quality_filter": "quality_status in OK,WARN",
                        "has_mechanism": "yes",
                        "mechanism": "strike-slip",
                        "strike": "10",
                        "dip": "80",
                        "rake": "1",
                    }
                ],
                delimiter=",",
            )
            export_dir = root / "us-manifest-only"
            export_dir.mkdir()
            (export_dir / "event.json").write_text("{}", encoding="utf-8")
            (export_dir / "stations.csv").write_text("station\nAAA\n", encoding="utf-8")
            (export_dir / "waveforms.csv.gz").write_bytes(b"placeholder")

            rows = build_completion.build_completion_rows(current_path, manifest_path, event_summary_path)

        by_id = {row["event_id"]: row for row in rows}
        self.assertEqual(set(by_id), {"manifest-only", "legacy-only"})
        self.assertEqual(by_id["manifest-only"]["collection_status"], "EXPORTED")
        self.assertEqual(by_id["manifest-only"]["existing_data_status"], "HAS_NORMALIZED")
        self.assertEqual(by_id["manifest-only"]["workflow_status"], "DONE")
        self.assertEqual(by_id["manifest-only"]["quality_station_count"], "3")
        self.assertEqual(by_id["manifest-only"]["export_event_dir"], "us-manifest-only")
        self.assertEqual(by_id["manifest-only"]["export_station_count"], "3")
        self.assertEqual(by_id["manifest-only"]["export_country"], "United States")
        self.assertEqual(by_id["legacy-only"]["collection_status"], "CURRENT_ONLY")
        self.assertEqual(by_id["legacy-only"]["existing_data_status"], "HAS_NORMALIZED")

    def test_export_source_is_derived_from_event_dir_prefix(self):
        rows = [
            {"event_id": "us-event", "event_dir": "us-us-event"},
            {"event_id": "nz-event", "event_dir": "nz-nz-event"},
            {"event_id": "au-event", "event_dir": "au-au-event"},
        ]

        mapped = [build_completion.source_from_manifest_row(row) for row in rows]

        self.assertEqual(
            mapped,
            [
                ("US", "EarthScope"),
                ("NZ", "GeoNet"),
                ("AU", "Geoscience Australia"),
            ],
        )

    def test_incomplete_manifest_package_is_not_counted_as_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current_path = root / "current.tsv"
            manifest_path = root / "manifest.tsv"
            event_summary_path = root / "event_summary.csv"

            self.write_rows(
                current_path,
                [
                    {
                        "region": "US",
                        "network": "EarthScope",
                        "event_id": "incomplete",
                        "magnitude": "6.0",
                        "event_date": "2020-01-02",
                        "event_time": "2020-01-02T03:04:05Z",
                        "place": "Incomplete package",
                        "stations_200km": "",
                        "stations_300km": "",
                        "existing_data_status": "NO_EXISTING",
                        "workflow_status": "",
                        "download_status": "",
                        "obs_validation_status": "",
                        "process_status": "",
                        "plot_status": "",
                        "quality_status": "",
                        "quality_station_count": "",
                        "quality_ok_stations": "",
                        "quality_warn_stations": "",
                        "quality_fail_stations": "",
                        "station_health_ratio": "",
                        "requested_stations": "",
                        "obs_files": "",
                        "kin_files": "",
                        "plot_files": "",
                        "cleanup_status": "",
                        "pride_cleanup_status": "",
                        "obs_cleanup_status": "",
                        "duration_seconds": "",
                        "workflow_dir": "",
                        "summary_json": "",
                    }
                ],
            )
            self.write_rows(
                manifest_path,
                [
                    {
                        "region": "US",
                        "network": "EarthScope",
                        "event_id": "incomplete",
                        "event_dir": "us-incomplete",
                        "event_time": "2020-01-02T03:04:05Z",
                        "magnitude": "6.0",
                        "place": "Incomplete package",
                        "stations_included": "1",
                        "ok_stations_included": "1",
                        "warn_stations_included": "0",
                        "waveform_rows": "10",
                        "event_grade": "C",
                        "quality_filter": "quality_status in OK,WARN",
                        "workflow_summary": "",
                        "stations": "AAA",
                    }
                ],
            )
            self.write_rows(
                event_summary_path,
                [
                    {
                        "event_id": "incomplete",
                        "event_dir": "us-incomplete",
                        "origin_time": "2020-01-02T03:04:05Z",
                        "longitude": "",
                        "latitude": "",
                        "depth_km": "",
                        "magnitude": "6.0",
                        "place": "Incomplete package",
                        "region": "US",
                        "country": "United States",
                        "network": "EarthScope",
                        "station_count": "1",
                        "ok_station_count": "1",
                        "warn_station_count": "0",
                        "waveform_rows": "10",
                        "event_grade": "C",
                        "event_grade_description": "",
                        "azimuth_bins_covered": "",
                        "azimuth_bin_count": "",
                        "azimuth_coverage_fraction": "",
                        "single_station_allowed": "",
                        "quality_filter": "quality_status in OK,WARN",
                        "has_mechanism": "",
                        "mechanism": "",
                        "strike": "",
                        "dip": "",
                        "rake": "",
                    }
                ],
                delimiter=",",
            )

            rows = build_completion.build_completion_rows(current_path, manifest_path, event_summary_path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_id"], "incomplete")
        self.assertEqual(rows[0]["collection_status"], "CURRENT_ONLY")
        self.assertEqual(rows[0]["export_package_status"], "NOT_IN_MANIFEST")

    def test_repository_manifest_exports_are_all_included(self):
        rows = build_completion.build_completion_rows(
            ROOT / "data" / "summaries" / "us_nz_current_event_completion.tsv",
            ROOT / "exports" / "normalized-ok-stations-us-nz" / "manifest.tsv",
            ROOT / "exports" / "normalized-ok-stations-us-nz" / "event_summary.csv",
        )

        exported = [row for row in rows if row["collection_status"] == "EXPORTED"]
        current_only = [row for row in rows if row["collection_status"] == "CURRENT_ONLY"]

        self.assertEqual(len(exported), 142)
        self.assertEqual(len(current_only), 13)
        self.assertEqual(len({row["event_id"] for row in rows}), 155)
        self.assertTrue(all(row["existing_data_status"] == "HAS_NORMALIZED" for row in exported))


if __name__ == "__main__":
    unittest.main()
