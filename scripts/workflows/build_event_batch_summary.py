#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "scripts" / "summaries" / "validate_normalized_export.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("validate_normalized_export", VALIDATOR_PATH)
validate_normalized_export = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(validate_normalized_export)

REQUIRED_PACKAGE_FILES = ["event.json", "stations.csv", "waveforms.csv.gz", "provenance.json"]

FIELDS = [
    "event_id",
    "event_time",
    "batch_status",
    "download_status",
    "obs_validation_status",
    "process_status",
    "plot_status",
    "quality_status",
    "quality_ok_stations",
    "quality_warn_stations",
    "quality_fail_stations",
    "cleanup_status",
    "pride_cleanup_status",
    "obs_cleanup_status",
    "normalized_status",
    "normalized_station_count",
    "normalized_waveform_rows",
    "normalized_event_grade",
    "waveform_rows",
    "event_grade",
    "normalized_event_dir",
    "normalized_exists",
    "export_package_status",
    "export_valid",
    "requested_stations",
    "obs_files",
    "kin_files",
    "kin_count",
    "plot_files",
    "duration_seconds",
    "workflow_dir",
    "summary_json",
    "latest_failure_reason",
    "suggested_next_action",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an EarthScope event batch summary TSV.")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--pipeline-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, default=None)
    return parser.parse_args(argv)


def portable(path_text: str, pipeline_root: Path) -> str:
    if not path_text:
        return ""
    if path_text == "@ROOT@" or path_text.startswith("@ROOT@/"):
        return path_text
    try:
        rel = Path(path_text).resolve().relative_to(pipeline_root.resolve())
    except ValueError:
        return path_text
    return "@ROOT@" if str(rel) == "." else f"@ROOT@/{rel.as_posix()}"


def resolve_portable(path_text: str, pipeline_root: Path) -> Path:
    if not path_text:
        return Path()
    if path_text == "@ROOT@":
        return pipeline_root
    if path_text.startswith("@ROOT@/"):
        return pipeline_root / path_text[len("@ROOT@/") :]
    path = Path(path_text)
    return path if path.is_absolute() else pipeline_root / path


def export_package_status(path_text: str, pipeline_root: Path) -> str:
    if not path_text:
        return ""
    path = resolve_portable(path_text, pipeline_root)
    missing = [name for name in REQUIRED_PACKAGE_FILES if not (path / name).exists()]
    return "COMPLETE" if not missing else "MISSING_" + ",".join(missing)


def summary_json_paths(run_root: Path, event_id: str) -> list[Path]:
    return sorted(run_root.glob(f"{event_id}/workflow-*/reports/workflow-summary.json"))


def latest_summary_json(run_root: Path, event_id: str) -> Path | None:
    matches = summary_json_paths(run_root, event_id)
    return matches[-1] if matches else None


def read_summary(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def status_value(summary: dict[str, Any], key: str) -> str:
    status = summary.get("status")
    if not isinstance(status, dict):
        return ""
    return first_text(status.get(key))


def count_value(summary: dict[str, Any], key: str) -> int:
    counts = summary.get("counts")
    if not isinstance(counts, dict):
        return 0
    try:
        return int(counts.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def summary_is_timeout(summary: dict[str, Any]) -> bool:
    status = summary.get("status")
    if not isinstance(status, dict):
        return False
    return any(str(value).upper() == "TIMEOUT" for value in status.values())


def yes_no(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "ok", "valid"}:
        return "yes"
    if text in {"0", "false", "no", "invalid"}:
        return "no"
    return ""


def workflow_export_valid(summary: dict[str, Any]) -> str:
    status = summary.get("status")
    status = status if isinstance(status, dict) else {}
    for value in [
        summary.get("normalized_export_valid"),
        summary.get("export_valid"),
        status.get("normalized_export_valid"),
        status.get("export_valid"),
    ]:
        result = yes_no(value)
        if result:
            return result
    return ""


def validate_event_export(export_root: Path, event_id: str) -> dict[str, Any]:
    if not event_id:
        return {}
    try:
        report = validate_normalized_export.validate_export(export_root, event_id=event_id)
    except Exception as exc:  # pragma: no cover - defensive summary generation
        return {
            "status": "INVALID",
            "event_count": 0,
            "station_count": 0,
            "waveform_rows": 0,
            "errors": [{"code": "VALIDATOR_ERROR", "message": str(exc)}],
            "packages": [],
        }
    return report if isinstance(report, dict) else {}


def export_valid_status(summary: dict[str, Any], validation_report: dict[str, Any]) -> str:
    from_workflow = workflow_export_valid(summary)
    if from_workflow:
        return from_workflow
    if not validation_report:
        return ""
    if validation_report.get("status") == "OK" and int(validation_report.get("event_count") or 0) > 0:
        return "yes"
    return "no"


def validation_package_dir(export_root: Path, validation_report: dict[str, Any]) -> str:
    packages = validation_report.get("packages")
    if not isinstance(packages, list) or not packages:
        return ""
    event_dir = first_text(packages[0].get("event_dir") if isinstance(packages[0], dict) else "")
    return str(export_root / event_dir) if event_dir else ""


def validation_count(validation_report: dict[str, Any], key: str) -> str:
    value = validation_report.get(key)
    if value is None:
        return ""
    return str(value)


def normalized_exists_status(path_text: str, pipeline_root: Path) -> str:
    if not path_text:
        return ""
    return "yes" if resolve_portable(path_text, pipeline_root).exists() else "no"


def classify_summary(
    batch_row: dict[str, str],
    summary: dict[str, Any],
    timeout_count: int,
    export_valid: str,
) -> tuple[str, str]:
    if export_valid == "yes":
        return "", "DONE"
    batch_status = (batch_row.get("status") or "").strip().upper()
    if timeout_count >= 3:
        return "TIMEOUT", "REVIEW_OR_ABANDON"
    if timeout_count > 0 or batch_status == "TIMEOUT":
        return "TIMEOUT", "RERUN_PROCESS"

    download = status_value(summary, "download")
    obs_validation = status_value(summary, "obs_validation")
    process = status_value(summary, "process")
    quality = status_value(summary, "quality")
    normalized = status_value(summary, "normalized") or status_value(summary, "normalize")
    plot = status_value(summary, "plot")
    obs_files = count_value(summary, "obs_files")
    kin_files = count_value(summary, "kin_files")

    if normalized == "OK" and plot == "FAIL":
        return "PLOT_FAIL", "RERUN_PLOT"
    if quality == "FAIL" or normalized == "SKIPPED_QUALITY_FAIL":
        return "QUALITY_FAIL", "REVIEW_QUALITY"
    if obs_validation == "FAIL" or process == "BLOCKED_OBS_VALIDATION" or (download in {"OK", "REUSED"} and obs_files == 0):
        return "NO_OBS", "CLASSIFY_NO_OBS"
    if normalized == "SKIPPED_NO_KIN" or (process in {"OK", "FAIL"} and kin_files == 0):
        return "NO_KIN", "CLASSIFY_NO_KIN"
    if download == "FAIL":
        return "DOWNLOAD_FAIL", "RERUN_DOWNLOAD"
    if process == "FAIL":
        return "PROCESS_FAIL", "RERUN_PROCESS"
    if normalized == "FAIL":
        return "NORMALIZE_FAIL", "RERUN_NORMALIZE"
    return "UNKNOWN", "REVIEW"


def latest_failure_reason(summary: dict[str, Any], failure_class: str) -> str:
    failure = summary.get("failure")
    failure = failure if isinstance(failure, dict) else {}
    code = first_text(summary.get("failure_code"), failure.get("code"))
    message = first_text(summary.get("failure_message"), failure.get("message"))
    if code and message:
        return f"{code}: {message}"
    if code:
        return code
    if failure_class == "UNKNOWN":
        return "UNKNOWN"
    return failure_class


def build_row(batch_row: dict[str, str], run_root: Path, pipeline_root: Path, export_root: Path) -> dict[str, Any]:
    event_id = (batch_row.get("event_id") or "").strip()
    summary_paths = summary_json_paths(run_root, event_id) if event_id else []
    latest_json = summary_paths[-1] if summary_paths else None
    summary = read_summary(latest_json)
    status = summary.get("status", {})
    counts = summary.get("counts", {})
    paths = summary.get("paths", {})
    quality = summary.get("quality", {}).get("summary", {})
    normalized_event_dir = paths.get("normalized_event_dir", "")
    validation_report = validate_event_export(export_root, event_id)
    if not normalized_event_dir:
        normalized_event_dir = validation_package_dir(export_root, validation_report)

    normalized_status = status.get("normalized", status.get("normalize", ""))
    export_valid = export_valid_status(summary, validation_report)
    timeout_count = sum(1 for path in summary_paths if summary_is_timeout(read_summary(path)))
    failure_class, suggested_next_action = classify_summary(batch_row, summary, timeout_count, export_valid)
    normalized_stations = first_text(counts.get("normalized_stations"), validation_count(validation_report, "station_count"))
    normalized_waveform_rows = first_text(counts.get("normalized_waveform_rows"), validation_count(validation_report, "waveform_rows"))
    normalized_event_grade = first_text(paths.get("normalized_event_grade"))
    kin_files = first_text(counts.get("kin_files"))

    return {
        "event_id": event_id,
        "event_time": (batch_row.get("event_time") or "").strip(),
        "batch_status": (batch_row.get("status") or "").strip(),
        "download_status": status.get("download", ""),
        "obs_validation_status": status.get("obs_validation", ""),
        "process_status": status.get("process", ""),
        "plot_status": status.get("plot", ""),
        "quality_status": status.get("quality", quality.get("status", "")),
        "quality_ok_stations": quality.get("ok_station_count", ""),
        "quality_warn_stations": quality.get("warn_station_count", ""),
        "quality_fail_stations": quality.get("fail_station_count", ""),
        "cleanup_status": status.get("cleanup", ""),
        "pride_cleanup_status": status.get("pride_cleanup", ""),
        "obs_cleanup_status": status.get("obs_cleanup", ""),
        "normalized_status": normalized_status,
        "normalized_station_count": normalized_stations,
        "normalized_waveform_rows": normalized_waveform_rows,
        "normalized_event_grade": normalized_event_grade,
        "waveform_rows": normalized_waveform_rows,
        "event_grade": normalized_event_grade,
        "normalized_event_dir": portable(normalized_event_dir, pipeline_root),
        "normalized_exists": normalized_exists_status(normalized_event_dir, pipeline_root),
        "export_package_status": export_package_status(normalized_event_dir, pipeline_root),
        "export_valid": export_valid,
        "requested_stations": counts.get("requested_stations", ""),
        "obs_files": counts.get("obs_files", ""),
        "kin_files": kin_files,
        "kin_count": kin_files,
        "plot_files": counts.get("plot_files", ""),
        "duration_seconds": summary.get("duration_seconds", ""),
        "workflow_dir": paths.get("workflow_dir", ""),
        "summary_json": portable(str(latest_json), pipeline_root) if latest_json else "",
        "latest_failure_reason": latest_failure_reason(summary, failure_class),
        "suggested_next_action": suggested_next_action,
    }


def build_rows(csv_path: Path, run_root: Path, pipeline_root: Path, export_root: Path) -> list[dict[str, Any]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return [build_row(row, run_root, pipeline_root, export_root) for row in csv.DictReader(handle)]


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    export_root = args.export_root or (args.pipeline_root / "exports" / "normalized-ok-stations-us-nz")
    rows = build_rows(args.csv, args.run_root, args.pipeline_root, export_root)
    write_summary(args.summary, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
