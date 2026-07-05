#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

FIELDS = [
    "event_id",
    "workflow_count",
    "latest_workflow",
    "latest_status",
    "export_status",
    "quality_status",
    "kin_count",
    "station_count",
    "plot_status",
    "failure_class",
    "next_action",
]
REQUIRED_PACKAGE_FILES = ["event.json", "stations.csv", "waveforms.csv.gz", "provenance.json"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a run ledger from workflow summaries and normalized exports.")
    parser.add_argument("--runs", type=Path, required=True, help="Workflow runs root.")
    parser.add_argument("--export-root", type=Path, required=True, help="Normalized export root.")
    parser.add_argument("--out", type=Path, required=True, help="Output TSV path.")
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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


def workflow_summary_paths(runs_root: Path, event_id: str) -> list[Path]:
    return sorted((runs_root / event_id).glob("workflow-*/reports/workflow-summary.json"))


def latest_summary(paths: list[Path]) -> dict[str, Any]:
    return load_json(paths[-1]) if paths else {}


def status_value(summary: dict[str, Any], key: str) -> str:
    status = summary.get("status")
    if not isinstance(status, dict):
        return ""
    return first_text(status.get(key))


def count_value(summary: dict[str, Any], key: str) -> str:
    counts = summary.get("counts")
    if not isinstance(counts, dict):
        return ""
    return first_text(counts.get(key))


def count_int(summary: dict[str, Any], key: str) -> int:
    try:
        return int(count_value(summary, key) or 0)
    except ValueError:
        return 0


def summary_is_timeout(summary: dict[str, Any]) -> bool:
    status = summary.get("status")
    if not isinstance(status, dict):
        return False
    return any(str(value).upper() == "TIMEOUT" for value in status.values())


def event_id_from_package(package_dir: Path) -> str:
    event = load_json(package_dir / "event.json")
    provenance = load_json(package_dir / "provenance.json")
    return first_text(event.get("event_id"), event.get("usgs_event_id"), provenance.get("event_id"), package_dir.name)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def build_export_index(export_root: Path) -> dict[str, dict[str, str]]:
    if not export_root.exists():
        return {}
    indexed: dict[str, dict[str, str]] = {}
    for path in sorted(export_root.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        event_id = event_id_from_package(path)
        if not event_id:
            continue
        missing = [name for name in REQUIRED_PACKAGE_FILES if not (path / name).exists()]
        indexed[event_id] = {
            "event_dir": path.name,
            "export_status": "OK" if not missing else "INVALID",
            "station_count": "" if missing else str(len(read_csv_rows(path / "stations.csv"))),
        }
    return indexed


def run_event_ids(runs_root: Path) -> set[str]:
    if not runs_root.exists():
        return set()
    event_ids = set()
    for path in sorted(runs_root.iterdir()):
        if path.is_dir() and list(path.glob("workflow-*/reports/workflow-summary.json")):
            event_ids.add(path.name)
    return event_ids


def classify_from_summary(
    summaries: list[Path],
    summary: dict[str, Any],
    export_status: str,
) -> tuple[str, str, str]:
    if export_status == "OK":
        return "OK", "", "DONE"
    timeout_count = sum(1 for path in summaries if summary_is_timeout(load_json(path)))
    if timeout_count >= 3:
        return "ABANDONED_REPEATED_TIMEOUT", "TIMEOUT", "REVIEW_OR_ABANDON"
    if timeout_count > 0:
        return "RETRY_PROCESS", "TIMEOUT", "RERUN_PROCESS"

    download = status_value(summary, "download")
    obs_validation = status_value(summary, "obs_validation")
    process = status_value(summary, "process")
    quality = status_value(summary, "quality")
    normalized = status_value(summary, "normalized") or status_value(summary, "normalize")
    normalized_validation = status_value(summary, "normalized_validation")
    plot = status_value(summary, "plot")
    obs_files = count_int(summary, "obs_files")
    kin_files = count_int(summary, "kin_files")

    if normalized_validation == "FAIL":
        return "RETRY_NORMALIZE", "NORMALIZED_VALIDATION_FAIL", "RERUN_NORMALIZE"
    if normalized == "OK" and plot == "FAIL":
        return "RETRY_PLOT", "PLOT_FAIL", "RERUN_PLOT"
    if quality == "FAIL" or normalized == "SKIPPED_QUALITY_FAIL":
        return "CLASSIFIED_QUALITY_FAIL", "QUALITY_FAIL", "REVIEW_QUALITY"
    if obs_validation == "FAIL" or process == "BLOCKED_OBS_VALIDATION" or (download in {"OK", "REUSED"} and obs_files == 0):
        return "CLASSIFIED_NO_OBS", "NO_OBS", "CLASSIFY_NO_OBS"
    if normalized == "SKIPPED_NO_KIN" or (process in {"OK", "FAIL"} and kin_files == 0):
        return "CLASSIFIED_NO_KIN", "NO_KIN", "CLASSIFY_NO_KIN"
    if download == "FAIL":
        return "RETRY_DOWNLOAD", "DOWNLOAD_FAIL", "RERUN_DOWNLOAD"
    if process == "FAIL":
        return "RETRY_PROCESS", "PROCESS_FAIL", "RERUN_PROCESS"
    if normalized == "FAIL":
        return "RETRY_NORMALIZE", "NORMALIZE_FAIL", "RERUN_NORMALIZE"
    return "UNKNOWN_REVIEW", "UNKNOWN", "REVIEW"


def station_count(summary: dict[str, Any], export_info: dict[str, str]) -> str:
    return first_text(export_info.get("station_count"), count_value(summary, "normalized_stations"))


def build_row(event_id: str, runs_root: Path, export_index: dict[str, dict[str, str]]) -> dict[str, str]:
    summaries = workflow_summary_paths(runs_root, event_id)
    summary = latest_summary(summaries)
    export_info = export_index.get(event_id, {})
    current_export_status = first_text(export_info.get("export_status"), "MISSING")
    latest_status, failure_class, next_action = classify_from_summary(summaries, summary, current_export_status)
    return {
        "event_id": event_id,
        "workflow_count": str(len(summaries)),
        "latest_workflow": str(summaries[-1].parents[1]) if summaries else "",
        "latest_status": latest_status,
        "export_status": current_export_status,
        "quality_status": status_value(summary, "quality"),
        "kin_count": count_value(summary, "kin_files"),
        "station_count": station_count(summary, export_info),
        "plot_status": status_value(summary, "plot"),
        "failure_class": failure_class,
        "next_action": next_action,
    }


def build_rows(runs_root: Path, export_root: Path) -> list[dict[str, str]]:
    export_index = build_export_index(export_root)
    event_ids = run_event_ids(runs_root) | set(export_index)
    return [build_row(event_id, runs_root, export_index) for event_id in sorted(event_ids)]


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = build_rows(args.runs, args.export_root)
    write_rows(args.out, rows)
    print(f"wrote run ledger: rows={len(rows)} out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
