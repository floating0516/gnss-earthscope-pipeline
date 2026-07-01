#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


BASE_COLUMNS = [
    "region",
    "network",
    "event_id",
    "magnitude",
    "event_date",
    "event_time",
    "place",
    "stations_200km",
    "stations_300km",
    "existing_data_status",
    "workflow_status",
    "download_status",
    "obs_validation_status",
    "process_status",
    "plot_status",
    "quality_status",
    "quality_station_count",
    "quality_ok_stations",
    "quality_warn_stations",
    "quality_fail_stations",
    "station_health_ratio",
    "requested_stations",
    "obs_files",
    "kin_files",
    "plot_files",
    "cleanup_status",
    "pride_cleanup_status",
    "obs_cleanup_status",
    "duration_seconds",
    "workflow_dir",
    "summary_json",
]

EXPORT_COLUMNS = [
    "collection_status",
    "export_event_dir",
    "export_region",
    "export_country",
    "export_network",
    "export_station_count",
    "export_ok_station_count",
    "export_warn_station_count",
    "export_waveform_rows",
    "export_event_grade",
    "export_quality_filter",
    "export_stations",
    "export_package_status",
]

OUTPUT_COLUMNS = BASE_COLUMNS + EXPORT_COLUMNS


def read_rows(path: Path, delimiter: str) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str] = OUTPUT_COLUMNS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def event_date(event_time: str) -> str:
    return event_time[:10] if event_time else ""


def source_from_manifest_row(row: dict[str, str]) -> tuple[str, str]:
    event_dir = row.get("event_dir", "")
    if event_dir.startswith("nz-"):
        return "NZ", "GeoNet"
    if event_dir.startswith("au-"):
        return "AU", "Geoscience Australia"
    if event_dir.startswith("us-"):
        return "US", "EarthScope"
    return row.get("region") or "US", row.get("network") or "EarthScope"


def workflow_dir(summary_path: str) -> str:
    if not summary_path:
        return ""
    path = Path(summary_path)
    if path.parent.name == "reports":
        return str(path.parent.parent)
    return ""


def summary_by_event(path: Path) -> dict[str, dict[str, str]]:
    rows = read_rows(path, ",")
    return {row["event_id"]: row for row in rows if row.get("event_id")}


def export_package_status(manifest_path: Path, event_dir: str) -> str:
    if not event_dir:
        return "MISSING_EVENT_DIR"
    package_dir = manifest_path.parent / event_dir
    required = ["event.json", "stations.csv", "waveforms.csv.gz"]
    missing = [name for name in required if not (package_dir / name).exists()]
    if missing:
        return "MISSING_" + ",".join(missing)
    return "COMPLETE"


def empty_row() -> dict[str, str]:
    return {field: "" for field in OUTPUT_COLUMNS}


def row_sort_key(row: dict[str, str]) -> tuple[str, str]:
    event_time = row.get("event_time", "")
    event_id = row.get("event_id", "")
    return (event_time, event_id)


def normalize_current_row(row: dict[str, str]) -> dict[str, str]:
    normalized = empty_row()
    for field in BASE_COLUMNS:
        normalized[field] = row.get(field, "")
    normalized["collection_status"] = "CURRENT_ONLY"
    normalized["export_package_status"] = "NOT_IN_MANIFEST"
    return normalized


