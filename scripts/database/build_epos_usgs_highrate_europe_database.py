#!/usr/bin/env python3
"""Build a USGS Europe M6+ / EPOS GNSS high-rate availability database."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "epos_availability" / "epos_usgs_m6plus_europe.sqlite"
DEFAULT_EVENT_CSV = ROOT / "data" / "epos_batches" / "epos_usgs_m6plus_europe_events.csv"
DEFAULT_STATION_CSV = ROOT / "data" / "epos_inventory" / "epos_highrate_stations_europe.csv"
DEFAULT_SUMMARY_CSV = ROOT / "data" / "epos_availability" / "epos_highrate_m6plus_europe_availability.csv"
DEFAULT_FILES_TSV = ROOT / "data" / "epos_availability" / "epos_highrate_m6plus_europe_files.tsv"
DEFAULT_BATCH_CSV = ROOT / "data" / "epos_batches" / "epos_usgs_m6plus_europe_highrate_candidates_300km.csv"
USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
EPOS_HIGHRATE_STATION_URL = "https://gnssdata-epos.oca.eu/GlassFramework/webresources/stations/v2/highrate/bbox/{minlon}/{minlat}/{maxlon}/{maxlat}"
EARTH_RADIUS_KM = 6371.0088
RINEX2_HOUR_CODES = "abcdefghijklmnopqrstuvwx"


@dataclass(frozen=True)
class Event:
    event_id: str
    time_utc: str
    year: int
    doy: int
    magnitude: float
    latitude: float
    longitude: float
    depth_km: float | None
    place: str
    title: str
    usgs_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out-event-csv", default=str(DEFAULT_EVENT_CSV))
    parser.add_argument("--out-station-csv", default=str(DEFAULT_STATION_CSV))
    parser.add_argument("--out-summary-csv", default=str(DEFAULT_SUMMARY_CSV))
    parser.add_argument("--out-files-tsv", default=str(DEFAULT_FILES_TSV))
    parser.add_argument("--out-batch-csv", default=str(DEFAULT_BATCH_CSV))
    parser.add_argument("--starttime", default="2010-01-01T00:00:00")
    parser.add_argument("--endtime", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    parser.add_argument("--min-magnitude", type=float, default=6.0)
    parser.add_argument("--minlat", type=float, default=34.0)
    parser.add_argument("--maxlat", type=float, default=72.0)
    parser.add_argument("--minlon", type=float, default=-25.0)
    parser.add_argument("--maxlon", type=float, default=45.0)
    parser.add_argument("--radius-km", type=float, default=300.0)
    parser.add_argument("--max-stations-per-event", type=int, default=20)
    parser.add_argument("--hours", type=float, default=3.0)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def parse_utc(value: str) -> dt.datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def iso_utc_from_ms(value: int | float) -> str:
    return dt.datetime.fromtimestamp(float(value) / 1000.0, tz=dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fetch_json(url: str, timeout: int = 60) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-earthscope-pipeline epos-europe"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def head_url(url: str, timeout: int = 20, retries: int = 2) -> tuple[bool, int | None]:
    headers = {"User-Agent": "gnss-earthscope-pipeline epos-europe"}
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers=headers, method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                length = response.headers.get("Content-Length")
                return True, int(length) if length and length.isdigit() else None
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False, None
        except (urllib.error.URLError, TimeoutError):
            pass
        if attempt < retries:
            time.sleep(min(2**attempt, 5))
    return False, None


def usgs_url(args: argparse.Namespace) -> str:
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


def fetch_events(args: argparse.Namespace) -> list[Event]:
    payload = fetch_json(usgs_url(args))
    events: list[Event] = []
    for feature in payload.get("features", []) if isinstance(payload, dict) else []:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [])
        if len(coords) < 3 or props.get("mag") is None or props.get("time") is None:
            continue
        time_utc = iso_utc_from_ms(props["time"])
        event_time = parse_utc(time_utc)
        events.append(
            Event(
                event_id=str(feature.get("id") or ""),
                time_utc=time_utc,
                year=event_time.year,
                doy=int(event_time.strftime("%j")),
                magnitude=float(props["mag"]),
                latitude=float(coords[1]),
                longitude=float(coords[0]),
                depth_km=float(coords[2]) if coords[2] is not None else None,
                place=str(props.get("place") or ""),
                title=str(props.get("title") or ""),
                usgs_url=str(props.get("url") or ""),
            )
        )
    return sorted(events, key=lambda item: (item.time_utc, item.event_id))


def fetch_highrate_stations(args: argparse.Namespace) -> list[dict[str, object]]:
    url = EPOS_HIGHRATE_STATION_URL.format(minlon=args.minlon, minlat=args.minlat, maxlon=args.maxlon, maxlat=args.maxlat)
    payload = fetch_json(url)
    rows: list[dict[str, object]] = []
    for feature in payload.get("features", []) if isinstance(payload, dict) else []:
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        station9 = str(props.get("GNSS Station ID") or feature.get("id") or "").upper()
        if not station9:
            continue
        rows.append(
            {
                "station": station9[:4],
                "station9": station9,
                "latitude": float(props.get("Latitude") or coords[1]),
                "longitude": float(props.get("Longitude") or coords[0]),
                "height_m": str(props.get("Altitude") or ""),
                "country": str(props.get("Country") or ""),
                "city": str(props.get("City") or ""),
                "networks": str(props.get("Networks") or ""),
                "data_providers": str(props.get("Data Providers") or ""),
                "installed_at": str(props.get("Installed at") or ""),
            }
        )
    return sorted(rows, key=lambda row: (str(row["station9"]), str(row["networks"])))


def station_active_at(station: dict[str, object], event_time: str) -> bool:
    installed = str(station.get("installed_at") or "")
    if not installed:
        return True
    try:
        return parse_utc(event_time) >= parse_utc(installed)
    except ValueError:
        return True


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def required_hours(event_time_utc: str, hours: float) -> list[int]:
    event_time = parse_utc(event_time_utc)
    start = max(event_time - dt.timedelta(hours=hours), event_time.replace(hour=0, minute=0, second=0, microsecond=0))
    end = min(event_time + dt.timedelta(hours=hours), event_time.replace(hour=23, minute=59, second=59, microsecond=0))
    current = start.replace(minute=0, second=0, microsecond=0)
    out: list[int] = []
    while current <= end:
        out.append(current.hour)
        current += dt.timedelta(hours=1)
    return out


def candidate_urls(station9: str, year: int, doy: int, hour: int, networks: str, providers: str) -> list[tuple[str, str, str]]:
    urls: list[tuple[str, str, str]] = []
    station4 = station9[:4].lower()
    year2 = year % 100
    hour_code = RINEX2_HOUR_CODES[hour]
    upper = station9.upper()
    network_text = f"{networks} {providers}".upper()
    if "RENAG" in network_text or upper.endswith("FRA"):
        name = f"{upper}_R_{year}{doy:03d}{hour:02d}00_01H_01S_MO.crx.gz"
        urls.append((name, f"https://renag.resif.fr/pub/rinex3_1s/{year}/{doy:03d}/{name}", "RENAG_RINEX3"))
    if "RING" in network_text or upper.endswith("ITA"):
        name3 = f"{upper}_R_{year}{doy:03d}{hour:02d}00_01H_01S_MO.crx.gz"
        urls.append((name3, f"http://gnssdata-epos-ring.ingv.it/01/{year}/{doy:03d}/{hour:02d}/{name3}", "RING_RINEX3"))
        name2 = f"{station4}{doy:03d}{hour_code}.{year2:02d}d.Z"
        urls.append((name2, f"http://gnssdata-epos-ring.ingv.it/01/{year}/{doy:03d}/{hour:02d}/{name2}", "RING_RINEX2"))
    return urls


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS epos_highrate_station_hour_files")
    conn.execute("DROP TABLE IF EXISTS epos_highrate_event_availability")
    conn.execute("DROP TABLE IF EXISTS epos_usgs_m6plus_candidates")
    conn.execute("DROP TABLE IF EXISTS epos_highrate_stations")
    conn.execute("DROP TABLE IF EXISTS epos_usgs_m6plus_events")
    conn.execute(
        """
        CREATE TABLE epos_usgs_m6plus_events (
            event_id TEXT PRIMARY KEY, time_utc TEXT, year INTEGER, doy TEXT,
            magnitude REAL, latitude REAL, longitude REAL, depth_km REAL,
            place TEXT, title TEXT, usgs_url TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE epos_highrate_stations (
            station9 TEXT PRIMARY KEY, station TEXT, latitude REAL, longitude REAL,
            height_m TEXT, country TEXT, city TEXT, networks TEXT, data_providers TEXT,
            installed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE epos_usgs_m6plus_candidates (
            event_id TEXT, station9 TEXT, station TEXT, station_rank INTEGER,
            distance_km REAL, event_time_utc TEXT, year INTEGER, doy TEXT,
            magnitude REAL, place TEXT, networks TEXT, data_providers TEXT,
            installed_at TEXT, PRIMARY KEY(event_id, station9)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE epos_highrate_event_availability (
            event_id TEXT PRIMARY KEY, event_time_utc TEXT, year INTEGER, doy TEXT,
            magnitude REAL, place TEXT, hours_each_side REAL, requested_hour_count INTEGER,
            candidate_station_count INTEGER, available_station_count INTEGER,
            available_file_count INTEGER, complete_station_count INTEGER,
            stations_with_1hz TEXT, checked_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE epos_highrate_station_hour_files (
            event_id TEXT, station9 TEXT, station TEXT, station_rank INTEGER,
            distance_km REAL, hour TEXT, has_1hz INTEGER, filename TEXT,
            url TEXT, file_size INTEGER, source_hint TEXT, checked_at TEXT,
            PRIMARY KEY(event_id, station9, hour)
        )
        """
    )


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str], delimiter: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=delimiter, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    events = fetch_events(args)
    stations = fetch_highrate_stations(args)
    checked_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if args.dry_run:
        print(f"Events: {len(events)}")
        print(f"EPOS high-rate stations: {len(stations)}")
        return 0

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        event_rows = [
            {
                "event_id": e.event_id,
                "time_utc": e.time_utc,
                "year": e.year,
                "doy": f"{e.doy:03d}",
                "magnitude": e.magnitude,
                "latitude": e.latitude,
                "longitude": e.longitude,
                "depth_km": e.depth_km,
                "place": e.place,
                "title": e.title,
                "usgs_url": e.usgs_url,
            }
            for e in events
        ]
        station_rows = [{**s} for s in stations]
        with conn:
            conn.executemany(
                "INSERT INTO epos_usgs_m6plus_events VALUES (:event_id,:time_utc,:year,:doy,:magnitude,:latitude,:longitude,:depth_km,:place,:title,:usgs_url)",
                event_rows,
            )
            conn.executemany(
                "INSERT INTO epos_highrate_stations VALUES (:station9,:station,:latitude,:longitude,:height_m,:country,:city,:networks,:data_providers,:installed_at)",
                station_rows,
            )

        all_candidate_rows: list[dict[str, object]] = []
        all_file_rows: list[dict[str, object]] = []
        summary_rows: list[dict[str, object]] = []
        batch_rows: list[dict[str, object]] = []
        for index, event in enumerate(events, start=1):
            ranked: list[tuple[float, dict[str, object]]] = []
            for station in stations:
                if not station_active_at(station, event.time_utc):
                    continue
                distance = haversine_km(event.latitude, event.longitude, float(station["latitude"]), float(station["longitude"]))
                if distance <= args.radius_km:
                    ranked.append((distance, station))
            ranked.sort(key=lambda item: (item[0], str(item[1]["station9"])))
            candidates = ranked[: args.max_stations_per_event] if args.max_stations_per_event > 0 else ranked
            hours = required_hours(event.time_utc, args.hours)
            available_stations: set[str] = set()
            station_counts: dict[str, int] = {}
            file_count = 0
            for rank, (distance, station) in enumerate(candidates, start=1):
                station_counts[str(station["station9"])] = 0
                candidate_row = {
                    "event_id": event.event_id,
                    "station9": station["station9"],
                    "station": station["station"],
                    "station_rank": rank,
                    "distance_km": round(distance, 3),
                    "event_time_utc": event.time_utc,
                    "year": event.year,
                    "doy": f"{event.doy:03d}",
                    "magnitude": event.magnitude,
                    "place": event.place,
                    "networks": station["networks"],
                    "data_providers": station["data_providers"],
                    "installed_at": station["installed_at"],
                }
                all_candidate_rows.append(candidate_row)
                for hour in hours:
                    found = None
                    for filename, url, source_hint in candidate_urls(str(station["station9"]), event.year, event.doy, hour, str(station["networks"]), str(station["data_providers"])):
                        exists, size = head_url(url, timeout=args.timeout)
                        if exists:
                            found = (filename, url, size, source_hint)
                            break
                    if found:
                        available_stations.add(str(station["station"]))
                        station_counts[str(station["station9"])] += 1
                        file_count += 1
                    all_file_rows.append(
                        {
                            "event_id": event.event_id,
                            "station9": station["station9"],
                            "station": station["station"],
                            "station_rank": rank,
                            "distance_km": round(distance, 3),
                            "hour": f"{hour:02d}",
                            "has_1hz": 1 if found else 0,
                            "filename": found[0] if found else "",
                            "url": found[1] if found else "",
                            "file_size": found[2] if found else "",
                            "source_hint": found[3] if found else "",
                            "checked_at": checked_at,
                        }
                    )
            complete_count = sum(1 for value in station_counts.values() if hours and value == len(hours))
            summary = {
                "event_id": event.event_id,
                "event_time_utc": event.time_utc,
                "year": event.year,
                "doy": f"{event.doy:03d}",
                "magnitude": event.magnitude,
                "place": event.place,
                "hours_each_side": args.hours,
                "requested_hour_count": len(hours),
                "candidate_station_count": len(candidates),
                "available_station_count": len(available_stations),
                "available_file_count": file_count,
                "complete_station_count": complete_count,
                "stations_with_1hz": " ".join(sorted(available_stations)),
                "checked_at": checked_at,
            }
            summary_rows.append(summary)
            if available_stations:
                batch_rows.append(
                    {
                        "event_id": event.event_id,
                        "event_time": event.time_utc,
                        "latitude": event.latitude,
                        "longitude": event.longitude,
                        "magnitude": event.magnitude,
                        "hours_each_side": args.hours,
                        "stations": " ".join(sorted(available_stations)),
                        "available_station_count": len(available_stations),
                        "complete_station_count": complete_count,
                        "status": "",
                    }
                )
            print(
                f"[{index:02d}/{len(events)}] {event.event_id} {event.time_utc[:10]} "
                f"{len(available_stations)}/{len(candidates)} stations, {file_count}/{len(candidates) * len(hours)} files",
                file=sys.stderr,
            )

        with conn:
            conn.executemany(
                """
                INSERT INTO epos_usgs_m6plus_candidates VALUES (
                    :event_id,:station9,:station,:station_rank,:distance_km,:event_time_utc,
                    :year,:doy,:magnitude,:place,:networks,:data_providers,:installed_at
                )
                """,
                all_candidate_rows,
            )
            conn.executemany(
                """
                INSERT INTO epos_highrate_event_availability VALUES (
                    :event_id,:event_time_utc,:year,:doy,:magnitude,:place,:hours_each_side,
                    :requested_hour_count,:candidate_station_count,:available_station_count,
                    :available_file_count,:complete_station_count,:stations_with_1hz,:checked_at
                )
                """,
                summary_rows,
            )
            conn.executemany(
                """
                INSERT INTO epos_highrate_station_hour_files VALUES (
                    :event_id,:station9,:station,:station_rank,:distance_km,:hour,:has_1hz,
                    :filename,:url,:file_size,:source_hint,:checked_at
                )
                """,
                all_file_rows,
            )

        write_csv(Path(args.out_event_csv), event_rows, ["event_id", "time_utc", "year", "doy", "magnitude", "latitude", "longitude", "depth_km", "place", "title", "usgs_url"])
        write_csv(Path(args.out_station_csv), station_rows, ["station", "station9", "latitude", "longitude", "height_m", "country", "city", "networks", "data_providers", "installed_at"])
        write_csv(Path(args.out_summary_csv), summary_rows, ["event_id", "event_time_utc", "year", "doy", "magnitude", "place", "hours_each_side", "requested_hour_count", "candidate_station_count", "available_station_count", "available_file_count", "complete_station_count", "stations_with_1hz", "checked_at"])
        write_csv(Path(args.out_files_tsv), all_file_rows, ["event_id", "station9", "station", "station_rank", "distance_km", "hour", "has_1hz", "filename", "url", "file_size", "source_hint", "checked_at"], delimiter="\t")
        write_csv(Path(args.out_batch_csv), batch_rows, ["event_id", "event_time", "latitude", "longitude", "magnitude", "hours_each_side", "stations", "available_station_count", "complete_station_count", "status"])
    finally:
        conn.close()

    print(f"Wrote SQLite database: {args.db}")
    print(f"Wrote summary CSV: {args.out_summary_csv}")
    print(f"Wrote batch CSV: {args.out_batch_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
