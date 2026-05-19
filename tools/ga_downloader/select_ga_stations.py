#!/usr/bin/env python3
"""Select Geoscience Australia stations by event distance and optional availability."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from ga_common import write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/ga_availability/ga_1hz.sqlite")
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--radius-km", type=float, default=300.0)
    parser.add_argument("--max-stations", type=int, default=0)
    parser.add_argument("--require-availability", action="store_true")
    parser.add_argument("--out-csv", default="")
    parser.add_argument("--out-stations", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--print-stations", action="store_true")
    return parser.parse_args()


def connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"GA database not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def read_event(conn: sqlite3.Connection, event_id: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT event_id, time_utc, latitude, longitude, magnitude, place
        FROM ga_m6plus_events_au
        WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone()
    if row is None:
        raise SystemExit(f"Event not found in GA database: {event_id}")
    return row


def availability_map(conn: sqlite3.Connection, event_id: str) -> dict[str, int]:
    table = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'event_ga_highrate_files'
        """
    ).fetchone()
    if table is None:
        return {}
    rows = conn.execute(
        """
        SELECT station, COUNT(*) AS file_count
        FROM event_ga_highrate_files
        WHERE event_id = ?
        GROUP BY station
        """,
        (event_id,),
    ).fetchall()
    return {str(row["station"]).upper(): int(row["file_count"]) for row in rows}


def selected_rows(conn: sqlite3.Connection, event_id: str, radius_km: float, require_availability: bool, max_stations: int) -> list[dict[str, object]]:
    available = availability_map(conn, event_id)
    rows = conn.execute(
        """
        SELECT station, station9, country, station_latitude, station_longitude,
               distance_km, radius_km, metadata_file
        FROM event_ga_station_candidates
        WHERE event_id = ? AND radius_km = ?
        ORDER BY distance_km, station
        """,
        (event_id, radius_km),
    ).fetchall()
    selected: list[dict[str, object]] = []
    for row in rows:
        station = str(row["station"]).upper()
        file_count = available.get(station, 0)
        if require_availability and file_count <= 0:
            continue
        selected.append(
            {
                "station": station,
                "station9": row["station9"] or "",
                "country": row["country"] or "",
                "latitude": f"{float(row['station_latitude']):.8f}",
                "longitude": f"{float(row['station_longitude']):.8f}",
                "distance_km": f"{float(row['distance_km']):.3f}",
                "radius_km": f"{float(row['radius_km']):.3f}",
                "available_file_count": file_count,
                "metadata_file": row["metadata_file"] or "",
            }
        )
    selected.sort(key=lambda item: (-int(item["available_file_count"]), float(item["distance_km"]), str(item["station"])))
    if max_stations > 0:
        selected = selected[:max_stations]
    return selected


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "station",
        "station9",
        "country",
        "latitude",
        "longitude",
        "distance_km",
        "radius_km",
        "available_file_count",
        "metadata_file",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    conn = connect(Path(args.db))
    try:
        event = read_event(conn, args.event_id)
        selected = selected_rows(conn, args.event_id, args.radius_km, args.require_availability, args.max_stations)
    finally:
        conn.close()

    stations = [str(row["station"]) for row in selected]
    if args.out_csv:
        write_csv(Path(args.out_csv), selected)
    if args.out_stations:
        out_stations = Path(args.out_stations)
        out_stations.parent.mkdir(parents=True, exist_ok=True)
        out_stations.write_text("\n".join(stations) + ("\n" if stations else ""), encoding="utf-8")
    if args.out_json:
        write_json(
            Path(args.out_json),
            {
                "source": "Geoscience Australia",
                "event_id": args.event_id,
                "event": dict(event),
                "radius_km": args.radius_km,
                "require_availability": args.require_availability,
                "station_count": len(stations),
                "stations": selected,
            },
        )
    if args.print_stations:
        for station in stations:
            print(station)
    else:
        print(f"Selected {len(stations)} GA stations within {args.radius_km:.1f} km")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