def export_row(
    manifest_row: dict[str, str],
    event_summary: dict[str, str],
    current_row: dict[str, str] | None,
    manifest_path: Path,
    package_status: str,
) -> dict[str, str]:
    row = normalize_current_row(current_row or {})
    region, network = source_from_manifest_row(manifest_row)
    summary_path = manifest_row.get("workflow_summary", "")
    stations_included = manifest_row.get("stations_included", "")
    ok_stations = manifest_row.get("ok_stations_included", "")
    warn_stations = manifest_row.get("warn_stations_included", "")

    row.update(
        {
            "region": region,
            "network": network,
            "event_id": manifest_row.get("event_id", ""),
            "magnitude": manifest_row.get("magnitude", "") or event_summary.get("magnitude", ""),
            "event_date": event_date(manifest_row.get("event_time", "") or event_summary.get("origin_time", "")),
            "event_time": manifest_row.get("event_time", "") or event_summary.get("origin_time", ""),
            "place": manifest_row.get("place", "") or event_summary.get("place", ""),
            "existing_data_status": "HAS_NORMALIZED",
            "workflow_status": row.get("workflow_status") or "DONE",
            "download_status": row.get("download_status") or "OK",
            "obs_validation_status": row.get("obs_validation_status") or "OK",
            "process_status": row.get("process_status") or "OK",
            "quality_status": row.get("quality_status") or "OK",
            "quality_station_count": row.get("quality_station_count") or stations_included,
            "quality_ok_stations": row.get("quality_ok_stations") or ok_stations,
            "quality_warn_stations": row.get("quality_warn_stations") or warn_stations,
            "quality_fail_stations": row.get("quality_fail_stations") or "0",
            "station_health_ratio": row.get("station_health_ratio") or "1.0",
            "requested_stations": row.get("requested_stations") or stations_included,
            "obs_files": row.get("obs_files") or stations_included,
            "kin_files": row.get("kin_files") or stations_included,
            "plot_files": row.get("plot_files") or "",
            "workflow_dir": row.get("workflow_dir") or workflow_dir(summary_path),
            "summary_json": row.get("summary_json") or summary_path,
            "collection_status": "EXPORTED",
            "export_event_dir": manifest_row.get("event_dir", ""),
            "export_region": event_summary.get("region", "") or manifest_row.get("region", ""),
            "export_country": event_summary.get("country", ""),
            "export_network": event_summary.get("network", "") or manifest_row.get("network", ""),
            "export_station_count": event_summary.get("station_count", "") or stations_included,
            "export_ok_station_count": event_summary.get("ok_station_count", "") or ok_stations,
            "export_warn_station_count": event_summary.get("warn_station_count", "") or warn_stations,
            "export_waveform_rows": event_summary.get("waveform_rows", "") or manifest_row.get("waveform_rows", ""),
            "export_event_grade": event_summary.get("event_grade", "") or manifest_row.get("event_grade", ""),
            "export_quality_filter": event_summary.get("quality_filter", "") or manifest_row.get("quality_filter", ""),
            "export_stations": manifest_row.get("stations", ""),
            "export_package_status": package_status,
        }
    )
    if not row.get("summary_json") and summary_path:
        row["summary_json"] = summary_path
    if row.get("summary_json") and not row.get("workflow_dir"):
        row["workflow_dir"] = workflow_dir(row["summary_json"])
    return row


def build_completion_rows(current_path: Path, manifest_path: Path, event_summary_path: Path) -> list[dict[str, str]]:
    current_rows = read_rows(current_path, "\t")
    current_by_id = {row["event_id"]: row for row in current_rows if row.get("event_id")}
    event_summaries = summary_by_event(event_summary_path)

    merged: dict[str, dict[str, str]] = {}
    for manifest_row in read_rows(manifest_path, "\t"):
        event_id = manifest_row.get("event_id")
        if not event_id:
            continue
        package_status = export_package_status(manifest_path, manifest_row.get("event_dir", ""))
        if package_status != "COMPLETE":
            continue
        merged[event_id] = export_row(
            manifest_row,
            event_summaries.get(event_id, {}),
            current_by_id.get(event_id),
            manifest_path,
            package_status,
        )

    for event_id, current_row in current_by_id.items():
        if event_id not in merged:
            merged[event_id] = normalize_current_row(current_row)

    return sorted(merged.values(), key=row_sort_key, reverse=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build manifest-driven current event completion TSVs for GNSS earthquake exports."
    )
    parser.add_argument("--current", type=Path, default=Path("data/summaries/us_nz_current_event_completion.tsv"))
    parser.add_argument("--manifest", type=Path, default=Path("exports/normalized-ok-stations-us-nz/manifest.tsv"))
    parser.add_argument("--event-summary", type=Path, default=Path("exports/normalized-ok-stations-us-nz/event_summary.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/summaries/us_nz_current_event_completion.tsv"))
    parser.add_argument("--us-output", type=Path, default=Path("data/summaries/us_current_event_completion.tsv"))
    parser.add_argument("--nz-output", type=Path, default=Path("data/summaries/nz_current_event_completion.tsv"))
    parser.add_argument("--au-output", type=Path, default=Path("data/summaries/au_current_event_completion.tsv"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rows = build_completion_rows(args.current, args.manifest, args.event_summary)
    write_rows(args.output, rows)
    write_rows(args.us_output, [row for row in rows if row.get("region") == "US"])
    write_rows(args.nz_output, [row for row in rows if row.get("region") == "NZ"])
    write_rows(args.au_output, [row for row in rows if row.get("region") == "AU"])

    exported = sum(1 for row in rows if row.get("collection_status") == "EXPORTED")
    current_only = sum(1 for row in rows if row.get("collection_status") == "CURRENT_ONLY")
    print(f"wrote {args.output}: rows={len(rows)} exported={exported} current_only={current_only}")
    print(f"wrote {args.us_output}: rows={sum(1 for row in rows if row.get('region') == 'US')}")
    print(f"wrote {args.nz_output}: rows={sum(1 for row in rows if row.get('region') == 'NZ')}")
    print(f"wrote {args.au_output}: rows={sum(1 for row in rows if row.get('region') == 'AU')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
