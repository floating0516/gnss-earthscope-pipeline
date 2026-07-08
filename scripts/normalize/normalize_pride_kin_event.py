#!/usr/bin/env python3
"""Normalize PRIDE kin_* outputs into the plotting export format."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

QUALITY_DIR = Path(__file__).resolve().parents[1] / "quality"
if str(QUALITY_DIR) not in sys.path:
    sys.path.insert(0, str(QUALITY_DIR))

from compute_kin_quality import kin_to_enu, parse_utc, station_from_path

ROOT = Path(__file__).resolve().parents[2]
EVENT_SCHEMA_VERSION = "normalized-event/v1"
PROVENANCE_SCHEMA_VERSION = "provenance/v1"
EARTHSCOPE_SOURCE = "earthscope"
EARTHSCOPE_SOURCE_LABEL = "EarthScope PRIDE PPP-AR kin quality-passing stations"
EARTHSCOPE_EVENT_AUTHORITY = "USGS"
EARTHSCOPE_STATION_AUTHORITY = "EarthScope/GAGE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-summary", type=Path, required=True)
    parser.add_argument("--quality-json", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--normalized-root", type=Path, required=True)
    parser.add_argument("--include-warn", action="store_true", help="Include WARN stations as well as OK stations.")
    overwrite = parser.add_mutually_exclusive_group()
    overwrite.add_argument("--overwrite", action="store_true", help="Replace an existing normalized event package.")
    overwrite.add_argument("--no-overwrite", dest="overwrite", action="store_false", help="Refuse to replace an existing package.")
    parser.set_defaults(overwrite=False)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def workflow_root(summary: dict) -> Path:
    value = str(summary.get("paths", {}).get("root") or "").strip()
    if value and value != "@ROOT@":
        return Path(value).expanduser()
    return ROOT


def resolve_workflow_path(value: str | Path, summary: dict, workflow_summary: Path) -> Path:
    text = str(value).strip()
    root = workflow_root(summary)
    if not text:
        return Path()
    if text == "@ROOT@":
        return root
    if text.startswith("@ROOT@/"):
        return root / text[len("@ROOT@/") :]
    path = Path(text).expanduser()
    if not path.is_absolute():
        return root / path
    if path.exists():
        return path
    marker = "/gnss-earthscope-pipeline/"
    if marker in text:
        return root / text.split(marker, 1)[1]
    return path


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def slug_part(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"


def short_float(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    text = f"{number:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", "-")


def make_slug(event: dict) -> str:
    event_id = slug_part(event.get("event_id"))
    magnitude = short_float(event.get("magnitude"))
    date = str(event.get("time_utc") or event.get("event_date") or "")[:10].replace("-", "")
    place = slug_part(event.get("place"))
    return f"us-{event_id}-m{magnitude}-{date}-{place}".strip("-")


def connect_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"Database not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def existing_table(conn: sqlite3.Connection, names: list[str]) -> str | None:
    for name in names:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        if row:
            return name
    return None


def read_event(conn: sqlite3.Connection, event_id: str, fallback_time: str) -> dict:
    for event_table, subset in [
        ("usgs_m6plus_events_usa", "usa"),
        ("usgs_m6plus_events_earthscope_nonconus", "nonconus"),
    ]:
        if not existing_table(conn, [event_table]):
            continue
        row = conn.execute(
            f"""
            SELECT event_id, title, time_utc, event_date, magnitude, longitude, latitude, depth_km, place, usgs_url
            FROM {event_table}
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
        if row:
            event = dict(row)
            event["earthscope_subset"] = subset
            return event
    return {
        "event_id": event_id,
        "title": event_id,
        "time_utc": fallback_time,
        "event_date": fallback_time[:10],
        "magnitude": None,
        "longitude": None,
        "latitude": None,
        "depth_km": None,
        "place": event_id,
        "usgs_url": "",
        "earthscope_subset": "unknown",
    }


