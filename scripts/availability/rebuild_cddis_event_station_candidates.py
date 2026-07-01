#!/usr/bin/env python3
"""Build CDDIS event-station candidates from high-rate availability and station metadata."""

from __future__ import annotations

import argparse
import datetime as dt
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "cddis_highrate" / "cddis_highrate.sqlite"
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Event:
    event_id: str
    event_time_utc: str
    latitude: float
    longitude: float
    magnitude: float | None
    place: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--event-id", action="append", default=[])
    parser.add_argument("--event-time")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--magnitude", type=float)
    parser.add_argument("--place", default="")
    parser.add_argument("--min-magnitude", type=float, default=6.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--radius-km", type=float, action="append")
    parser.add_argument("--window-minutes", type=float, default=15.0, help="Availability window starting at event time")
    parser.add_argument("--start-time", help="Override availability window start UTC")
    parser.add_argument("--end-time", help="Override availability window end UTC")
    parser.add_argument("--clear-event", action="store_true", help="Delete existing candidates for selected events before inserting")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def parse_utc(value: str) -> dt.datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a = math.sin(delta_lat / 2.0) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2.0) ** 2
    return EARTH_RADIUS_KM * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cddis_events (
            event_id TEXT PRIMARY KEY,
            event_time_utc TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            magnitude REAL,
            place TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_cddis_station_candidates (
            event_id TEXT NOT NULL,
            station4 TEXT NOT NULL,
            radius_km REAL NOT NULL,
            distance_km REAL NOT NULL,
            event_time_utc TEXT NOT NULL,
            window_start_utc TEXT NOT NULL,
            window_end_utc TEXT NOT NULL,
            station_latitude REAL NOT NULL,
            station_longitude REAL NOT NULL,
            station_elevation_m REAL NOT NULL,
            available_file_count INTEGER NOT NULL,
            filenames TEXT NOT NULL,
            urls TEXT NOT NULL,
            metadata_source_file TEXT NOT NULL,
            availability_source TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(event_id, station4, radius_km),
            FOREIGN KEY(event_id) REFERENCES cddis_events(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_cddis_candidates_event ON event_cddis_station_candidates(event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_cddis_candidates_radius ON event_cddis_station_candidates(radius_km)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_cddis_candidates_station ON event_cddis_station_candidates(station4)")


def read_requested_event_ids(args: argparse.Namespace) -> list[str]:
    return [event_id for event_id in args.event_id if event_id]


def read_events(conn: sqlite3.Connection, args: argparse.Namespace) -> list[Event]:
    requested = read_requested_event_ids(args)
    explicit_event = args.event_time or args.latitude is not None or args.longitude is not None
    if explicit_event:
        if len(requested) != 1 or not args.event_time or args.latitude is None or args.longitude is None:
            raise SystemExit("explicit event rebuild requires exactly one --event-id plus --event-time, --latitude, and --longitude")
        return [Event(requested[0], iso_utc(parse_utc(args.event_time)), args.latitude, args.longitude, args.magnitude, args.place)]

    params: list[object] = [args.min_magnitude]
    clauses = ["COALESCE(magnitude, 0) >= ?"]
    if requested:
        placeholders = ",".join("?" for _ in requested)
        clauses.append(f"event_id IN ({placeholders})")
        params.extend(requested)
    sql = f"""
        SELECT event_id, event_time_utc, latitude, longitude, magnitude, place
        FROM cddis_events
        WHERE {' AND '.join(clauses)}
        ORDER BY event_time_utc, event_id
    """
    if args.limit > 0:
        sql += " LIMIT ?"
        params.append(args.limit)
    rows = conn.execute(sql, params).fetchall()
    return [
        Event(
            event_id=str(row["event_id"]),
            event_time_utc=str(row["event_time_utc"]),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            magnitude=row["magnitude"],
            place=str(row["place"]),
        )
        for row in rows
    ]


def slot_window(event_time: dt.datetime, window_minutes: float) -> tuple[dt.datetime, dt.datetime]:
    if window_minutes <= 0:
        raise SystemExit("--window-minutes must be positive")
    if window_minutes == 15.0:
        minute = (event_time.minute // 15) * 15
        start = event_time.replace(minute=minute, second=0, microsecond=0)
    else:
        start = event_time
    return start, start + dt.timedelta(minutes=window_minutes)


def availability_window(args: argparse.Namespace, event: Event) -> tuple[dt.datetime, dt.datetime]:
    if args.start_time or args.end_time:
        if not args.start_time or not args.end_time:
            raise SystemExit("--start-time and --end-time must be provided together")
        if len(read_requested_event_ids(args)) != 1:
            raise SystemExit("--start-time and --end-time can only be used with one --event-id")
        start = parse_utc(args.start_time)
        end = parse_utc(args.end_time)
    else:
        start, end = slot_window(parse_utc(event.event_time_utc), args.window_minutes)
    if end <= start:
        raise SystemExit("candidate availability window must have positive duration")
    return start, end


def read_available_stations(conn: sqlite3.Connection, start_utc: str, end_utc: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return list(
        conn.execute(
            """
            SELECT f.station4,
                   s.latitude,
                   s.longitude,
                   s.elevation_m,
                   s.source_file AS metadata_source_file,
                   COUNT(*) AS available_file_count,
                   GROUP_CONCAT(f.filename, ' ') AS filenames,
                   GROUP_CONCAT(f.url, ' ') AS urls
            FROM cddis_highrate_files f
            JOIN cddis_stations s ON s.station4 = f.station4
            WHERE f.start_time_utc < ? AND f.end_time_utc > ?
            GROUP BY f.station4, s.latitude, s.longitude, s.elevation_m, s.source_file
            ORDER BY f.station4
            """,
            (end_utc, start_utc),
        )
    )


def upsert_event(conn: sqlite3.Connection, event: Event, updated_at: str) -> None:
    conn.execute(
        """
        INSERT INTO cddis_events (
            event_id, event_time_utc, latitude, longitude, magnitude, place, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            event_time_utc = excluded.event_time_utc,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            magnitude = excluded.magnitude,
            place = excluded.place,
            updated_at = excluded.updated_at
        """,
        (
            event.event_id,
            iso_utc(parse_utc(event.event_time_utc)),
            event.latitude,
            event.longitude,
            event.magnitude,
            event.place,
            updated_at,
        ),
    )


def build_candidate_rows(
    event: Event,
    stations: list[sqlite3.Row],
    radii: list[float],
    start_utc: str,
    end_utc: str,
    updated_at: str,
) -> list[tuple[object, ...]]:
    rows: list[tuple[object, ...]] = []
    event_time = iso_utc(parse_utc(event.event_time_utc))
    for station in stations:
        distance = haversine_km(event.latitude, event.longitude, float(station["latitude"]), float(station["longitude"]))
        for radius in radii:
            if distance <= radius:
                rows.append(
                    (
                        event.event_id,
                        station["station4"],
                        radius,
                        distance,
                        event_time,
                        start_utc,
                        end_utc,
                        station["latitude"],
                        station["longitude"],
                        station["elevation_m"],
                        station["available_file_count"],
                        station["filenames"] or "",
                        station["urls"] or "",
                        station["metadata_source_file"],
                        "CDDIS highrate GNSS + RINEX header metadata",
                        updated_at,
                    )
                )
    rows.sort(key=lambda row: (float(row[2]), float(row[3]), str(row[1])))
    return rows


def insert_candidates(conn: sqlite3.Connection, rows: list[tuple[object, ...]]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO event_cddis_station_candidates (
            event_id, station4, radius_km, distance_km, event_time_utc,
            window_start_utc, window_end_utc, station_latitude, station_longitude,
            station_elevation_m, available_file_count, filenames, urls,
            metadata_source_file, availability_source, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    radii = sorted(set(float(radius) for radius in (args.radius_km or [200.0, 500.0, 1000.0])))
    updated_at = utc_now()
    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        events = read_events(conn, args)
        explicit_event = args.event_time or args.latitude is not None or args.longitude is not None
        total_rows = 0
        events_with_stations = 0
        events_with_candidates = 0
        selected_event_ids = [event.event_id for event in events]
        if not args.dry_run:
            with conn:
                if args.clear_event and selected_event_ids:
                    conn.executemany("DELETE FROM event_cddis_station_candidates WHERE event_id = ?", [(event_id,) for event_id in selected_event_ids])
        for event in events:
            start, end = availability_window(args, event)
            start_utc = iso_utc(start)
            end_utc = iso_utc(end)
            stations = read_available_stations(conn, start_utc, end_utc)
            rows = build_candidate_rows(event, stations, radii, start_utc, end_utc, updated_at)
            total_rows += len(rows)
            if stations:
                events_with_stations += 1
            if rows:
                events_with_candidates += 1
            if not args.dry_run:
                with conn:
                    if explicit_event:
                        upsert_event(conn, event, updated_at)
                    insert_candidates(conn, rows)
            print(
                "EVENT"
                f"\tevent_id={event.event_id}"
                f"\twindow={start_utc}->{end_utc}"
                f"\tavailable_stations={len(stations)}"
                f"\tcandidate_rows={len(rows)}"
            )
            for row in rows:
                print(f"CANDIDATE\t{row[0]}\t{row[1]}\tradius={row[2]:.0f}\tdistance_km={row[3]:.3f}")
        print(
            "SUMMARY"
            f"\tevents={len(events)}"
            f"\tevents_with_available_stations={events_with_stations}"
            f"\tevents_with_candidates={events_with_candidates}"
            f"\tcandidate_rows={total_rows}"
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
