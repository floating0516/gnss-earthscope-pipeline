#!/usr/bin/env python3
"""Rebuild event/station candidate rows from EarthScope availability metadata."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"
DEFAULT_METADATA_ROOT = ROOT / "data" / "earthscope_metadata"
SOURCE = "earthscope_same_day_1hz+metadata"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--metadata-root", default=str(DEFAULT_METADATA_ROOT))
    parser.add_argument("--radius-km", type=float, action="append", default=[200.0, 300.0])
    parser.add_argument("--event-id", action="append", help="Limit rebuild to one or more event ids.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def doy_from_date(value: str) -> int:
    return int(dt.date.fromisoformat(value).strftime("%j"))


def metadata_file_for_event(metadata_root: Path, year: int, doy: int) -> Path:
    return metadata_root / str(year) / f"earthscope-metadata-{year}-{doy:03d}-le1.json"


def metadata_date(path: Path) -> dt.date | None:
    parts = path.stem.split("-")
    if len(parts) != 5:
        return None
    try:
        return dt.datetime.strptime(f"{parts[2]}-{parts[3]}", "%Y-%j").date()
    except ValueError:
        return None


def metadata_files_for_event(metadata_root: Path, year: int, doy: int) -> list[Path]:
    event_date = dt.datetime.strptime(f"{year}-{doy:03d}", "%Y-%j").date()
    files = []
    for path in metadata_root.glob("*/earthscope-metadata-*-le1.json"):
        date = metadata_date(path)
        if date is not None and date <= event_date:
            files.append((date, path))
    files.sort(reverse=True)
    return [path for _, path in files]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def init_candidate_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_earthscope_station_candidates (
            event_id TEXT NOT NULL,
            station TEXT NOT NULL,
            event_date TEXT NOT NULL,
            radius_km REAL NOT NULL,
            distance_km REAL NOT NULL,
            station_latitude REAL NOT NULL,
            station_longitude REAL NOT NULL,
            site_id TEXT,
            sample_interval REAL,
            data_type TEXT,
            availability_source TEXT NOT NULL,
            metadata_file TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (event_id, station, radius_km)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_candidates_event ON event_earthscope_station_candidates(event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_candidates_radius ON event_earthscope_station_candidates(radius_km)")


def event_table(conn: sqlite3.Connection) -> str:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "usgs_m6plus_events_usa" in tables:
        return "usgs_m6plus_events_usa"
    if "usgs_m6plus_events_earthscope_nonconus" in tables:
        return "usgs_m6plus_events_earthscope_nonconus"
    raise SystemExit("missing supported EarthScope event table")


def read_events(conn: sqlite3.Connection, event_ids: list[str] | None) -> list[sqlite3.Row]:
    table = event_table(conn)
    sql = f"""
        SELECT event_id, event_date, year, latitude, longitude
        FROM {table}
    """
    params: list[str] = []
    if event_ids:
        placeholders = ",".join("?" for _ in event_ids)
        sql += f" WHERE event_id IN ({placeholders})"
        params.extend(event_ids)
    sql += " ORDER BY event_date, event_id"
    return list(conn.execute(sql, params))


def read_day_availability(conn: sqlite3.Connection, event_date: str) -> set[str]:
    return {
        str(row[0]).strip().upper()
        for row in conn.execute(
            """
            SELECT station
            FROM station_day_availability
            WHERE date = ? AND has_1hz = 1
            """,
            (event_date,),
        )
        if str(row[0]).strip()
    }


def read_metadata_stations(metadata_files: list[Path], available: set[str]) -> dict[str, dict[str, object]]:
    stations: dict[str, dict[str, object]] = {}
    for metadata_file in metadata_files:
        payload = json.loads(metadata_file.read_text())
        for feature in payload.get("features", []):
            props = feature.get("properties", {})
            station = str(props.get("site_code") or "").strip().upper()
            if not station or station not in available or station in stations:
                continue
            try:
                sample_interval = float(props.get("sample_interval"))
            except (TypeError, ValueError):
                continue
            if sample_interval > 1.0:
                continue
            coords = feature.get("geometry", {}).get("coordinates") or []
            if len(coords) < 2:
                continue
            try:
                lon = float(coords[0])
                lat = float(coords[1])
            except (TypeError, ValueError):
                continue
            stations[station] = {
                "station": station,
                "latitude": lat,
                "longitude": lon,
                "site_id": str(props.get("site_id") or ""),
                "sample_interval": sample_interval,
                "data_type": str(props.get("data_type") or ""),
                "metadata_file": str(metadata_file),
            }
        if available.issubset(stations):
            break
    return stations


def rebuild(conn: sqlite3.Connection, metadata_root: Path, radii: list[float], event_ids: list[str] | None, dry_run: bool) -> int:
    init_candidate_table(conn)
    events = read_events(conn, event_ids)
    updated_at = utc_now()
    total_rows = 0
    missing_metadata = 0
    no_availability = 0

    if not dry_run:
        with conn:
            if event_ids:
                conn.executemany("DELETE FROM event_earthscope_station_candidates WHERE event_id = ?", [(event_id,) for event_id in event_ids])
            else:
                conn.execute("DELETE FROM event_earthscope_station_candidates")

    for event in events:
        event_id = str(event["event_id"])
        event_date = str(event["event_date"])
        year = int(event["year"])
        doy = doy_from_date(event_date)
        metadata_files = metadata_files_for_event(metadata_root, year, doy)
        if not metadata_files:
            missing_metadata += 1
            print(f"MISSING_METADATA\t{event_id}\t{event_date}\t{metadata_file_for_event(metadata_root, year, doy)}")
            continue
        available = read_day_availability(conn, event_date)
        if not available:
            no_availability += 1
            print(f"NO_AVAILABILITY\t{event_id}\t{event_date}")
            continue
        stations = read_metadata_stations(metadata_files, available)
        rows = []
        for station in stations.values():
            distance = haversine_km(
                float(event["latitude"]),
                float(event["longitude"]),
                float(station["latitude"]),
                float(station["longitude"]),
            )
            for radius in radii:
                if distance <= radius:
                    rows.append(
                        (
                            event_id,
                            station["station"],
                            event_date,
                            float(radius),
                            distance,
                            station["latitude"],
                            station["longitude"],
                            station["site_id"],
                            station["sample_interval"],
                            station["data_type"],
                            SOURCE,
                            str(station["metadata_file"]),
                            updated_at,
                        )
                    )
        total_rows += len(rows)
        print(f"EVENT\t{event_id}\t{event_date}\trows={len(rows)}")
        if rows and not dry_run:
            with conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO event_earthscope_station_candidates (
                        event_id, station, event_date, radius_km, distance_km,
                        station_latitude, station_longitude, site_id, sample_interval,
                        data_type, availability_source, metadata_file, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )

    print(
        "SUMMARY"
        f"\tevents={len(events)}"
        f"\trows={total_rows}"
        f"\tmissing_metadata={missing_metadata}"
        f"\tno_availability={no_availability}"
    )
    return 0


def main() -> int:
    args = parse_args()
    radii = sorted(set(float(radius) for radius in args.radius_km))
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        return rebuild(conn, Path(args.metadata_root), radii, args.event_id, args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
