#!/usr/bin/env python3
"""Build a trial Rénag/USGS earthquake and 1 Hz availability SQLite database."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sqlite3
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "renag_downloader"
sys.path.insert(0, str(TOOLS))

from renag_common import day_url, haversine_km, list_day_files, normalize_doy  # noqa: E402


DEFAULT_DB = ROOT / "data" / "renag_availability" / "renag_1hz.sqlite"
DEFAULT_AVAILABILITY_DIR = ROOT / "data" / "renag_availability"
DEFAULT_BATCH_CSV = ROOT / "data" / "renag_batches" / "renag_usgs_m45_france_alps_candidates.csv"
USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


@dataclass(frozen=True)
class Event:
    event_id: str
    title: str
    time_utc: str
    latitude: float
    longitude: float
    depth_km: float | None
    magnitude: float
    mag_type: str
    place: str
    event_type: str
    usgs_url: str

    @property
    def event_date(self) -> str:
        return self.time_utc[:10]

    @property
    def year(self) -> int:
        return int(self.time_utc[:4])

    @property
    def doy(self) -> int:
        instant = parse_utc(self.time_utc)
        return int(instant.strftime("%j"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--availability-dir", default=str(DEFAULT_AVAILABILITY_DIR))
    parser.add_argument("--starttime", default="2019-01-01T00:00:00")
    parser.add_argument("--endtime", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    parser.add_argument("--min-magnitude", type=float, default=4.5)
    parser.add_argument("--minlatitude", type=float, default=41.0)
    parser.add_argument("--maxlatitude", type=float, default=52.0)
    parser.add_argument("--minlongitude", type=float, default=-6.0)
    parser.add_argument("--maxlongitude", type=float, default=10.0)
    parser.add_argument("--write-batch-csv", default=str(DEFAULT_BATCH_CSV))
    parser.add_argument("--max-batch-stations", type=int, default=12)
    parser.add_argument("--inventory", default="")
    parser.add_argument("--radius-km", type=float, default=300.0)
    parser.add_argument("--check-availability", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> dt.datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def normalize_time_ms(value: int | float) -> str:
    instant = dt.datetime.fromtimestamp(float(value) / 1000.0, tz=dt.timezone.utc)
    return instant.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fetch_json(url: str, timeout: int = 60) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-earthscope-pipeline renag-usgs-db"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_usgs_url(args: argparse.Namespace) -> str:
    params: dict[str, object] = {
        "format": "geojson",
        "starttime": args.starttime,
        "endtime": args.endtime,
        "minmagnitude": args.min_magnitude,
        "minlatitude": args.minlatitude,
        "maxlatitude": args.maxlatitude,
        "minlongitude": args.minlongitude,
        "maxlongitude": args.maxlongitude,
        "orderby": "time-asc",
    }
    return USGS_EVENT_URL + "?" + urllib.parse.urlencode(params)


def fetch_events(args: argparse.Namespace) -> tuple[list[Event], str]:
    url = build_usgs_url(args)
    payload = fetch_json(url)
    features = payload.get("features", []) if isinstance(payload, dict) else []
    events: list[Event] = []
    for feature in features:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates") or []
        if len(coords) < 3:
            continue
        mag = props.get("mag")
        timestamp = props.get("time")
        if mag is None or timestamp is None:
            continue
        events.append(
            Event(
                event_id=str(feature.get("id") or ""),
                title=str(props.get("title") or ""),
                time_utc=normalize_time_ms(timestamp),
                longitude=float(coords[0]),
                latitude=float(coords[1]),
                depth_km=None if coords[2] is None else float(coords[2]),
                magnitude=float(mag),
                mag_type=str(props.get("magType") or ""),
                place=str(props.get("place") or ""),
                event_type=str(props.get("type") or ""),
                usgs_url=str(props.get("url") or ""),
            )
        )
    return events, url


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS renag_usgs_events (
            event_id TEXT PRIMARY KEY,
            title TEXT,
            time_utc TEXT NOT NULL,
            event_date TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            magnitude REAL NOT NULL,
            mag_type TEXT,
            longitude REAL NOT NULL,
            latitude REAL NOT NULL,
            depth_km REAL,
            place TEXT,
            event_type TEXT,
            usgs_url TEXT,
            query_url TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_renag_usgs_events_date ON renag_usgs_events(event_date)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS renag_day_availability (
            event_id TEXT NOT NULL,
            date TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            has_1hz INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            station_count INTEGER NOT NULL,
            stations TEXT NOT NULL,
            listing_url TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            PRIMARY KEY (event_id, date),
            FOREIGN KEY(event_id) REFERENCES renag_usgs_events(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_renag_day_available ON renag_day_availability(has_1hz, date)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_renag_station_candidates (
            event_id TEXT NOT NULL,
            station TEXT NOT NULL,
            event_date TEXT NOT NULL,
            radius_km REAL NOT NULL,
            distance_km REAL NOT NULL,
            station_latitude REAL NOT NULL,
            station_longitude REAL NOT NULL,
            station_available_on_event_day INTEGER NOT NULL,
            metadata_file TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (event_id, station, radius_km),
            FOREIGN KEY(event_id) REFERENCES renag_usgs_events(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_renag_candidates_event ON event_renag_station_candidates(event_id)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS build_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def write_db(conn: sqlite3.Connection, events: list[Event], query_url: str, args: argparse.Namespace) -> None:
    init_db(conn)
    updated_at = utc_now()
    with conn:
        conn.execute("DELETE FROM event_renag_station_candidates")
        conn.execute("DELETE FROM renag_day_availability")
        conn.execute("DELETE FROM renag_usgs_events")
        conn.executemany(
            """
            INSERT OR REPLACE INTO renag_usgs_events (
                event_id, title, time_utc, event_date, year, doy, magnitude, mag_type,
                longitude, latitude, depth_km, place, event_type, usgs_url, query_url, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event.event_id,
                    event.title,
                    event.time_utc,
                    event.event_date,
                    event.year,
                    event.doy,
                    event.magnitude,
                    event.mag_type,
                    event.longitude,
                    event.latitude,
                    event.depth_km,
                    event.place,
                    event.event_type,
                    event.usgs_url,
                    query_url,
                    updated_at,
                )
                for event in events
            ],
        )
        day_station_map: dict[str, set[str]] = {}
        if args.check_availability:
            rows = []
            for event in events:
                doy = normalize_doy(event.doy)
                try:
                    files = list_day_files(event.year, doy)
                except RuntimeError:
                    files = []
                stations = sorted({item.station for item in files})
                day_station_map[event.event_id] = set(stations)
                rows.append(
                    (
                        event.event_id,
                        event.event_date,
                        event.year,
                        doy,
                        1 if files else 0,
                        len(files),
                        len(stations),
                        " ".join(stations),
                        day_url(event.year, doy),
                        updated_at,
                    )
                )
            conn.executemany(
                """
                INSERT OR REPLACE INTO renag_day_availability (
                    event_id, date, year, doy, has_1hz, file_count, station_count,
                    stations, listing_url, checked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        if args.inventory:
            inventory_rows = read_inventory(Path(args.inventory))
            candidate_rows = []
            for event in events:
                available = day_station_map.get(event.event_id)
                for station in inventory_rows:
                    station_id = station["station"]
                    if available is not None and station_id not in available:
                        continue
                    distance = haversine_km(event.latitude, event.longitude, station["latitude"], station["longitude"])
                    if distance > args.radius_km:
                        continue
                    candidate_rows.append(
                        (
                            event.event_id,
                            station_id,
                            event.event_date,
                            args.radius_km,
                            distance,
                            station["latitude"],
                            station["longitude"],
                            1 if available is None or station_id in available else 0,
                            station.get("metadata_file", ""),
                            updated_at,
                        )
                    )
            conn.executemany(
                """
                INSERT OR REPLACE INTO event_renag_station_candidates (
                    event_id, station, event_date, radius_km, distance_km,
                    station_latitude, station_longitude, station_available_on_event_day,
                    metadata_file, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                candidate_rows,
            )
        conn.executemany(
            "INSERT OR REPLACE INTO build_metadata(key, value) VALUES (?, ?)",
            [
                ("source", "Rénag + USGS ComCat"),
                ("event_service", USGS_EVENT_URL),
                ("event_query_url", query_url),
                ("starttime", args.starttime),
                ("endtime", args.endtime),
                ("min_magnitude", str(args.min_magnitude)),
                ("bbox", f"{args.minlongitude},{args.minlatitude},{args.maxlongitude},{args.maxlatitude}"),
                ("availability_checked", "1" if args.check_availability else "0"),
                ("inventory", args.inventory),
                ("radius_km", str(args.radius_km)),
                ("updated_at", updated_at),
            ],
        )


def read_inventory(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                rows.append(
                    {
                        **row,
                        "station": str(row["station"]).upper(),
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                    }
                )
            except (KeyError, ValueError):
                continue
    return rows


def write_batch_csv(conn: sqlite3.Connection, path: Path, max_stations: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT e.event_id, e.time_utc, e.latitude, e.longitude, e.magnitude,
               COALESCE(a.stations, '') AS available_stations,
               COALESCE(a.has_1hz, 0) AS has_1hz
        FROM renag_usgs_events e
        LEFT JOIN renag_day_availability a USING(event_id)
        ORDER BY e.time_utc, e.event_id
        """
    ).fetchall()
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["event_id", "event_time", "latitude", "longitude", "magnitude", "radius_km", "stations", "status"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            candidate_rows = conn.execute(
                """
                SELECT station
                FROM event_renag_station_candidates
                WHERE event_id = ?
                ORDER BY distance_km, station
                """,
                (row["event_id"],),
            ).fetchall()
            stations = [candidate["station"] for candidate in candidate_rows]
            if not stations:
                stations = str(row["available_stations"] or "").split()
            if max_stations > 0:
                stations = stations[:max_stations]
            status = "" if int(row["has_1hz"]) and stations else "NO_RENAG_RADIUS_STATIONS"
            writer.writerow(
                {
                    "event_id": row["event_id"],
                    "event_time": row["time_utc"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "magnitude": row["magnitude"],
                    "radius_km": "",
                    "stations": " ".join(stations),
                    "status": status,
                }
            )


def main() -> int:
    args = parse_args()
    events, query_url = fetch_events(args)
    print(f"USGS events: {len(events)}", file=sys.stderr)
    print(f"USGS query: {query_url}", file=sys.stderr)
    if args.dry_run:
        return 0

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        write_db(conn, events, query_url, args)
        if args.write_batch_csv:
            write_batch_csv(conn, Path(args.write_batch_csv), args.max_batch_stations)
    finally:
        conn.close()
    print(f"Wrote Rénag trial database: {db_path}")
    if args.write_batch_csv:
        print(f"Wrote Rénag trial batch CSV: {args.write_batch_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
