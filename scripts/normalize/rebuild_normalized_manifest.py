#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_PACKAGE_FILES = ["event.json", "stations.csv", "waveforms.csv.gz", "provenance.json"]

MANIFEST_FIELDS = [
    "region",
    "network",
    "event_id",
    "event_dir",
    "event_time",
    "magnitude",
    "place",
    "stations_included",
    "ok_stations_included",
    "warn_stations_included",
    "waveform_rows",
    "event_grade",
    "quality_filter",
    "workflow_summary",
    "stations",
]

EVENT_SUMMARY_FIELDS = [
    "event_id",
    "event_dir",
    "origin_time",
    "longitude",
    "latitude",
    "depth_km",
    "magnitude",
    "place",
    "region",
    "country",
    "network",
    "station_count",
    "ok_station_count",
    "warn_station_count",
    "waveform_rows",
    "event_grade",
    "event_grade_description",
    "azimuth_bins_covered",
    "azimuth_bin_count",
    "azimuth_coverage_fraction",
    "single_station_allowed",
    "quality_filter",
    "has_mechanism",
    "mechanism",
    "strike",
    "dip",
    "rake",
]

FILE_INVENTORY_FIELDS = [
    "event_id",
    "event_dir",
    "event.json",
    "stations.csv",
    "waveforms.csv.gz",
    "provenance.json",
    "complete",
]


class NormalizedIndexes:
    def __init__(
        self,
        manifest_rows: list[dict[str, str]],
        event_summary_rows: list[dict[str, str]],
        file_inventory_rows: list[dict[str, str]],
    ) -> None:
        self.manifest_rows = manifest_rows
        self.event_summary_rows = event_summary_rows
        self.file_inventory_rows = file_inventory_rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild normalized export index files from event packages.")
    parser.add_argument("--root", type=Path, required=True, help="Normalized export root")
    parser.add_argument("--write", action="store_true", help="Write manifest.tsv, event_summary.csv, and file_inventory.tsv")
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def count_gzip_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def first_text(*values: Any) -> str:
    for value in values:
        result = text(value).strip()
        if result:
            return result
    return ""


def count_text(value: Any, fallback: int = 0) -> str:
    result = first_text(value)
    if result:
        return result
    return str(fallback)


def station_id(row: dict[str, str]) -> str:
    return first_text(row.get("Station"), row.get("station")).upper()


def station_status(row: dict[str, str]) -> str:
    return first_text(row.get("Quality_Status"), row.get("quality_status")).upper()


def quality_summary(provenance: dict[str, Any]) -> dict[str, Any]:
    payload = provenance.get("quality_summary")
    return payload if isinstance(payload, dict) else {}


def station_quality_counts(provenance: dict[str, Any]) -> dict[str, Any]:
    payload = provenance.get("station_quality_counts")
    return payload if isinstance(payload, dict) else {}


def grade_payload(provenance: dict[str, Any]) -> dict[str, Any]:
    payload = provenance.get("event_grade")
    return payload if isinstance(payload, dict) else {}


def event_grade(event: dict[str, Any], provenance: dict[str, Any]) -> str:
    return first_text(event.get("event_grade"), grade_payload(provenance).get("grade"))


def event_grade_description(event: dict[str, Any], provenance: dict[str, Any]) -> str:
    return first_text(event.get("event_grade_description"), grade_payload(provenance).get("description"))


def quality_filter(event: dict[str, Any], provenance: dict[str, Any]) -> str:
    normalization = provenance.get("normalization")
    if not isinstance(normalization, dict):
        normalization = {}
    return first_text(event.get("quality_filter"), normalization.get("quality_filter"))


def event_package_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        path
        for path in sorted(root.iterdir())
        if path.is_dir()
        and not path.name.startswith(".")
        and all((path / name).exists() for name in REQUIRED_PACKAGE_FILES)
    ]


