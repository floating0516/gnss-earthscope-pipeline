#!/usr/bin/env python3
"""Label GeoNet events that already exist in the normalized GNSS dataset."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import math
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "geonet_availability" / "geonet_1hz.sqlite"
DEFAULT_NORMALIZED_ROOT = ROOT.parent / "openclaw-gnss-collector-agent" / "data" / "gnss_data" / "normalized"
EARTH_RADIUS_KM = 6371.0088


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--normalized-root", default=str(DEFAULT_NORMALIZED_ROOT))
    parser.add_argument("--time-tolerance-seconds", type=float, default=600.0)
    parser.add_argument("--distance-tolerance-km", type=float, default=50.0)
    parser.add_argument("--reset", action="store_true", help="Clear existing normalized labels before applying labels.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: object) -> dt.datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(geonet_m6plus_events_nz)")}
    columns = {
        "existing_data_status": "TEXT NOT NULL DEFAULT ''",
        "existing_data_source": "TEXT",
        "existing_dataset_dir": "TEXT",
        "existing_station_count": "INTEGER NOT NULL DEFAULT 0",
        "existing_waveform_file": "TEXT",
        "existing_event_file": "TEXT",
        "existing_updated_at": "TEXT",
    }
    for name, declaration in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE geonet_m6plus_events_nz ADD COLUMN {name} {declaration}")


def reset_labels(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE geonet_m6plus_events_nz
        SET existing_data_status = '',
            existing_data_source = NULL,
            existing_dataset_dir = NULL,
            existing_station_count = 0,
            existing_waveform_file = NULL,
            existing_event_file = NULL,
            existing_updated_at = NULL
        """
    )


def count_station_rows(stations_csv: Path) -> int:
    if not stations_csv.exists():
        return 0
    with stations_csv.open(newline="", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def count_waveform_rows(waveform_file: Path) -> int:
    if not waveform_file.exists():
        return 0
    opener = gzip.open if waveform_file.suffix == ".gz" else open
    with opener(waveform_file, "rt", newline="", encoding="utf-8", errors="replace") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def discover(normalized_root: Path) -> list[dict[str, object]]:
    labels: list[dict[str, object]] = []
    for event_file in sorted(normalized_root.glob("*/event.json")):
        dataset_dir = event_file.parent
        try:
            event = json.loads(event_file.read_text(encoding="utf-8"))
            event_time = parse_utc(event.get("date") or event.get("time") or event.get("time_utc"))
            latitude = float(event["latitude"])
            longitude = float(event["longitude"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        stations_csv = dataset_dir / "stations.csv"
        waveform_file = dataset_dir / "waveforms.csv.gz"
        station_count = int(event.get("stations") or 0) or count_station_rows(stations_csv)
        labels.append(
            {
                "event_time": event_time,
                "latitude": latitude,
                "longitude": longitude,
                "magnitude": float(event.get("magnitude") or 0.0),
                "dataset_slug": dataset_dir.name,
                "existing_data_status": "HAS_NORMALIZED",
                "existing_data_source": str(event.get("source") or "normalized_gnss_data"),
                "existing_dataset_dir": str(dataset_dir),
                "existing_station_count": station_count,
                "existing_waveform_file": str(waveform_file) if waveform_file.exists() else "",
                "existing_event_file": str(event_file),
                "waveform_rows": count_waveform_rows(waveform_file),
            }
        )
    return labels


def find_matches(
    conn: sqlite3.Connection,
    labels: list[dict[str, object]],
    time_tolerance_seconds: float,
    distance_tolerance_km: float,
) -> list[dict[str, object]]:
    events = conn.execute(
        """
        SELECT event_id, time_utc, latitude, longitude, magnitude, place
        FROM geonet_m6plus_events_nz
        ORDER BY time_utc, event_id
        """
    ).fetchall()
    matches: list[dict[str, object]] = []
    for event in events:
        event_time = parse_utc(event["time_utc"])
        candidates = []
        for label in labels:
            delta_seconds = abs((event_time - label["event_time"]).total_seconds())
            distance_km = haversine_km(
                float(event["latitude"]),
                float(event["longitude"]),
                float(label["latitude"]),
                float(label["longitude"]),
            )
            if delta_seconds <= time_tolerance_seconds and distance_km <= distance_tolerance_km:
                candidates.append((delta_seconds, distance_km, label))
        if not candidates:
            continue
        delta_seconds, distance_km, label = sorted(candidates, key=lambda item: (item[0], item[1]))[0]
        matches.append(
            {
                "event_id": event["event_id"],
                "time_utc": event["time_utc"],
                "magnitude": event["magnitude"],
                "place": event["place"],
                "delta_seconds": delta_seconds,
                "distance_km": distance_km,
                **label,
            }
        )
    return matches


def apply_matches(conn: sqlite3.Connection, matches: list[dict[str, object]], dry_run: bool) -> int:
    if dry_run:
        return len(matches)
    updated_at = utc_now()
    with conn:
        for match in matches:
            conn.execute(
                """
                UPDATE geonet_m6plus_events_nz
                SET existing_data_status = ?,
                    existing_data_source = ?,
                    existing_dataset_dir = ?,
                    existing_station_count = ?,
                    existing_waveform_file = ?,
                    existing_event_file = ?,
                    existing_updated_at = ?
                WHERE event_id = ?
                """,
                (
                    match["existing_data_status"],
                    match["existing_data_source"],
                    match["existing_dataset_dir"],
                    match["existing_station_count"],
                    match["existing_waveform_file"],
                    match["existing_event_file"],
                    updated_at,
                    match["event_id"],
                ),
            )
        conn.executemany(
            "INSERT OR REPLACE INTO build_metadata(key, value) VALUES (?, ?)",
            [
                ("geonet_existing_normalized_labels_updated_at", updated_at),
                ("geonet_existing_normalized_labels_matched", str(len(matches))),
            ],
        )
    return len(matches)


def main() -> int:
    args = parse_args()
    normalized_root = Path(args.normalized_root).expanduser()
    if not normalized_root.exists():
        raise SystemExit(f"normalized root not found: {normalized_root}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        ensure_columns(conn)
        if args.reset and not args.dry_run:
            with conn:
                reset_labels(conn)
        labels = discover(normalized_root)
        matches = find_matches(conn, labels, args.time_tolerance_seconds, args.distance_tolerance_km)
        applied = apply_matches(conn, matches, args.dry_run)
        for match in matches:
            print(
                "MATCHED\t"
                f"{match['event_id']}\t{match['existing_data_status']}\t"
                f"dataset={match['dataset_slug']}\tstations={match['existing_station_count']}\t"
                f"dt_s={match['delta_seconds']:.1f}\tdistance_km={match['distance_km']:.2f}\t"
                f"{match['existing_dataset_dir']}"
            )
        print(
            f"SUMMARY\tdiscovered={len(labels)}\tmatched={len(matches)}\tapplied={applied}\t"
            f"time_tolerance_seconds={args.time_tolerance_seconds:g}\t"
            f"distance_tolerance_km={args.distance_tolerance_km:g}\tdry_run={int(args.dry_run)}"
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
