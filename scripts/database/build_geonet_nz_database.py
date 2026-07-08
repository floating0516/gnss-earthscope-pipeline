#!/usr/bin/env python3
"""Build a GeoNet New Zealand earthquake/station SQLite database."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import sqlite3
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gnss_eq.station_siting import ensure_station_siting_table, upsert_station_siting

DEFAULT_DB = ROOT / "data" / "geonet_availability" / "geonet_1hz.sqlite"
DEFAULT_STATION_CSV = ROOT / "data" / "geonet_inventory" / "geonet_gnss_stations_all.csv"
DEFAULT_BATCH_CSV = ROOT / "data" / "geonet_batches" / "geonet_m6plus_nz_candidates_300km.csv"
DEFAULT_AVAILABILITY_DIR = ROOT / "data" / "geonet_availability"
GEONET_EVENT_URL = "https://service.geonet.org.nz/fdsnws/event/1/query"
GEONET_STATION_URL = "https://api.geonet.org.nz/network/station?sensorType=8&endDate=9999-01-01"
EARTH_RADIUS_KM = 6371.0088

# Split the NZ/Kermadec bounding box at the antimeridian.
NZ_REGION_BOXES = [
    {"minlatitude": -55, "maxlatitude": -25, "minlongitude": 160, "maxlongitude": 180},
    {"minlatitude": -55, "maxlatitude": -25, "minlongitude": -180, "maxlongitude": -170},
]


@dataclass(frozen=True)
class Event:
    event_id: str
    time_utc: str
    latitude: float
    longitude: float
    depth_km: float | None
    magnitude: float
    mag_type: str
    place: str
    event_type: str
    author: str
    catalog: str
    contributor: str
    contributor_id: str
    mag_author: str

    @property
    def event_date(self) -> str:
        return self.time_utc[:10]

    @property
    def year(self) -> int:
        return int(self.time_utc[:4])

    @property
    def doy(self) -> int:
        return int(parse_utc(self.time_utc).strftime("%j"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--station-csv", default=str(DEFAULT_STATION_CSV))
    parser.add_argument("--availability-dir", default=str(DEFAULT_AVAILABILITY_DIR))
    parser.add_argument("--starttime", default="2010-01-01T00:00:00")
    parser.add_argument("--endtime", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    parser.add_argument("--min-magnitude", type=float, default=6.0)
    parser.add_argument("--radius-km", type=float, action="append", default=[200.0, 300.0])
    parser.add_argument("--write-batch-csv", default=str(DEFAULT_BATCH_CSV))
    parser.add_argument("--batch-radius-km", type=float, default=300.0)
    parser.add_argument("--max-batch-stations", type=int, default=12)
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


def normalize_time(value: str) -> str:
    return parse_utc(value).isoformat().replace("+00:00", "Z")


def fetch_text(url: str, timeout: int = 60) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-earthscope-pipeline geonet-db"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def build_event_url(starttime: str, endtime: str, min_magnitude: float, box: dict[str, float]) -> str:
    params: dict[str, object] = {
        "starttime": starttime,
        "endtime": endtime,
        "minmagnitude": min_magnitude,
        "eventtype": "earthquake",
        "format": "text",
    }
    params.update(box)
    return GEONET_EVENT_URL + "?" + urllib.parse.urlencode(params)


def parse_float(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_event_text(text: str) -> list[Event]:
    rows: list[Event] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 14:
            continue
        depth = parse_float(parts[4])
        magnitude = parse_float(parts[10])
        latitude = parse_float(parts[2])
        longitude = parse_float(parts[3])
        if magnitude is None or latitude is None or longitude is None:
            continue
        rows.append(
            Event(
                event_id=parts[0],
                time_utc=normalize_time(parts[1]),
                latitude=latitude,
                longitude=longitude,
                depth_km=depth,
                author=parts[5],
                catalog=parts[6],
                contributor=parts[7],
                contributor_id=parts[8],
                mag_type=parts[9],
                magnitude=magnitude,
                mag_author=parts[11],
                place=parts[12],
                event_type=parts[13],
            )
        )
    return rows


def fetch_events(starttime: str, endtime: str, min_magnitude: float) -> tuple[list[Event], list[str]]:
    by_id: dict[str, Event] = {}
    urls: list[str] = []
    for box in NZ_REGION_BOXES:
        url = build_event_url(starttime, endtime, min_magnitude, box)
        urls.append(url)
        for event in parse_event_text(fetch_text(url)):
            existing = by_id.get(event.event_id)
            if existing is None or event.time_utc < existing.time_utc:
                by_id[event.event_id] = event
    return sorted(by_id.values(), key=lambda item: (item.time_utc, item.event_id)), urls


def fetch_station_inventory(path: Path) -> None:
    payload = json.loads(fetch_text(GEONET_STATION_URL))
    features = payload.get("features", [])
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "station",
        "station9",
        "network",
        "name",
        "latitude",
        "longitude",
        "start",
        "end",
        "sensor_type",
        "source",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for feature in features:
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates") or []
            code = str(props.get("Code", "")).upper()
            if len(coords) < 2 or not code:
                continue
            writer.writerow(
                {
                    "station": code,
                    "station9": f"{code}00NZL" if len(code) == 4 else code,
                    "network": props.get("Network", ""),
                    "name": props.get("Name", ""),
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "start": props.get("Start", ""),
                    "end": props.get("End", ""),
                    "sensor_type": props.get("SensorType", ""),
                    "source": "GeoNet",
                }
            )


def read_stations(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        fetch_station_inventory(path)
    stations: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (KeyError, ValueError):
                continue
            stations.append({**row, "latitude": lat, "longitude": lon})
    return stations


def station_active_at(station: dict[str, object], event_time: str) -> bool:
    start = str(station.get("start") or "")
    end = str(station.get("end") or "")
    instant = parse_utc(event_time)
    if start:
        try:
            if instant < parse_utc(start):
                return False
        except ValueError:
            pass
    if end and not end.startswith("9999-"):
        try:
            if instant > parse_utc(end):
                return False
        except ValueError:
            pass
    return True


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS geonet_m6plus_events_nz (
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
            geonet_url TEXT,
            query_start TEXT NOT NULL,
            query_end TEXT NOT NULL,
            min_magnitude REAL NOT NULL,
            region_filter TEXT NOT NULL,
            event_type TEXT,
            author TEXT,
            catalog TEXT,
            contributor TEXT,
            contributor_id TEXT,
            mag_author TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_geonet_m6plus_events_nz_date ON geonet_m6plus_events_nz(event_date)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS geonet_gnss_stations (
            station TEXT PRIMARY KEY,
            station9 TEXT,
            network TEXT,
            name TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            start TEXT,
            end TEXT,
            sensor_type TEXT,
            source TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_geonet_gnss_stations_network ON geonet_gnss_stations(network)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_geonet_station_candidates (
            event_id TEXT NOT NULL,
            station TEXT NOT NULL,
            event_date TEXT NOT NULL,
            radius_km REAL NOT NULL,
            distance_km REAL NOT NULL,
            station_latitude REAL NOT NULL,
            station_longitude REAL NOT NULL,
            station9 TEXT,
            network TEXT,
            station_active_at_event INTEGER NOT NULL,
            availability_source TEXT NOT NULL,
            metadata_file TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (event_id, station, radius_km),
            FOREIGN KEY(event_id) REFERENCES geonet_m6plus_events_nz(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_geonet_candidates_event ON event_geonet_station_candidates(event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_geonet_candidates_radius ON event_geonet_station_candidates(radius_km)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS station_day_availability (
            station TEXT NOT NULL,
            date TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            has_1hz INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL,
            listing_url TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            PRIMARY KEY (station, date)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_geonet_station_day_date ON station_day_availability(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_geonet_station_day_station ON station_day_availability(station)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS build_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    ensure_station_siting_table(conn)


def date_from_year_doy(year: int, doy: int) -> str:
    return (dt.date(year, 1, 1) + dt.timedelta(days=doy - 1)).isoformat()


def read_availability_snapshots(path: Path) -> list[tuple[str, str, int, int, int, str, str, str]]:
    rows: list[tuple[str, str, int, int, int, str, str, str]] = []
    checked_at = utc_now()
    if not path.exists():
        return rows
    for tsv in sorted(path.glob("geonet_1hz_*.tsv")):
        parts = tsv.stem.split("_")
        if len(parts) < 4:
            continue
        try:
            year = int(parts[-2])
            doy = int(parts[-1])
        except ValueError:
            continue
        event_date = date_from_year_doy(year, doy)
        listing_url = f"https://data.geonet.org.nz/v1/data/gnss/rinex1Hz/{year}/{doy:03d}/"
        stations: set[str] = set()
        with tsv.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                station = str(row.get("station4") or row.get("station") or "").strip().upper()
                if len(station) > 4:
                    station = station[:4]
                if station:
                    stations.add(station)
        for station in sorted(stations):
            rows.append((station, event_date, year, doy, 1, "GeoNet", listing_url, checked_at))
    return rows


def write_db(
    conn: sqlite3.Connection,
    events: list[Event],
    stations: list[dict[str, object]],
    args: argparse.Namespace,
    source_urls: list[str],
) -> None:
    init_db(conn)
    updated_at = utc_now()
    radii = sorted(set(float(radius) for radius in args.radius_km))
    region_filter = "NZ_Kermadec_bbox_split_antimeridian"
    station_file = str(Path(args.station_csv))

    with conn:
        conn.execute("DELETE FROM event_geonet_station_candidates")
        conn.execute("DELETE FROM geonet_m6plus_events_nz")
        conn.execute("DELETE FROM geonet_gnss_stations")
        conn.execute("DELETE FROM station_day_availability")
        conn.execute("DELETE FROM station_siting_metadata WHERE provider = 'GeoNet'")
        conn.executemany(
            """
            INSERT OR REPLACE INTO geonet_m6plus_events_nz (
                event_id, title, time_utc, event_date, year, doy, magnitude, mag_type,
                longitude, latitude, depth_km, place, geonet_url, query_start, query_end,
                min_magnitude, region_filter, event_type, author, catalog, contributor,
                contributor_id, mag_author, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event.event_id,
                    f"M{event.magnitude:.1f} - {event.place}",
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
                    f"https://www.geonet.org.nz/earthquake/{event.event_id}",
                    args.starttime,
                    args.endtime,
                    args.min_magnitude,
                    region_filter,
                    event.event_type,
                    event.author,
                    event.catalog,
                    event.contributor,
                    event.contributor_id,
                    event.mag_author,
                    updated_at,
                )
                for event in events
            ],
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO geonet_gnss_stations (
                station, station9, network, name, latitude, longitude, start, end,
                sensor_type, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(station.get("station") or "").upper(),
                    str(station.get("station9") or ""),
                    str(station.get("network") or ""),
                    str(station.get("name") or ""),
                    float(station["latitude"]),
                    float(station["longitude"]),
                    str(station.get("start") or ""),
                    str(station.get("end") or ""),
                    str(station.get("sensor_type") or ""),
                    str(station.get("source") or "GeoNet"),
                    updated_at,
                )
                for station in stations
                if str(station.get("station") or "").strip()
            ],
        )
        for station in stations:
            station_code = str(station.get("station") or "").strip().upper()
            if not station_code:
                continue
            upsert_station_siting(
                conn,
                provider="GeoNet",
                station=station_code,
                station9=str(station.get("station9") or ""),
                station_name=str(station.get("name") or ""),
                latitude=float(station["latitude"]),
                longitude=float(station["longitude"]),
                monument_style="UNKNOWN",
                siting_source="GeoNet station inventory",
                raw_metadata=station,
                updated_at=updated_at,
            )

        candidate_rows = []
        for event in events:
            for station in stations:
                active = station_active_at(station, event.time_utc)
                if not active:
                    continue
                distance = haversine_km(
                    event.latitude,
                    event.longitude,
                    float(station["latitude"]),
                    float(station["longitude"]),
                )
                for radius in radii:
                    if distance <= radius:
                        candidate_rows.append(
                            (
                                event.event_id,
                                str(station.get("station") or "").upper(),
                                event.event_date,
                                radius,
                                distance,
                                float(station["latitude"]),
                                float(station["longitude"]),
                                str(station.get("station9") or ""),
                                str(station.get("network") or ""),
                                1,
                                "geonet_inventory_active_at_event",
                                station_file,
                                updated_at,
                            )
                        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO event_geonet_station_candidates (
                event_id, station, event_date, radius_km, distance_km,
                station_latitude, station_longitude, station9, network,
                station_active_at_event, availability_source, metadata_file, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            candidate_rows,
        )
        availability_rows = read_availability_snapshots(Path(args.availability_dir))
        conn.executemany(
            """
            INSERT OR REPLACE INTO station_day_availability (
                station, date, year, doy, has_1hz, source, listing_url, checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            availability_rows,
        )
        conn.executemany(
            "INSERT OR REPLACE INTO build_metadata(key, value) VALUES (?, ?)",
            [
                ("source", "GeoNet"),
                ("event_service", GEONET_EVENT_URL),
                ("station_service", GEONET_STATION_URL),
                ("event_query_urls", json.dumps(source_urls, ensure_ascii=False)),
                ("starttime", args.starttime),
                ("endtime", args.endtime),
                ("min_magnitude", str(args.min_magnitude)),
                ("region_filter", region_filter),
                ("radii_km", ",".join(str(radius) for radius in radii)),
                ("availability_dir", str(Path(args.availability_dir))),
                ("availability_rows", str(len(availability_rows))),
                ("updated_at", updated_at),
            ],
        )


def write_batch_csv(conn: sqlite3.Connection, path: Path, radius_km: float, max_stations: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event_rows = conn.execute(
        """
        SELECT event_id, time_utc, latitude, longitude, magnitude
        FROM geonet_m6plus_events_nz
        ORDER BY event_date, event_id
        """
    ).fetchall()
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["event_id", "event_time", "latitude", "longitude", "magnitude", "radius_km", "stations", "status"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for event in event_rows:
            station_rows = conn.execute(
                """
                SELECT station
                FROM event_geonet_station_candidates
                WHERE event_id = ? AND radius_km = ?
                ORDER BY distance_km, station
                """,
                (event["event_id"], radius_km),
            ).fetchall()
            stations = [row["station"] for row in station_rows]
            if max_stations > 0:
                stations = stations[:max_stations]
            writer.writerow(
                {
                    "event_id": event["event_id"],
                    "event_time": event["time_utc"],
                    "latitude": event["latitude"],
                    "longitude": event["longitude"],
                    "magnitude": event["magnitude"],
                    "radius_km": radius_km,
                    "stations": " ".join(stations),
                    "status": "" if stations else "NO_STATIONS",
                }
            )


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    station_csv = Path(args.station_csv)
    events, source_urls = fetch_events(args.starttime, args.endtime, args.min_magnitude)
    stations = read_stations(station_csv)
    print(f"GeoNet events: {len(events)}", file=sys.stderr)
    print(f"GeoNet stations: {len(stations)}", file=sys.stderr)
    if args.dry_run:
        return 0

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        write_db(conn, events, stations, args, source_urls)
        if args.write_batch_csv:
            write_batch_csv(conn, Path(args.write_batch_csv), args.batch_radius_km, args.max_batch_stations)
    finally:
        conn.close()
    print(f"Wrote GeoNet NZ database: {db_path}")
    if args.write_batch_csv:
        print(f"Wrote GeoNet batch CSV: {args.write_batch_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
