#!/usr/bin/env python3
"""Update INGV RING 1 Hz high-rate availability for USGS M6+ event candidates."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "ring_downloader"
sys.path.insert(0, str(TOOLS))

from ring_common import find_direct_highrate_file  # noqa: E402


DEFAULT_DB = ROOT / "data" / "ring_availability" / "ring_usgs_m6plus_italy.sqlite"
DEFAULT_SUMMARY_CSV = ROOT / "data" / "ring_availability" / "ring_highrate_m6plus_availability.csv"
DEFAULT_FILES_TSV = ROOT / "data" / "ring_availability" / "ring_highrate_m6plus_files.tsv"
DEFAULT_BATCH_CSV = ROOT / "data" / "ring_batches" / "ring_usgs_m6plus_italy_highrate_candidates_300km.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out-summary-csv", default=str(DEFAULT_SUMMARY_CSV))
    parser.add_argument("--out-files-tsv", default=str(DEFAULT_FILES_TSV))
    parser.add_argument("--out-batch-csv", default=str(DEFAULT_BATCH_CSV))
    parser.add_argument("--hours", type=float, default=3.0, help="Hours before/after event to probe. Default: 3")
    parser.add_argument("--max-stations-per-event", type=int, default=16)
    parser.add_argument("--min-available-hours", type=int, default=1)
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


def event_day_window(event_time: dt.datetime, hours: float) -> tuple[dt.datetime, dt.datetime]:
    start = event_time - dt.timedelta(hours=hours)
    end = event_time + dt.timedelta(hours=hours)
    day_start = event_time.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = event_time.replace(hour=23, minute=59, second=59, microsecond=0)
    return max(start, day_start), min(end, day_end)


def required_hours(event_time_utc: str, hours: float) -> list[int]:
    event_time = parse_utc(event_time_utc)
    start, end = event_day_window(event_time, hours)
    current = start.replace(minute=0, second=0, microsecond=0)
    values: list[int] = []
    while current <= end:
        values.append(current.hour)
        current += dt.timedelta(hours=1)
    return values


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ring_highrate_event_availability (
            event_id TEXT PRIMARY KEY,
            event_time_utc TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy TEXT NOT NULL,
            magnitude REAL NOT NULL,
            place TEXT,
            hours_each_side REAL NOT NULL,
            requested_hour_count INTEGER NOT NULL,
            candidate_station_count INTEGER NOT NULL,
            available_station_count INTEGER NOT NULL,
            available_file_count INTEGER NOT NULL,
            complete_station_count INTEGER NOT NULL,
            stations_with_1hz TEXT NOT NULL,
            source TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES ring_usgs_m6plus_events(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ring_highrate_station_hour_files (
            event_id TEXT NOT NULL,
            station TEXT NOT NULL,
            station9 TEXT,
            station_rank INTEGER NOT NULL,
            distance_km REAL NOT NULL,
            event_time_utc TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy TEXT NOT NULL,
            hour TEXT NOT NULL,
            has_1hz INTEGER NOT NULL,
            filename TEXT,
            url TEXT,
            file_size INTEGER,
            rinex_format TEXT,
            sampling_window TEXT,
            sampling_frequency TEXT,
            station_date_from TEXT,
            station_date_to TEXT,
            checked_at TEXT NOT NULL,
            PRIMARY KEY(event_id, station, hour),
            FOREIGN KEY(event_id) REFERENCES ring_usgs_m6plus_events(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ring_highrate_station_hour_event "
        "ON ring_highrate_station_hour_files(event_id, has_1hz)"
    )


def read_events(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT event_id, time_utc, year, doy, magnitude, place
        FROM ring_usgs_m6plus_events
        ORDER BY time_utc, event_id
        """
    ).fetchall()


