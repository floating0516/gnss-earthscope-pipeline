#!/usr/bin/env python3
"""Update Geoscience Australia event-window 1 Hz RINEX availability."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GA_TOOLS = ROOT / "tools" / "ga_downloader"
if str(GA_TOOLS) not in sys.path:
    sys.path.insert(0, str(GA_TOOLS))

from ga_common import GA_RINEX_API_URL, event_current_slot_window, iso_utc, list_ga_files, parse_utc  # noqa: E402

DEFAULT_DB = ROOT / "data" / "ga_availability" / "ga_1hz.sqlite"
DEFAULT_SUMMARY_CSV = ROOT / "data" / "ga_availability" / "ga_event_highrate_m6plus_availability.csv"
DEFAULT_FILES_TSV = ROOT / "data" / "ga_availability" / "ga_event_highrate_m6plus_files.tsv"
DEFAULT_BATCH_CSV = ROOT / "data" / "ga_batches" / "ga_m6plus_au_event_highrate_candidates_300km.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out-summary-csv", default=str(DEFAULT_SUMMARY_CSV))
    parser.add_argument("--out-files-tsv", default=str(DEFAULT_FILES_TSV))
    parser.add_argument("--out-batch-csv", default=str(DEFAULT_BATCH_CSV))
    parser.add_argument("--hours", type=float, default=3.0, help="Deprecated legacy window; GA availability now checks the event current 15-minute slot.")
    parser.add_argument("--radius-km", type=float, default=300.0)
    parser.add_argument("--batch-radius-km", type=float, default=300.0)
    parser.add_argument("--max-batch-stations", type=int, default=12)
    parser.add_argument("--ga-api-url", default=GA_RINEX_API_URL)
    parser.add_argument("--chunk-size", type=int, default=40)
    parser.add_argument("--jobs", type=int, default=1, help="Number of events to query concurrently. SQLite writes remain serial.")
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_ga_highrate_availability (
            event_id TEXT PRIMARY KEY,
            event_date TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            has_1hz INTEGER NOT NULL,
            candidate_station_count INTEGER NOT NULL,
            available_station_count INTEGER NOT NULL,
            complete_station_count INTEGER NOT NULL DEFAULT 0,
            partial_station_count INTEGER NOT NULL DEFAULT 0,
            file_count INTEGER NOT NULL,
            stations TEXT NOT NULL,
            source TEXT NOT NULL,
            window_mode TEXT NOT NULL DEFAULT 'event_15min_current',
            required_slot_count INTEGER NOT NULL DEFAULT 1,
            required_slots_utc TEXT NOT NULL DEFAULT '',
            query_start_utc TEXT NOT NULL,
            query_end_utc TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES ga_m6plus_events_au(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ga_event_highrate_has_1hz "
        "ON event_ga_highrate_availability(has_1hz, event_date)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_ga_highrate_files (
            event_id TEXT NOT NULL,
            station TEXT NOT NULL,
            event_date TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_location TEXT NOT NULL,
            file_period TEXT NOT NULL,
            file_type TEXT NOT NULL,
            rinex_version TEXT,
            metadata_status TEXT,
            start_time_utc TEXT NOT NULL,
            size_bytes INTEGER,
            within_candidate INTEGER NOT NULL,
            distance_candidate_km REAL,
            required_slot INTEGER NOT NULL DEFAULT 0,
            slot_role TEXT NOT NULL DEFAULT '',
            slot_complete_station INTEGER NOT NULL DEFAULT 0,
            checked_at TEXT NOT NULL,
            PRIMARY KEY(event_id, station, filename, start_time_utc),
            FOREIGN KEY(event_id) REFERENCES ga_m6plus_events_au(event_id) ON DELETE CASCADE
        )
        """
    )
    for table, columns in {
        "event_ga_highrate_availability": {
            "complete_station_count": "INTEGER NOT NULL DEFAULT 0",
            "partial_station_count": "INTEGER NOT NULL DEFAULT 0",
            "window_mode": "TEXT NOT NULL DEFAULT 'event_15min_current'",
            "required_slot_count": "INTEGER NOT NULL DEFAULT 1",
            "required_slots_utc": "TEXT NOT NULL DEFAULT ''",
        },
        "event_ga_highrate_files": {
            "required_slot": "INTEGER NOT NULL DEFAULT 0",
            "slot_role": "TEXT NOT NULL DEFAULT ''",
            "slot_complete_station": "INTEGER NOT NULL DEFAULT 0",
        },
    }.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, definition in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ga_event_highrate_files_event ON event_ga_highrate_files(event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ga_event_highrate_files_station ON event_ga_highrate_files(station)")


def read_events(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT event_id, time_utc, event_date, year, doy, magnitude, latitude, longitude, place
        FROM ga_m6plus_events_au
        ORDER BY event_date, event_id
        """
    ).fetchall()


def candidate_stations(conn: sqlite3.Connection, event_id: str, radius_km: float) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT station, distance_km
        FROM event_ga_station_candidates
        WHERE event_id = ? AND radius_km = ?
        ORDER BY distance_km, station
        """,
        (event_id, radius_km),
    ).fetchall()
    return {str(row["station"]).upper(): float(row["distance_km"]) for row in rows}


def evaluate_event(event: sqlite3.Row, candidates: dict[str, float], ga_api_url: str, chunk_size: int) -> dict[str, object]:
    event_time = parse_utc(event["time_utc"])
    start, end, slots = event_current_slot_window(event_time)
    slot_roles = {slots[0]: (0, "current")} if slots else {}
    required_slot_set = set(slots)
    files = list_ga_files(sorted(candidates), start, end, api_url=ga_api_url, chunk_size=chunk_size) if candidates else []
    station_slots: dict[str, set[dt.datetime]] = {station: set() for station in candidates}
    for item in files:
        if item.station in candidates and item.start_time in required_slot_set:
            station_slots[item.station].add(item.start_time)
    complete_stations = sorted(station for station, station_slot_set in station_slots.items() if required_slot_set.issubset(station_slot_set))
    partial_stations = sorted(
        station for station, station_slot_set in station_slots.items()
        if station_slot_set and not required_slot_set.issubset(station_slot_set)
    )
    return {
        "event": event,
        "start": start,
        "end": end,
        "slots": slots,
        "slot_roles": slot_roles,
        "candidates": candidates,
        "files": files,
        "complete_stations": complete_stations,
        "partial_stations": partial_stations,
    }


def write_csvs(conn: sqlite3.Connection, summary_path: Path, files_path: Path, batch_path: Path, batch_radius_km: float, max_batch_stations: int) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    files_path.parent.mkdir(parents=True, exist_ok=True)
    batch_path.parent.mkdir(parents=True, exist_ok=True)

    summary_rows = conn.execute(
        """
        SELECT e.event_id, e.time_utc, e.magnitude, e.latitude, e.longitude, e.place,
               a.event_date, a.year, a.doy, a.has_1hz, a.candidate_station_count,
               a.available_station_count, a.complete_station_count, a.partial_station_count,
               a.file_count, a.stations, a.window_mode, a.required_slot_count,
               a.required_slots_utc, a.query_start_utc,
               a.query_end_utc, a.checked_at
        FROM ga_m6plus_events_au e
        JOIN event_ga_highrate_availability a USING(event_id)
        ORDER BY e.event_date, e.event_id
        """
    ).fetchall()
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "event_id",
            "time_utc",
            "magnitude",
            "latitude",
            "longitude",
            "place",
            "event_date",
            "year",
            "doy",
            "has_1hz",
            "candidate_station_count",
            "available_station_count",
            "complete_station_count",
            "partial_station_count",
            "file_count",
            "stations",
            "window_mode",
            "required_slot_count",
            "required_slots_utc",
            "query_start_utc",
            "query_end_utc",
            "checked_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(dict(row) for row in summary_rows)

    file_rows = conn.execute(
        """
        SELECT event_id, station, event_date, year, doy, filename, file_location,
               file_period, file_type, rinex_version, metadata_status, start_time_utc,
               size_bytes, within_candidate, distance_candidate_km, required_slot,
               slot_role, slot_complete_station, checked_at
        FROM event_ga_highrate_files
        ORDER BY event_date, event_id, station, start_time_utc, filename
        """
    ).fetchall()
    with files_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "event_id",
            "station",
            "event_date",
            "year",
            "doy",
            "filename",
            "file_location",
            "file_period",
            "file_type",
            "rinex_version",
            "metadata_status",
            "start_time_utc",
            "size_bytes",
            "within_candidate",
            "distance_candidate_km",
            "required_slot",
            "slot_role",
            "slot_complete_station",
            "checked_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(dict(row) for row in file_rows)

    batch_events = conn.execute(
        """
        SELECT e.event_id, e.time_utc, e.latitude, e.longitude, e.magnitude
        FROM ga_m6plus_events_au e
        JOIN event_ga_highrate_availability a USING(event_id)
        WHERE a.available_station_count > 0
        ORDER BY e.event_date, e.event_id
        """
    ).fetchall()
    with batch_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "event_id",
            "event_time",
            "latitude",
            "longitude",
            "magnitude",
            "radius_km",
            "stations",
            "available_station_count",
            "status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for event in batch_events:
            rows = conn.execute(
                """
                SELECT DISTINCT f.station, c.distance_km
                FROM event_ga_highrate_files f
                JOIN event_ga_station_candidates c
                  ON c.event_id = f.event_id
                 AND c.station = f.station
                 AND c.radius_km = ?
                WHERE f.event_id = ?
                  AND f.slot_complete_station = 1
                ORDER BY c.distance_km, f.station
                """,
                (batch_radius_km, event["event_id"]),
            ).fetchall()
            stations = [row["station"] for row in rows]
            written = stations[:max_batch_stations] if max_batch_stations > 0 else stations
            writer.writerow(
                {
                    "event_id": event["event_id"],
                    "event_time": event["time_utc"],
                    "latitude": event["latitude"],
                    "longitude": event["longitude"],
                    "magnitude": event["magnitude"],
                    "radius_km": batch_radius_km,
                    "stations": " ".join(written),
                    "available_station_count": len(stations),
                    "status": "" if stations else "NO_AVAILABLE_CANDIDATE_STATIONS",
                }
            )


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    checked_at = utc_now()
    try:
        init_db(conn)
        events = read_events(conn)
        if not events:
            raise RuntimeError(f"No GA events found in {db_path}")
        with conn:
            conn.execute("DELETE FROM event_ga_highrate_files")
            conn.execute("DELETE FROM event_ga_highrate_availability")

        available_events = 0
        total_files = 0
        total_stations: set[str] = set()
        event_inputs = [
            (event, candidate_stations(conn, event["event_id"], args.radius_km))
            for event in events
        ]

        def write_result(index: int, result: dict[str, object]) -> None:
            nonlocal available_events, total_files
            event = result["event"]
            start = result["start"]
            end = result["end"]
            slots = result["slots"]
            slot_roles = result["slot_roles"]
            candidates = result["candidates"]
            files = result["files"]
            complete_stations = result["complete_stations"]
            partial_stations = result["partial_stations"]
            stations = complete_stations
            if stations:
                available_events += 1
                total_stations.update(stations)
            total_files += len(files)

            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO event_ga_highrate_availability (
                        event_id, event_date, year, doy, has_1hz, candidate_station_count,
                        available_station_count, complete_station_count, partial_station_count,
                        file_count, stations, source, window_mode, required_slot_count,
                        required_slots_utc, query_start_utc,
                        query_end_utc, checked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["event_id"],
                        event["event_date"],
                        event["year"],
                        event["doy"],
                        1 if stations else 0,
                        len(candidates),
                        len(stations),
                        len(stations),
                        len(partial_stations),
                        len(files),
                        " ".join(stations),
                        "Geoscience Australia RINEX API 15M 01S obs",
                        "event_15min_current",
                        len(slots),
                        " ".join(iso_utc(slot) for slot in slots),
                        iso_utc(start),
                        iso_utc(end),
                        checked_at,
                    ),
                )
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO event_ga_highrate_files (
                        event_id, station, event_date, year, doy, filename, file_location,
                        file_period, file_type, rinex_version, metadata_status, start_time_utc,
                        size_bytes, within_candidate, distance_candidate_km, required_slot,
                        slot_role, slot_complete_station, checked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            event["event_id"],
                            item.station,
                            event["event_date"],
                            event["year"],
                            event["doy"],
                            item.filename,
                            item.url,
                            item.file_period,
                            item.file_type,
                            item.rinex_version,
                            item.metadata_status,
                            iso_utc(item.start_time),
                            item.size_bytes,
                            1 if item.station in candidates else 0,
                            candidates.get(item.station),
                            slot_roles.get(item.start_time, (0, ""))[0],
                            slot_roles.get(item.start_time, (0, ""))[1],
                            1 if item.station in complete_stations else 0,
                            checked_at,
                        )
                        for item in files
                    ],
                )
            print(
                f"[{index:03d}/{len(events)}] {event['event_id']} {event['event_date']} "
                f"{len(files)} files, {len(complete_stations)} complete and {len(partial_stations)} partial "
                f"{args.radius_km:g} km candidates",
                file=sys.stderr,
            )

        if args.jobs <= 1:
            for index, (event, candidates) in enumerate(event_inputs, start=1):
                write_result(index, evaluate_event(event, candidates, args.ga_api_url, args.chunk_size))
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
                futures = [
                    executor.submit(evaluate_event, event, candidates, args.ga_api_url, args.chunk_size)
                    for event, candidates in event_inputs
                ]
                for index, future in enumerate(futures, start=1):
                    write_result(index, future.result())

        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO build_metadata(key, value) VALUES (?, ?)",
                [
                    ("event_highrate_source", "Geoscience Australia RINEX API 15M 01S obs"),
                    ("event_highrate_available_events", str(available_events)),
                    ("event_highrate_total_events_checked", str(len(events))),
                    ("event_highrate_file_rows", str(total_files)),
                    ("event_highrate_unique_stations", str(len(total_stations))),
                    ("event_highrate_hours_each_side", "deprecated; event_15min_current"),
                    ("event_highrate_checked_at", checked_at),
                ],
            )
        write_csvs(
            conn,
            Path(args.out_summary_csv),
            Path(args.out_files_tsv),
            Path(args.out_batch_csv),
            args.batch_radius_km,
            args.max_batch_stations,
        )
    finally:
        conn.close()

    print(f"Wrote GA event high-rate availability to {db_path}")
    print(f"Wrote summary CSV: {args.out_summary_csv}")
    print(f"Wrote files TSV: {args.out_files_tsv}")
    print(f"Wrote high-rate batch CSV: {args.out_batch_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
