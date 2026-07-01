#!/usr/bin/env python3
"""Import USGS earthquake events into the isolated CDDIS prototype database."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "cddis_highrate" / "cddis_highrate.sqlite"
USGS_EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
USER_AGENT = "gnss-earthscope-pipeline cddis-usgs-import"


@dataclass(frozen=True)
class Event:
    event_id: str
    event_time_utc: str
    latitude: float
    longitude: float
    depth_km: float | None
    magnitude: float
    mag_type: str
    place: str
    title: str
    usgs_url: str
    updated_utc: str


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def iso_utc_from_ms(value: int | float | None, fallback: str = "") -> str:
    if value is None:
        return fallback
    return dt.datetime.fromtimestamp(float(value) / 1000.0, tz=dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--starttime", default="2010-01-01T00:00:00Z")
    parser.add_argument("--endtime", default=utc_now())
    parser.add_argument("--min-magnitude", type=float, default=6.0)
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def build_usgs_url(args: argparse.Namespace) -> str:
    params = {
        "format": "geojson",
        "starttime": args.starttime,
        "endtime": args.endtime,
        "minmagnitude": args.min_magnitude,
        "orderby": "time-asc",
        "limit": args.limit,
    }
    return USGS_EVENT_URL + "?" + urllib.parse.urlencode(params)


def fetch_json(url: str, timeout: int) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_events(payload: Any) -> list[Event]:
    if not isinstance(payload, dict):
        return []
    events: list[Event] = []
    for feature in payload.get("features", []):
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
        coords = geometry.get("coordinates") if isinstance(geometry.get("coordinates"), list) else []
        if len(coords) < 3 or props.get("mag") is None or props.get("time") is None:
            continue
        event_id = str(feature.get("id") or props.get("code") or "").strip()
        if not event_id:
            continue
        try:
            longitude = float(coords[0])
            latitude = float(coords[1])
            depth_km = float(coords[2]) if coords[2] is not None else None
            magnitude = float(props["mag"])
        except (TypeError, ValueError):
            continue
        event_time = iso_utc_from_ms(props.get("time"))
        updated = iso_utc_from_ms(props.get("updated"), fallback=event_time)
        events.append(
            Event(
                event_id=event_id,
                event_time_utc=event_time,
                latitude=latitude,
                longitude=longitude,
                depth_km=depth_km,
                magnitude=magnitude,
                mag_type=str(props.get("magType") or ""),
                place=str(props.get("place") or ""),
                title=str(props.get("title") or ""),
                usgs_url=str(props.get("url") or ""),
                updated_utc=updated,
            )
        )
    return sorted(events, key=lambda item: (item.event_time_utc, item.event_id))


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
    columns = {row[1] for row in conn.execute("PRAGMA table_info(cddis_events)")}
    additions = {
        "depth_km": "REAL",
        "mag_type": "TEXT NOT NULL DEFAULT ''",
        "title": "TEXT NOT NULL DEFAULT ''",
        "usgs_url": "TEXT NOT NULL DEFAULT ''",
        "event_source": "TEXT NOT NULL DEFAULT 'USGS'",
        "usgs_updated_at": "TEXT NOT NULL DEFAULT ''",
    }
    for name, definition in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE cddis_events ADD COLUMN {name} {definition}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cddis_events_time ON cddis_events(event_time_utc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cddis_events_magnitude ON cddis_events(magnitude)")


def upsert_events(conn: sqlite3.Connection, events: list[Event], imported_at: str) -> None:
    conn.executemany(
        """
        INSERT INTO cddis_events (
            event_id, event_time_utc, latitude, longitude, magnitude, place, updated_at,
            depth_km, mag_type, title, usgs_url, event_source, usgs_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USGS', ?)
        ON CONFLICT(event_id) DO UPDATE SET
            event_time_utc = excluded.event_time_utc,
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            magnitude = excluded.magnitude,
            place = excluded.place,
            updated_at = excluded.updated_at,
            depth_km = excluded.depth_km,
            mag_type = excluded.mag_type,
            title = excluded.title,
            usgs_url = excluded.usgs_url,
            event_source = excluded.event_source,
            usgs_updated_at = excluded.usgs_updated_at
        """,
        [
            (
                event.event_id,
                event.event_time_utc,
                event.latitude,
                event.longitude,
                event.magnitude,
                event.place,
                imported_at,
                event.depth_km,
                event.mag_type,
                event.title,
                event.usgs_url,
                event.updated_utc,
            )
            for event in events
        ],
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    url = build_usgs_url(args)
    payload = fetch_json(url, args.timeout)
    events = parse_events(payload)
    print(f"USGS events: {len(events)}")
    print(f"Window: {args.starttime} -> {args.endtime}")
    print(f"Min magnitude: {args.min_magnitude:g}")
    if args.dry_run:
        return 0

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    try:
        with conn:
            init_db(conn)
            upsert_events(conn, events, utc_now())
    finally:
        conn.close()
    print(f"CDDIS DB: {args.db}")
    print(f"Imported/updated: {len(events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
