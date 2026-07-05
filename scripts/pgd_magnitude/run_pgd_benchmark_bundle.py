#!/usr/bin/env python3
"""Run the lightweight PGD benchmark package workflow."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pgd_contract
import evaluate_pgd_magnitude as pgd


DEFAULT_EXPORT_ROOT = Path("exports/normalized-ok-stations-us-nz")
DEFAULT_OUT_DIR = Path("reports/pgd_magnitude/benchmark/latest")
BENCHMARK_FILES = {
    "events": "events.csv",
    "stations": "stations.csv",
    "formula_errors": "formula_errors.csv",
    "formula_summary": "formula_summary.csv",
}
FILTER_BENCHMARK_DIRNAME = "filter_benchmark"
INTERPRETATION_DIRNAME = "interpretation"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Unknown PGD report options are passed through to run_pgd_report.py.",
    )
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT, help="Normalized export root.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Compact benchmark package directory.")
    parser.add_argument("--work-dir", type=Path, default=None, help="Intermediate full PGD report directory.")
    parser.add_argument("--out-json", type=Path, default=None, help="Benchmark summary JSON. Defaults to <out-dir>/summary.json.")
    parser.add_argument(
        "--countries",
        nargs="*",
        default=None,
        help="Countries to include. Defaults to all countries discovered in complete normalized event packages.",
    )
    args, passthrough = parser.parse_known_args(argv)
    args.pgd_report_args = passthrough
    return args


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def script_command(script_name: str, *args: object) -> list[str]:
    return [sys.executable, str(SCRIPT_DIR / script_name), *(str(arg) for arg in args)]


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def complete_event_package_countries(export_root: Path) -> list[str]:
    countries: set[str] = set()
    for event_json in sorted(export_root.glob("*/event.json")):
        event_dir = event_json.parent
        if not (event_dir / "stations.csv").exists() or not (event_dir / "waveforms.csv.gz").exists():
            continue
        country = str(pgd.event_country_value(read_json(event_json), event_dir) or "").strip()
        if country:
            countries.add(country)
    return sorted(countries)


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def resolve_country_scope(args: argparse.Namespace) -> tuple[str, list[str]]:
    if args.countries is not None:
        countries = ordered_unique([str(country) for country in args.countries])
        if not countries:
            raise ValueError("--countries was provided but no non-empty country names were supplied")
        return "explicit", countries
    countries = complete_event_package_countries(args.export_root)
    if not countries:
        raise ValueError(f"No countries discovered in complete normalized event packages under {args.export_root}")
    return "all_normalized_export_countries", countries


def csv_station_aggregation_values(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if "station_aggregation" not in (reader.fieldnames or []):
            return set()
        return {str(row.get("station_aggregation") or "").strip() for row in reader if str(row.get("station_aggregation") or "").strip()}


def assert_median_contract(report_dir: Path, report_summary: dict[str, Any]) -> None:
    values: set[str] = set()
    parameters = report_summary.get("parameters", {})
    recommendation = report_summary.get("formula_recommendation", {})
    if isinstance(parameters, dict) and parameters.get("station_aggregation"):
        values.add(str(parameters["station_aggregation"]))
    if isinstance(recommendation, dict) and recommendation.get("station_aggregation"):
        values.add(str(recommendation["station_aggregation"]))
    for name in ["events.csv", "stations.csv", "formula_comparison.csv"]:
        values.update(csv_station_aggregation_values(report_dir / name))
    bad_values = sorted(value for value in values if not pgd_contract.is_median_station_aggregation(value))
    if bad_values:
        raise ValueError(f"PGD benchmark requires station_aggregation=median; found {bad_values}")


def remove_stale_benchmark_outputs(out_dir: Path) -> None:
    for relative in [*BENCHMARK_FILES.values(), "summary.json", "README.md"]:
        path = out_dir / relative
        if path.is_file():
            path.unlink()
    for stale in out_dir.glob("*method*"):
        if stale.is_file():
            stale.unlink()
    filter_dir = out_dir / FILTER_BENCHMARK_DIRNAME
    if filter_dir.is_dir():
        shutil.rmtree(filter_dir)


def copy_required_file(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing PGD report product: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def output_paths(out_dir: Path) -> dict[str, str]:
    return {key: str(out_dir / filename) for key, filename in BENCHMARK_FILES.items()}


def filter_benchmark_paths(out_dir: Path) -> dict[str, str]:
    filter_dir = out_dir / FILTER_BENCHMARK_DIRNAME
    return {
        "root": str(filter_dir),
        "scenario_formula_summary": str(filter_dir / "scenario_formula_summary.csv"),
        "scenario_event_errors": str(filter_dir / "scenario_event_errors.csv"),
        "scenario_exclusions": str(filter_dir / "scenario_exclusions.csv"),
        "summary": str(filter_dir / "summary.json"),
        "readme": str(filter_dir / "README.md"),
    }


def benchmark_interpretation_paths(out_dir: Path) -> dict[str, str]:
    interpretation_dir = out_dir / FILTER_BENCHMARK_DIRNAME / INTERPRETATION_DIRNAME
    return {
        "root": str(interpretation_dir),
        "markdown": str(interpretation_dir / "pgd_benchmark_interpretation.md"),
        "json": str(interpretation_dir / "pgd_benchmark_interpretation.json"),
        "figures_dir": str(interpretation_dir / "figures"),
    }


def write_readme(path: Path, payload: dict[str, Any]) -> None:
    outputs = payload["benchmark_outputs"]
    filter_outputs = payload.get("filter_benchmark", {}) if isinstance(payload.get("filter_benchmark"), dict) else {}
    interpretation_outputs = payload.get("benchmark_interpretation", {}) if isinstance(payload.get("benchmark_interpretation"), dict) else {}
    country_scope = payload.get("country_scope", {}) if isinstance(payload.get("country_scope"), dict) else {}
    country_scope_label = "all normalized export countries" if country_scope.get("mode") == "all_normalized_export_countries" else str(country_scope.get("mode") or "")
    countries = country_scope.get("countries", [])
    lines = [
        "# PGD Benchmark Package",
        "",
        "This is the compact, four-stage PGD benchmark package for formula-baseline and later ML comparison work.",
        "",
        "## Four-Stage Workflow",
        "",
        "1. Compute PGD station/event features from normalized waveforms.",
        "2. Estimate event magnitude with the three PGD formulas.",
        "3. Compare each formula estimate to the catalog magnitude and record residuals.",
        "4. Package the benchmark tables for downstream analysis.",
        "",
        "The package uses one station aggregation method: `median`. The labels `melgar_2015`, `crowell_2016_gfast`, and `ruhl_2019` are formulas/scaling laws, not station aggregation methods.",
        "",
        "## Files",
        "",
        f"- `events.csv`: event/formula rows from the PGD report.",
        f"- `stations.csv`: station/formula PGD feature rows.",
        f"- `formula_errors.csv`: formula-level event residual rows copied from `events.csv` for explicit benchmark use.",
        f"- `formula_summary.csv`: overall per-formula error metrics.",
        f"- `summary.json`: machine-readable benchmark summary.",
        f"- `filter_benchmark/`: station-level filter scenarios for amplitude, SNR, distance, QUALITY, and STRICT gates.",
        f"- `filter_benchmark/interpretation/`: PGD Benchmark Interpretation Markdown, JSON, and SVG figures.",
        "",
        "## Current Counts",
        "",
        f"- Status: `{payload.get('status', '')}`",
        f"- Unique events: {payload.get('counts', {}).get('unique_events', 0)}",
        f"- Formula error rows: {payload.get('counts', {}).get('formula_error_rows', 0)}",
        f"- Station rows: {payload.get('counts', {}).get('station_rows', 0)}",
        f"- Recommended baseline formula: `{payload.get('recommended_formula', '')}`",
        f"- Country scope: {country_scope_label}",
        f"- Countries: {', '.join(countries) if isinstance(countries, list) else ''}",
        "",
        "## Output Paths",
        "",
        *[f"- `{key}`: `{value}`" for key, value in outputs.items()],
        "",
        "## Filter Benchmark Paths",
        "",
        *[f"- `{key}`: `{value}`" for key, value in filter_outputs.items() if key != "summary_payload"],
        "",
        "## PGD Benchmark Interpretation Paths",
        "",
        *[f"- `{key}`: `{value}`" for key, value in interpretation_outputs.items() if key != "summary_payload"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_success_payload(
    *,
    args: argparse.Namespace,
    work_dir: Path,
    out_json: Path,
    report_summary: dict[str, Any],
    stages: list[dict[str, Any]],
) -> dict[str, Any]:
    report_counts = report_summary.get("counts", {}) if isinstance(report_summary.get("counts"), dict) else {}
    recommendation = report_summary.get("formula_recommendation", {}) if isinstance(report_summary.get("formula_recommendation"), dict) else {}
    filter_paths = filter_benchmark_paths(args.out_dir)
    interpretation_paths = benchmark_interpretation_paths(args.out_dir)
    filter_summary_path = Path(filter_paths["summary"])
    interpretation_summary_path = Path(interpretation_paths["json"])
    return {
        "schema_version": "pgd-benchmark-bundle/v1",
        "workflow": "pgd_benchmark_bundle",
        "status": "OK",
        "created_at": utc_now(),
        "export_root": str(args.export_root),
        "out_dir": str(args.out_dir),
        "work_dir": str(work_dir),
        "out_json": str(out_json),
        "station_aggregation": pgd_contract.STATION_AGGREGATION_METHOD,
        "formulas": list(pgd_contract.FORMULA_NAMES),
        "country_scope": {
            "mode": str(getattr(args, "country_scope_mode", "")),
            "countries": list(getattr(args, "resolved_countries", [])),
        },
        "recommended_formula": str(recommendation.get("recommended_formula") or ""),
        "stage_count": len(stages),
        "stages": stages,
        "counts": {
            "unique_events": int(report_counts.get("unique_events") or 0),
            "formula_error_rows": int(report_counts.get("event_rows") or 0),
            "station_rows": int(report_counts.get("station_rows") or 0),
            "formula_summary_rows": int(report_counts.get("formula_comparison_rows") or 0),
        },
        "benchmark_outputs": output_paths(args.out_dir),
        "filter_benchmark": {
            **filter_paths,
            "summary_payload": read_json(filter_summary_path) if filter_summary_path.exists() else {},
        },
        "benchmark_interpretation": {
            **interpretation_paths,
            "summary_payload": read_json(interpretation_summary_path) if interpretation_summary_path.exists() else {},
        },
        "report_summary": report_summary,
    }


def build_failure_payload(
    *,
    args: argparse.Namespace,
    work_dir: Path,
    out_json: Path,
    stages: list[dict[str, Any]],
    failed_stage: str,
) -> dict[str, Any]:
    return {
        "schema_version": "pgd-benchmark-bundle/v1",
        "workflow": "pgd_benchmark_bundle",
        "status": "FAILED",
        "created_at": utc_now(),
        "export_root": str(args.export_root),
        "out_dir": str(args.out_dir),
        "work_dir": str(work_dir),
        "out_json": str(out_json),
        "failed_stage": failed_stage,
        "country_scope": {
            "mode": str(getattr(args, "country_scope_mode", "")),
            "countries": list(getattr(args, "resolved_countries", [])),
        },
        "stage_count": len(stages),
        "stages": stages,
        "benchmark_outputs": output_paths(args.out_dir),
        "filter_benchmark": filter_benchmark_paths(args.out_dir),
        "benchmark_interpretation": benchmark_interpretation_paths(args.out_dir),
    }


def copy_benchmark_products(report_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    remove_stale_benchmark_outputs(out_dir)
    copy_required_file(report_dir / "events.csv", out_dir / "events.csv")
    copy_required_file(report_dir / "events.csv", out_dir / "formula_errors.csv")
    copy_required_file(report_dir / "stations.csv", out_dir / "stations.csv")
    copy_required_file(report_dir / "formula_comparison.csv", out_dir / "formula_summary.csv")


def run_stage(stage_name: str, command: list[str]) -> dict[str, Any]:
    result = run_command(command)
    return {
        "stage": stage_name,
        "command": command,
        "returncode": result.returncode,
        "status": "OK" if result.returncode == 0 else "FAILED",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_bundle(args: argparse.Namespace, work_dir: Path, out_json: Path) -> int:
    try:
        args.country_scope_mode, args.resolved_countries = resolve_country_scope(args)
    except Exception as exc:  # noqa: BLE001
        stage = {
            "stage": "country_scope",
            "command": [],
            "returncode": 1,
            "status": "FAILED",
            "stdout": "",
            "stderr": str(exc),
        }
        payload = build_failure_payload(args=args, work_dir=work_dir, out_json=out_json, stages=[stage], failed_stage="country_scope")
        write_json(out_json, payload)
        print(json.dumps({"status": payload["status"], "failed_stage": payload["failed_stage"], "out_json": str(out_json)}, indent=2))
        return 1

    command = script_command(
        "run_pgd_report.py",
        "--export-root",
        args.export_root,
        "--out-dir",
        work_dir,
        "--countries",
        *args.resolved_countries,
        *args.pgd_report_args,
    )
    stages = [run_stage("pgd_report", command)]
    if stages[-1]["returncode"] != 0:
        payload = build_failure_payload(args=args, work_dir=work_dir, out_json=out_json, stages=stages, failed_stage="pgd_report")
        write_json(out_json, payload)
        print(json.dumps({"status": payload["status"], "failed_stage": payload["failed_stage"], "out_json": str(out_json)}, indent=2))
        return int(stages[-1]["returncode"])

    try:
        report_summary = read_json(work_dir / "summary.json")
        assert_median_contract(work_dir, report_summary)
        copy_benchmark_products(work_dir, args.out_dir)
    except Exception as exc:  # noqa: BLE001
        package_stage = {
            "stage": "benchmark_package",
            "command": [],
            "returncode": 1,
            "status": "FAILED",
            "stdout": "",
            "stderr": str(exc),
        }
        payload = build_failure_payload(args=args, work_dir=work_dir, out_json=out_json, stages=[*stages, package_stage], failed_stage="benchmark_package")
        write_json(out_json, payload)
        print(json.dumps({"status": payload["status"], "failed_stage": payload["failed_stage"], "out_json": str(out_json)}, indent=2))
        return 1

    filter_dir = args.out_dir / FILTER_BENCHMARK_DIRNAME
    filter_command = script_command("build_pgd_filter_benchmark.py", "--benchmark-dir", args.out_dir, "--out-dir", filter_dir)
    stages.append(run_stage("filter_benchmark", filter_command))
    if stages[-1]["returncode"] != 0:
        payload = build_failure_payload(args=args, work_dir=work_dir, out_json=out_json, stages=stages, failed_stage="filter_benchmark")
        write_json(out_json, payload)
        print(json.dumps({"status": payload["status"], "failed_stage": payload["failed_stage"], "out_json": str(out_json)}, indent=2))
        return int(stages[-1]["returncode"])

    interpretation_dir = filter_dir / INTERPRETATION_DIRNAME
    interpretation_command = script_command("build_pgd_benchmark_interpretation.py", "--filter-dir", filter_dir, "--out-dir", interpretation_dir)
    stages.append(run_stage("benchmark_interpretation", interpretation_command))
    if stages[-1]["returncode"] != 0:
        payload = build_failure_payload(args=args, work_dir=work_dir, out_json=out_json, stages=stages, failed_stage="benchmark_interpretation")
        write_json(out_json, payload)
        print(json.dumps({"status": payload["status"], "failed_stage": payload["failed_stage"], "out_json": str(out_json)}, indent=2))
        return int(stages[-1]["returncode"])

    try:
        payload = build_success_payload(args=args, work_dir=work_dir, out_json=out_json, report_summary=report_summary, stages=stages)
        write_json(args.out_dir / "summary.json", payload)
        if out_json != args.out_dir / "summary.json":
            write_json(out_json, payload)
        write_readme(args.out_dir / "README.md", payload)
    except Exception as exc:  # noqa: BLE001
        summary_stage = {
            "stage": "benchmark_summary",
            "command": [],
            "returncode": 1,
            "status": "FAILED",
            "stdout": "",
            "stderr": str(exc),
        }
        payload = build_failure_payload(args=args, work_dir=work_dir, out_json=out_json, stages=[*stages, summary_stage], failed_stage="benchmark_summary")
        write_json(out_json, payload)
        print(json.dumps({"status": payload["status"], "failed_stage": payload["failed_stage"], "out_json": str(out_json)}, indent=2))
        return 1

    print(
        json.dumps(
            {
                "status": payload["status"],
                "unique_events": payload["counts"]["unique_events"],
                "formula_error_rows": payload["counts"]["formula_error_rows"],
                "stage_count": payload["stage_count"],
                "out_dir": str(args.out_dir),
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_json = args.out_json or args.out_dir / "summary.json"
    if args.work_dir is not None:
        return run_bundle(args, args.work_dir, out_json)
    with tempfile.TemporaryDirectory(prefix="pgd-benchmark-report-") as tmp:
        return run_bundle(args, Path(tmp), out_json)


if __name__ == "__main__":
    raise SystemExit(main())
