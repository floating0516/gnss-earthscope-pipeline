from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "build_pgd_interpretation_report.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing PGD interpretation script: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("build_pgd_interpretation_report", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class BuildPgdInterpretationReportTest(unittest.TestCase):
    def test_cli_writes_json_and_markdown_interpretation(self):
        builder = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "reports" / "pgd_magnitude" / "latest"
            sensitivity_dir = root / "reports" / "pgd_magnitude" / "sensitivity" / "latest"
            out_json = report_dir / "pgd_interpretation.json"
            out_md = report_dir / "pgd_interpretation.md"
            write_json(
                report_dir / "summary.json",
                {
                    "status": "OK",
                    "counts": {"unique_events": 94, "event_rows": 282, "station_rows": 1947},
                    "formula_recommendation": {
                        "recommended_formula": "ruhl_2019",
                        "station_aggregation": "median",
                        "criterion": "lowest_mae_mw",
                        "mae_mw": 0.43587,
                        "rmse_mw": 0.53454,
                        "event_count": 94,
                    },
                    "pgd_release_set": {
                        "total_events": 94,
                        "ready_events": 13,
                        "excluded_events": 81,
                        "review_required_events": 0,
                    },
                },
            )
            write_json(
                report_dir / "residual_review_triage_summary.json",
                {
                    "status": "OK",
                    "row_count": 20,
                    "suggested_status_counts": {"NEEDS_DATA_CHECK": 19, "NEEDS_FORMULA_REVIEW": 1},
                    "suggested_cause_counts": {"data_quality": 19, "formula_limitation": 1},
                    "top_priority_rows": [
                        {
                            "event_id": "event-a",
                            "formula": "crowell_2016_gfast",
                            "abs_residual_mw": "1.8",
                            "triage_status_suggestion": "NEEDS_DATA_CHECK",
                            "triage_cause_suggestion": "data_quality",
                        }
                    ],
                },
            )
            write_json(
                sensitivity_dir / "summary.json",
                {
                    "status": "OK",
                    "recommendation_stable": "no",
                    "recommendations": [
                        {"scenario_id": "baseline", "recommended_formula": "ruhl_2019", "matches_baseline": "yes", "mae_mw": 0.43587},
                        {"scenario_id": "horizontal", "recommended_formula": "melgar_2015", "matches_baseline": "no", "mae_mw": 0.35362},
                        {"scenario_id": "epicentral", "recommended_formula": "ruhl_2019", "matches_baseline": "yes", "mae_mw": 0.43879},
                        {"scenario_id": "calibrated", "recommended_formula": "melgar_2015", "matches_baseline": "no", "mae_mw": 0.34052},
                    ],
                },
            )

            rc = builder.main(
                [
                    "--report-dir",
                    str(report_dir),
                    "--sensitivity-dir",
                    str(sensitivity_dir),
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                ]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["baseline"]["recommended_formula"], "ruhl_2019")
            self.assertEqual(payload["baseline"]["station_aggregation"], "median")
            self.assertEqual(payload["sensitivity"]["recommendation_stable"], "no")
            self.assertEqual(payload["sensitivity"]["formula_switch_scenarios"], ["horizontal", "calibrated"])
            self.assertTrue(payload["interpretation_flags"]["requires_sensitivity_caveat"])
            self.assertTrue(payload["interpretation_flags"]["residuals_data_quality_dominated"])
            self.assertEqual(payload["release_set"]["ready_events"], 13)
            self.assertEqual(payload["residual_triage"]["suggested_status_counts"]["NEEDS_DATA_CHECK"], 19)
            markdown = out_md.read_text(encoding="utf-8")
            self.assertIn("PGD Interpretation Report", markdown)
            self.assertIn("ruhl_2019", markdown)
            self.assertIn("Recommendation stability: `no`", markdown)
            self.assertIn("horizontal", markdown)
            self.assertIn("Residual triage is dominated by data-quality checks", markdown)


if __name__ == "__main__":
    unittest.main()
