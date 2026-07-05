import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_PUBLIC_PATHS = [
    "docs/mainline_operating_model.md",
    "docs/normalized_export_schema.md",
    "docs/pgd_magnitude_report.md",
    "docs/research_cddis.md",
    "docs/runbook_earthscope_geonet.md",
    "docs/source_promotion_checklist.md",
    "docs/watcher_operating_model.md",
    "scripts/pgd_magnitude/pgd_contract.py",
    "scripts/pgd_magnitude/build_pgd_release_package.py",
    "scripts/pgd_magnitude/build_pgd_release_readiness_report.py",
    "scripts/pgd_magnitude/build_pgd_interpretation_report.py",
    "scripts/pgd_magnitude/build_pgd_formula_test_matrix.py",
    "scripts/pgd_magnitude/build_pgd_filter_benchmark.py",
    "scripts/pgd_magnitude/build_pgd_benchmark_interpretation.py",
    "scripts/pgd_magnitude/build_pgd_baseline_narrative_handoff.py",
    "scripts/pgd_magnitude/build_pgd_baseline_science_narrative.py",
    "scripts/pgd_magnitude/build_pgd_comparison_formula_review_packet_summary.py",
    "scripts/pgd_magnitude/build_pgd_review_briefing.py",
    "scripts/pgd_magnitude/build_pgd_release_blocker_analysis.py",
    "scripts/pgd_magnitude/build_pgd_release_blocker_decision_guide.py",
    "scripts/pgd_magnitude/build_pgd_release_blocker_review_prompt.py",
    "scripts/pgd_magnitude/build_pgd_external_review_handoff.py",
    "scripts/pgd_magnitude/build_pgd_release_readme.py",
    "scripts/pgd_magnitude/build_pgd_recommended_formula_release_status.py",
    "scripts/pgd_magnitude/build_release_blocking_review_starter.py",
    "scripts/pgd_magnitude/build_residual_review_decision_report.py",
    "scripts/pgd_magnitude/build_residual_review_dashboard.py",
    "scripts/pgd_magnitude/build_residual_review_template.py",
    "scripts/pgd_magnitude/build_residual_review_worklist.py",
    "scripts/pgd_magnitude/build_reviewed_release_set.py",
    "scripts/pgd_magnitude/manage_residual_review.py",
    "scripts/pgd_magnitude/run_pgd_benchmark_bundle.py",
    "scripts/pgd_magnitude/run_pgd_science_bundle.py",
    "scripts/pgd_magnitude/triage_residual_review.py",
    "scripts/pgd_magnitude/validate_release_starter_annotations.py",
    "scripts/ops/check_shell_syntax.sh",
    "scripts/ops/export_watcher_state.py",
    "scripts/ops/smoke_test_offline.sh",
    "tools/ga_downloader/README.md",
    "tools/ring_downloader/README.md",
    "tools/renag_downloader/README.md",
    "tools/epos_downloader/README.md",
]


def is_ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-v", path],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 1:
        return False
    if result.returncode != 0:
        raise AssertionError(result.stderr or f"git check-ignore failed for {path}")
    pattern = result.stdout.split("\t", 1)[0].rsplit(":", 1)[-1]
    return not pattern.startswith("!")


class RepoAllowlistTest(unittest.TestCase):
    def test_mainline_docs_ops_scripts_and_parked_readmes_are_not_ignored(self):
        for relative_path in REQUIRED_PUBLIC_PATHS:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT / relative_path).exists(), relative_path)
                self.assertFalse(is_ignored(relative_path), relative_path)


if __name__ == "__main__":
    unittest.main()
