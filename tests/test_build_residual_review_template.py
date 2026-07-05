from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_residual_review_template.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing residual review template builder: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("build_residual_review_template", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def review_row(event_id: str, formula: str, status: str, abs_residual: str) -> dict[str, str]:
    return {
        "event_id": event_id,
        "event_time": "2020-01-01T00:00:00Z",
        "country": "United States",
        "place": "Synthetic event",
        "formula": formula,
        "usgs_magnitude": "6.4",
        "estimated_mw_median": "7.2",
        "residual_mw": "0.8",
        "abs_residual_mw": abs_residual,
        "pgd_reliability": "UNUSABLE",
        "usable_station_count": "0",
        "median_pgd_snr": "",
        "median_distance_km": "25.0",
        "review_status": status,
        "suspected_cause": "",
        "waveform_issue": "",
        "station_geometry_issue": "",
        "magnitude_metadata_issue": "",
        "formula_limitation": "",
        "reviewer_note": "",
    }


class BuildResidualReviewTemplateTest(unittest.TestCase):
    def test_cli_writes_pending_template_with_formula_and_release_context(self):
        builder = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_csv = root / "residual_review_annotated.csv"
            events_csv = root / "events.csv"
            release_set_csv = root / "release_set.csv"
            out_csv = root / "residual_review_annotations_template.csv"
            out_md = root / "residual_review_guide.md"
            write_rows(
                review_csv,
                [
                    review_row("event-a", "ruhl_2019", "REVIEWED", "1.5"),
                    review_row("event-b", "crowell_2016_gfast", "UNREVIEWED", "1.2"),
                    review_row("event-b", "melgar_2015", "NEEDS_METADATA_CHECK", "0.4"),
                ],
            )
            write_rows(
                events_csv,
                [
                    {
                        "event_id": "event-b",
                        "formula": "melgar_2015",
                        "abs_residual_mw": "0.4",
                        "residual_mw": "0.4",
                        "estimated_mw_median": "6.8",
                        "pgd_reliability": "LOW",
                        "usable_station_count": "1",
                        "median_pgd_snr": "2.5",
                        "median_distance_km": "25.0",
                    },
                    {
                        "event_id": "event-b",
                        "formula": "crowell_2016_gfast",
                        "abs_residual_mw": "1.2",
                        "residual_mw": "1.2",
                        "estimated_mw_median": "7.6",
                        "pgd_reliability": "UNUSABLE",
                        "usable_station_count": "0",
                        "median_pgd_snr": "",
                        "median_distance_km": "25.0",
                    },
                    {
                        "event_id": "event-b",
                        "formula": "ruhl_2019",
                        "abs_residual_mw": "0.6",
                        "residual_mw": "0.6",
                        "estimated_mw_median": "7.0",
                        "pgd_reliability": "LOW",
                        "usable_station_count": "1",
                        "median_pgd_snr": "2.5",
                        "median_distance_km": "25.0",
                    },
                ],
            )
            write_rows(
                release_set_csv,
                [
                    {
                        "event_id": "event-b",
                        "formula": "ruhl_2019",
                        "release_status": "EXCLUDED_RELEASE_SET",
                        "release_failure_reasons": "insufficient_usable_stations;low_reliability",
                        "release_review_reasons": "",
                    }
                ],
            )

            rc = builder.main(
                [
                    "--review-csv",
                    str(review_csv),
                    "--events-csv",
                    str(events_csv),
                    "--release-set-csv",
                    str(release_set_csv),
                    "--out-csv",
                    str(out_csv),
                    "--out-md",
                    str(out_md),
                ]
            )

            self.assertEqual(rc, 0)
            with out_csv.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([(row["event_id"], row["formula"]) for row in rows], [("event-b", "crowell_2016_gfast"), ("event-b", "melgar_2015")])
            first = rows[0]
            self.assertEqual(first["review_priority"], "1")
            self.assertEqual(first["review_status"], "UNREVIEWED")
            self.assertEqual(first["best_formula_for_event"], "melgar_2015")
            self.assertEqual(first["best_formula_abs_residual_mw"], "0.4")
            self.assertIn("crowell_2016_gfast=1.2", first["formula_residuals_for_event"])
            self.assertEqual(first["release_status"], "EXCLUDED_RELEASE_SET")
            self.assertIn("insufficient_usable_stations", first["release_failure_reasons"])
            self.assertIn("check usable station filtering", first["suggested_checks"])
            self.assertIn("compare formula limitation", first["suggested_checks"])
            self.assertEqual(first["suspected_cause"], "")
            guide = out_md.read_text(encoding="utf-8")
            self.assertIn("Residual Review Guide", guide)
            self.assertIn("Allowed Review Statuses", guide)
            self.assertIn("event-b", guide)
            self.assertIn("crowell_2016_gfast", guide)


if __name__ == "__main__":
    unittest.main()
