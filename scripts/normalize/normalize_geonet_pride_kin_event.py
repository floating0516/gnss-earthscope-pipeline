#!/usr/bin/env python3
"""Normalize GeoNet PRIDE kin_* outputs into the shared export format."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import normalize_pride_kin_event as shared


EVENT_SCHEMA_VERSION = "normalized-event/v1"
PROVENANCE_SCHEMA_VERSION = "provenance/v1"
GEONET_SOURCE = "geonet"
GEONET_SOURCE_LABEL = "GeoNet PRIDE PPP-AR kin quality-passing stations"
GEONET_EVENT_AUTHORITY = "GeoNet"
GEONET_STATION_AUTHORITY = "GeoNet"
GEONET_REGION = "New Zealand"
GEONET_NETWORK = "GeoNet"
GEONET_WORKFLOW_SCRIPT = "scripts/workflows/run_geonet_event_1hz_pride_workflow.sh"
GEONET_DOWNLOADER = "tools/geonet_downloader/"


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


def make_slug(event: dict) -> str:
    event_id = shared.slug_part(event.get("event_id"))
    magnitude = shared.short_float(event.get("magnitude"))
    date = str(event.get("time_utc") or event.get("event_date") or "")[:10].replace("-", "")
    place = shared.slug_part(event.get("place"))
    return f"nz-geonet-{event_id}-m{magnitude}-{date}-{place}".strip("-")


def connect_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"Database not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def read_event(conn: sqlite3.Connection, event_id: str, fallback_time: str) -> dict:
    if shared.existing_table(conn, ["geonet_m6plus_events_nz"]):
        row = conn.execute(
            """
            SELECT event_id, title, time_utc, event_date, magnitude, mag_type,
                   longitude, latitude, depth_km, place, geonet_url
            FROM geonet_m6plus_events_nz
            WHERE event_id = ?
            """,
            (event_id,),
        ).fetchone()
        if row:
            return dict(row)
    return {
        "event_id": event_id,
        "title": event_id,
        "time_utc": fallback_time,
        "event_date": fallback_time[:10],
        "magnitude": None,
        "mag_type": "",
        "longitude": None,
        "latitude": None,
        "depth_km": None,
        "place": event_id,
        "geonet_url": "",
    }


def read_station_metadata(conn: sqlite3.Connection, event_id: str) -> dict[str, dict[str, float]]:
    metadata: dict[str, dict[str, float]] = {}
    if not shared.existing_table(conn, ["event_geonet_station_candidates"]):
        return metadata
    rows = conn.execute(
        """
        SELECT station, station_latitude, station_longitude, MIN(distance_km) AS distance_km
        FROM event_geonet_station_candidates
        WHERE event_id = ?
          AND station_latitude IS NOT NULL
          AND station_longitude IS NOT NULL
        GROUP BY station
        """,
        (event_id,),
    ).fetchall()
    for row in rows:
        station = str(row["station"]).upper()
        metadata[station] = {
            "latitude": float(row["station_latitude"]),
            "longitude": float(row["station_longitude"]),
            "distance_km": float(row["distance_km"]) if row["distance_km"] is not None else math.nan,
        }
    return metadata


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
    metadata = shared.normalization_metadata(include_warn)
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event": title,
        "event_id": event.get("event_id"),
        "source": GEONET_SOURCE,
        "source_label": GEONET_SOURCE_LABEL,
        "event_authority": GEONET_EVENT_AUTHORITY,
        "station_authority": GEONET_STATION_AUTHORITY,
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
        "country": GEONET_REGION,
        "data_type": "gnss_displacement_waveform",
        "paper_title": "",
        "paper_url": "",
        "data_url": event.get("geonet_url") or "",
        "download_path": "",
        "parse_status": "normalized",
        "place": event.get("place") or "",
        "region": GEONET_REGION,
        "network": GEONET_NETWORK,
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


def provenance_payload(
    *,
    event_id: str,
    summary: dict,
    args: argparse.Namespace,
    quality: dict,
    station_rows: list[dict[str, object]],
    waveform_rows: int,
    grade: dict[str, object],
    skipped_stations: list[dict[str, str]],
    generated_at: str,
    selected_kin_files: list[Path],
) -> dict[str, object]:
    sampling_hz = sorted({str(row["Sampling_Hz"]) for row in station_rows})
    quality_summary = quality.get("summary", {}) if isinstance(quality.get("summary"), dict) else {}
    thresholds = quality.get("thresholds", {}) if isinstance(quality.get("thresholds"), dict) else {}
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "source_label": f"GeoNet PRIDE PPP-AR / {event_id}",
        "data_type": "gnss_displacement_waveform",
        "format_hint": "normalized_waveforms_csv_gz",
        "sampling_hz": sampling_hz,
        "notes": "Generated from GeoNet PRIDE kin_* files. Events are retained when at least one quality-passing station exists; event_grade records analysis suitability.",
        "workflow_summary": str(args.workflow_summary),
        "quality_json": str(args.quality_json),
        "parse_status": "normalized",
        "station_count": len(station_rows),
        "waveform_rows": waveform_rows,
        "event_id": event_id,
        "event_grade": grade,
        "normalization": shared.normalization_metadata(args.include_warn),
        "quality_summary": quality_summary,
        "station_quality_counts": dict(Counter(row["Quality_Status"] for row in station_rows)),
        "skipped_stations": skipped_stations,
        "generated_at": generated_at,
        "workflow": {
            "name": "geonet-event-1hz-pride",
            "script": GEONET_WORKFLOW_SCRIPT,
            "started_at": shared.workflow_started_at(summary, generated_at),
            "completed_at": generated_at,
            "git_commit": shared.workflow_text(summary, "git_commit"),
            "command": shared.workflow_text(summary, "command"),
        },
        "source": {
            "name": GEONET_SOURCE,
            "event_authority": GEONET_EVENT_AUTHORITY,
            "station_authority": GEONET_STATION_AUTHORITY,
            "downloader": GEONET_DOWNLOADER,
        },
        "processing": {
            "pride_processor": "tools/pride_processor/process_event_window.sh",
            "pdp3": "pdp3",
            "crx2rnx": "CRX2RNX",
            "window_hours": summary.get("parameters", {}).get("process_window_hours_each_side")
            or summary.get("window_hours")
            or summary.get("hours_each_side"),
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
    event_time = shared.parse_utc(str(event.get("time_utc") or event_time_text))

    quality_by_station = shared.quality_station_map(quality, args.include_warn)
    if not quality_by_station:
        raise SystemExit("No quality-passing stations to normalize")

    selected = []
    for kin_file in shared.workflow_kin_files(summary, args.workflow_summary):
        station = shared.station_from_path(kin_file)
        if station in quality_by_station:
            selected.append((station, kin_file))
    if not selected:
        raise SystemExit("No kin files matched quality-passing stations")

    slug = make_slug(event)
    output_dir = args.normalized_root / slug
    overwrite = bool(getattr(args, "overwrite", False))
    if output_dir.exists() and not overwrite:
        raise SystemExit(f"Normalized event package already exists: {output_dir}")
    stage_dir = shared.make_staging_dir(args.normalized_root, slug)

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
                series = shared.kin_to_enu(kin_file, event_time)
                if not series:
                    continue
                hz = shared.sampling_hz(series)
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
                azimuth = shared.azimuth_deg(event.get("latitude"), event.get("longitude"), lat, lon)
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

        grade = shared.event_grade(station_rows)
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
            grade=grade,
            skipped_stations=skipped_stations,
            generated_at=generated_at,
            selected_kin_files=[path for _, path in selected],
        )
        (stage_dir / "provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        shared.install_staged_package(stage_dir, output_dir, overwrite)
    except BaseException:
        if stage_dir.exists():
            import shutil

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
