#!/usr/bin/env python3
"""Build an independent NASA CDDIS high-rate GNSS availability database."""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CDDIS_TOOLS = ROOT / "tools" / "cddis_downloader"
if str(CDDIS_TOOLS) not in sys.path:
    sys.path.insert(0, str(CDDIS_TOOLS))

from cddis_common import (  # noqa: E402
    CDDIS_HIGHRATE_COLLECTION,
    CMR_GRANULES_URL,
    CddisGranule,
    filter_granules_by_station,
    iso_utc,
    parse_utc,
    query_cmr_granules,
    query_directory_granules,
    read_station_file,
    unique_stations,
)

DEFAULT_DB = ROOT / "data" / "cddis_highrate" / "cddis_highrate.sqlite"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--start-time", required=True, help="UTC scan window start")
    parser.add_argument("--end-time", required=True, help="UTC scan window end")
    parser.add_argument("--stations", default="", help="Station codes separated by comma/space")
    parser.add_argument("--stations-file", help="Optional station-code file")
    parser.add_argument("--query-mode", choices=["auto", "cmr", "directory"], default="auto")
    parser.add_argument("--rinex-subdir", help="CDDIS high-rate subdirectory such as 26o; default is YYo from start time")
    parser.add_argument("--collection-concept-id", default=CDDIS_HIGHRATE_COLLECTION)
    parser.add_argument("--cmr-url", default=CMR_GRANULES_URL)
    parser.add_argument("--page-size", type=int, default=2000)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cookie-file", default=str(Path.home() / ".urs_cookies"))
    parser.add_argument("--clear-window", action="store_true", help="Delete existing file rows overlapping the requested window before inserting")
    parser.add_argument("station_args", nargs="*")
    return parser.parse_args(argv)