def read_station_metadata(conn: sqlite3.Connection, event_id: str) -> dict[str, dict[str, float]]:
    metadata: dict[str, dict[str, float]] = {}
    for table in ["event_earthscope_station_verified_files", "event_earthscope_station_candidates"]:
        rows = conn.execute(
            f"""
            SELECT station, station_latitude, station_longitude, MIN(distance_km) AS distance_km
            FROM {table}
            WHERE event_id = ?
              AND station_latitude IS NOT NULL
              AND station_longitude IS NOT NULL
            GROUP BY station
            """,
            (event_id,),
        ).fetchall()
        for row in rows:
            station = str(row["station"]).upper()
            metadata.setdefault(
                station,
                {
                    "latitude": float(row["station_latitude"]),
                    "longitude": float(row["station_longitude"]),
                    "distance_km": float(row["distance_km"]) if row["distance_km"] is not None else math.nan,
                },
            )
    return metadata


def quality_station_map(payload: dict, include_warn: bool) -> dict[str, dict]:
    allowed = {"OK", "WARN"} if include_warn else {"OK"}
    result = {}
    for row in payload.get("stations", []):
        station = str(row.get("station") or "").upper()
        if station and row.get("quality_status") in allowed:
            result[station] = row
    return result


def azimuth_deg(ev_lat: object, ev_lon: object, station_lat: float, station_lon: float) -> float | None:
    try:
        lat1 = math.radians(float(ev_lat))
        lat2 = math.radians(float(station_lat))
        dlon = math.radians(float(station_lon) - float(ev_lon))
    except (TypeError, ValueError):
        return None
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def event_grade(station_rows: list[dict], azimuth_bin_count: int = 8) -> dict[str, object]:
    station_count = len(station_rows)
    bins = {
        int(float(row["Azimuth_Deg"]) // (360.0 / azimuth_bin_count))
        for row in station_rows
        if row.get("Azimuth_Deg") not in {None, ""}
    }
    covered_bins = len(bins)
    if station_count >= 8 and covered_bins >= 6:
        grade = "A"
        description = "spatially well covered event"
    elif station_count >= 3:
        grade = "B"
        description = "multi-station event with limited azimuth coverage"
    elif station_count >= 1:
        grade = "C"
        description = "single/few-station event retained for collection"
    else:
        grade = "D"
        description = "no usable normalized stations"
    return {
        "grade": grade,
        "description": description,
        "station_count": station_count,
        "azimuth_bin_count": azimuth_bin_count,
        "azimuth_bins_covered": covered_bins,
        "azimuth_coverage_fraction": round(covered_bins / azimuth_bin_count, 3),
        "single_station_allowed": True,
    }


def normalization_metadata(include_warn: bool) -> dict[str, object]:
    return {
        "coordinate_transform": "ECEF XYZ minus reference position, then rotated to local ENU",
        "coordinate_frame": "PRIDE kin_* input frame inherited from processing products; kin epochs are interpreted as GPST and exported as UTC; output components are local ENU",
        "reference_position": "median ECEF position over all pre-event epochs; fallback to first 300 epochs when no pre-event data exists",
        "reference_epoch": "event-relative pre-event window, not a single epoch",
        "input_units": "PRIDE kin_* coordinates in meters; intermediate ENU displacement in centimeters",
        "output_units": "Value_m is meters",
        "detrend": "none",
        "filtering": "none",
        "quality_filter": "quality_status in OK,WARN" if include_warn else "quality_status == OK",
        "collection_policy": "retain any event with at least one quality-passing station; event grade records analysis suitability",
    }


def sampling_hz(series: list[tuple]) -> float:
    if len(series) < 2:
        return 1.0
    intervals = [
        (curr[0] - prev[0]).total_seconds()
        for prev, curr in zip(series, series[1:])
        if (curr[0] - prev[0]).total_seconds() > 0
    ]
    if not intervals:
        return 1.0
    intervals.sort()
    median_interval = intervals[len(intervals) // 2]
    return round(1.0 / median_interval, 6) if median_interval > 0 else 1.0


EARTHSCOPE_COUNTRY_PATTERNS = [
    ("antigua and barbuda", "Antigua and Barbuda"),
    ("costa rica", "Costa Rica"),
    ("cuba", "Cuba"),
    ("dominican republic", "Dominican Republic"),
    ("el salvador", "El Salvador"),
    ("guadeloupe", "Guadeloupe"),
    ("guatemala", "Guatemala"),
    ("honduras", "Honduras"),
    ("jamaica", "Jamaica"),
    ("mexico", "Mexico"),
    ("nicaragua", "Nicaragua"),
    ("panama", "Panama"),
    ("puerto rico", "Puerto Rico"),
    ("venezuela", "Venezuela"),
    ("haiti", "Haiti"),
]


def earthscope_country(event: dict) -> str:
    subset = event.get("earthscope_subset") or "unknown"
    if subset != "nonconus":
        return "United States"
    text = " ".join(str(event.get(key) or "") for key in ["place", "title"])
    text = text.casefold()
    for pattern, country in EARTHSCOPE_COUNTRY_PATTERNS:
        if pattern in text:
            return country
    return "Americas"


def event_json(
    event: dict,
    station_count: int,
    waveform_rows: int,
    workflow_summary: Path,
    grade: dict[str, object],
    include_warn: bool,
    skipped_stations: list[dict[str, str]] | None = None,
) -> dict:
    title = event.get("title") or event.get("place") or event.get("event_id")
    metadata = normalization_metadata(include_warn)
    subset = event.get("earthscope_subset") or "unknown"
    country = earthscope_country(event)
    region = "Americas" if subset == "nonconus" else "US"
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event": title,
        "usgs_event_id": event.get("event_id"),
        "event_id": event.get("event_id"),
        "source": EARTHSCOPE_SOURCE,
        "source_label": EARTHSCOPE_SOURCE_LABEL,
        "event_authority": EARTHSCOPE_EVENT_AUTHORITY,
        "station_authority": EARTHSCOPE_STATION_AUTHORITY,
        "event_time": event.get("time_utc"),
        "date": event.get("time_utc"),
        "longitude": event.get("longitude"),
        "latitude": event.get("latitude"),
        "depth_km": event.get("depth_km"),
        "magnitude": event.get("magnitude"),
        "magnitude_type": event.get("mag_type") or "",
        "station_count": station_count,
        "waveform_rows": waveform_rows,
        "stations": station_count,
        "country": country,
        "data_type": "gnss_displacement_waveform",
        "paper_title": "",
        "paper_url": "",
        "data_url": event.get("usgs_url") or "",
        "download_path": "",
        "parse_status": "normalized",
        "usgs_detail_url": event.get("usgs_url") or "",
        "usgs_place": event.get("place") or "",
        "place": event.get("place") or "",
        "region": region,
        "earthscope_subset": subset,
        "network": "EarthScope",
        "workflow_summary": str(workflow_summary),
        "quality_filter": metadata["quality_filter"],
        "event_grade": grade["grade"],
        "event_grade_description": grade["description"],
        "azimuth_bins_covered": grade["azimuth_bins_covered"],
        "azimuth_bin_count": grade["azimuth_bin_count"],
        "single_station_allowed": True,
        "normalization": metadata,
        "skipped_stations": skipped_stations or [],
    }


def workflow_text(summary: dict, *keys: str, fallback: str = "") -> str:
    current: object = summary
    for key in keys:
        if not isinstance(current, dict):
            return fallback
        current = current.get(key)
    return str(current or fallback)


def workflow_started_at(summary: dict, fallback: str) -> str:
    for keys in [
        ("workflow", "started_at"),
        ("workflow_started_at",),
        ("started_at",),
        ("started_utc",),
    ]:
        value = workflow_text(summary, *keys)
        if value:
            return value
    return fallback

def provenance_payload(
    *,
    event_id: str,
    summary: dict,
    args: argparse.Namespace,
    quality: dict,
    station_rows: list[dict[str, object]],
    waveform_rows: int,
    event: dict,
    grade: dict[str, object],
    skipped_stations: list[dict[str, str]],
    generated_at: str,
    selected_kin_files: list[Path],
) -> dict[str, object]:
    sampling_hz = sorted({str(row["Sampling_Hz"]) for row in station_rows})
    quality_summary = quality.get("summary", {}) if isinstance(quality.get("summary"), dict) else {}
    thresholds = quality.get("thresholds", {}) if isinstance(quality.get("thresholds"), dict) else {}
    workflow_script = "scripts/workflows/run_event_1hz_pride_workflow.sh"
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "source_label": f"EarthScope PRIDE PPP-AR / {event_id}",
        "data_type": "gnss_displacement_waveform",
        "format_hint": "normalized_waveforms_csv_gz",
        "sampling_hz": sampling_hz,
        "notes": "Generated from PRIDE kin_* files. Events are retained when at least one quality-passing station exists; event_grade records analysis suitability.",
        "workflow_summary": str(args.workflow_summary),
        "quality_json": str(args.quality_json),
        "parse_status": "normalized",
        "station_count": len(station_rows),
        "waveform_rows": waveform_rows,
        "event_id": event_id,
        "earthscope_subset": event.get("earthscope_subset") or "unknown",
        "event_grade": grade,
        "normalization": normalization_metadata(args.include_warn),
        "quality_summary": quality_summary,
        "station_quality_counts": dict(Counter(row["Quality_Status"] for row in station_rows)),
        "skipped_stations": skipped_stations,
        "generated_at": generated_at,
        "workflow": {
            "name": "earthscope-event-1hz-pride",
            "script": workflow_script,
            "started_at": workflow_started_at(summary, generated_at),
            "completed_at": generated_at,
            "git_commit": workflow_text(summary, "git_commit"),
            "command": workflow_text(summary, "command"),
        },
        "source": {
            "name": EARTHSCOPE_SOURCE,
            "event_authority": EARTHSCOPE_EVENT_AUTHORITY,
            "station_authority": EARTHSCOPE_STATION_AUTHORITY,
            "downloader": "tools/earthscope_downloader/download_event_window.py",
        },
        "processing": {
            "pride_processor": "tools/pride_processor/process_event_window.sh",
            "pdp3": "pdp3",
            "crx2rnx": "CRX2RNX",
            "window_hours": summary.get("window_hours") or summary.get("hours_each_side"),
            "sampling_hz": sampling_hz,
        },
        "quality": {
            "quality_json": str(args.quality_json),
            "thresholds": thresholds,
            "summary_status": str(quality_summary.get("status") or ""),
        },
        "inputs": [str(path) for path in selected_kin_files],
        "outputs": ["event.json", "stations.csv", "waveforms.csv.gz", "provenance.json"],
    }


