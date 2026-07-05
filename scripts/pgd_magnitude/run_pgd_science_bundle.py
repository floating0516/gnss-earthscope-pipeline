#!/usr/bin/env python3
"""Run the complete PGD science product bundle."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("exports/normalized-ok-stations-us-nz")
DEFAULT_REPORT_DIR = Path("reports/pgd_magnitude/latest")
DEFAULT_SENSITIVITY_DIR = Path("reports/pgd_magnitude/sensitivity/latest")
DEFAULT_RELEASE_DIR = Path("reports/pgd_magnitude/release/latest")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT, help="Normalized export root.")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR, help="PGD latest report output directory.")
    parser.add_argument("--sensitivity-dir", type=Path, default=DEFAULT_SENSITIVITY_DIR, help="PGD sensitivity report output directory.")
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE_DIR, help="PGD release package output directory.")
    annotation_group = parser.add_mutually_exclusive_group()
    annotation_group.add_argument("--annotations", type=Path, default=None, help="Optional manual residual-review annotation CSV.")
    annotation_group.add_argument(
        "--starter-annotations",
        type=Path,
        default=None,
        help="Optional completed release starter CSV to import through manage_residual_review.py --starter-annotations.",
    )
    parser.add_argument("--out-json", type=Path, default=None, help="Bundle summary JSON. Defaults to <report-dir>/pgd_science_bundle_summary.json.")
    parser.add_argument("--skip-report", action="store_true", help="Skip run_pgd_report.py and reuse existing report-dir products.")
    parser.add_argument("--skip-sensitivity", action="store_true", help="Skip run_pgd_sensitivity.py and reuse existing sensitivity-dir products.")
    parser.add_argument("--skip-template", action="store_true", help="Skip residual review annotation template generation.")
    parser.add_argument("--skip-release-package", action="store_true", help="Skip build_pgd_release_package.py and reuse existing release-dir products.")
    parser.add_argument("--skip-release-review", action="store_true", help="Skip release dashboard, decision report, and reviewed release-set generation.")
    return parser.parse_args(argv)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def script_command(script_name: str, *args: object) -> list[str]:
    return [sys.executable, str(SCRIPT_DIR / script_name), *(str(arg) for arg in args)]


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def selected_annotations(args: argparse.Namespace) -> Path | None:
    if args.starter_annotations is not None:
        return None
    if args.annotations is not None:
        return args.annotations
    candidate = args.report_dir / "residual_review_annotations.csv"
    return candidate if candidate.exists() else None


def selected_starter_annotations(args: argparse.Namespace) -> Path | None:
    return args.starter_annotations


def output_paths(args: argparse.Namespace) -> dict[str, str]:
    return {
        "report_summary": str(args.report_dir / "summary.json"),
        "residual_review_annotated": str(args.report_dir / "residual_review_annotated.csv"),
        "residual_review_summary": str(args.report_dir / "residual_review_summary.json"),
        "residual_review_triage": str(args.report_dir / "residual_review_triage.csv"),
        "residual_review_triage_summary": str(args.report_dir / "residual_review_triage_summary.json"),
        "residual_review_template": str(args.report_dir / "residual_review_annotations_template.csv"),
        "residual_review_guide": str(args.report_dir / "residual_review_guide.md"),
        "sensitivity_summary": str(args.sensitivity_dir / "summary.json"),
        "pgd_interpretation": str(args.report_dir / "pgd_interpretation.json"),
        "pgd_interpretation_md": str(args.report_dir / "pgd_interpretation.md"),
        "release_package_summary": str(args.release_dir / "release_package_summary.json"),
        "release_package": str(args.release_dir / "release_package.md"),
        "release_package_manifest": str(args.release_dir / "package_manifest.csv"),
        "residual_review_dashboard": str(args.release_dir / "residual_review_dashboard.csv"),
        "residual_review_dashboard_summary": str(args.release_dir / "residual_review_dashboard.json"),
        "residual_review_decision_report": str(args.release_dir / "residual_review_decision_report.csv"),
        "residual_review_decision_summary": str(args.release_dir / "residual_review_decision_report.json"),
        "reviewed_release_events": str(args.release_dir / "reviewed_release_events.csv"),
        "reviewed_release_blockers": str(args.release_dir / "reviewed_release_blockers.csv"),
        "reviewed_release_summary": str(args.release_dir / "reviewed_release_summary.json"),
        "residual_review_worklist": str(args.release_dir / "residual_review_worklist.csv"),
        "residual_review_worklist_summary": str(args.release_dir / "residual_review_worklist.json"),
        "release_blocking_review_starter": str(args.release_dir / "release_blocking_review_starter.csv"),
        "release_blocking_review_starter_summary": str(args.release_dir / "release_blocking_review_starter.json"),
        "release_starter_validation": str(args.release_dir / "release_starter_validation.json"),
        "release_starter_validation_csv": str(args.release_dir / "release_starter_validation.csv"),
        "release_starter_validation_md": str(args.release_dir / "release_starter_validation.md"),
        "pgd_release_readiness": str(args.release_dir / "pgd_release_readiness.json"),
        "pgd_release_readiness_md": str(args.release_dir / "pgd_release_readiness.md"),
        "pgd_formula_test_matrix": str(args.release_dir / "pgd_formula_test_matrix.csv"),
        "pgd_formula_test_matrix_json": str(args.release_dir / "pgd_formula_test_matrix.json"),
        "pgd_formula_test_matrix_md": str(args.release_dir / "pgd_formula_test_matrix.md"),
        "pgd_release_blocker_analysis": str(args.release_dir / "pgd_release_blocker_analysis.csv"),
        "pgd_release_blocker_analysis_json": str(args.release_dir / "pgd_release_blocker_analysis.json"),
        "pgd_release_blocker_analysis_md": str(args.release_dir / "pgd_release_blocker_analysis.md"),
        "pgd_release_blocker_decision_guide": str(args.release_dir / "pgd_release_blocker_decision_guide.csv"),
        "pgd_release_blocker_decision_guide_json": str(args.release_dir / "pgd_release_blocker_decision_guide.json"),
        "pgd_release_blocker_decision_guide_md": str(args.release_dir / "pgd_release_blocker_decision_guide.md"),
        "pgd_recommended_formula_release_status": str(args.release_dir / "pgd_recommended_formula_release_status.csv"),
        "pgd_recommended_formula_release_status_json": str(args.release_dir / "pgd_recommended_formula_release_status.json"),
        "pgd_recommended_formula_release_status_md": str(args.release_dir / "pgd_recommended_formula_release_status.md"),
        "pgd_baseline_narrative_handoff": str(args.release_dir / "pgd_baseline_narrative_handoff.json"),
        "pgd_baseline_narrative_handoff_md": str(args.release_dir / "pgd_baseline_narrative_handoff.md"),
        "pgd_baseline_science_narrative": str(args.release_dir / "pgd_baseline_science_narrative.json"),
        "pgd_baseline_science_narrative_md": str(args.release_dir / "pgd_baseline_science_narrative.md"),
        "pgd_comparison_formula_review_packet_summary": str(args.release_dir / "pgd_comparison_formula_review_packet_summary.csv"),
        "pgd_comparison_formula_review_packet_summary_json": str(args.release_dir / "pgd_comparison_formula_review_packet_summary.json"),
        "pgd_comparison_formula_review_packet_summary_md": str(args.release_dir / "pgd_comparison_formula_review_packet_summary.md"),
        "pgd_review_briefing": str(args.release_dir / "pgd_review_briefing.json"),
        "pgd_review_briefing_md": str(args.release_dir / "pgd_review_briefing.md"),
        "pgd_release_readme": str(args.release_dir / "README.md"),
        "pgd_release_readme_json": str(args.release_dir / "release_readme.json"),
        "pgd_release_blocker_review_prompt": str(args.release_dir / "pgd_release_blocker_review_prompt.md"),
        "pgd_release_blocker_review_prompt_json": str(args.release_dir / "pgd_release_blocker_review_prompt.json"),
        "pgd_external_review_handoff": str(args.release_dir / "pgd_external_review_handoff.md"),
        "pgd_external_review_handoff_manifest": str(args.release_dir / "pgd_external_review_handoff_manifest.json"),
        "pgd_external_review_handoff_manifest_csv": str(args.release_dir / "pgd_external_review_handoff_manifest.csv"),
        "bundle_summary": str(args.out_json),
    }


def stage_commands(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    commands: list[tuple[str, list[str]]] = []
    report_dir = args.report_dir
    sensitivity_dir = args.sensitivity_dir
    if not args.skip_report:
        commands.append(
            (
                "pgd_report",
                script_command("run_pgd_report.py", "--export-root", args.export_root, "--out-dir", report_dir),
            )
        )

    starter_annotations = selected_starter_annotations(args)
    if starter_annotations is not None:
        commands.append(
            (
                "release_starter_validation",
                script_command(
                    "validate_release_starter_annotations.py",
                    "--release-dir",
                    args.release_dir,
                    "--completed-starter",
                    starter_annotations,
                    "--require-complete",
                    "--strict",
                ),
            )
        )

    review_merge_command = script_command(
        "manage_residual_review.py",
        "--review-csv",
        report_dir / "residual_review.csv",
        "--out-csv",
        report_dir / "residual_review_annotated.csv",
        "--out-json",
        report_dir / "residual_review_summary.json",
        "--out-md",
        report_dir / "residual_review_summary.md",
        "--strict",
    )
    annotations = selected_annotations(args)
    if starter_annotations is not None:
        review_merge_command.extend(["--starter-annotations", str(starter_annotations)])
    elif annotations is not None:
        review_merge_command.extend(["--annotations", str(annotations)])
    commands.append(("residual_review_merge", review_merge_command))

    commands.append(
        (
            "residual_review_triage",
            script_command(
                "triage_residual_review.py",
                "--review-csv",
                report_dir / "residual_review_annotated.csv",
                "--events-csv",
                report_dir / "events.csv",
                "--release-set-csv",
                report_dir / "release_set.csv",
                "--out-csv",
                report_dir / "residual_review_triage.csv",
                "--out-json",
                report_dir / "residual_review_triage_summary.json",
                "--out-md",
                report_dir / "residual_review_triage.md",
            ),
        )
    )

    if not args.skip_template:
        commands.append(
            (
                "residual_review_template",
                script_command(
                    "build_residual_review_template.py",
                    "--review-csv",
                    report_dir / "residual_review_annotated.csv",
                    "--events-csv",
                    report_dir / "events.csv",
                    "--release-set-csv",
                    report_dir / "release_set.csv",
                    "--out-csv",
                    report_dir / "residual_review_annotations_template.csv",
                    "--out-md",
                    report_dir / "residual_review_guide.md",
                ),
            )
        )

    if not args.skip_sensitivity:
        commands.append(
            (
                "pgd_sensitivity",
                script_command("run_pgd_sensitivity.py", "--export-root", args.export_root, "--out-dir", sensitivity_dir),
            )
        )

    commands.append(
        (
            "pgd_interpretation",
            script_command(
                "build_pgd_interpretation_report.py",
                "--report-dir",
                report_dir,
                "--sensitivity-dir",
                sensitivity_dir,
                "--out-json",
                report_dir / "pgd_interpretation.json",
                "--out-md",
                report_dir / "pgd_interpretation.md",
            ),
        )
    )
    if not args.skip_release_package:
        commands.append(
            (
                "pgd_release_package",
                script_command(
                    "build_pgd_release_package.py",
                    "--report-dir",
                    report_dir,
                    "--sensitivity-dir",
                    sensitivity_dir,
                    "--out-dir",
                    args.release_dir,
                ),
            )
        )

    if not args.skip_release_review:
        commands.append(
            (
                "release_review_dashboard",
                script_command("build_residual_review_dashboard.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "release_review_decision_report",
                script_command("build_residual_review_decision_report.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "reviewed_release_set",
                script_command("build_reviewed_release_set.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "residual_review_worklist",
                script_command("build_residual_review_worklist.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "release_blocking_review_starter",
                script_command("build_release_blocking_review_starter.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_release_readiness",
                script_command("build_pgd_release_readiness_report.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_formula_test_matrix",
                script_command("build_pgd_formula_test_matrix.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_release_blocker_analysis",
                script_command("build_pgd_release_blocker_analysis.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_release_blocker_decision_guide",
                script_command("build_pgd_release_blocker_decision_guide.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_recommended_formula_release_status",
                script_command("build_pgd_recommended_formula_release_status.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_baseline_narrative_handoff",
                script_command("build_pgd_baseline_narrative_handoff.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_baseline_science_narrative",
                script_command("build_pgd_baseline_science_narrative.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_comparison_formula_review_packet_summary",
                script_command("build_pgd_comparison_formula_review_packet_summary.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_review_briefing",
                script_command("build_pgd_review_briefing.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_release_readme",
                script_command("build_pgd_release_readme.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_release_blocker_review_prompt",
                script_command("build_pgd_release_blocker_review_prompt.py", "--release-dir", args.release_dir),
            )
        )
        commands.append(
            (
                "pgd_external_review_handoff",
                script_command("build_pgd_external_review_handoff.py", "--release-dir", args.release_dir),
            )
        )
    return commands


def stage_record(stage: str, command: list[str], result: Any) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "OK" if int(result.returncode) == 0 else "FAILED",
        "returncode": int(result.returncode),
        "command": command,
        "stdout": getattr(result, "stdout", "") or "",
        "stderr": getattr(result, "stderr", "") or "",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_bundle_summary_path(args: argparse.Namespace) -> Path:
    return args.report_dir / "pgd_science_bundle_summary.json"


def write_bundle_summary(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    write_json(args.out_json, payload)
    default_path = default_bundle_summary_path(args)
    if args.out_json != default_path:
        write_json(default_path, payload)


def base_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "status": "OK",
        "started_at": utc_now(),
        "completed_at": "",
        "export_root": str(args.export_root),
        "report_dir": str(args.report_dir),
        "sensitivity_dir": str(args.sensitivity_dir),
        "release_dir": str(args.release_dir),
        "annotations": "" if selected_annotations(args) is None else str(selected_annotations(args)),
        "starter_annotations": "" if selected_starter_annotations(args) is None else str(selected_starter_annotations(args)),
        "skip_report": bool(args.skip_report),
        "skip_sensitivity": bool(args.skip_sensitivity),
        "skip_template": bool(args.skip_template),
        "skip_release_package": bool(args.skip_release_package),
        "skip_release_review": bool(args.skip_release_review),
        "outputs": output_paths(args),
        "stages": [],
    }


def run_bundle(args: argparse.Namespace) -> dict[str, Any]:
    if args.out_json is None:
        args.out_json = args.report_dir / "pgd_science_bundle_summary.json"
    payload = base_payload(args)
    for stage, command in stage_commands(args):
        print(f"[pgd-bundle] {stage}: {' '.join(command)}", file=sys.stderr)
        result = run_command(command)
        record = stage_record(stage, command, result)
        payload["stages"].append(record)
        if record["returncode"] != 0:
            payload["status"] = "FAILED"
            payload["failed_stage"] = stage
            payload["completed_at"] = utc_now()
            write_bundle_summary(args, payload)
            return payload
        write_bundle_summary(args, payload)
    payload["completed_at"] = utc_now()
    write_bundle_summary(args, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_bundle(args)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "stage_count": len(payload["stages"]),
                "out_json": str(args.out_json),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
