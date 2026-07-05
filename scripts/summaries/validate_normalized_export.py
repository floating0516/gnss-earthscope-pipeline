#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_INDEXES = ["manifest.tsv", "event_summary.csv", "file_inventory.tsv"]
REQUIRED_PACKAGE_FILES = ["event.json", "stations.csv", "waveforms.csv.gz", "provenance.json"]
NORMALIZED_EVENT_SCHEMA_VERSION = "normalized-event/v1"
PROVENANCE_SCHEMA_VERSION = "provenance/v1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a normalized GNSS earthquake export root.")
    parser.add_argument("--root", type=Path, required=True, help="Normalized export root")
    parser.add_argument("--event-id", help="Validate one event_id within the export")
    parser.add_argument("--json-out", type=Path, help="Write machine-readable validation report")
    parser.add_argument("--strict", action="store_true", help="Treat orphan/incomplete package directories as errors")
    return parser.parse_args(argv)


def read_rows(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    return read_rows(path, ",")


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    return read_rows(path, "\t")


def add_issue(
    issues: list[dict[str, str]],
    code: str,
    message: str,
    *,
    event_id: str = "",
    path: Path | str | None = None,
) -> None:
    issue = {"code": code, "message": message}
    if event_id:
        issue["event_id"] = event_id
    if path is not None and str(path):
        issue["path"] = str(path)
    issues.append(issue)


def load_json(path: Path, errors: list[dict[str, str]], code: str, event_id: str = "") -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        add_issue(errors, code, f"Invalid JSON: {exc}", event_id=event_id, path=path)
        return {}
    if not isinstance(payload, dict):
        add_issue(errors, code, "JSON root must be an object", event_id=event_id, path=path)
        return {}
    return payload


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def station_value(row: dict[str, str]) -> str:
    for key in ["Station", "station"]:
        value = (row.get(key) or "").strip()
        if value:
            return value.upper()
    return ""


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_number_or_none(value: Any) -> bool:
    return value is None or isinstance(value, int | float)


def is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def add_schema_issue(
    errors: list[dict[str, str]],
    code: str,
    field: str,
    reason: str,
    *,
    event_id: str,
    path: Path,
) -> None:
    add_issue(errors, code, f"{field}: {reason}", event_id=event_id, path=path)


def validate_event_schema(
    payload: dict[str, Any],
    *,
    event_id: str,
    station_count: int,
    waveform_rows: int,
    errors: list[dict[str, str]],
    path: Path,
) -> None:
    code = "EVENT_SCHEMA_INVALID"
    if payload.get("schema_version") != NORMALIZED_EVENT_SCHEMA_VERSION:
        add_schema_issue(
            errors,
            code,
            "schema_version",
            f"expected {NORMALIZED_EVENT_SCHEMA_VERSION}",
            event_id=event_id,
            path=path,
        )
    if payload.get("event_id") != event_id:
        add_schema_issue(errors, code, "event_id", f"expected {event_id}", event_id=event_id, path=path)
    for field in ["source", "event_authority", "station_authority", "event_time", "region"]:
        if not is_nonempty_string(payload.get(field)):
            add_schema_issue(errors, code, field, "must be a non-empty string", event_id=event_id, path=path)
    if "magnitude_type" not in payload or not (payload.get("magnitude_type") is None or isinstance(payload.get("magnitude_type"), str)):
        add_schema_issue(errors, code, "magnitude_type", "must be present as a string or null", event_id=event_id, path=path)
    for field in ["latitude", "longitude", "depth_km", "magnitude"]:
        if field not in payload or not is_number_or_none(payload.get(field)):
            add_schema_issue(errors, code, field, "must be present as a number or null", event_id=event_id, path=path)
    if not is_nonnegative_int(payload.get("station_count")):
        add_schema_issue(errors, code, "station_count", "must be a non-negative integer", event_id=event_id, path=path)
    elif int(payload["station_count"]) != station_count:
        add_schema_issue(errors, code, "station_count", f"expected {station_count}", event_id=event_id, path=path)
    if not is_nonnegative_int(payload.get("waveform_rows")):
        add_schema_issue(errors, code, "waveform_rows", "must be a non-negative integer", event_id=event_id, path=path)
    elif int(payload["waveform_rows"]) != waveform_rows:
        add_schema_issue(errors, code, "waveform_rows", f"expected {waveform_rows}", event_id=event_id, path=path)


def nested_mapping(payload: dict[str, Any], field: str) -> dict[str, Any]:
    value = payload.get(field)
    return value if isinstance(value, dict) else {}


def validate_required_nested_strings(
    nested: dict[str, Any],
    *,
    section: str,
    fields: list[str],
    errors: list[dict[str, str]],
    event_id: str,
    path: Path,
    allow_empty: set[str] | None = None,
) -> None:
    allow_empty = allow_empty or set()
    for field in fields:
        value = nested.get(field)
        dotted = f"{section}.{field}"
        if field in allow_empty:
            if not isinstance(value, str):
                add_schema_issue(errors, "PROVENANCE_SCHEMA_INVALID", dotted, "must be a string", event_id=event_id, path=path)
        elif not is_nonempty_string(value):
            add_schema_issue(errors, "PROVENANCE_SCHEMA_INVALID", dotted, "must be a non-empty string", event_id=event_id, path=path)


def validate_provenance_schema(
    payload: dict[str, Any],
    *,
    event_id: str,
    station_count: int,
    waveform_rows: int,
    errors: list[dict[str, str]],
    path: Path,
) -> None:
    code = "PROVENANCE_SCHEMA_INVALID"
    if payload.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        add_schema_issue(errors, code, "schema_version", f"expected {PROVENANCE_SCHEMA_VERSION}", event_id=event_id, path=path)
    if payload.get("event_id") != event_id:
        add_schema_issue(errors, code, "event_id", f"expected {event_id}", event_id=event_id, path=path)
    if not is_nonnegative_int(payload.get("station_count")):
        add_schema_issue(errors, code, "station_count", "must be a non-negative integer", event_id=event_id, path=path)
    elif int(payload["station_count"]) != station_count:
        add_schema_issue(errors, code, "station_count", f"expected {station_count}", event_id=event_id, path=path)
    if not is_nonnegative_int(payload.get("waveform_rows")):
        add_schema_issue(errors, code, "waveform_rows", "must be a non-negative integer", event_id=event_id, path=path)
    elif int(payload["waveform_rows"]) != waveform_rows:
        add_schema_issue(errors, code, "waveform_rows", f"expected {waveform_rows}", event_id=event_id, path=path)

    workflow = nested_mapping(payload, "workflow")
    source = nested_mapping(payload, "source")
    processing = nested_mapping(payload, "processing")
    quality = nested_mapping(payload, "quality")
    if not workflow:
        add_schema_issue(errors, code, "workflow", "must be an object", event_id=event_id, path=path)
    if not source:
        add_schema_issue(errors, code, "source", "must be an object", event_id=event_id, path=path)
    if not processing:
        add_schema_issue(errors, code, "processing", "must be an object", event_id=event_id, path=path)
    if not quality:
        add_schema_issue(errors, code, "quality", "must be an object", event_id=event_id, path=path)

    validate_required_nested_strings(
        workflow,
        section="workflow",
        fields=["name", "script", "started_at", "completed_at", "git_commit", "command"],
        allow_empty={"git_commit", "command"},
        errors=errors,
        event_id=event_id,
        path=path,
    )
    validate_required_nested_strings(
        source,
        section="source",
        fields=["name", "event_authority", "station_authority", "downloader"],
        errors=errors,
        event_id=event_id,
        path=path,
    )
    for field in ["pride_processor", "pdp3", "crx2rnx", "window_hours", "sampling_hz"]:
        if field not in processing:
            add_schema_issue(errors, code, f"processing.{field}", "must be present", event_id=event_id, path=path)
    if "quality_json" not in quality or not isinstance(quality.get("quality_json"), str):
        add_schema_issue(errors, code, "quality.quality_json", "must be a string", event_id=event_id, path=path)
    if not isinstance(quality.get("thresholds"), dict):
        add_schema_issue(errors, code, "quality.thresholds", "must be an object", event_id=event_id, path=path)
    if "summary_status" not in quality or not isinstance(quality.get("summary_status"), str):
        add_schema_issue(errors, code, "quality.summary_status", "must be a string", event_id=event_id, path=path)
    for field in ["inputs", "outputs"]:
        if not isinstance(payload.get(field), list):
            add_schema_issue(errors, code, field, "must be a list", event_id=event_id, path=path)


def count_csv_rows(path: Path, errors: list[dict[str, str]], code: str, event_id: str = "") -> list[dict[str, str]]:
    try:
        rows = read_csv_rows(path)
    except csv.Error as exc:
        add_issue(errors, code, f"Invalid CSV: {exc}", event_id=event_id, path=path)
        return []
    return rows


def count_gzip_csv_rows(path: Path, errors: list[dict[str, str]], code: str, event_id: str = "") -> list[dict[str, str]]:
    try:
        with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        add_issue(errors, code, f"Invalid gzip CSV: {exc}", event_id=event_id, path=path)
        return []


def event_id_from_summary_row(row: dict[str, str]) -> str:
    return (row.get("event_id") or row.get("Event_ID") or "").strip()


def filtered_rows(rows: list[dict[str, str]], event_id: str | None) -> list[dict[str, str]]:
    if not event_id:
        return rows
    return [row for row in rows if event_id_from_summary_row(row) == event_id]


def collect_event_dirs(*row_groups: list[dict[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for rows in row_groups:
        for row in rows:
            event_id = event_id_from_summary_row(row)
            event_dir = (row.get("event_dir") or row.get("Event_Dir") or "").strip()
            if event_id and event_dir:
                result.setdefault(event_id, event_dir)
    return result


def package_payload_event_id(package_dir: Path) -> str:
    event_payload = read_json_object(package_dir / "event.json")
    provenance_payload = read_json_object(package_dir / "provenance.json")
    return str(
        event_payload.get("event_id")
        or event_payload.get("usgs_event_id")
        or provenance_payload.get("event_id")
        or ""
    ).strip()


def find_event_package_dir(root: Path, event_id: str) -> str:
    for path in sorted(root.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        if package_payload_event_id(path) == event_id:
            return path.name
    return ""


def read_indexes(root: Path, event_id: str | None, errors: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    missing = [name for name in REQUIRED_INDEXES if not (root / name).exists()]
    for name in missing:
        add_issue(errors, "MISSING_INDEX", f"Missing required index {name}", path=root / name)
    if missing:
        return [], [], []

    manifest_rows = filtered_rows(read_tsv_rows(root / "manifest.tsv"), event_id)
    event_summary_rows = filtered_rows(read_csv_rows(root / "event_summary.csv"), event_id)
    inventory_rows = read_tsv_rows(root / "file_inventory.tsv")
    if event_id:
        event_dirs = {
            row.get("event_dir", "")
            for row in manifest_rows + event_summary_rows
            if row.get("event_dir")
        }
        inventory_rows = [
            row
            for row in inventory_rows
            if event_id_from_summary_row(row) == event_id or (row.get("event_dir") or "") in event_dirs
        ]
    return manifest_rows, event_summary_rows, inventory_rows


def check_package(root: Path, event_id: str, event_dir: str, errors: list[dict[str, str]], enforce_schema: bool = False) -> dict[str, Any]:
    package_dir = root / event_dir
    if not package_dir.exists():
        add_issue(errors, "MISSING_PACKAGE_DIR", f"Missing package directory {event_dir}", event_id=event_id, path=package_dir)
        return {"event_id": event_id, "event_dir": event_dir, "station_count": 0, "waveform_rows": 0}
    if not package_dir.is_dir():
        add_issue(errors, "PACKAGE_NOT_DIRECTORY", f"Package path is not a directory: {event_dir}", event_id=event_id, path=package_dir)
        return {"event_id": event_id, "event_dir": event_dir, "station_count": 0, "waveform_rows": 0}

    missing_files = [name for name in REQUIRED_PACKAGE_FILES if not (package_dir / name).exists()]
    for name in missing_files:
        add_issue(errors, "MISSING_PACKAGE_FILE", f"Missing package file {name}", event_id=event_id, path=package_dir / name)
    if missing_files:
        return {"event_id": event_id, "event_dir": event_dir, "station_count": 0, "waveform_rows": 0}

    event_payload = load_json(package_dir / "event.json", errors, "INVALID_EVENT_JSON", event_id)
    provenance_payload = load_json(package_dir / "provenance.json", errors, "INVALID_PROVENANCE_JSON", event_id)
    payload_event_id = str(event_payload.get("event_id") or event_payload.get("usgs_event_id") or provenance_payload.get("event_id") or "").strip()
    if payload_event_id and payload_event_id != event_id:
        add_issue(
            errors,
            "PACKAGE_EVENT_ID_MISMATCH",
            f"Package event_id {payload_event_id} does not match index event_id {event_id}",
            event_id=event_id,
            path=package_dir / "event.json",
        )

    station_rows = count_csv_rows(package_dir / "stations.csv", errors, "INVALID_STATIONS_CSV", event_id)
    waveform_rows = count_gzip_csv_rows(package_dir / "waveforms.csv.gz", errors, "INVALID_WAVEFORMS_CSV", event_id)
    if not station_rows:
        add_issue(errors, "EMPTY_STATIONS", "stations.csv has no station rows", event_id=event_id, path=package_dir / "stations.csv")
    if not waveform_rows:
        add_issue(errors, "EMPTY_WAVEFORMS", "waveforms.csv.gz has no waveform rows", event_id=event_id, path=package_dir / "waveforms.csv.gz")

    station_ids = {station_value(row) for row in station_rows if station_value(row)}
    waveform_station_ids = {station_value(row) for row in waveform_rows if station_value(row)}
    missing_waveform_stations = sorted(station_ids - waveform_station_ids)
    for station in missing_waveform_stations:
        add_issue(
            errors,
            "STATION_WITHOUT_WAVEFORM",
            f"Station {station} in stations.csv has no waveform rows",
            event_id=event_id,
            path=package_dir / "waveforms.csv.gz",
        )

    if enforce_schema:
        validate_event_schema(
            event_payload,
            event_id=event_id,
            station_count=len(station_rows),
            waveform_rows=len(waveform_rows),
            errors=errors,
            path=package_dir / "event.json",
        )
        validate_provenance_schema(
            provenance_payload,
            event_id=event_id,
            station_count=len(station_rows),
            waveform_rows=len(waveform_rows),
            errors=errors,
            path=package_dir / "provenance.json",
        )

    return {
        "event_id": event_id,
        "event_dir": event_dir,
        "station_count": len(station_rows),
        "waveform_rows": len(waveform_rows),
        "event_schema_version": str(event_payload.get("schema_version") or ""),
        "provenance_schema_version": str(provenance_payload.get("schema_version") or ""),
    }


def inventory_file_path(row: dict[str, str]) -> str:
    for key in ["file", "path", "relative_path", "filepath"]:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def check_file_inventory(root: Path, inventory_rows: list[dict[str, str]], errors: list[dict[str, str]], strict: bool) -> None:
    for row in inventory_rows:
        explicit = inventory_file_path(row)
        if explicit:
            path = root / explicit
            if not path.exists():
                add_issue(errors, "FILE_INVENTORY_MISSING_FILE", f"Inventory file does not exist: {explicit}", path=path)
            continue

        event_dir = (row.get("event_dir") or "").strip()
        if not event_dir:
            add_issue(errors, "FILE_INVENTORY_MISSING_EVENT_DIR", "file_inventory.tsv row lacks event_dir")
            continue
        for name in REQUIRED_PACKAGE_FILES:
            value = (row.get(name) or "").strip().lower()
            if value in {"yes", "true", "1", "present", "ok"} and not (root / event_dir / name).exists():
                add_issue(
                    errors,
                    "FILE_INVENTORY_MISSING_FILE",
                    f"Inventory marks {name} present but file is missing",
                    path=root / event_dir / name,
                )
            if strict and value in {"no", "false", "0", "missing"}:
                add_issue(
                    errors,
                    "FILE_INVENTORY_INCOMPLETE_PACKAGE",
                    f"Inventory marks {name} missing for {event_dir}",
                    path=root / event_dir / name,
                )


def check_event_sets(
    manifest_rows: list[dict[str, str]],
    event_summary_rows: list[dict[str, str]],
    package_ids: set[str],
    errors: list[dict[str, str]],
) -> None:
    manifest_ids = {event_id_from_summary_row(row) for row in manifest_rows if event_id_from_summary_row(row)}
    summary_ids = {event_id_from_summary_row(row) for row in event_summary_rows if event_id_from_summary_row(row)}
    if manifest_ids != summary_ids or manifest_ids != package_ids:
        details = (
            f"manifest={len(manifest_ids)} event_summary={len(summary_ids)} "
            f"packages={len(package_ids)}"
        )
        add_issue(errors, "EVENT_SET_MISMATCH", f"Event ID sets do not match: {details}")


def check_orphans(root: Path, indexed_event_dirs: set[str], errors: list[dict[str, str]], strict: bool) -> None:
    if not strict:
        return
    for path in sorted(root.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        if path.name not in indexed_event_dirs:
            add_issue(errors, "ORPHAN_PACKAGE_DIR", f"Package directory is not indexed: {path.name}", path=path)


def validate_export(root: Path, event_id: str | None = None, strict: bool = False) -> dict[str, Any]:
    root = root.expanduser()
    errors: list[dict[str, str]] = []
    packages: list[dict[str, Any]] = []

    if not root.exists():
        add_issue(errors, "MISSING_ROOT", f"Export root does not exist: {root}", path=root)
        return report(root, event_id, strict, packages, errors)
    if not root.is_dir():
        add_issue(errors, "ROOT_NOT_DIRECTORY", f"Export root is not a directory: {root}", path=root)
        return report(root, event_id, strict, packages, errors)

    if event_id:
        if all((root / name).exists() for name in REQUIRED_INDEXES):
            manifest_rows, event_summary_rows, inventory_rows = read_indexes(root, event_id, errors)
            if errors:
                return report(root, event_id, strict, packages, errors)
        else:
            manifest_rows, event_summary_rows, inventory_rows = [], [], []
    else:
        manifest_rows, event_summary_rows, inventory_rows = read_indexes(root, event_id, errors)
        if errors:
            return report(root, event_id, strict, packages, errors)

    event_dirs = collect_event_dirs(manifest_rows, event_summary_rows)
    if event_id and event_id not in event_dirs:
        scanned_event_dir = find_event_package_dir(root, event_id)
        if scanned_event_dir:
            event_dirs[event_id] = scanned_event_dir
        else:
            add_issue(errors, "EVENT_NOT_FOUND", f"Event package not found for event_id {event_id}", event_id=event_id)
            return report(root, event_id, strict, packages, errors)

    package_ids: set[str] = set()
    for package_event_id, event_dir in sorted(event_dirs.items()):
        package_report = check_package(root, package_event_id, event_dir, errors, enforce_schema=bool(event_id) or strict)
        packages.append(package_report)
        if not any(error.get("event_id") == package_event_id and error["code"].startswith("MISSING_PACKAGE") for error in errors):
            package_ids.add(package_event_id)

    if not event_id:
        check_event_sets(manifest_rows, event_summary_rows, package_ids, errors)
    check_file_inventory(root, inventory_rows, errors, strict)
    if not event_id:
        check_orphans(root, set(event_dirs.values()), errors, strict)
    return report(root, event_id, strict, packages, errors)


def report(
    root: Path,
    event_id: str | None,
    strict: bool,
    packages: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "status": "OK" if not errors else "INVALID",
        "root": str(root),
        "event_id": event_id or "",
        "strict": strict,
        "event_count": len(packages),
        "station_count": sum(int(package.get("station_count") or 0) for package in packages),
        "waveform_rows": sum(int(package.get("waveform_rows") or 0) for package in packages),
        "error_count": len(errors),
        "errors": errors,
        "packages": packages,
    }


def print_human_report(payload: dict[str, Any]) -> None:
    print(f"normalized_export_status\t{payload['status']}")
    print(f"root\t{payload['root']}")
    if payload.get("event_id"):
        print(f"event_id\t{payload['event_id']}")
    print(f"strict\t{str(payload['strict']).lower()}")
    print(f"events\t{payload['event_count']}")
    print(f"stations\t{payload['station_count']}")
    print(f"waveform_rows\t{payload['waveform_rows']}")
    print(f"errors\t{payload['error_count']}")
    for error in payload["errors"]:
        event = f"\tevent_id={error['event_id']}" if error.get("event_id") else ""
        path = f"\tpath={error['path']}" if error.get("path") else ""
        print(f"ERROR\t{error['code']}\t{error['message']}{event}{path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = validate_export(args.root, event_id=args.event_id, strict=args.strict)
    print_human_report(payload)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
