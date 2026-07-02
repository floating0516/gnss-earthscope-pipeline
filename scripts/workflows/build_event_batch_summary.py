#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


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
    "normalized_event_dir",
    "export_package_status",
    "requested_stations",
    "obs_files",
    "kin_files",
    "plot_files",
    "duration_seconds",
    "workflow_dir",
    "summary_json",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an EarthScope event batch summary TSV.")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--pipeline-root", type=Path, required=True)
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
    missing = [name for name in ["event.json", "stations.csv", "waveforms.csv.gz"] if not (path / name).exists()]
    return "COMPLETE" if not missing else "MISSING_" + ",".join(missing)


def latest_summary_json(run_root: Path, event_id: str) -> Path | None:
    matches = sorted(run_root.glob(f"{event_id}/workflow-*/reports/workflow-summary.json"))
    return matches[-1] if matches else None


def read_summary(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_row(batch_row: dict[str, str], run_root: Path, pipeline_root: Path) -> dict[str, Any]:
    event_id = (batch_row.get("event_id") or "").strip()
    latest_json = latest_summary_json(run_root, event_id) if event_id else None
    summary = read_summary(latest_json)
    status = summary.get("status", {})
    counts = summary.get("counts", {})
    paths = summary.get("paths", {})
    quality = summary.get("quality", {}).get("summary", {})
    normalized_event_dir = paths.get("normalized_event_dir", "")

    normalized_status = status.get("normalized", status.get("normalize", ""))

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
        "normalized_station_count": counts.get("normalized_stations", ""),
        "normalized_waveform_rows": counts.get("normalized_waveform_rows", ""),
        "normalized_event_grade": paths.get("normalized_event_grade", ""),
        "normalized_event_dir": portable(normalized_event_dir, pipeline_root),
        "export_package_status": export_package_status(normalized_event_dir, pipeline_root),
        "requested_stations": counts.get("requested_stations", ""),
        "obs_files": counts.get("obs_files", ""),
        "kin_files": counts.get("kin_files", ""),
        "plot_files": counts.get("plot_files", ""),
        "duration_seconds": summary.get("duration_seconds", ""),
        "workflow_dir": paths.get("workflow_dir", ""),
        "summary_json": portable(str(latest_json), pipeline_root) if latest_json else "",
    }


def build_rows(csv_path: Path, run_root: Path, pipeline_root: Path) -> list[dict[str, Any]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return [build_row(row, run_root, pipeline_root) for row in csv.DictReader(handle)]


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = build_rows(args.csv, args.run_root, args.pipeline_root)
    write_summary(args.summary, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
