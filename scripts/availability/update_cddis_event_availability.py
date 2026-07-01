#!/usr/bin/env python3
"""Populate CDDIS high-rate availability for imported USGS events."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CDDIS_TOOLS = ROOT / "tools" / "cddis_downloader"
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (CDDIS_TOOLS, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cddis_common import (  # noqa: E402
    CDDIS_HIGHRATE_COLLECTION,
    CMR_GRANULES_URL,
    CddisGranule,
    filter_granules_by_station,
    iso_utc,
    parse_utc,
    query_directory_granules,
)
from update_cddis_highrate_availability import (  # noqa: E402
    init_db,
    insert_files,
    insert_scan,
    query_granules,
    utc_now,
)

DEFAULT_DB = ROOT / "data" / "cddis_highrate" / "cddis_highrate.sqlite"


@dataclass(frozen=True)
class EventWindow:
    start: dt.datetime
    end: dt.datetime

    @property
    def start_utc(self) -> str:
        return iso_utc(self.start)

    @property
    def end_utc(self) -> str:
        return iso_utc(self.end)


@dataclass(frozen=True)
class ScanResult:
    window: EventWindow
    status: str
    query_mode: str
    granules: list[CddisGranule]
    reason: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--start-time", default="2010-01-01T00:00:00Z")
    parser.add_argument("--end-time", default=utc_now())
    parser.add_argument("--min-magnitude", type=float, default=6.0)
    parser.add_argument("--event-id", action="append", default=[])
    parser.add_argument("--query-mode", choices=["auto", "cmr", "directory"], default="directory")
    parser.add_argument("--rinex-subdir", help="CDDIS high-rate subdirectory such as 26d or 26o; default scans both YYd and YYo")
    parser.add_argument("--collection-concept-id", default=CDDIS_HIGHRATE_COLLECTION)
    parser.add_argument("--cmr-url", default=CMR_GRANULES_URL)
    parser.add_argument("--page-size", type=int, default=2000)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cookie-file", default=str(Path.home() / ".urs_cookies"))
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0, help="Scan at most N unique windows; 0 means all")
    parser.add_argument("--clear", action="store_true", help="Clear existing CDDIS scan/file availability rows before inserting")
    parser.add_argument("--dry-run", action="store_true", help="Print window count without querying CDDIS or writing")
    return parser.parse_args(argv)


def slot_window(event_time: dt.datetime) -> EventWindow:
    minute = (event_time.minute // 15) * 15
    start = event_time.replace(minute=minute, second=0, microsecond=0)
    return EventWindow(start=start, end=start + dt.timedelta(minutes=15))


def read_event_windows(conn: sqlite3.Connection, args: argparse.Namespace) -> list[EventWindow]:
    start = parse_utc(args.start_time)
    end = parse_utc(args.end_time)
    if end <= start:
        raise SystemExit("--end-time must be later than --start-time")
    params: list[object] = [iso_utc(start), iso_utc(end), args.min_magnitude]
    clauses = ["event_time_utc >= ?", "event_time_utc < ?", "COALESCE(magnitude, 0) >= ?"]
    if args.event_id:
        placeholders = ",".join("?" for _ in args.event_id)
        clauses.append(f"event_id IN ({placeholders})")
        params.extend(args.event_id)
    rows = conn.execute(
        f"""
        SELECT event_time_utc
        FROM cddis_events
        WHERE {' AND '.join(clauses)}
        ORDER BY event_time_utc, event_id
        """,
        params,
    ).fetchall()
    seen: set[tuple[str, str]] = set()
    windows: list[EventWindow] = []
    for row in rows:
        window = slot_window(parse_utc(row[0]))
        key = (window.start_utc, window.end_utc)
        if key in seen:
            continue
        seen.add(key)
        windows.append(window)
    if args.limit > 0:
        windows = windows[: args.limit]
    return windows


def is_missing_cddis_directory(message: str) -> bool:
    return "CDDIS directory query failed" in message and "404" in message


def is_retryable_cddis_error(message: str) -> bool:
    retryable_markers = (
        "Connection timed out",
        "Recv failure",
        "Failed to connect",
        "Operation timed out",
    )
    return "CDDIS directory query failed" in message and any(marker in message for marker in retryable_markers)


def default_rinex_subdirs(start: dt.datetime) -> list[str]:
    year = start.astimezone(dt.timezone.utc).year % 100
    return [f"{year:02d}d", f"{year:02d}o"]


def query_directory_granules_for_event(args: argparse.Namespace, window: EventWindow) -> tuple[list[CddisGranule], str, list[str]]:
    if args.rinex_subdir or args.query_mode != "directory":
        return query_granules(args, window.start, window.end)

    subdirs = default_rinex_subdirs(window.start)
    granules: list[CddisGranule] = []
    seen_urls: set[str] = set()
    warnings: list[str] = []
    missing_subdirs: list[str] = []
    for subdir in subdirs:
        try:
            subdir_granules = query_directory_granules(
                window.start,
                window.end,
                rinex_subdir=subdir,
                timeout=args.timeout,
                cookie_file=Path(args.cookie_file),
            )
        except RuntimeError as exc:
            message = str(exc)
            if is_missing_cddis_directory(message):
                missing_subdirs.append(subdir)
                continue
            raise
        for granule in subdir_granules:
            if granule.url in seen_urls:
                continue
            seen_urls.add(granule.url)
            granules.append(granule)
    if len(missing_subdirs) == len(subdirs):
        warnings.append("CDDIS directory not found")
    elif missing_subdirs:
        warnings.append(f"CDDIS subdirectories not found: {' '.join(missing_subdirs)}")
    return granules, "directory", warnings


def query_window(args: argparse.Namespace, window: EventWindow) -> ScanResult:
    last_message = ""
    for attempt in range(args.retries + 1):
        try:
            granules, query_mode, warnings = query_directory_granules_for_event(args, window)
            selected = filter_granules_by_station(granules, [])
            return ScanResult(window=window, status="OK", query_mode=query_mode, granules=selected, reason="; ".join(warnings))
        except RuntimeError as exc:
            last_message = str(exc)
            if is_missing_cddis_directory(last_message):
                query_mode = "directory" if args.query_mode == "auto" else args.query_mode
                return ScanResult(window=window, status="OK", query_mode=query_mode, granules=[], reason="CDDIS directory not found")
            if attempt < args.retries and is_retryable_cddis_error(last_message):
                continue
            return ScanResult(window=window, status="FAIL", query_mode=args.query_mode, granules=[], reason=last_message)
    return ScanResult(window=window, status="FAIL", query_mode=args.query_mode, granules=[], reason=last_message)


def clear_availability(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM cddis_highrate_files")
    conn.execute("DELETE FROM cddis_scan_runs")


def write_results(conn: sqlite3.Connection, args: argparse.Namespace, results: list[ScanResult], checked_at: str) -> None:
    for result in results:
        station_count = len({granule.station4 for granule in result.granules})
        scan_id = insert_scan(
            conn,
            start_utc=result.window.start_utc,
            end_utc=result.window.end_utc,
            stations=[],
            query_mode=result.query_mode,
            collection_concept_id=args.collection_concept_id,
            status=result.status,
            file_count=len(result.granules),
            station_count=station_count,
            reason=result.reason,
            checked_at=checked_at,
        )
        if result.status == "OK" and result.granules:
            insert_files(conn, result.granules, scan_id, checked_at)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.jobs < 1:
        raise SystemExit("--jobs must be a positive integer")
    if args.page_size < 1:
        raise SystemExit("--page-size must be positive")
    if args.retries < 0:
        raise SystemExit("--retries must be non-negative")

    db_path = Path(args.db).expanduser()
    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        windows = read_event_windows(conn, args)
    finally:
        conn.close()

    print(f"CDDIS event windows: {len(windows)}")
    print(f"Window filter: {args.start_time} -> {args.end_time}; min_magnitude={args.min_magnitude:g}")
    if args.dry_run:
        return 0
    if not windows:
        return 0

    results: list[ScanResult] = []
    if args.jobs == 1:
        for index, window in enumerate(windows, start=1):
            result = query_window(args, window)
            results.append(result)
            print(f"[{index}/{len(windows)}] {window.start_utc} {result.status} files={len(result.granules)}", file=sys.stderr)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_map = {executor.submit(query_window, args, window): window for window in windows}
            for index, future in enumerate(concurrent.futures.as_completed(future_map), start=1):
                result = future.result()
                results.append(result)
                print(f"[{index}/{len(windows)}] {result.window.start_utc} {result.status} files={len(result.granules)}", file=sys.stderr)
        results.sort(key=lambda item: item.window.start_utc)

    checked_at = utc_now()
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            init_db(conn)
            if args.clear:
                clear_availability(conn)
            write_results(conn, args, results, checked_at)
    finally:
        conn.close()

    ok_count = sum(1 for result in results if result.status == "OK")
    fail_count = len(results) - ok_count
    file_count = sum(len(result.granules) for result in results)
    station_count = len({granule.station4 for result in results for granule in result.granules})
    print(f"CDDIS availability DB: {db_path}")
    print(f"Scanned windows: {len(results)}")
    print(f"OK: {ok_count}")
    print(f"FAIL: {fail_count}")
    print(f"Files: {file_count}")
    print(f"Stations: {station_count}")
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
