from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "run_pgd_report.py"
SPEC = importlib.util.spec_from_file_location("run_pgd_report", MODULE_PATH)
run_pgd_report = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_pgd_report)


class RunPgdReportTest(unittest.TestCase):
    def write_rows(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_event_package(
        self,
        root: Path,
        *,
        event_id: str = "event-a",
        dirname: str = "us-event-a",
        country: str = "United States",
        region: str = "US",
        source: str = "earthscope",
        magnitude: float = 6.4,
        distance_km: str = "20.0",
        signal_base: float = 0.20,
        signal_step: float = 0.001,
        station_distances: list[tuple[str, str]] | None = None,
    ) -> None:
        package = root / dirname
        package.mkdir(parents=True)
        stations = station_distances or [("ABCD", distance_km)]
        (package / "event.json").write_text(
            json.dumps(
                {
                    "event_id": event_id,
                    "date": "2020-01-01T00:00:00Z",
                    "country": country,
                    "region": region,
                    "source": source,
                    "place": "Synthetic PGD event",
                    "magnitude": magnitude,
                    "depth_km": 10.0,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (package / "provenance.json").write_text(
            json.dumps({"event_id": event_id, "station_count": 1, "waveform_rows": 153}) + "\n",
            encoding="utf-8",
        )
        self.write_rows(
            package / "stations.csv",
            [
                {
                    "Station": station,
                    "Latitude": "35.0",
                    "Longitude": "-120.0",
                    "Distance_Km": station_distance,
                    "Quality_Status": "OK",
                }
                for station, station_distance in stations
            ],
        )
        with gzip.open(package / "waveforms.csv.gz", "wt", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz", "Source_File"],
                lineterminator="\n",
            )
            writer.writeheader()
            for offset in range(-40, 11):
                base = 0.001 if offset < 0 else signal_base + offset * signal_step
                for station, _station_distance in stations:
                    for component, value in [("E", base), ("N", base / 2.0), ("U", base / 4.0)]:
                        writer.writerow(
                            {
                                "Station": station,
                                "Time_UTC": "2020-01-01T00:00:00Z",
                                "Time_Offset_s": str(offset),
                                "Component": component,
                                "Value_m": f"{value:.6f}",
                                "Sampling_Hz": "1.0",
                                "Source_File": "synthetic",
                            }
                        )

    def test_cli_writes_pgd_report_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "reports" / "pgd"
            self.make_event_package(export_root)
            out_dir.mkdir(parents=True)
            (out_dir / "method_summary.csv").write_text("stale\n", encoding="utf-8")
            (out_dir / "method_comparison.csv").write_text("stale\n", encoding="utf-8")
            (out_dir / "figures").mkdir()
            (out_dir / "figures" / "method_mae_by_region.svg").write_text("stale\n", encoding="utf-8")

            rc = run_pgd_report.main(["--export-root", str(export_root), "--out-dir", str(out_dir)])

            self.assertEqual(rc, 0)
            expected = [
                out_dir / "events.csv",
                out_dir / "stations.csv",
                out_dir / "residuals.csv",
                out_dir / "residual_outliers.csv",
                out_dir / "residual_review.csv",
                out_dir / "release_set.csv",
                out_dir / "release_set_summary.json",
                out_dir / "science_narrative.md",
                out_dir / "science_release_events.csv",
                out_dir / "science_formula_summary.csv",
                out_dir / "science_figure_manifest.csv",
                out_dir / "formula_comparison.csv",
                out_dir / "formula_breakdown.csv",
                out_dir / "formula_breakdown.md",
                out_dir / "formula_summary.csv",
                out_dir / "formula_summary_raw.csv",
                out_dir / "formula_summary_by_magnitude_bin.csv",
                out_dir / "formula_summary_quality_filtered_by_magnitude_bin.csv",
                out_dir / "summary.json",
                out_dir / "summary.md",
                out_dir / "figures" / "estimated_vs_usgs_by_region.svg",
                out_dir / "figures" / "formula_mae_by_region.svg",
                out_dir / "figures" / "residual_vs_usgs_magnitude.svg",
            ]
            for path in expected:
                self.assertTrue(path.exists(), path)
            not_expected = [
                out_dir / "method_comparison.csv",
                out_dir / "method_comparison.md",
                out_dir / "method_summary.csv",
                out_dir / "method_summary_raw.csv",
                out_dir / "method_summary_by_magnitude_bin.csv",
                out_dir / "method_summary_quality_filtered_by_magnitude_bin.csv",
                out_dir / "figures" / "method_mae_by_region.svg",
            ]
            for path in not_expected:
                self.assertFalse(path.exists(), path)
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["counts"]["event_rows"], 3)
            self.assertEqual(payload["counts"]["station_rows"], 3)
            self.assertEqual(payload["counts"]["unique_events"], 1)
            self.assertEqual(payload["counts"]["magnitude_bin_summary_rows"], 3)
            self.assertEqual(payload["counts"]["quality_filtered_magnitude_bin_summary_rows"], 0)
            self.assertEqual(payload["counts"]["residual_outlier_rows"], 3)
            self.assertEqual(payload["counts"]["release_set_rows"], 1)
            self.assertEqual(payload["counts"]["formula_comparison_rows"], 3)
            self.assertNotIn("method_summary_rows", payload["counts"])
            self.assertNotIn("method_comparison_rows", payload["counts"])
            self.assertNotIn("method_summary", payload)
            self.assertNotIn("method_comparison", payload)
            self.assertEqual(payload["parameters"]["pgd_component"], "3d")
            self.assertEqual(payload["parameters"]["station_aggregation"], "median")
            self.assertEqual(payload["formula_recommendation"]["station_aggregation"], "median")
            self.assertEqual(
                {row["station_aggregation"] for row in payload["formula_breakdown"]},
                {"median"},
            )
            self.assertIn(payload["formula_recommendation"]["recommended_formula"], {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            with (out_dir / "events.csv").open(newline="", encoding="utf-8") as handle:
                events = list(csv.DictReader(handle))
            self.assertEqual({row["formula"] for row in events}, {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            self.assertEqual({row["station_aggregation"] for row in events}, {"median"})
            with (out_dir / "formula_comparison.csv").open(newline="", encoding="utf-8") as handle:
                formula_comparison = list(csv.DictReader(handle))
            self.assertEqual({row["formula"] for row in formula_comparison}, {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            self.assertEqual({row["station_aggregation"] for row in formula_comparison}, {"median"})
            self.assertEqual({row["comparison_group"] for row in formula_comparison}, {"all"})
            self.assertEqual({row["event_count"] for row in formula_comparison}, {"1"})
            best_formula = min(formula_comparison, key=lambda row: float(row["mae_mw"]))["formula"]
            self.assertEqual(payload["formula_recommendation"]["recommended_formula"], best_formula)
            with (out_dir / "formula_breakdown.csv").open(newline="", encoding="utf-8") as handle:
                formula_breakdown = list(csv.DictReader(handle))
            self.assertEqual({row["formula"] for row in formula_breakdown}, {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            self.assertEqual({row["station_aggregation"] for row in formula_breakdown}, {"median"})
            self.assertTrue(any(row["comparison_group"] == "magnitude_bin" and row["comparison_value"] == "6.0-7.0" for row in formula_breakdown))
            self.assertTrue(any(row["comparison_group"] == "region" and row["comparison_value"] == "US" for row in formula_breakdown))
            self.assertTrue(any(row["comparison_group"] == "source" and row["comparison_value"] == "earthscope" for row in formula_breakdown))
            with (out_dir / "formula_summary_by_magnitude_bin.csv").open(newline="", encoding="utf-8") as handle:
                bin_summary = list(csv.DictReader(handle))
            self.assertEqual({row["magnitude_bin"] for row in bin_summary}, {"6.0-7.0"})
            self.assertEqual({row["quality_filter"] for row in bin_summary}, {"ALL"})
            with (out_dir / "formula_summary_quality_filtered_by_magnitude_bin.csv").open(newline="", encoding="utf-8") as handle:
                filtered_bin_summary = list(csv.DictReader(handle))
            self.assertEqual(filtered_bin_summary, [])
            with (out_dir / "formula_summary.csv").open(newline="", encoding="utf-8") as handle:
                formula_summary_rows = list(csv.DictReader(handle))
            self.assertEqual({row["formula"] for row in formula_summary_rows}, {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            with (out_dir / "residuals.csv").open(newline="", encoding="utf-8") as handle:
                residuals = list(csv.DictReader(handle))
            self.assertEqual(len(residuals), 3)
            with (out_dir / "residual_outliers.csv").open(newline="", encoding="utf-8") as handle:
                outliers = list(csv.DictReader(handle))
            self.assertEqual(len(outliers), 3)
            self.assertEqual(
                [float(row["abs_residual_mw"]) for row in outliers],
                sorted((float(row["abs_residual_mw"]) for row in outliers), reverse=True),
            )
            with (out_dir / "residual_review.csv").open(newline="", encoding="utf-8") as handle:
                review_rows = list(csv.DictReader(handle))
            self.assertEqual(len(review_rows), 3)
            self.assertEqual(
                [float(row["abs_residual_mw"]) for row in review_rows],
                sorted((float(row["abs_residual_mw"]) for row in review_rows), reverse=True),
            )
            for field in [
                "review_status",
                "suspected_cause",
                "waveform_issue",
                "station_geometry_issue",
                "magnitude_metadata_issue",
                "formula_limitation",
                "reviewer_note",
            ]:
                self.assertIn(field, review_rows[0])
            self.assertEqual({row["review_status"] for row in review_rows}, {"UNREVIEWED"})
            with (out_dir / "release_set.csv").open(newline="", encoding="utf-8") as handle:
                release_rows = list(csv.DictReader(handle))
            self.assertEqual(len(release_rows), 1)
            self.assertEqual(release_rows[0]["event_id"], "event-a")
            self.assertEqual(release_rows[0]["formula"], payload["formula_recommendation"]["recommended_formula"])
            self.assertEqual(release_rows[0]["release_status"], "EXCLUDED_RELEASE_SET")
            release_summary = json.loads((out_dir / "release_set_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(release_summary["total_events"], 1)
            self.assertEqual(release_summary["excluded_events"], 1)
            self.assertEqual(payload["pgd_release_set"]["excluded_events"], 1)
            with (out_dir / "science_release_events.csv").open(newline="", encoding="utf-8") as handle:
                science_release_rows = list(csv.DictReader(handle))
            self.assertEqual(science_release_rows, [])
            with (out_dir / "science_formula_summary.csv").open(newline="", encoding="utf-8") as handle:
                science_formula_rows = list(csv.DictReader(handle))
            self.assertEqual({row["formula"] for row in science_formula_rows}, {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            with (out_dir / "science_figure_manifest.csv").open(newline="", encoding="utf-8") as handle:
                figure_manifest_rows = list(csv.DictReader(handle))
            self.assertEqual(len(figure_manifest_rows), 3)
            summary_md = (out_dir / "summary.md").read_text(encoding="utf-8")
            self.assertIn("event-a", summary_md)
            self.assertIn("Formula Summary", summary_md)
            self.assertNotIn("## Method Summary", summary_md)
            self.assertIn("Magnitude-bin Summary", summary_md)
            self.assertIn("Quality-filtered Magnitude-bin Summary", summary_md)
            self.assertIn("Largest Residuals", summary_md)
            self.assertIn("Formula Comparison", summary_md)
            self.assertIn("PGD Inclusion/Exclusion", summary_md)
            self.assertIn("Residual Review", summary_md)
            self.assertIn("PGD Release Set", summary_md)
            self.assertIn("Station aggregation: `median`", summary_md)
            science_md = (out_dir / "science_narrative.md").read_text(encoding="utf-8")
            for section in [
                "Dataset Description",
                "Median Aggregation And Formulas",
                "Formula Comparison",
                "Release Set",
                "Residual Behavior",
                "Outlier Review Status",
                "Limitations",
                "Next Experiments",
            ]:
                self.assertIn(section, science_md)
            self.assertIn("one station aggregation method: `median`", science_md)
            self.assertIn("not station aggregation methods", science_md)
            self.assertNotIn("## PGD Method", science_md)
            self.assertNotIn("three methods", science_md.lower())
            self.assertIn("median", science_md)
            self.assertIn(payload["formula_recommendation"]["recommended_formula"], science_md)
            formula_breakdown_md = (out_dir / "formula_breakdown.md").read_text(encoding="utf-8")
            self.assertIn("Median-only Formula Breakdown", formula_breakdown_md)
            self.assertIn("not station aggregation methods", formula_breakdown_md)

    def test_release_set_gate_includes_hard_passes_and_marks_residual_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "reports" / "pgd"
            self.make_event_package(
                export_root,
                event_id="release-a",
                dirname="us-release-a",
                station_distances=[("ABCD", "20.0"), ("EFGH", "25.0"), ("IJKL", "30.0")],
                signal_base=0.20,
            )
            self.make_event_package(
                export_root,
                event_id="release-b",
                dirname="us-release-b",
                station_distances=[("MNOP", "20.0")],
                signal_base=0.20,
            )

            rc = run_pgd_report.main(
                [
                    "--export-root",
                    str(export_root),
                    "--out-dir",
                    str(out_dir),
                    "--release-residual-review-threshold",
                    "99",
                ]
            )

            self.assertEqual(rc, 0)
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            with (out_dir / "release_set.csv").open(newline="", encoding="utf-8") as handle:
                rows = {row["event_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(set(rows), {"release-a", "release-b"})
            self.assertEqual(rows["release-a"]["release_status"], "INCLUDED_RELEASE_SET")
            self.assertEqual(rows["release-a"]["release_candidate"], "yes")
            self.assertEqual(rows["release-a"]["release_ready"], "yes")
            self.assertEqual(rows["release-a"]["review_required"], "no")
            self.assertEqual(rows["release-b"]["release_status"], "EXCLUDED_RELEASE_SET")
            self.assertEqual(rows["release-b"]["release_candidate"], "no")
            self.assertIn("insufficient_usable_stations", rows["release-b"]["release_failure_reasons"])
            self.assertIn("low_reliability", rows["release-b"]["release_failure_reasons"])
            self.assertEqual(payload["pgd_release_set"]["candidate_events"], 1)
            self.assertEqual(payload["pgd_release_set"]["ready_events"], 1)
            self.assertEqual(payload["pgd_release_set"]["excluded_events"], 1)

            review_out_dir = root / "reports" / "pgd-review"
            rc = run_pgd_report.main(
                [
                    "--export-root",
                    str(export_root),
                    "--out-dir",
                    str(review_out_dir),
                    "--release-residual-review-threshold",
                    "0",
                ]
            )

            self.assertEqual(rc, 0)
            with (review_out_dir / "release_set.csv").open(newline="", encoding="utf-8") as handle:
                review_rows = {row["event_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(review_rows["release-a"]["release_status"], "NEEDS_RESIDUAL_REVIEW")
            self.assertEqual(review_rows["release-a"]["release_candidate"], "yes")
            self.assertEqual(review_rows["release-a"]["release_ready"], "no")
            self.assertEqual(review_rows["release-a"]["review_required"], "yes")
            self.assertIn("abs_residual_mw", review_rows["release-a"]["release_review_reasons"])
            self.assertEqual(review_rows["release-b"]["release_review_reasons"], "")
            with (out_dir / "science_release_events.csv").open(newline="", encoding="utf-8") as handle:
                science_release_rows = list(csv.DictReader(handle))
            self.assertEqual([row["event_id"] for row in science_release_rows], ["release-a"])
            self.assertEqual(science_release_rows[0]["release_status"], "INCLUDED_RELEASE_SET")

    def test_cli_rejects_non_median_station_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "reports" / "pgd"
            self.make_event_package(export_root)

            with self.assertRaises(SystemExit):
                run_pgd_report.main(
                    [
                        "--export-root",
                        str(export_root),
                        "--out-dir",
                        str(out_dir),
                        "--station-aggregation",
                        "mean",
                    ]
                )

    def test_cli_rejects_trim_fraction_without_trimmed_mean_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "reports" / "pgd"
            self.make_event_package(export_root)

            with self.assertRaises(SystemExit):
                run_pgd_report.main(
                    [
                        "--export-root",
                        str(export_root),
                        "--out-dir",
                        str(out_dir),
                        "--trim-fraction",
                        "0.1",
                    ]
                )

    def test_residual_review_preserves_manual_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "reports" / "pgd"
            self.make_event_package(export_root)

            rc = run_pgd_report.main(["--export-root", str(export_root), "--out-dir", str(out_dir)])
            self.assertEqual(rc, 0)

            review_path = out_dir / "residual_review.csv"
            with review_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = handle.seek(0) or list(csv.DictReader(handle).fieldnames or [])
            first_key = (rows[0]["event_id"], rows[0]["formula"])
            rows[0]["review_status"] = "REVIEWED"
            rows[0]["suspected_cause"] = "waveform"
            rows[0]["waveform_issue"] = "late_peak"
            rows[0]["station_geometry_issue"] = "geometry_ok"
            rows[0]["magnitude_metadata_issue"] = "metadata_ok"
            rows[0]["formula_limitation"] = "not_primary"
            rows[0]["reviewer_note"] = "manual note should survive"
            with review_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)

            rc = run_pgd_report.main(["--export-root", str(export_root), "--out-dir", str(out_dir)])
            self.assertEqual(rc, 0)

            with review_path.open(newline="", encoding="utf-8") as handle:
                regenerated = list(csv.DictReader(handle))
            preserved = next(row for row in regenerated if (row["event_id"], row["formula"]) == first_key)
            self.assertEqual(preserved["review_status"], "REVIEWED")
            self.assertEqual(preserved["suspected_cause"], "waveform")
            self.assertEqual(preserved["waveform_issue"], "late_peak")
            self.assertEqual(preserved["station_geometry_issue"], "geometry_ok")
            self.assertEqual(preserved["magnitude_metadata_issue"], "metadata_ok")
            self.assertEqual(preserved["formula_limitation"], "not_primary")
            self.assertEqual(preserved["reviewer_note"], "manual note should survive")

    def test_cli_writes_pgd_inclusion_exclusion_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "reports" / "pgd"
            self.make_event_package(export_root, event_id="event-a", dirname="us-event-a")
            self.make_event_package(
                export_root,
                event_id="event-b",
                dirname="nz-event-b",
                country="Americas",
                region="Americas",
                signal_base=0.20,
            )
            self.make_event_package(
                export_root,
                event_id="event-c",
                dirname="us-event-c-low-pgd",
                signal_base=0.000000001,
                signal_step=0.0,
            )

            rc = run_pgd_report.main(["--export-root", str(export_root), "--out-dir", str(out_dir)])

            self.assertEqual(rc, 0)
            for path in [out_dir / "inclusion_exclusion.csv", out_dir / "inclusion_exclusion.md"]:
                self.assertTrue(path.exists(), path)
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["pgd_inclusion_exclusion"]["total_normalized_events"], 3)
            self.assertEqual(payload["pgd_inclusion_exclusion"]["pgd_evaluable_events"], 2)
            self.assertEqual(payload["pgd_inclusion_exclusion"]["pgd_excluded_events"], 1)
            with (out_dir / "inclusion_exclusion.csv").open(newline="", encoding="utf-8") as handle:
                rows = {row["event_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["event-a"]["pgd_status"], "INCLUDED_PGD_EVALUATED")
            self.assertEqual(rows["event-b"]["pgd_status"], "INCLUDED_PGD_EVALUATED")
            self.assertEqual(rows["event-b"]["country"], "New Zealand")
            self.assertEqual(rows["event-b"]["region"], "New Zealand")
            self.assertEqual(rows["event-c"]["exclusion_reason"], "BELOW_PGD_THRESHOLD")
            inclusion_md = (out_dir / "inclusion_exclusion.md").read_text(encoding="utf-8")
            self.assertIn("Total normalized events: 3", inclusion_md)
            self.assertIn("PGD evaluable events: 2", inclusion_md)

    def test_empty_export_returns_nonzero_with_clear_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            out_dir = root / "reports" / "pgd"
            export_root.mkdir()

            rc = run_pgd_report.main(["--export-root", str(export_root), "--out-dir", str(out_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "NO_PGD_EVENTS")
            self.assertIn("No PGD event rows", (out_dir / "summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