def read_candidates(conn: sqlite3.Connection, event_id: str, max_stations: int) -> list[sqlite3.Row]:
    limit = "" if max_stations <= 0 else f"LIMIT {int(max_stations)}"
    return conn.execute(
        f"""
        SELECT event_id, event_time_utc, year, doy, magnitude, place, station_rank, station,
               station9, network, distance_km, station_date_from, station_date_to
        FROM ring_usgs_m6plus_candidates
        WHERE event_id = ?
        ORDER BY station_rank, distance_km, station
        {limit}
        """,
        (event_id,),
    ).fetchall()


def write_csvs(conn: sqlite3.Connection, summary_path: Path, files_path: Path, batch_path: Path, min_available_hours: int) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    files_path.parent.mkdir(parents=True, exist_ok=True)
    batch_path.parent.mkdir(parents=True, exist_ok=True)

    summary_rows = conn.execute(
        """
        SELECT event_id, event_time_utc, year, doy, magnitude, place, hours_each_side,
               requested_hour_count, candidate_station_count, available_station_count,
               available_file_count, complete_station_count, stations_with_1hz, source, checked_at
        FROM ring_highrate_event_availability
        ORDER BY event_time_utc, event_id
        """
    ).fetchall()
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "event_id",
            "event_time_utc",
            "year",
            "doy",
            "magnitude",
            "place",
            "hours_each_side",
            "requested_hour_count",
            "candidate_station_count",
            "available_station_count",
            "available_file_count",
            "complete_station_count",
            "stations_with_1hz",
            "source",
            "checked_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(dict(row) for row in summary_rows)

    file_rows = conn.execute(
        """
        SELECT event_id, station, station9, station_rank, distance_km, event_time_utc, year,
               doy, hour, has_1hz, filename, url, file_size, rinex_format, sampling_window,
               sampling_frequency, station_date_from, station_date_to, checked_at
        FROM ring_highrate_station_hour_files
        ORDER BY event_time_utc, event_id, station_rank, station, hour
        """
    ).fetchall()
    with files_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "event_id",
            "station",
            "station9",
            "station_rank",
            "distance_km",
            "event_time_utc",
            "year",
            "doy",
            "hour",
            "has_1hz",
            "filename",
            "url",
            "file_size",
            "rinex_format",
            "sampling_window",
            "sampling_frequency",
            "station_date_from",
            "station_date_to",
            "checked_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(dict(row) for row in file_rows)

    batch_rows = conn.execute(
        """
        SELECT a.event_id, a.event_time_utc, e.latitude, e.longitude, a.magnitude,
               a.hours_each_side, a.requested_hour_count
        FROM ring_highrate_event_availability a
        JOIN ring_usgs_m6plus_events e USING(event_id)
        WHERE a.available_station_count > 0
        ORDER BY a.event_time_utc, a.event_id
        """
    ).fetchall()
    with batch_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "event_id",
            "event_time",
            "latitude",
            "longitude",
            "magnitude",
            "hours_each_side",
            "requested_hour_count",
            "stations",
            "available_station_count",
            "complete_station_count",
            "status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for event in batch_rows:
            stations = conn.execute(
                """
                SELECT station, SUM(has_1hz) AS available_hours
                FROM ring_highrate_station_hour_files
                WHERE event_id = ?
                GROUP BY station
                HAVING available_hours >= ?
                ORDER BY MIN(station_rank), station
                """,
                (event["event_id"], min_available_hours),
            ).fetchall()
            complete_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM (
                    SELECT station, SUM(has_1hz) AS available_hours, COUNT(*) AS requested_hours
                    FROM ring_highrate_station_hour_files
                    WHERE event_id = ?
                    GROUP BY station
                    HAVING available_hours = requested_hours
                )
                """,
                (event["event_id"],),
            ).fetchone()["count"]
            writer.writerow(
                {
                    "event_id": event["event_id"],
                    "event_time": event["event_time_utc"],
                    "latitude": event["latitude"],
                    "longitude": event["longitude"],
                    "magnitude": event["magnitude"],
                    "hours_each_side": event["hours_each_side"],
                    "requested_hour_count": event["requested_hour_count"],
                    "stations": " ".join(row["station"] for row in stations),
                    "available_station_count": len(stations),
                    "complete_station_count": complete_count,
                    "status": "" if stations else "NO_AVAILABLE_1HZ_STATIONS",
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
            raise RuntimeError(f"No RING/USGS events found in {db_path}")
        with conn:
            conn.execute("DELETE FROM ring_highrate_station_hour_files")
            conn.execute("DELETE FROM ring_highrate_event_availability")

        for index, event in enumerate(events, start=1):
            candidates = read_candidates(conn, event["event_id"], args.max_stations_per_event)
            hours = required_hours(event["time_utc"], args.hours)
            available_files = 0
            stations_with_1hz: set[str] = set()
            complete_stations = 0
            station_available_counts: dict[str, int] = {}
            rows: list[tuple[object, ...]] = []
            for candidate in candidates:
                station = str(candidate["station"])
                station_available_counts[station] = 0
                for hour in hours:
                    item = find_direct_highrate_file(station, int(event["year"]), int(event["doy"]), hour)
                    has_1hz = 1 if item is not None else 0
                    if item is not None:
                        available_files += 1
                        stations_with_1hz.add(station)
                        station_available_counts[station] += 1
                    rows.append(
                        (
                            event["event_id"],
                            station,
                            candidate["station9"],
                            candidate["station_rank"],
                            candidate["distance_km"],
                            event["time_utc"],
                            event["year"],
                            event["doy"],
                            f"{hour:02d}",
                            has_1hz,
                            item.filename if item else "",
                            item.url if item else "",
                            item.file_size if item else None,
                            item.format if item else "",
                            item.sampling_window if item else "",
                            item.sampling_frequency if item else "",
                            candidate["station_date_from"],
                            candidate["station_date_to"],
                            checked_at,
                        )
                    )
            complete_stations = sum(1 for count in station_available_counts.values() if count == len(hours) and len(hours) > 0)
            with conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO ring_highrate_station_hour_files (
                        event_id, station, station9, station_rank, distance_km, event_time_utc,
                        year, doy, hour, has_1hz, filename, url, file_size, rinex_format,
                        sampling_window, sampling_frequency, station_date_from, station_date_to, checked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO ring_highrate_event_availability (
                        event_id, event_time_utc, year, doy, magnitude, place, hours_each_side,
                        requested_hour_count, candidate_station_count, available_station_count,
                        available_file_count, complete_station_count, stations_with_1hz,
                        source, checked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["event_id"],
                        event["time_utc"],
                        event["year"],
                        event["doy"],
                        event["magnitude"],
                        event["place"],
                        args.hours,
                        len(hours),
                        len(candidates),
                        len(stations_with_1hz),
                        available_files,
                        complete_stations,
                        " ".join(sorted(stations_with_1hz)),
                        "INGV RING high-rate 1Hz direct repository HEAD",
                        checked_at,
                    ),
                )
            print(
                f"[{index:02d}/{len(events)}] {event['event_id']} {event['time_utc'][:10]} "
                f"{len(stations_with_1hz)}/{len(candidates)} stations with 1Hz, "
                f"{available_files}/{len(candidates) * len(hours)} hourly files",
                file=sys.stderr,
            )

        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO ring_usgs_query_metadata(key, value) VALUES (?, ?)",
                [
                    ("ring_highrate_source", "INGV RING high-rate 1Hz direct repository HEAD"),
                    ("ring_highrate_hours_each_side", str(args.hours)),
                    ("ring_highrate_total_events_checked", str(len(events))),
                    ("ring_highrate_checked_at", checked_at),
                ],
            )
        write_csvs(conn, Path(args.out_summary_csv), Path(args.out_files_tsv), Path(args.out_batch_csv), args.min_available_hours)
    finally:
        conn.close()

    print(f"Wrote RING high-rate availability to {db_path}")
    print(f"Wrote summary CSV: {args.out_summary_csv}")
    print(f"Wrote files TSV: {args.out_files_tsv}")
    print(f"Wrote high-rate batch CSV: {args.out_batch_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
