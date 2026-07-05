import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_release_package.py"
SPEC = importlib.util.spec_from_file_location("build_pgd_release_package", MODULE_PATH)
build_pgd_release_package = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(build_pgd_release_package)


class BuildPgdReleasePackageTest(unittest.TestCase):
    def write_csv(self, path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(rows[0]) if rows else ["event_id"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def make_report_bundle(self, root: Path, *, ready_rows: int = 2, omit: set[str] | None = None) -> tuple[Path, Path]:
        omit = omit or set()
        report_dir = root / "reports" / "pgd_magnitude" / "latest"
        sensitivity_dir = root / "reports" / "pgd_magnitude" / "sensitivity" / "latest"
        report_dir.mkdir(parents=True)
        sensitivity_dir.mkdir(parents=True)
        release_rows = [
            {
                "event_id": f"event-{index}",
                "event_time": f"2020-01-0{index}T00:00:00Z",
                "country": "United States",
                "region": "US",
                "place": f"Synthetic event {index}",
                "formula": "ruhl_2019",
                "usgs_magnitude": "6.5",
                "estimated_mw_median": "6.4",
                "residual_mw": "-0.1",
                "abs_residual_mw": "0.1",
                "pgd_reliability": "MEDIUM",
                "usable_station_count": "4",
                "median_pgd_snr": "5.0",
                "median_distance_km": "100.0",
                "release_status": "INCLUDED_RELEASE_SET",
            }
            for index in range(1, ready_rows + 1)
        ]
        formula_rows = [
            {
                "comparison_group": "all",
                "comparison_value": "ALL",
                "formula": formula,
                "station_aggregation": "median",
                "event_count": "94",
                "high_medium_reliability_events": "13",
                "low_reliability_events": "31",
                "residual_outlier_count": "6",
                "bias_mw": "0.1",
                "mae_mw": mae,
                "rmse_mw": "0.5",
                "median_abs_error_mw": "0.4",
            }
            for formula, mae in [("melgar_2015", "0.53"), ("crowell_2016_gfast", "0.74"), ("ruhl_2019", "0.43")]
        ]
        figure_rows = [
            {"figure_type": "estimated_vs_usgs_by_region", "path": "reports/pgd_magnitude/latest/figures/estimated_vs_usgs_by_region.svg", "role": "formula fit diagnostic"},
            {"figure_type": "residual_vs_usgs_magnitude", "path": "reports/pgd_magnitude/latest/figures/residual_vs_usgs_magnitude.svg", "role": "residual diagnostic"},
        ]
        sensitivity_rows = [
            {
                "scenario_id": "baseline",
                "scenario_label": "3D PGD, hypocentral distance, no calibration",
                "pgd_component": "3d",
                "distance_mode": "hypocentral",
                "calibration": "none",
                "station_aggregation": "median",
                "recommended_formula": "ruhl_2019",
                "criterion": "lowest_mae_mw",
                "event_count": "94",
                "mae_mw": "0.43",
                "rmse_mw": "0.53",
                "median_abs_error_mw": "0.38",
                "residual_outlier_count": "6",
                "matches_baseline": "yes",
            },
            {
                "scenario_id": "horizontal",
                "scenario_label": "Horizontal PGD",
                "pgd_component": "horizontal",
                "distance_mode": "hypocentral",
                "calibration": "none",
                "station_aggregation": "median",
                "recommended_formula": "melgar_2015",
                "criterion": "lowest_mae_mw",
                "event_count": "94",
                "mae_mw": "0.35",
                "rmse_mw": "0.43",
                "median_abs_error_mw": "0.29",
                "residual_outlier_count": "3",
                "matches_baseline": "no",
            },
        ]
        residual_triage_rows = [
            {
                "event_id": "event-x",
                "formula": "crowell_2016_gfast",
                "review_status": "UNREVIEWED",
                "abs_residual_mw": "1.8",
                "usable_station_count": "0",
                "median_pgd_snr": "",
                "median_distance_km": "",
                "pgd_reliability": "UNUSABLE",
                "triage_priority": "1",
                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                "triage_cause_suggestion": "data_quality",
                "triage_reason": "zero usable stations; release gate: EXCLUDED_RELEASE_SET",
                "next_review_action": "CHECK_WAVEFORM_AND_STATION_FILTERING;CHECK_RELEASE_GATE",
                "best_formula_for_event": "ruhl_2019",
                "best_formula_abs_residual_mw": "0.4",
                "formula_residuals_for_event": "crowell_2016_gfast=1.8;ruhl_2019=0.4",
                "formula_limitation_suggested": "yes",
                "release_status": "EXCLUDED_RELEASE_SET",
                "release_failure_reasons": "insufficient_usable_stations;low_reliability",
                "release_review_reasons": "",
            },
            {
                "event_id": "event-y",
                "formula": "ruhl_2019",
                "review_status": "UNREVIEWED",
                "abs_residual_mw": "1.1",
                "usable_station_count": "3",
                "median_pgd_snr": "4.2",
                "median_distance_km": "120",
                "pgd_reliability": "MEDIUM",
                "triage_priority": "2",
                "triage_status_suggestion": "NEEDS_FORMULA_REVIEW",
                "triage_cause_suggestion": "formula_limitation",
                "triage_reason": "abs residual 1.1 >= 1",
                "next_review_action": "COMPARE_FORMULA_RESIDUALS",
                "best_formula_for_event": "melgar_2015",
                "best_formula_abs_residual_mw": "0.3",
                "formula_residuals_for_event": "melgar_2015=0.3;ruhl_2019=1.1",
                "formula_limitation_suggested": "yes",
                "release_status": "NEEDS_RESIDUAL_REVIEW",
                "release_failure_reasons": "",
                "release_review_reasons": "residual_review_threshold",
            },
        ]
        if "science_release_events.csv" not in omit:
            self.write_csv(report_dir / "science_release_events.csv", release_rows)
        if "science_formula_summary.csv" not in omit:
            self.write_csv(report_dir / "science_formula_summary.csv", formula_rows)
        if "science_figure_manifest.csv" not in omit:
            self.write_csv(report_dir / "science_figure_manifest.csv", figure_rows)
        if "sensitivity_recommendations.csv" not in omit:
            self.write_csv(sensitivity_dir / "sensitivity_recommendations.csv", sensitivity_rows)
        if "residual_review_triage.csv" not in omit:
            self.write_csv(report_dir / "residual_review_triage.csv", residual_triage_rows)
        if "summary.json" not in omit:
            (report_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "status": "OK",
                        "counts": {"unique_events": 94, "event_rows": 282, "station_rows": 1947},
                        "formula_recommendation": {"recommended_formula": "ruhl_2019", "station_aggregation": "median", "mae_mw": "0.43"},
                        "pgd_release_set": {"ready_events": ready_rows, "total_events": 94, "excluded_events": 94 - ready_rows, "review_required_events": 0},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        if "pgd_interpretation.json" not in omit:
            (report_dir / "pgd_interpretation.json").write_text(
                json.dumps(
                    {
                        "status": "OK",
                        "baseline": {"recommended_formula": "ruhl_2019", "station_aggregation": "median", "event_count": 94},
                        "sensitivity": {"recommendation_stable": "no", "formula_switch_scenarios": ["horizontal"]},
                        "release_set": {"ready_events": ready_rows, "total_events": 94},
                        "interpretation_flags": {"requires_sensitivity_caveat": True, "residuals_data_quality_dominated": True},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        if "residual_review_triage_summary.json" not in omit:
            (report_dir / "residual_review_triage_summary.json").write_text(
                json.dumps(
                    {
                        "status": "OK",
                        "row_count": 20,
                        "suggested_status_counts": {"NEEDS_DATA_CHECK": 19, "NEEDS_FORMULA_REVIEW": 1},
                        "top_priority_rows": [
                            {
                                "event_id": "event-x",
                                "formula": "crowell_2016_gfast",
                                "abs_residual_mw": "1.8",
                                "triage_status_suggestion": "NEEDS_DATA_CHECK",
                                "triage_cause_suggestion": "data_quality",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        if "pgd_science_bundle_summary.json" not in omit:
            (report_dir / "pgd_science_bundle_summary.json").write_text(
                json.dumps({"status": "OK", "stages": [{"stage": "pgd_report", "status": "OK"}]}) + "\n",
                encoding="utf-8",
            )
        if "sensitivity_summary.json" not in omit:
            (sensitivity_dir / "summary.json").write_text(
                json.dumps({"status": "OK", "recommendation_stable": "no", "counts": {"scenario_count": 4}}) + "\n",
                encoding="utf-8",
            )
        return report_dir, sensitivity_dir

    def test_builds_release_package_from_bundle_products(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir, sensitivity_dir = self.make_report_bundle(root)
            out_dir = root / "release" / "latest"
            out_dir.mkdir(parents=True)
            (out_dir / "formula_method_note.md").write_text("stale\n", encoding="utf-8")

            rc = build_pgd_release_package.main(
                [
                    "--report-dir",
                    str(report_dir),
                    "--sensitivity-dir",
                    str(sensitivity_dir),
                    "--out-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(rc, 0)
            expected = [
                "release_package_summary.json",
                "release_package.md",
                "release_events.csv",
                "formula_comparison.csv",
                "sensitivity_recommendations.csv",
                "residual_triage_top.csv",
                "residual_review_evidence.csv",
                "residual_review_evidence.json",
                "residual_review_evidence.md",
                "residual_review_annotations_starter.csv",
                "residual_review_annotations_starter.md",
                "residual_review_checklist.md",
                "residual_review_packet_index.csv",
                "residual_review_packet_index.md",
                "figure_manifest.csv",
                "package_manifest.csv",
                "data_dictionary.csv",
                "data_dictionary.md",
                "formula_aggregation_note.md",
                "formula_coefficients.csv",
                "formula_coefficients.json",
                "formula_provenance.md",
            ]
            for name in expected:
                self.assertTrue((out_dir / name).exists(), name)
            payload = json.loads((out_dir / "release_package_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["ready_event_count"], 2)
            self.assertEqual(payload["recommended_formula"], "ruhl_2019")
            self.assertEqual(payload["station_aggregation"], "median")
            self.assertTrue(payload["requires_sensitivity_caveat"])
            self.assertEqual(payload["sensitivity_switch_scenarios"], ["horizontal"])
            self.assertEqual(payload["residual_triage"]["row_count"], 20)
            self.assertEqual(payload["residual_review_evidence"]["row_count"], 2)
            self.assertEqual(payload["residual_review_evidence"]["suggested_status_counts"]["NEEDS_DATA_CHECK"], 1)
            self.assertEqual(payload["residual_review_annotations_starter"]["row_count"], 2)
            self.assertEqual(payload["residual_review_packets"]["row_count"], 2)
            with (out_dir / "release_events.csv").open(newline="", encoding="utf-8") as handle:
                release_rows = list(csv.DictReader(handle))
            self.assertEqual([row["event_id"] for row in release_rows], ["event-1", "event-2"])
            markdown = (out_dir / "release_package.md").read_text(encoding="utf-8")
            self.assertIn("PGD Release Package", markdown)
            self.assertIn("Ready events: 2", markdown)
            self.assertIn("Recommended formula: `ruhl_2019`", markdown)
            self.assertIn("Sensitivity caveat: `required`", markdown)
            with (out_dir / "data_dictionary.csv").open(newline="", encoding="utf-8") as handle:
                dictionary_rows = list(csv.DictReader(handle))
            self.assertTrue(
                any(row["product"] == "release_events" and row["field"] == "estimated_mw_median" and "median station aggregation" in row["description"] for row in dictionary_rows)
            )
            self.assertTrue(
                any(row["product"] == "formula_comparison" and row["field"] == "formula" and "PGD scaling formula" in row["description"] for row in dictionary_rows)
            )
            self.assertTrue(
                any(row["product"] == "sensitivity_recommendations" and row["field"] == "station_aggregation" and row["allowed_values"] == "median" for row in dictionary_rows)
            )
            self.assertTrue(
                any(row["product"] == "residual_review_annotations_starter" and row["field"] == "manual_review_status" for row in dictionary_rows)
            )
            self.assertTrue(
                any(row["product"] == "residual_review_annotations_starter" and row["field"] == "accepted_for_release" for row in dictionary_rows)
            )
            self.assertTrue(any(row["product"] == "residual_review_packet_index" and row["field"] == "packet_path" for row in dictionary_rows))
            data_dictionary_md = (out_dir / "data_dictionary.md").read_text(encoding="utf-8")
            self.assertIn("estimated_mw_median", data_dictionary_md)
            self.assertIn("station_aggregation", data_dictionary_md)
            self.assertFalse((out_dir / "formula_method_note.md").exists())
            formula_note = (out_dir / "formula_aggregation_note.md").read_text(encoding="utf-8")
            self.assertIn("Station aggregation method: `median`", formula_note)
            self.assertIn("`melgar_2015`", formula_note)
            self.assertIn("`crowell_2016_gfast`", formula_note)
            self.assertIn("`ruhl_2019`", formula_note)
            self.assertIn("not station aggregation methods", formula_note)
            with (out_dir / "package_manifest.csv").open(newline="", encoding="utf-8") as handle:
                manifest_products = {row["product"] for row in csv.DictReader(handle)}
            self.assertIn("data_dictionary", manifest_products)
            self.assertIn("formula_aggregation_note", manifest_products)
            self.assertNotIn("formula_method_note", manifest_products)
            with (out_dir / "formula_coefficients.csv").open(newline="", encoding="utf-8") as handle:
                coefficient_rows = {row["formula"]: row for row in csv.DictReader(handle)}
            self.assertEqual(set(coefficient_rows), {"melgar_2015", "crowell_2016_gfast", "ruhl_2019"})
            self.assertEqual(coefficient_rows["melgar_2015"]["coefficient_a"], "-4.434")
            self.assertEqual(coefficient_rows["crowell_2016_gfast"]["coefficient_b"], "1.5")
            self.assertEqual(coefficient_rows["ruhl_2019"]["pgd_unit"], "m")
            self.assertIn("log10(PGD)", coefficient_rows["ruhl_2019"]["equation"])
            self.assertIn("10.1785/0220180177", coefficient_rows["ruhl_2019"]["doi"])
            coefficients_json = json.loads((out_dir / "formula_coefficients.json").read_text(encoding="utf-8"))
            self.assertEqual(coefficients_json["schema_version"], "pgd-formula-provenance/v1")
            self.assertEqual(coefficients_json["station_aggregation"], "median")
            self.assertEqual(len(coefficients_json["formulas"]), 3)
            provenance_md = (out_dir / "formula_provenance.md").read_text(encoding="utf-8")
            self.assertIn("Mw = (log10(PGD) - a) / (b + c * log10(R))", provenance_md)
            self.assertIn("Melgar et al. (2015)", provenance_md)
            self.assertIn("Crowell et al. (2016)", provenance_md)
            self.assertIn("Ruhl et al. (2019)", provenance_md)
            self.assertIn("formula_coefficients", manifest_products)
            self.assertIn("formula_provenance", manifest_products)
            with (out_dir / "residual_review_evidence.csv").open(newline="", encoding="utf-8") as handle:
                evidence_rows = list(csv.DictReader(handle))
            self.assertEqual([row["triage_priority"] for row in evidence_rows], ["1", "2"])
            self.assertEqual(evidence_rows[0]["event_id"], "event-x")
            self.assertEqual(evidence_rows[0]["next_review_action"], "CHECK_WAVEFORM_AND_STATION_FILTERING;CHECK_RELEASE_GATE")
            evidence_json = json.loads((out_dir / "residual_review_evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence_json["schema_version"], "pgd-residual-review-evidence/v1")
            self.assertEqual(evidence_json["row_count"], 2)
            self.assertEqual(evidence_json["suggested_cause_counts"]["data_quality"], 1)
            evidence_md = (out_dir / "residual_review_evidence.md").read_text(encoding="utf-8")
            self.assertIn("Residual Review Evidence", evidence_md)
            self.assertIn("event-x", evidence_md)
            self.assertIn("CHECK_WAVEFORM_AND_STATION_FILTERING", evidence_md)
            self.assertIn("residual_review_evidence", manifest_products)
            with (out_dir / "residual_review_annotations_starter.csv").open(newline="", encoding="utf-8") as handle:
                starter_rows = list(csv.DictReader(handle))
            self.assertEqual([row["event_id"] for row in starter_rows], ["event-x", "event-y"])
            self.assertEqual(starter_rows[0]["triage_status_suggestion"], "NEEDS_DATA_CHECK")
            self.assertEqual(starter_rows[0]["manual_review_status"], "")
            self.assertEqual(starter_rows[0]["manual_review_cause"], "")
            self.assertEqual(starter_rows[0]["manual_review_notes"], "")
            self.assertEqual(starter_rows[0]["accepted_for_release"], "")
            self.assertEqual(starter_rows[0]["reviewer"], "")
            self.assertEqual(starter_rows[0]["reviewed_at"], "")
            with (out_dir / "residual_review_annotations_starter.csv").open(newline="", encoding="utf-8") as handle:
                starter_fieldnames = list(csv.DictReader(handle).fieldnames or [])
            self.assertIn("event_id", starter_fieldnames)
            self.assertIn("next_review_action", starter_fieldnames)
            self.assertIn("manual_review_status", starter_fieldnames)
            starter_md = (out_dir / "residual_review_annotations_starter.md").read_text(encoding="utf-8")
            self.assertIn("Residual Review Annotation Starter", starter_md)
            self.assertIn("event-x", starter_md)
            self.assertIn("manual_review_status", starter_md)
            checklist = (out_dir / "residual_review_checklist.md").read_text(encoding="utf-8")
            self.assertIn("Residual Review Checklist", checklist)
            self.assertIn("Manual fields are intentionally blank", checklist)
            self.assertIn("NEEDS_DATA_CHECK", checklist)
            self.assertIn("residual_review_annotations_starter", manifest_products)
            self.assertIn("residual_review_checklist", manifest_products)
            self.assertIn("residual_review_packet_index", manifest_products)
            self.assertIn("residual_review_packets", manifest_products)
            with (out_dir / "residual_review_packet_index.csv").open(newline="", encoding="utf-8") as handle:
                packet_rows = list(csv.DictReader(handle))
                packet_fields = list(handle.seek(0) or csv.DictReader(handle).fieldnames or [])
            self.assertEqual([row["event_id"] for row in packet_rows], ["event-x", "event-y"])
            self.assertEqual(packet_rows[0]["packet_path"], "residual_review_packets/001-event-x-crowell_2016_gfast.md")
            self.assertEqual(packet_rows[0]["manual_review_status"], "")
            self.assertIn("packet_path", packet_fields)
            packet_index_md = (out_dir / "residual_review_packet_index.md").read_text(encoding="utf-8")
            self.assertIn("Residual Review Packet Index", packet_index_md)
            self.assertIn("001-event-x-crowell_2016_gfast.md", packet_index_md)
            packet_path = out_dir / "residual_review_packets" / "001-event-x-crowell_2016_gfast.md"
            self.assertTrue(packet_path.exists())
            packet_md = packet_path.read_text(encoding="utf-8")
            self.assertIn("# PGD Residual Review Packet: event-x / crowell_2016_gfast", packet_md)
            self.assertIn("Abs residual Mw: `1.8`", packet_md)
            self.assertIn("Suggested status: `NEEDS_DATA_CHECK`", packet_md)
            self.assertIn("Best formula for event: `ruhl_2019`", packet_md)
            self.assertIn("Release status: `EXCLUDED_RELEASE_SET`", packet_md)
            self.assertIn("manual_review_status", packet_md)

    def test_zero_ready_events_returns_nonzero_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir, sensitivity_dir = self.make_report_bundle(root, ready_rows=0)
            out_dir = root / "release" / "empty"

            rc = build_pgd_release_package.main(["--report-dir", str(report_dir), "--sensitivity-dir", str(sensitivity_dir), "--out-dir", str(out_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((out_dir / "release_package_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "NO_READY_EVENTS")
            self.assertEqual(payload["ready_event_count"], 0)
            self.assertTrue((out_dir / "release_package.md").exists())

    def test_missing_required_input_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir, sensitivity_dir = self.make_report_bundle(root, omit={"science_release_events.csv"})
            out_dir = root / "release" / "broken"

            rc = build_pgd_release_package.main(["--report-dir", str(report_dir), "--sensitivity-dir", str(sensitivity_dir), "--out-dir", str(out_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((out_dir / "release_package_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(any(error["code"] == "MISSING_INPUT" and "science_release_events.csv" in error["path"] for error in payload["errors"]))

    def test_non_median_station_aggregation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir, sensitivity_dir = self.make_report_bundle(root)
            summary_path = report_dir / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["formula_recommendation"]["station_aggregation"] = "mean"
            summary_path.write_text(json.dumps(summary) + "\n", encoding="utf-8")
            out_dir = root / "release" / "non-median"

            rc = build_pgd_release_package.main(["--report-dir", str(report_dir), "--sensitivity-dir", str(sensitivity_dir), "--out-dir", str(out_dir)])

            self.assertEqual(rc, 1)
            payload = json.loads((out_dir / "release_package_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "INVALID")
            self.assertTrue(
                any(
                    error["code"] == "NON_MEDIAN_STATION_AGGREGATION"
                    and error["value"] == "mean"
                    and error["path"].endswith("summary.json")
                    for error in payload["errors"]
                )
            )
            markdown = (out_dir / "release_package.md").read_text(encoding="utf-8")
            self.assertIn("Station aggregation method: `median`", markdown)


if __name__ == "__main__":
    unittest.main()