def package_rows(package_dir: Path) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    event = load_json(package_dir / "event.json")
    provenance = load_json(package_dir / "provenance.json")
    stations = read_csv_rows(package_dir / "stations.csv")
    q_summary = quality_summary(provenance)
    q_counts = station_quality_counts(provenance)
    grade = grade_payload(provenance)

    event_id = first_text(event.get("event_id"), event.get("usgs_event_id"), provenance.get("event_id"), package_dir.name)
    event_time = first_text(event.get("date"), event.get("event_time"), event.get("origin_time"))
    station_ids = sorted(station_id(row) for row in stations if station_id(row))
    station_count = len(stations)
    ok_count = sum(1 for row in stations if station_status(row) == "OK")
    warn_count = sum(1 for row in stations if station_status(row) == "WARN")
    waveform_rows = first_text(provenance.get("waveform_rows"), event.get("waveform_rows"))
    if not waveform_rows:
        waveform_rows = str(count_gzip_csv_rows(package_dir / "waveforms.csv.gz"))

    station_count_text = count_text(provenance.get("station_count"), station_count)
    ok_count_text = count_text(q_summary.get("ok_station_count") or q_counts.get("OK"), ok_count)
    warn_count_text = count_text(q_summary.get("warn_station_count") or q_counts.get("WARN"), warn_count)
    common = {
        "event_id": event_id,
        "event_dir": package_dir.name,
        "event_time": event_time,
        "magnitude": first_text(event.get("magnitude"), provenance.get("magnitude")),
        "place": first_text(event.get("place"), event.get("usgs_place"), event.get("event")),
        "region": first_text(event.get("region"), provenance.get("region")),
        "country": first_text(event.get("country"), provenance.get("country")),
        "network": first_text(event.get("network"), provenance.get("network")),
        "station_count": station_count_text,
        "ok_station_count": ok_count_text,
        "warn_station_count": warn_count_text,
        "waveform_rows": waveform_rows,
        "event_grade": event_grade(event, provenance),
        "event_grade_description": event_grade_description(event, provenance),
        "quality_filter": quality_filter(event, provenance),
        "workflow_summary": first_text(event.get("workflow_summary"), provenance.get("workflow_summary")),
        "stations": " ".join(station_ids),
    }

    manifest_row = {
        "region": common["region"],
        "network": common["network"],
        "event_id": common["event_id"],
        "event_dir": common["event_dir"],
        "event_time": common["event_time"],
        "magnitude": common["magnitude"],
        "place": common["place"],
        "stations_included": common["station_count"],
        "ok_stations_included": common["ok_station_count"],
        "warn_stations_included": common["warn_station_count"],
        "waveform_rows": common["waveform_rows"],
        "event_grade": common["event_grade"],
        "quality_filter": common["quality_filter"],
        "workflow_summary": common["workflow_summary"],
        "stations": common["stations"],
    }
    event_summary_row = {
        "event_id": common["event_id"],
        "event_dir": common["event_dir"],
        "origin_time": common["event_time"],
        "longitude": first_text(event.get("longitude"), provenance.get("longitude")),
        "latitude": first_text(event.get("latitude"), provenance.get("latitude")),
        "depth_km": first_text(event.get("depth_km"), provenance.get("depth_km")),
        "magnitude": common["magnitude"],
        "place": common["place"],
        "region": common["region"],
        "country": common["country"],
        "network": common["network"],
        "station_count": common["station_count"],
        "ok_station_count": common["ok_station_count"],
        "warn_station_count": common["warn_station_count"],
        "waveform_rows": common["waveform_rows"],
        "event_grade": common["event_grade"],
        "event_grade_description": common["event_grade_description"],
        "azimuth_bins_covered": first_text(event.get("azimuth_bins_covered"), grade.get("azimuth_bins_covered")),
        "azimuth_bin_count": first_text(event.get("azimuth_bin_count"), grade.get("azimuth_bin_count")),
        "azimuth_coverage_fraction": first_text(grade.get("azimuth_coverage_fraction")),
        "single_station_allowed": first_text(event.get("single_station_allowed"), grade.get("single_station_allowed")),
        "quality_filter": common["quality_filter"],
        "has_mechanism": first_text(event.get("has_mechanism")),
        "mechanism": first_text(event.get("mechanism")),
        "strike": first_text(event.get("strike")),
        "dip": first_text(event.get("dip")),
        "rake": first_text(event.get("rake")),
    }
    file_inventory_row = {
        "event_id": common["event_id"],
        "event_dir": common["event_dir"],
    }
    complete = True
    for name in REQUIRED_PACKAGE_FILES:
        exists = (package_dir / name).exists()
        file_inventory_row[name] = "yes" if exists else "no"
        complete = complete and exists
    file_inventory_row["complete"] = "yes" if complete else "no"
    return manifest_row, event_summary_row, file_inventory_row


def row_sort_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("event_time") or row.get("origin_time", ""), row.get("event_id", "")


def build_indexes(root: Path) -> NormalizedIndexes:
    manifest_rows: list[dict[str, str]] = []
    event_summary_rows: list[dict[str, str]] = []
    file_inventory_rows: list[dict[str, str]] = []
    for package_dir in event_package_dirs(root.expanduser()):
        manifest_row, event_summary_row, file_inventory_row = package_rows(package_dir)
        manifest_rows.append(manifest_row)
        event_summary_rows.append(event_summary_row)
        file_inventory_rows.append(file_inventory_row)
    manifest_rows.sort(key=row_sort_key)
    event_summary_rows.sort(key=row_sort_key)
    file_inventory_rows.sort(key=lambda row: (row.get("event_dir", ""), row.get("event_id", "")))
    return NormalizedIndexes(manifest_rows, event_summary_rows, file_inventory_rows)


def render_rows(rows: list[dict[str, str]], fieldnames: list[str], delimiter: str) -> str:
    from io import StringIO

    handle = StringIO()
    writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=delimiter, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return handle.getvalue()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def rendered_outputs(indexes: NormalizedIndexes) -> dict[str, str]:
    return {
        "manifest.tsv": render_rows(indexes.manifest_rows, MANIFEST_FIELDS, "\t"),
        "event_summary.csv": render_rows(indexes.event_summary_rows, EVENT_SUMMARY_FIELDS, ","),
        "file_inventory.tsv": render_rows(indexes.file_inventory_rows, FILE_INVENTORY_FIELDS, "\t"),
    }


def write_indexes(root: Path, indexes: NormalizedIndexes) -> None:
    for name, content in rendered_outputs(indexes).items():
        atomic_write_text(root / name, content)


def diff_summary(root: Path, outputs: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, content in outputs.items():
        path = root / name
        if not path.exists():
            result[name] = "missing"
        elif path.read_text(encoding="utf-8") == content:
            result[name] = "unchanged"
        else:
            result[name] = "changed"
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = args.root.expanduser()
    indexes = build_indexes(root)
    outputs = rendered_outputs(indexes)
    diffs = diff_summary(root, outputs)
    if args.write:
        write_indexes(root, indexes)
        action = "wrote"
    else:
        action = "dry-run"
    print(
        f"{action} normalized indexes: events={len(indexes.manifest_rows)} "
        f"manifest.tsv={diffs['manifest.tsv']} "
        f"event_summary.csv={diffs['event_summary.csv']} "
        f"file_inventory.tsv={diffs['file_inventory.tsv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
