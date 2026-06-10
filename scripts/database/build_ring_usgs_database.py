#!/usr/bin/env python3
"""Build Italy/Adriatic M6+ USGS event and INGV RING station candidate tables."""

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
DEFAULT_STATION_CSV = ROOT / "data" / "ring_inventory" / "ring_gnss_stations_italy.csv"
DEFAULT_DB = ROOT / "data" / "ring_availability" / "ring_usgs_m6plus_italy.sqlite"
DEFAULT_EVENT_CSV = ROOT / "data" / "ring_batches" / "ring_usgs_m6plus_italy_events.csv"
DEFAULT_BATCH_CSV = ROOT / "data" / "ring_batches" / "ring_usgs_m6plus_italy_candidates_300km.csv"
USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
EARTH_RADIUS_KM = 6371.0088


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
    def year(self) -> int:
        return int(self.time_utc[:4])

    @property
    def doy(self) -> int:
        return int(parse_utc(self.time_utc).strftime("%j"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station-csv", default=str(DEFAULT_STATION_CSV))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--write-event-csv", default=str(DEFAULT_EVENT_CSV))
    parser.add_argument("--write-batch-csv", default=str(DEFAULT_BATCH_CSV))
    parser.add_argument("--starttime", default="2010-01-01T00:00:00")
    parser.add_argument("--endtime", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    parser.add_argument("--min-magnitude", type=float, default=6.0)
    parser.add_argument("--minlat", type=float, default=35.0)
    parser.add_argument("--maxlat", type=float, default=48.0)
    parser.add_argument("--minlon", type=float, default=5.0)
    parser.add_argument("--maxlon", type=float, default=20.0)
    parser.add_argument("--batch-radius-km", type=float, default=300.0)
    parser.add_argument("--max-batch-stations", type=int, default=16)
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
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-earthscope-pipeline ring-usgs-builder"})
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


def parse_events(payload: object) -> list[Event]:
    if not isinstance(payload, dict):
        return []
    events: list[Event] = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {}) if isinstance(feature, dict) else {}
        geometry = feature.get("geometry", {}) if isinstance(feature, dict) else {}
        coords = geometry.get("coordinates", []) if isinstance(geometry, dict) else []
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


def read_stations(path: Path) -> list[dict[str, object]]:
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
    instant = parse_utc(event_time)
    start = str(station.get("date_from") or "")
    end = str(station.get("date_to") or "")
    if start:
        try:
            if instant < parse_utc(start):
                return False
        except ValueError:
            pass
    if end and end.lower() != "none":
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


def event_rows(events: list[Event]) -> list[dict[str, str]]:
    return [
        {
            "event_id": event.event_id,
            "time_utc": event.time_utc,
            "year": str(event.year),
            "doy": f"{event.doy:03d}",
            "magnitude": f"{event.magnitude:.3f}",
            "mag_type": event.mag_type,
            "latitude": f"{event.latitude:.6f}",
            "longitude": f"{event.longitude:.6f}",
            "depth_km": "" if event.depth_km is None else f"{event.depth_km:.3f}",
            "place": event.place,
            "title": event.title,
            "usgs_url": event.usgs_url,
        }
        for event in events
    ]


def candidate_rows(events: list[Event], stations: list[dict[str, object]], radius_km: float, max_stations: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for event in events:
        ranked: list[tuple[float, dict[str, object]]] = []
        for station in stations:
            if not station_active_at(station, event.time_utc):
                continue
            distance = haversine_km(event.latitude, event.longitude, float(station["latitude"]), float(station["longitude"]))
            if distance <= radius_km:
                ranked.append((distance, station))
        ranked.sort(key=lambda item: (item[0], str(item[1].get("station") or "")))
        for rank, (distance, station) in enumerate(ranked[:max_stations], start=1):
            rows.append(
                {
                    "event_id": event.event_id,
                    "event_time_utc": event.time_utc,
                    "year": str(event.year),
                    "doy": f"{event.doy:03d}",
                    "magnitude": f"{event.magnitude:.3f}",
                    "place": event.place,
                    "event_latitude": f"{event.latitude:.6f}",
                    "event_longitude": f"{event.longitude:.6f}",
                    "station_rank": str(rank),
                    "station": str(station.get("station") or ""),
                    "station9": str(station.get("station9") or ""),
                    "network": str(station.get("network") or ""),
                    "station_latitude": f"{float(station['latitude']):.6f}",
                    "station_longitude": f"{float(station['longitude']):.6f}",
                    "distance_km": f"{distance:.3f}",
                    "station_date_from": str(station.get("date_from") or ""),
                    "station_date_to": str(station.get("date_to") or ""),
                    "workflow_hint": (
                        "scripts/workflows/run_ring_event_1hz_pride_workflow.sh "
                        f"--event-id {event.event_id} --event-time {event.time_utc} --stations {station.get('station')}"
                    ),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite(path: Path, events: list[dict[str, str]], candidates: list[dict[str, str]], query_url: str, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("DROP TABLE IF EXISTS ring_usgs_m6plus_events")
        conn.execute("DROP TABLE IF EXISTS ring_usgs_m6plus_candidates")
        conn.execute("DROP TABLE IF EXISTS ring_usgs_query_metadata")
        conn.execute(
            """
            CREATE TABLE ring_usgs_m6plus_events (
                event_id TEXT PRIMARY KEY,
                time_utc TEXT NOT NULL,
                year INTEGER NOT NULL,
                doy TEXT NOT NULL,
                magnitude REAL NOT NULL,
                mag_type TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                depth_km REAL,
                place TEXT,
                title TEXT,
                usgs_url TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE ring_usgs_m6plus_candidates (
                event_id TEXT NOT NULL,
                event_time_utc TEXT NOT NULL,
                year INTEGER NOT NULL,
                doy TEXT NOT NULL,
                magnitude REAL NOT NULL,
                place TEXT,
                event_latitude REAL NOT NULL,
                event_longitude REAL NOT NULL,
                station_rank INTEGER NOT NULL,
                station TEXT NOT NULL,
                station9 TEXT,
                network TEXT,
                station_latitude REAL NOT NULL,
                station_longitude REAL NOT NULL,
                distance_km REAL NOT NULL,
                station_date_from TEXT,
                station_date_to TEXT,
                workflow_hint TEXT,
                PRIMARY KEY (event_id, station)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE ring_usgs_query_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        if events:
            conn.executemany(
                """
                INSERT INTO ring_usgs_m6plus_events (
                    event_id, time_utc, year, doy, magnitude, mag_type, latitude, longitude,
                    depth_km, place, title, usgs_url
                ) VALUES (
                    :event_id, :time_utc, :year, :doy, :magnitude, :mag_type, :latitude, :longitude,
                    :depth_km, :place, :title, :usgs_url
                )
                """,
                events,
            )
        if candidates:
            conn.executemany(
                """
                INSERT INTO ring_usgs_m6plus_candidates (
                    event_id, event_time_utc, year, doy, magnitude, place, event_latitude,
                    event_longitude, station_rank, station, station9, network, station_latitude,
                    station_longitude, distance_km, station_date_from, station_date_to, workflow_hint
                ) VALUES (
                    :event_id, :event_time_utc, :year, :doy, :magnitude, :place, :event_latitude,
                    :event_longitude, :station_rank, :station, :station9, :network, :station_latitude,
                    :station_longitude, :distance_km, :station_date_from, :station_date_to, :workflow_hint
                )
                """,
                candidates,
            )
        metadata = {
            "source": "USGS ComCat + INGV RING/GLASS",
            "query_url": query_url,
            "station_csv": str(Path(args.station_csv)),
            "starttime": args.starttime,
            "endtime": args.endtime,
            "min_magnitude": str(args.min_magnitude),
            "bbox": f"{args.minlat},{args.maxlat},{args.minlon},{args.maxlon}",
            "batch_radius_km": str(args.batch_radius_km),
            "max_batch_stations": str(args.max_batch_stations),
        }
        conn.executemany("INSERT INTO ring_usgs_query_metadata (key, value) VALUES (?, ?)", metadata.items())
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    args = parse_args()
    station_csv = Path(args.station_csv)
    if not station_csv.exists():
        raise SystemExit(f"Station CSV not found: {station_csv}. Run tools/ring_downloader/ring_station_inventory.py first.")

    query_url = build_usgs_url(args)
    events = parse_events(fetch_json(query_url))
    stations = read_stations(station_csv)
    events_out = event_rows(events)
    candidates_out = candidate_rows(events, stations, args.batch_radius_km, args.max_batch_stations)

    if args.dry_run:
        print(f"USGS query: {query_url}")
        print(f"Events: {len(events_out)}")
        print(f"Stations: {len(stations)}")
        print(f"Candidate rows: {len(candidates_out)}")
        return 0

    write_csv(
        Path(args.write_event_csv),
        events_out,
        ["event_id", "time_utc", "year", "doy", "magnitude", "mag_type", "latitude", "longitude", "depth_km", "place", "title", "usgs_url"],
    )
    write_csv(
        Path(args.write_batch_csv),
        candidates_out,
        [
            "event_id",
            "event_time_utc",
            "year",
            "doy",
            "magnitude",
            "place",
            "event_latitude",
            "event_longitude",
            "station_rank",
            "station",
            "station9",
            "network",
            "station_latitude",
            "station_longitude",
            "distance_km",
            "station_date_from",
            "station_date_to",
            "workflow_hint",
        ],
    )
    write_sqlite(Path(args.db), events_out, candidates_out, query_url, args)
    print(f"Wrote {len(events_out)} USGS M6+ events to {args.write_event_csv}")
    print(f"Wrote {len(candidates_out)} RING candidate rows to {args.write_batch_csv}")
    print(f"Wrote SQLite database to {args.db}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        sys.exit(1)
