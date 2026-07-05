import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pgd_magnitude" / "run_pgd_science_bundle.py"
SPEC = importlib.util.spec_from_file_location("run_pgd_science_bundle", MODULE_PATH)
run_pgd_science_bundle = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_pgd_science_bundle)


class RunPgdScienceBundleTest(unittest.TestCase):
    def test_runs_standard_bundle_stages_in_order_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_root = root / "exports"
            report_dir = root / "reports" / "pgd" / "latest"
            sensitivity_dir = root / "reports" / "pgd" / "sensitivity" / "latest"
            release_dir = root / "reports" / "pgd" / "release" / "latest"
            out_json = root / "bundle-summary.json"
            commands: list[list[str]] = []

            def fake_run(command: list[str]):
                commands.append(command)
                return SimpleNamespace(returncode=0, stdout=f"ran {Path(command[1]).name}", stderr="")

            original_run_command = run_pgd_science_bundle.run_command
            try:
                run_pgd_science_bundle.run_command = fake_run

                rc = run_pgd_science_bundle.main(
                    [
                        "--export-root",
                        str(export_root),
                        "--report-dir",
                        str(report_dir),
                        "--sensitivity-dir",
                        str(sensitivity_dir),
                        "--release-dir",
                        str(release_dir),
                        "--out-json",
                        str(out_json),
                    ]
                )
            finally:
                run_pgd_science_bundle.run_command = original_run_command

            self.assertEqual(rc, 0)
            self.assertEqual(
                [Path(command[1]).name for command in commands],
                [
                    "run_pgd_report.py",
                    "manage_residual_review.py",
                    "triage_residual_review.py",
                    "build_residual_review_template.py",
                    "run_pgd_sensitivity.py",
                    "build_pgd_interpretation_report.py",
                    "build_pgd_release_package.py",
                    "build_residual_review_dashboard.py",
                    "build_residual_review_decision_report.py",
                    "build_reviewed_release_set.py",
                    "build_residual_review_worklist.py",
                    "build_release_blocking_review_starter.py",
                    "build_pgd_release_readiness_report.py",
                    "build_pgd_formula_test_matrix.py",
                    "build_pgd_release_blocker_analysis.py",
                    "build_pgd_release_blocker_decision_guide.py",
                    "build_pgd_recommended_formula_release_status.py",
                    "build_pgd_baseline_narrative_handoff.py",
                    "build_pgd_baseline_science_narrative.py",
                    "build_pgd_comparison_formula_review_packet_summary.py",
                    "build_pgd_review_briefing.py",
                    "build_pgd_release_readme.py",
                    "build_pgd_release_blocker_review_prompt.py",
                    "build_pgd_external_review_handoff.py",
                ],
            )
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(
                [stage["stage"] for stage in payload["stages"]],
                [
                    "pgd_report",
                    "residual_review_merge",
                    "residual_review_triage",
                    "residual_review_template",
                    "pgd_sensitivity",
                    "pgd_interpretation",
                    "pgd_release_package",
                    "release_review_dashboard",
                    "release_review_decision_report",
                    "reviewed_release_set",
                    "residual_review_worklist",
                    "release_blocking_review_starter",
                    "pgd_release_readiness",
                    "pgd_formula_test_matrix",
                    "pgd_release_blocker_analysis",
                    "pgd_release_blocker_decision_guide",
                    "pgd_recommended_formula_release_status",
                    "pgd_baseline_narrative_handoff",
                    "pgd_baseline_science_narrative",
                    "pgd_comparison_formula_review_packet_summary",
                    "pgd_review_briefing",
                    "pgd_release_readme",
                    "pgd_release_blocker_review_prompt",
                    "pgd_external_review_handoff",
                ],
            )
            self.assertEqual({stage["returncode"] for stage in payload["stages"]}, {0})
            self.assertEqual(payload["outputs"]["report_summary"], str(report_dir / "summary.json"))
            self.assertEqual(payload["outputs"]["sensitivity_summary"], str(sensitivity_dir / "summary.json"))
            self.assertEqual(payload["outputs"]["release_package_summary"], str(release_dir / "release_package_summary.json"))
            self.assertEqual(payload["outputs"]["residual_review_dashboard"], str(release_dir / "residual_review_dashboard.csv"))
            self.assertEqual(payload["outputs"]["residual_review_decision_report"], str(release_dir / "residual_review_decision_report.csv"))
            self.assertEqual(payload["outputs"]["reviewed_release_summary"], str(release_dir / "reviewed_release_summary.json"))
            self.assertEqual(payload["outputs"]["residual_review_worklist"], str(release_dir / "residual_review_worklist.csv"))
            self.assertEqual(payload["outputs"]["release_blocking_review_starter"], str(release_dir / "release_blocking_review_starter.csv"))
            self.assertEqual(payload["outputs"]["pgd_release_readiness"], str(release_dir / "pgd_release_readiness.json"))
            self.assertEqual(payload["outputs"]["pgd_formula_test_matrix"], str(release_dir / "pgd_formula_test_matrix.csv"))
            self.assertEqual(payload["outputs"]["pgd_release_blocker_analysis"], str(release_dir / "pgd_release_blocker_analysis.csv"))
            self.assertEqual(payload["outputs"]["pgd_release_blocker_decision_guide"], str(release_dir / "pgd_release_blocker_decision_guide.csv"))
            self.assertEqual(payload["outputs"]["pgd_recommended_formula_release_status"], str(release_dir / "pgd_recommended_formula_release_status.csv"))
            self.assertEqual(payload["outputs"]["pgd_baseline_narrative_handoff"], str(release_dir / "pgd_baseline_narrative_handoff.json"))
            self.assertEqual(payload["outputs"]["pgd_baseline_science_narrative"], str(release_dir / "pgd_baseline_science_narrative.json"))
            self.assertEqual(payload["outputs"]["pgd_comparison_formula_review_packet_summary"], str(release_dir / "pgd_comparison_formula_review_packet_summary.csv"))
            self.assertEqual(payload["outputs"]["pgd_review_briefing"], str(release_dir / "pgd_review_briefing.json"))
            self.assertEqual(payload["outputs"]["pgd_release_readme"], str(release_dir / "README.md"))
            self.assertEqual(payload["outputs"]["pgd_release_blocker_review_prompt"], str(release_dir / "pgd_release_blocker_review_prompt.md"))
            self.assertEqual(payload["outputs"]["pgd_external_review_handoff"], str(release_dir / "pgd_external_review_handoff.md"))
            self.assertEqual(payload["outputs"]["pgd_external_review_handoff_manifest"], str(release_dir / "pgd_external_review_handoff_manifest.json"))
            self.assertNotIn("--annotations", commands[1])
            self.assertIn(str(export_root), commands[0])
            self.assertIn(str(report_dir), commands[0])
            self.assertIn(str(sensitivity_dir), commands[4])
            self.assertIn(str(release_dir), commands[6])

    def test_passes_annotations_and_can_skip_template_and_sensitivity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            annotations = root / "manual_annotations.csv"
            out_json = root / "summary.json"
            commands: list[list[str]] = []

            def fake_run(command: list[str]):
                commands.append(command)
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            original_run_command = run_pgd_science_bundle.run_command
            try:
                run_pgd_science_bundle.run_command = fake_run

                rc = run_pgd_science_bundle.main(
                    [
                        "--export-root",
                        str(root / "exports"),
                        "--report-dir",
                        str(root / "latest"),
                        "--sensitivity-dir",
                        str(root / "sensitivity"),
                        "--annotations",
                        str(annotations),
                        "--skip-template",
                        "--skip-sensitivity",
                        "--skip-release-package",
                        "--skip-release-review",
                        "--out-json",
                        str(out_json),
                    ]
                )
            finally:
                run_pgd_science_bundle.run_command = original_run_command

            self.assertEqual(rc, 0)
            self.assertEqual(
                [Path(command[1]).name for command in commands],
                [
                    "run_pgd_report.py",
                    "manage_residual_review.py",
                    "triage_residual_review.py",
                    "build_pgd_interpretation_report.py",
                ],
            )
            self.assertIn("--annotations", commands[1])
            self.assertIn(str(annotations), commands[1])
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual([stage["stage"] for stage in payload["stages"]], ["pgd_report", "residual_review_merge", "residual_review_triage", "pgd_interpretation"])
            self.assertEqual(payload["annotations"], str(annotations))
            self.assertEqual(payload["starter_annotations"], "")

    def test_validates_starter_annotations_before_residual_review_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            starter_annotations = root / "completed_release_blocking_review_starter.csv"
            out_json = root / "summary.json"
            commands: list[list[str]] = []

            def fake_run(command: list[str]):
                commands.append(command)
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            original_run_command = run_pgd_science_bundle.run_command
            try:
                run_pgd_science_bundle.run_command = fake_run

                rc = run_pgd_science_bundle.main(
                    [
                        "--export-root",
                        str(root / "exports"),
                        "--report-dir",
                        str(root / "latest"),
                        "--sensitivity-dir",
                        str(root / "sensitivity"),
                        "--release-dir",
                        str(root / "release"),
                        "--starter-annotations",
                        str(starter_annotations),
                        "--skip-template",
                        "--skip-sensitivity",
                        "--skip-release-package",
                        "--skip-release-review",
                        "--out-json",
                        str(out_json),
                    ]
                )
            finally:
                run_pgd_science_bundle.run_command = original_run_command

            self.assertEqual(rc, 0)
            self.assertEqual(
                [Path(command[1]).name for command in commands],
                [
                    "run_pgd_report.py",
                    "validate_release_starter_annotations.py",
                    "manage_residual_review.py",
                    "triage_residual_review.py",
                    "build_pgd_interpretation_report.py",
                ],
            )
            validation_command = commands[1]
            self.assertIn("--completed-starter", validation_command)
            self.assertIn(str(starter_annotations), validation_command)
            self.assertIn("--release-dir", validation_command)
            self.assertIn(str(root / "release"), validation_command)
            self.assertIn("--require-complete", validation_command)
            self.assertIn("--strict", validation_command)
            self.assertIn("--starter-annotations", commands[2])
            self.assertIn(str(starter_annotations), commands[2])
            self.assertNotIn("--annotations", commands[2])
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual([stage["stage"] for stage in payload["stages"]], ["pgd_report", "release_starter_validation", "residual_review_merge", "residual_review_triage", "pgd_interpretation"])
            self.assertEqual(payload["annotations"], "")
            self.assertEqual(payload["starter_annotations"], str(starter_annotations))
            self.assertEqual(payload["outputs"]["release_starter_validation"], str(root / "release" / "release_starter_validation.json"))

    def test_starter_validation_failure_stops_before_residual_review_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            starter_annotations = root / "completed_release_blocking_review_starter.csv"
            out_json = root / "summary.json"
            commands: list[list[str]] = []

            def fake_run(command: list[str]):
                commands.append(command)
                if Path(command[1]).name == "validate_release_starter_annotations.py":
                    return SimpleNamespace(returncode=1, stdout="{}", stderr="starter invalid")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            original_run_command = run_pgd_science_bundle.run_command
            try:
                run_pgd_science_bundle.run_command = fake_run

                rc = run_pgd_science_bundle.main(
                    [
                        "--export-root",
                        str(root / "exports"),
                        "--report-dir",
                        str(root / "latest"),
                        "--sensitivity-dir",
                        str(root / "sensitivity"),
                        "--release-dir",
                        str(root / "release"),
                        "--starter-annotations",
                        str(starter_annotations),
                        "--out-json",
                        str(out_json),
                    ]
                )
            finally:
                run_pgd_science_bundle.run_command = original_run_command

            self.assertEqual(rc, 1)
            self.assertEqual([Path(command[1]).name for command in commands], ["run_pgd_report.py", "validate_release_starter_annotations.py"])
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "FAILED")
            self.assertEqual(payload["failed_stage"], "release_starter_validation")
            self.assertIn("starter invalid", payload["stages"][-1]["stderr"])

    def test_annotations_and_starter_annotations_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SystemExit) as ctx:
                run_pgd_science_bundle.parse_args(
                    [
                        "--export-root",
                        str(root / "exports"),
                        "--report-dir",
                        str(root / "latest"),
                        "--annotations",
                        str(root / "manual_annotations.csv"),
                        "--starter-annotations",
                        str(root / "completed_starter.csv"),
                    ]
                )
            self.assertEqual(ctx.exception.code, 2)

    def test_can_skip_release_review_while_still_building_release_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_json = root / "summary.json"
            commands: list[list[str]] = []

            def fake_run(command: list[str]):
                commands.append(command)
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            original_run_command = run_pgd_science_bundle.run_command
            try:
                run_pgd_science_bundle.run_command = fake_run

                rc = run_pgd_science_bundle.main(
                    [
                        "--export-root",
                        str(root / "exports"),
                        "--report-dir",
                        str(root / "latest"),
                        "--sensitivity-dir",
                        str(root / "sensitivity"),
                        "--release-dir",
                        str(root / "release"),
                        "--skip-release-review",
                        "--out-json",
                        str(out_json),
                    ]
                )
            finally:
                run_pgd_science_bundle.run_command = original_run_command

            self.assertEqual(rc, 0)
            self.assertIn("build_pgd_release_package.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_residual_review_dashboard.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_residual_review_worklist.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_release_blocking_review_starter.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_pgd_release_readiness_report.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_pgd_formula_test_matrix.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_pgd_release_blocker_analysis.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_pgd_release_blocker_decision_guide.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_pgd_recommended_formula_release_status.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_pgd_comparison_formula_review_packet_summary.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_pgd_review_briefing.py", [Path(command[1]).name for command in commands])
            self.assertNotIn("build_pgd_release_readme.py", [Path(command[1]).name for command in commands])
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertIn("pgd_release_package", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("release_review_dashboard", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("residual_review_worklist", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("release_blocking_review_starter", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("pgd_release_readiness", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("pgd_formula_test_matrix", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("pgd_release_blocker_analysis", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("pgd_release_blocker_decision_guide", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("pgd_recommended_formula_release_status", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("pgd_comparison_formula_review_packet_summary", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("pgd_review_briefing", [stage["stage"] for stage in payload["stages"]])
            self.assertNotIn("pgd_release_readme", [stage["stage"] for stage in payload["stages"]])

    def test_fails_fast_and_writes_failed_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_json = root / "summary.json"
            commands: list[list[str]] = []

            def fake_run(command: list[str]):
                commands.append(command)
                if Path(command[1]).name == "manage_residual_review.py":
                    return SimpleNamespace(returncode=7, stdout="", stderr="merge failed")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            original_run_command = run_pgd_science_bundle.run_command
            try:
                run_pgd_science_bundle.run_command = fake_run

                rc = run_pgd_science_bundle.main(
                    [
                        "--export-root",
                        str(root / "exports"),
                        "--report-dir",
                        str(root / "latest"),
                        "--sensitivity-dir",
                        str(root / "sensitivity"),
                        "--out-json",
                        str(out_json),
                    ]
                )
            finally:
                run_pgd_science_bundle.run_command = original_run_command

            self.assertEqual(rc, 1)
            self.assertEqual([Path(command[1]).name for command in commands], ["run_pgd_report.py", "manage_residual_review.py"])
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "FAILED")
            self.assertEqual(payload["failed_stage"], "residual_review_merge")
            self.assertEqual(payload["stages"][-1]["returncode"], 7)
            self.assertIn("merge failed", payload["stages"][-1]["stderr"])


if __name__ == "__main__":
    unittest.main()
