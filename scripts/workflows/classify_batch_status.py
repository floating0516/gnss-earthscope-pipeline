#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "scripts" / "summaries" / "validate_normalized_export.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("validate_normalized_export", VALIDATOR_PATH)
validate_normalized_export = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(validate_normalized_export)

APPENDED_FIELDS = ["final_status", "failure_class", "next_action", "latest_workflow"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify batch event status from workflow runs and normalized exports.")
    parser.add_argument("--batch", type=Path, required=True, help="Input batch CSV")
    parser.add_argument("--runs", type=Path, required=True, help="Workflow runs root")
    parser.add_argument("--export-root", type=Path, required=True, help="Normalized export root")
    parser.add_argument("--out", type=Path, required=True, help="Output classified CSV")
    return parser.parse_args(argv)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def workflow_summary_paths(runs_root: Path, event_id: str) -> list[Path]:
    return sorted((runs_root / event_id).glob("workflow-*/reports/workflow-summary.json"))


def latest_workflow_path(summary_path: Path | None) -> str:
    if summary_path is None:
        return ""
    return str(summary_path.parents[1])


def status_value(summary: dict[str, Any], key: str) -> str:
    status = summary.get("status")
    if not isinstance(status, dict):
        return ""
    return str(status.get(key) or "").strip()


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


def export_is_valid(export_root: Path, event_id: str) -> bool:
    report = validate_normalized_export.validate_export(export_root, event_id=event_id)
    return report.get("status") == "OK" and int(report.get("event_count") or 0) > 0


def result(final_status: str, failure_class: str, next_action: str) -> dict[str, str]:
    return {
        "final_status": final_status,
        "failure_class": failure_class,
        "next_action": next_action,
    }


def classify_event(row: dict[str, str], runs_root: Path, export_root: Path) -> dict[str, str]:
    event_id = row.get("event_id", "").strip()
    if event_id and export_is_valid(export_root, event_id):
        return {**result("OK", "", "DONE"), "latest_workflow": ""}

    summaries = workflow_summary_paths(runs_root, event_id) if event_id else []
    latest_summary_path = summaries[-1] if summaries else None
    latest_summary = load_json(latest_summary_path) if latest_summary_path else {}
    latest_workflow = latest_workflow_path(latest_summary_path)
    timeout_count = sum(1 for path in summaries if summary_is_timeout(load_json(path)))
    batch_status = (row.get("status") or "").strip().upper()

    if timeout_count >= 3:
        classified = result("ABANDONED_REPEATED_TIMEOUT", "TIMEOUT", "REVIEW_OR_ABANDON")
    elif timeout_count > 0 or batch_status == "TIMEOUT":
        classified = result("RETRY_PROCESS", "TIMEOUT", "RERUN_PROCESS")
    else:
        download = status_value(latest_summary, "download")
        obs_validation = status_value(latest_summary, "obs_validation")
        process = status_value(latest_summary, "process")
        quality = status_value(latest_summary, "quality")
        normalized = status_value(latest_summary, "normalized") or status_value(latest_summary, "normalize")
        normalized_validation = status_value(latest_summary, "normalized_validation")
        plot = status_value(latest_summary, "plot")
        obs_files = count_value(latest_summary, "obs_files")
        kin_files = count_value(latest_summary, "kin_files")

        if normalized_validation == "FAIL":
            classified = result("RETRY_NORMALIZE", "NORMALIZED_VALIDATION_FAIL", "RERUN_NORMALIZE")
        elif normalized == "OK" and plot == "FAIL":
            classified = result("RETRY_PLOT", "PLOT_FAIL", "RERUN_PLOT")
        elif quality == "FAIL" or normalized == "SKIPPED_QUALITY_FAIL":
            classified = result("CLASSIFIED_QUALITY_FAIL", "QUALITY_FAIL", "REVIEW_QUALITY")
        elif obs_validation == "FAIL" or process == "BLOCKED_OBS_VALIDATION" or (download in {"OK", "REUSED"} and obs_files == 0):
            classified = result("CLASSIFIED_NO_OBS", "NO_OBS", "CLASSIFY_NO_OBS")
        elif normalized == "SKIPPED_NO_KIN" or (process in {"OK", "FAIL"} and kin_files == 0):
            classified = result("CLASSIFIED_NO_KIN", "NO_KIN", "CLASSIFY_NO_KIN")
        elif download == "FAIL":
            classified = result("RETRY_DOWNLOAD", "DOWNLOAD_FAIL", "RERUN_DOWNLOAD")
        elif process == "FAIL":
            classified = result("RETRY_PROCESS", "PROCESS_FAIL", "RERUN_PROCESS")
        elif normalized == "FAIL":
            classified = result("RETRY_NORMALIZE", "NORMALIZE_FAIL", "RERUN_NORMALIZE")
        else:
            classified = result("UNKNOWN_REVIEW", "UNKNOWN", "REVIEW")

    return {**classified, "latest_workflow": latest_workflow}


def classify_batch(batch: Path, runs_root: Path, export_root: Path) -> list[dict[str, str]]:
    rows = read_csv_rows(batch)
    classified_rows = []
    for row in rows:
        classified = dict(row)
        classified.update(classify_event(row, runs_root, export_root))
        classified_rows.append(classified)
    return classified_rows


def output_fieldnames(input_fieldnames: list[str]) -> list[str]:
    fields = list(input_fieldnames)
    for field in APPENDED_FIELDS:
        if field not in fields:
            fields.append(field)
    return fields


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rows = classify_batch(args.batch, args.runs, args.export_root)
    with args.batch.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = output_fieldnames(reader.fieldnames or [])
    write_csv_rows(args.out, rows, fieldnames)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["final_status"]] = counts.get(row["final_status"], 0) + 1
    print(f"wrote classified batch: rows={len(rows)} statuses={counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