def workflow_kin_files(summary: dict, workflow_summary: Path) -> list[Path]:
    kin_files = [resolve_workflow_path(path, summary, workflow_summary) for path in summary.get("files", {}).get("kin", [])]
    if kin_files:
        return unique_paths(kin_files)
    manifest = workflow_summary.parent.parent / "manifests" / "kin-files.txt"
    if manifest.exists():
        return unique_paths(
            [
                resolve_workflow_path(line.strip(), summary, workflow_summary)
                for line in manifest.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        )
    return []


def make_staging_dir(root: Path, slug: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f".tmp-{slug}-", dir=root))


def install_staged_package(stage_dir: Path, output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists() and not overwrite:
        raise SystemExit(f"Normalized event package already exists: {output_dir}")
    if not output_dir.exists():
        stage_dir.rename(output_dir)
        return

    backup_dir = Path(tempfile.mkdtemp(prefix=f".old-{output_dir.name}-", dir=output_dir.parent))
    backup_dir.rmdir()
    output_dir.rename(backup_dir)
    try:
        stage_dir.rename(output_dir)
    except BaseException:
        if output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)
        backup_dir.rename(output_dir)
        raise
    shutil.rmtree(backup_dir, ignore_errors=True)


def write_outputs(args: argparse.Namespace, summary: dict, quality: dict) -> dict:
    workflow_event = summary.get("event", {})
    event_id = str(workflow_event.get("id") or summary.get("event_id") or "").strip()
    event_time_text = str(workflow_event.get("time_utc") or "").strip()
    if not event_id or not event_time_text:
        raise SystemExit("Workflow summary is missing event.id or event.time_utc")

    conn = connect_db(args.db)
    try:
        event = read_event(conn, event_id, event_time_text)
        metadata = read_station_metadata(conn, event_id)
    finally:
        conn.close()
    event_time = parse_utc(str(event.get("time_utc") or event_time_text))

    quality_by_station = quality_station_map(quality, args.include_warn)
    if not quality_by_station:
        raise SystemExit("No quality-passing stations to normalize")

    selected = []
    for kin_file in workflow_kin_files(summary, args.workflow_summary):
        station = station_from_path(kin_file)
        if station in quality_by_station:
            selected.append((station, kin_file))
    if not selected:
        raise SystemExit("No kin files matched quality-passing stations")

    slug = make_slug(event)
    output_dir = args.normalized_root / slug
    overwrite = bool(getattr(args, "overwrite", False))
    if output_dir.exists() and not overwrite:
        raise SystemExit(f"Normalized event package already exists: {output_dir}")
    stage_dir = make_staging_dir(args.normalized_root, slug)

    station_rows = []
    skipped_stations: list[dict[str, str]] = []
    waveform_rows = 0
    try:
        waveforms_path = stage_dir / "waveforms.csv.gz"
        with gzip.open(waveforms_path, "wt", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["Station", "Time_UTC", "Time_Offset_s", "Component", "Value_m", "Sampling_Hz", "Source_File"],
                lineterminator="\n",
            )
            writer.writeheader()
            for station, kin_file in selected:
                if station not in metadata:
                    skipped_stations.append({"station": station, "reason": "missing_coordinates"})
                    continue
                series = kin_to_enu(kin_file, event_time)
                if not series:
                    continue
                hz = sampling_hz(series)
                for timestamp, seconds, east_cm, north_cm, up_cm in series:
                    time_text = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                    for component, value_cm in [("E", east_cm), ("N", north_cm), ("U", up_cm)]:
                        writer.writerow(
                            {
                                "Station": station,
                                "Time_UTC": time_text,
                                "Time_Offset_s": f"{seconds:.6f}",
                                "Component": component,
                                "Value_m": f"{value_cm / 100.0:.9f}",
                                "Sampling_Hz": hz,
                                "Source_File": str(kin_file),
                            }
                        )
                        waveform_rows += 1
                station_meta = metadata[station]
                lat = station_meta["latitude"]
                lon = station_meta["longitude"]
                azimuth = azimuth_deg(event.get("latitude"), event.get("longitude"), lat, lon)
                station_rows.append(
                    {
                        "Station": station,
                        "Latitude": f"{lat:.8f}",
                        "Longitude": f"{lon:.8f}",
                        "Sampling_Hz": hz,
                        "Waveform_Rows": len(series) * 3,
                        "Quality_Status": quality_by_station[station].get("quality_status", ""),
                        "Quality_Flags": quality_by_station[station].get("quality_flags", ""),
                        "Distance_Km": "" if math.isnan(station_meta["distance_km"]) else f"{station_meta['distance_km']:.3f}",
                        "Azimuth_Deg": "" if azimuth is None else f"{azimuth:.3f}",
                    }
                )

        if not station_rows:
            raise SystemExit("No waveform rows were normalized")

        station_fieldnames = [
            "Station",
            "Latitude",
            "Longitude",
            "Sampling_Hz",
            "Waveform_Rows",
            "Quality_Status",
            "Quality_Flags",
            "Distance_Km",
            "Azimuth_Deg",
        ]
        with (stage_dir / "stations.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=station_fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(sorted(station_rows, key=lambda row: row["Station"]))

        grade = event_grade(station_rows)
        event_payload = event_json(event, len(station_rows), waveform_rows, args.workflow_summary, grade, args.include_warn, skipped_stations)
        (stage_dir / "event.json").write_text(json.dumps(event_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        provenance = provenance_payload(
            event_id=event_id,
            summary=summary,
            args=args,
            quality=quality,
            station_rows=station_rows,
            waveform_rows=waveform_rows,
            event=event,
            grade=grade,
            skipped_stations=skipped_stations,
            generated_at=generated_at,
            selected_kin_files=[path for _, path in selected],
        )
        (stage_dir / "provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        install_staged_package(stage_dir, output_dir, overwrite)
    except BaseException:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise

    return {
        "normalized_status": "OK",
        "normalized_event_dir": str(output_dir),
        "normalized_station_count": len(station_rows),
        "normalized_waveform_rows": waveform_rows,
        "event_grade": grade["grade"],
        "azimuth_bins_covered": grade["azimuth_bins_covered"],
        "skipped_stations": skipped_stations,
    }


def main() -> int:
    args = parse_args()
    summary = load_json(args.workflow_summary)
    quality = load_json(args.quality_json)
    result = write_outputs(args, summary, quality)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