def parse_station_args(args: argparse.Namespace) -> list[str]:
    values: list[str] = []
    if args.stations:
        values.extend(args.stations.replace(",", " ").split())
    if args.stations_file:
        values.extend(read_station_file(Path(args.stations_file)))
    values.extend(args.station_args)
    return unique_stations(values)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cddis_scan_runs (
            scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time_utc TEXT NOT NULL,
            end_time_utc TEXT NOT NULL,
            stations TEXT NOT NULL,
            query_mode TEXT NOT NULL,
            collection_concept_id TEXT NOT NULL,
            status TEXT NOT NULL,
            file_count INTEGER NOT NULL,
            station_count INTEGER NOT NULL,
            reason TEXT NOT NULL,
            checked_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cddis_highrate_files (
            station4 TEXT NOT NULL,
            station9 TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            hour INTEGER NOT NULL,
            start_time_utc TEXT NOT NULL,
            end_time_utc TEXT NOT NULL,
            filename TEXT NOT NULL,
            url TEXT NOT NULL PRIMARY KEY,
            source TEXT NOT NULL,
            scan_id INTEGER NOT NULL,
            discovered_at TEXT NOT NULL,
            FOREIGN KEY(scan_id) REFERENCES cddis_scan_runs(scan_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cddis_highrate_station_time ON cddis_highrate_files(station4, start_time_utc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cddis_highrate_time ON cddis_highrate_files(start_time_utc, end_time_utc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cddis_scan_runs_time ON cddis_scan_runs(start_time_utc, end_time_utc)")


def query_granules(args: argparse.Namespace, start: dt.datetime, end: dt.datetime) -> tuple[list[CddisGranule], str, list[str]]:
    query_mode_used = args.query_mode
    warnings: list[str] = []
    try:
        if args.query_mode == "directory":
            granules = query_directory_granules(
                start,
                end,
                rinex_subdir=args.rinex_subdir,
                timeout=args.timeout,
                cookie_file=Path(args.cookie_file),
            )
        else:
            granules = query_cmr_granules(
                start,
                end,
                collection_concept_id=args.collection_concept_id,
                cmr_url=args.cmr_url,
                page_size=args.page_size,
                timeout=args.timeout,
            )
            if args.query_mode == "auto" and not granules:
                warnings.append("CMR returned no granules; used authenticated CDDIS directory listing fallback")
                query_mode_used = "directory"
                granules = query_directory_granules(
                    start,
                    end,
                    rinex_subdir=args.rinex_subdir,
                    timeout=args.timeout,
                    cookie_file=Path(args.cookie_file),
                )
    except RuntimeError as exc:
        if args.query_mode != "auto":
            raise
        warnings.append(f"CMR failed ({exc}); used authenticated CDDIS directory listing fallback")
        query_mode_used = "directory"
        granules = query_directory_granules(
            start,
            end,
            rinex_subdir=args.rinex_subdir,
            timeout=args.timeout,
            cookie_file=Path(args.cookie_file),
        )
    return granules, query_mode_used, warnings


def granule_db_row(granule: CddisGranule, scan_id: int, discovered_at: str) -> tuple[object, ...]:
    start = parse_utc(granule.start_utc)
    return (
        granule.station4,
        granule.station9,
        start.year,
        int(start.strftime("%j")),
        start.hour,
        granule.start_utc,
        granule.end_utc,
        granule.filename,
        granule.url,
        "CDDIS highrate GNSS",
        scan_id,
        discovered_at,
    )


def clear_window(conn: sqlite3.Connection, start_utc: str, end_utc: str) -> None:
    conn.execute(
        """
        DELETE FROM cddis_highrate_files
        WHERE start_time_utc < ? AND end_time_utc > ?
        """,
        (end_utc, start_utc),
    )


def insert_scan(
    conn: sqlite3.Connection,
    *,
    start_utc: str,
    end_utc: str,
    stations: list[str],
    query_mode: str,
    collection_concept_id: str,
    status: str,
    file_count: int,
    station_count: int,
    reason: str,
    checked_at: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO cddis_scan_runs (
            start_time_utc, end_time_utc, stations, query_mode, collection_concept_id,
            status, file_count, station_count, reason, checked_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            start_utc,
            end_utc,
            " ".join(stations),
            query_mode,
            collection_concept_id,
            status,
            file_count,
            station_count,
            reason,
            checked_at,
        ),
    )
    return int(cursor.lastrowid)


def insert_files(conn: sqlite3.Connection, granules: list[CddisGranule], scan_id: int, checked_at: str) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO cddis_highrate_files (
            station4, station9, year, doy, hour, start_time_utc, end_time_utc,
            filename, url, source, scan_id, discovered_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [granule_db_row(granule, scan_id, checked_at) for granule in granules],
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    start = parse_utc(args.start_time)
    end = parse_utc(args.end_time)
    if end <= start:
        raise SystemExit("--end-time must be later than --start-time")
    if args.page_size < 1:
        raise SystemExit("--page-size must be positive")

    stations = parse_station_args(args)
    start_utc = iso_utc(start)
    end_utc = iso_utc(end)
    checked_at = utc_now()
    db_path = Path(args.db).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        try:
            granules, query_mode_used, warnings = query_granules(args, start, end)
        except RuntimeError as exc:
            with conn:
                scan_id = insert_scan(
                    conn,
                    start_utc=start_utc,
                    end_utc=end_utc,
                    stations=stations,
                    query_mode=args.query_mode,
                    collection_concept_id=args.collection_concept_id,
                    status="FAIL",
                    file_count=0,
                    station_count=0,
                    reason=str(exc),
                    checked_at=checked_at,
                )
            print(f"CDDIS availability scan failed: {exc} (scan_id={scan_id})", file=sys.stderr)
            return 1

        selected = filter_granules_by_station(granules, stations)
        station_count = len({granule.station4 for granule in selected})
        reason = "; ".join(warnings)
        with conn:
            if args.clear_window:
                clear_window(conn, start_utc, end_utc)
            scan_id = insert_scan(
                conn,
                start_utc=start_utc,
                end_utc=end_utc,
                stations=stations,
                query_mode=query_mode_used,
                collection_concept_id=args.collection_concept_id,
                status="OK",
                file_count=len(selected),
                station_count=station_count,
                reason=reason,
                checked_at=checked_at,
            )
            insert_files(conn, selected, scan_id, checked_at)

        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        print(f"CDDIS availability DB: {db_path}", file=sys.stderr)
        print(f"Scan ID: {scan_id}", file=sys.stderr)
        print(f"Query mode: {query_mode_used}", file=sys.stderr)
        print(f"Files: {len(selected)}; stations: {station_count}", file=sys.stderr)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
