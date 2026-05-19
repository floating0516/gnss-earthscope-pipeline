#!/usr/bin/env python3
"""Build a Geoscience Australia Southwest Pacific earthquake/station SQLite database."""

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
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GA_TOOLS = ROOT / "tools" / "ga_downloader"
if str(GA_TOOLS) not in sys.path:
    sys.path.insert(0, str(GA_TOOLS))

from ga_common import GA_METADATA_API_URL, haversine_km, normalize_station, parse_utc  # noqa: E402

csv.field_size_limit(sys.maxsize)

DEFAULT_DB = ROOT / "data" / "ga_availability" / "ga_1hz.sqlite"
DEFAULT_STATION_CSV = ROOT / "data" / "ga_inventory" / "ga_gnss_stations.csv"
DEFAULT_BATCH_CSV = ROOT / "data" / "ga_batches" / "ga_m6plus_au_candidates_300km.csv"
USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


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
    title: str
    usgs_url: str

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
    parser.add_argument("--write-batch-csv", default=str(DEFAULT_BATCH_CSV))
    parser.add_argument("--starttime", default="2010-01-01T00:00:00")
    parser.add_argument("--endtime", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    parser.add_argument("--min-magnitude", type=float, default=6.0)
    parser.add_argument("--minlat", type=float, default=-55.0)
    parser.add_argument("--maxlat", type=float, default=5.0)
    parser.add_argument("--minlon", type=float, default=90.0)
    parser.add_argument("--maxlon", type=float, default=180.0)
    parser.add_argument("--radius-km", type=float, action="append", default=[300.0, 500.0, 800.0])
    parser.add_argument("--batch-radius-km", type=float, default=300.0)
    parser.add_argument("--max-batch-stations", type=int, default=12)
    parser.add_argument("--metadata-api-url", default=GA_METADATA_API_URL)
    parser.add_argument("--metadata-page-size", type=int, default=100)
    parser.add_argument("--metadata-max-pages", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def iso_utc_from_ms(value: int | float) -> str:
    return dt.datetime.fromtimestamp(float(value) / 1000.0, tz=dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fetch_json(url: str, timeout: int = 90) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-earthscope-pipeline ga-builder"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_usgs_url(args: argparse.Namespace) -> str:
    params = {
        "format": "geojson",
        "starttime": args.starttime,
        "endtime": args.endtime,
        "minmagnitude": args.min_magnitude,
        "minlatitude": args.minlat,
        "maxlatitude": args.maxlat,
        "minlongitude": args.minlon,
        "maxlongitude": args.maxlon,
        "orderby": "time-asc",
    }
    return USGS_EVENT_URL + "?" + urllib.parse.urlencode(params)


def parse_events(payload: Any) -> list[Event]:
    if not isinstance(payload, dict):
        return []
    events: list[Event] = []
    for feature in payload.get("features", []):
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties", {}) if isinstance(feature.get("properties"), dict) else {}
        geometry = feature.get("geometry", {}) if isinstance(feature.get("geometry"), dict) else {}
        coords = geometry.get("coordinates", []) if isinstance(geometry.get("coordinates"), list) else []
        if len(coords) < 3 or props.get("mag") is None or props.get("time") is None:
            continue
        try:
            longitude = float(coords[0])
            latitude = float(coords[1])
            depth = float(coords[2])
            magnitude = float(props["mag"])
        except (TypeError, ValueError):
            continue
        events.append(
            Event(
                event_id=str(feature.get("id") or props.get("code") or ""),
                time_utc=iso_utc_from_ms(props["time"]),
                latitude=latitude,
                longitude=longitude,
                depth_km=depth,
                magnitude=magnitude,
                mag_type=str(props.get("magType") or ""),
                place=str(props.get("place") or ""),
                title=str(props.get("title") or ""),
                usgs_url=str(props.get("url") or ""),
            )
        )
    return sorted(events, key=lambda item: (item.time_utc, item.event_id))


def first_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, list):
        return first_text(value[0]) if value else ""
    if isinstance(value, dict):
        for key in ("value", "text", "name", "id"):
            if key in value:
                return first_text(value[key])
    return ""


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def coordinates_from_site(site: dict[str, Any]) -> tuple[float, float, float | None] | None:
    candidates = [
        nested(site, "siteLocation", "approximatePosition", "geodeticPosition", "coordinates"),
        nested(site, "siteLocation", "approximatePosition", "geodeticPosition"),
        nested(site, "siteLocation", "approximatePosition"),
        nested(site, "siteLocation"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and len(candidate) >= 2:
            try:
                lat = float(candidate[0])
                lon = float(candidate[1])
                height = float(candidate[2]) if len(candidate) > 2 and candidate[2] is not None else None
                return lat, lon, height
            except (TypeError, ValueError):
                continue
        if isinstance(candidate, dict):
            lat_raw = candidate.get("latitude") or candidate.get("lat")
            lon_raw = candidate.get("longitude") or candidate.get("lon") or candidate.get("lng")
            height_raw = candidate.get("height") or candidate.get("height_m") or candidate.get("ellipsoidalHeight")
            try:
                if lat_raw is not None and lon_raw is not None:
                    height = float(height_raw) if height_raw not in {None, ""} else None
                    return float(lat_raw), float(lon_raw), height
            except (TypeError, ValueError):
                continue
    return None


def site_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    embedded = payload.get("_embedded")
    if isinstance(embedded, dict) and isinstance(embedded.get("siteLogs"), list):
        return [item for item in embedded["siteLogs"] if isinstance(item, dict)]
    for key in ("siteLogs", "records", "data", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if isinstance(payload.get("features"), list):
        rows = []
        for feature in payload["features"]:
            if isinstance(feature, dict):
                props = feature.get("properties")
                rows.append(props if isinstance(props, dict) else feature)
        return rows
    return [payload]


def parse_station_inventory(payload: Any) -> list[dict[str, str]]:
    stations: dict[str, dict[str, str]] = {}
    for site in site_records(payload):
        ident = nested(site, "siteIdentification") or site
        four = normalize_station(first_text(nested(ident, "fourCharacterId") or ident.get("fourCharacterId") or ident.get("siteId") or ident.get("station")))
        nine = first_text(nested(ident, "nineCharacterId") or ident.get("nineCharacterId") or ident.get("site9") or ident.get("station9"))
        if not four and nine:
            four = normalize_station(nine)
        coords = coordinates_from_site(site)
        if not four or coords is None:
            continue
        lat, lon, height = coords
        stations[four] = {
            "station": four,
            "station9": nine,
            "four_character_id": first_text(nested(ident, "fourCharacterId") or ident.get("fourCharacterId") or four),
            "nine_character_id": nine,
            "name": first_text(nested(ident, "siteName") or ident.get("siteName") or ident.get("name")),
            "country": first_text(nested(site, "siteLocation", "country") or site.get("country")),
            "latitude": f"{lat:.8f}",
            "longitude": f"{lon:.8f}",
            "height_m": "" if height is None else f"{height:.4f}",
            "date_installed": first_text(nested(ident, "dateInstalled") or ident.get("dateInstalled") or site.get("dateInstalled")),
            "metadata_json": json.dumps(site, ensure_ascii=False, sort_keys=True),
        }
    return [stations[key] for key in sorted(stations)]


def fetch_station_inventory(path: Path, api_url: str, page_size: int = 100, max_pages: int = 100) -> list[dict[str, str]]:
    rows: list[dict[str, Any]] = []
    if "?" in api_url:
        payload = fetch_json(api_url)
        rows = site_records(payload)
    else:
        for page in range(max_pages):
            query = api_url + "?" + urllib.parse.urlencode({"format": "json", "page": page, "size": page_size})
            payload = fetch_json(query)
            page_rows = site_records(payload)
            rows.extend(page_rows)
            page_info = payload.get("page") if isinstance(payload, dict) else None
            if not page_rows:
                break
            if isinstance(page_info, dict):
                total_pages = page_info.get("totalPages")
                if isinstance(total_pages, int) and page + 1 >= total_pages:
                    break
            elif len(page_rows) < page_size:
                break
    stations = parse_station_inventory(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "station",
        "station9",
        "four_character_id",
        "nine_character_id",
        "name",
        "country",
        "latitude",
        "longitude",
        "height_m",
        "date_installed",
        "metadata_json",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(stations)
    return stations


def read_stations(path: Path, api_url: str, page_size: int = 100, max_pages: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        fetch_station_inventory(path, api_url, page_size=page_size, max_pages=max_pages)
    stations: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except (KeyError, ValueError):
                continue
            station = normalize_station(row.get("station") or row.get("station9") or "")
            if station:
                stations.append({**row, "station": station, "latitude": lat, "longitude": lon})
    return stations


def station_active_at(station: dict[str, Any], event_time: str) -> bool:
    installed = str(station.get("date_installed") or "")
    if not installed:
        return True
    try:
        return parse_utc(event_time) >= parse_utc(installed)
    except ValueError:
        return True


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ga_m6plus_events_au (
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
            usgs_url TEXT,
            query_start TEXT NOT NULL,
            query_end TEXT NOT NULL,
            min_magnitude REAL NOT NULL,
            region_filter TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ga_m6plus_events_au_date ON ga_m6plus_events_au(event_date)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ga_gnss_stations (
            station TEXT PRIMARY KEY,
            station9 TEXT,
            four_character_id TEXT,
            nine_character_id TEXT,
            name TEXT,
            country TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            height_m REAL,
            date_installed TEXT,
            metadata_json TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ga_gnss_stations_country ON ga_gnss_stations(country)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_ga_station_candidates (
            event_id TEXT NOT NULL,
            station TEXT NOT NULL,
            event_date TEXT NOT NULL,
            radius_km REAL NOT NULL,
            distance_km REAL NOT NULL,
            station_latitude REAL NOT NULL,
            station_longitude REAL NOT NULL,
            station9 TEXT,
            country TEXT,
            station_active_at_event INTEGER NOT NULL,
            availability_source TEXT NOT NULL,
            metadata_file TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (event_id, station, radius_km),
            FOREIGN KEY(event_id) REFERENCES ga_m6plus_events_au(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_ga_candidates_event ON event_ga_station_candidates(event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_ga_candidates_radius ON event_ga_station_candidates(radius_km)")
    conn.execute("CREATE TABLE IF NOT EXISTS build_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")


def optional_float(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def write_db(conn: sqlite3.Connection, events: list[Event], stations: list[dict[str, Any]], args: argparse.Namespace, query_url: str) -> None:
    init_db(conn)
    updated_at = utc_now()
    radii = sorted(set(float(radius) for radius in args.radius_km))
    region_filter = f"USGS_bbox_{args.minlat}_{args.maxlat}_{args.minlon}_{args.maxlon}"
    station_file = str(Path(args.station_csv))
    with conn:
        conn.execute("DELETE FROM event_ga_station_candidates")
        conn.execute("DELETE FROM ga_m6plus_events_au")
        conn.execute("DELETE FROM ga_gnss_stations")
        conn.executemany(
            """
            INSERT OR REPLACE INTO ga_m6plus_events_au (
                event_id, title, time_utc, event_date, year, doy, magnitude, mag_type,
                longitude, latitude, depth_km, place, usgs_url, query_start, query_end,
                min_magnitude, region_filter, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event.event_id,
                    event.title or f"M{event.magnitude:.1f} - {event.place}",
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
                    event.usgs_url,
                    args.starttime,
                    args.endtime,
                    args.min_magnitude,
                    region_filter,
                    updated_at,
                )
                for event in events
            ],
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO ga_gnss_stations (
                station, station9, four_character_id, nine_character_id, name, country,
                latitude, longitude, height_m, date_installed, metadata_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    station["station"],
                    str(station.get("station9") or ""),
                    str(station.get("four_character_id") or ""),
                    str(station.get("nine_character_id") or ""),
                    str(station.get("name") or ""),
                    str(station.get("country") or ""),
                    float(station["latitude"]),
                    float(station["longitude"]),
                    optional_float(station.get("height_m")),
                    str(station.get("date_installed") or ""),
                    str(station.get("metadata_json") or ""),
                    updated_at,
                )
                for station in stations
            ],
        )
        candidate_rows = []
        for event in events:
            for station in stations:
                if not station_active_at(station, event.time_utc):
                    continue
                distance = haversine_km(event.latitude, event.longitude, float(station["latitude"]), float(station["longitude"]))
                for radius in radii:
                    if distance <= radius:
                        candidate_rows.append(
                            (
                                event.event_id,
                                station["station"],
                                event.event_date,
                                radius,
                                distance,
                                float(station["latitude"]),
                                float(station["longitude"]),
                                str(station.get("station9") or ""),
                                str(station.get("country") or ""),
                                1,
                                "ga_metadata_active_at_event",
                                station_file,
                                updated_at,
                            )
                        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO event_ga_station_candidates (
                event_id, station, event_date, radius_km, distance_km,
                station_latitude, station_longitude, station9, country,
                station_active_at_event, availability_source, metadata_file, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            candidate_rows,
        )
        conn.executemany(
            "INSERT OR REPLACE INTO build_metadata(key, value) VALUES (?, ?)",
            [
                ("source", "Geoscience Australia + USGS ComCat"),
                ("event_service", USGS_EVENT_URL),
                ("station_service", args.metadata_api_url),
                ("event_query_url", query_url),
                ("starttime", args.starttime),
                ("endtime", args.endtime),
                ("min_magnitude", str(args.min_magnitude)),
                ("region_filter", region_filter),
                ("radii_km", ",".join(str(radius) for radius in radii)),
                ("station_csv", station_file),
                ("updated_at", updated_at),
            ],
        )


def write_batch_csv(conn: sqlite3.Connection, path: Path, radius_km: float, max_stations: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    events = conn.execute(
        """
        SELECT event_id, time_utc, latitude, longitude, magnitude
        FROM ga_m6plus_events_au
        ORDER BY event_date, event_id
        """
    ).fetchall()
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["event_id", "event_time", "latitude", "longitude", "magnitude", "radius_km", "stations", "status"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for event in events:
            rows = conn.execute(
                """
                SELECT station
                FROM event_ga_station_candidates
                WHERE event_id = ? AND radius_km = ?
                ORDER BY distance_km, station
                """,
                (event["event_id"], radius_km),
            ).fetchall()
            stations = [row["station"] for row in rows]
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
    query_url = build_usgs_url(args)
    events = parse_events(fetch_json(query_url))
    stations = read_stations(
        Path(args.station_csv),
        args.metadata_api_url,
        page_size=args.metadata_page_size,
        max_pages=args.metadata_max_pages,
    )
    print(f"GA-region USGS events: {len(events)}", file=sys.stderr)
    print(f"GA stations: {len(stations)}", file=sys.stderr)
    if args.dry_run:
        print(f"USGS query: {query_url}")
        return 0

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        write_db(conn, events, stations, args, query_url)
        if args.write_batch_csv:
            write_batch_csv(conn, Path(args.write_batch_csv), args.batch_radius_km, args.max_batch_stations)
    finally:
        conn.close()
    print(f"Wrote GA database: {db_path}")
    if args.write_batch_csv:
        print(f"Wrote GA batch CSV: {args.write_batch_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
