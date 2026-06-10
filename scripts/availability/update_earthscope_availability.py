#!/usr/bin/env python3
"""Build a local SQLite index of EarthScope 1 Hz GNSS availability."""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite"
SOURCE = "gage_file_server"
BASE_URL = "https://gage-data.earthscope.org/archive/gnss/highrate/1-Hz/rinex"


class FetchResult:
    def __init__(
        self,
        status: str,
        stations: list[str] | None = None,
        http_status: int | None = None,
        error: str = "",
        attempt_count: int = 0,
        token_refreshed: bool = False,
    ) -> None:
        self.status = status
        self.stations = stations or []
        self.http_status = http_status
        self.error = error
        self.attempt_count = attempt_count
        self.token_refreshed = token_refreshed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--date", help="Single UTC date, YYYY-MM-DD.")
    scope.add_argument("--recent-days", type=int, help="Update the last N UTC dates including today.")
    parser.add_argument("--start-date", help="Start UTC date, YYYY-MM-DD.")
    parser.add_argument("--end-date", help="End UTC date, YYYY-MM-DD.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help=f"SQLite DB path. Default: {DEFAULT_DB}")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between day requests in seconds.")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds.")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=30.0, help="Base backoff delay in seconds.")
    parser.add_argument("--force", action="store_true", help="Refetch dates already marked OK.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned requests without writing the DB.")
    return parser.parse_args()


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def iter_dates(args: argparse.Namespace) -> list[dt.date]:
    if args.date:
        if args.start_date or args.end_date:
            raise SystemExit("--date cannot be combined with --start-date/--end-date")
        return [parse_date(args.date)]
    if args.recent_days is not None:
        if args.recent_days <= 0:
            raise SystemExit("--recent-days must be positive")
        if args.start_date or args.end_date:
            raise SystemExit("--recent-days cannot be combined with --start-date/--end-date")
        today = dt.datetime.now(dt.timezone.utc).date()
        start = today - dt.timedelta(days=args.recent_days - 1)
        return [start + dt.timedelta(days=offset) for offset in range(args.recent_days)]
    if not args.start_date or not args.end_date:
        raise SystemExit("Use --date, --recent-days, or both --start-date and --end-date")
    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    if end < start:
        raise SystemExit("--end-date must be on or after --start-date")
    return [start + dt.timedelta(days=offset) for offset in range((end - start).days + 1)]


def date_parts(day: dt.date) -> tuple[int, int]:
    return day.year, int(day.strftime("%j"))


def listing_url(day: dt.date) -> str:
    year, doy = date_parts(day)
    return f"{BASE_URL}/{year}/{doy:03d}/?list&dirs&uris"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_listing (
            date TEXT PRIMARY KEY,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            listing_url TEXT NOT NULL,
            station_count INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            http_status INTEGER,
            error TEXT,
            fetched_at TEXT NOT NULL,
            attempt_count INTEGER DEFAULT 0
        )
        """
    )
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_station_day_date ON station_day_availability(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_station_day_station ON station_day_availability(station)")
    conn.commit()


def existing_status(conn: sqlite3.Connection, day: dt.date) -> str | None:
    row = conn.execute("SELECT status FROM daily_listing WHERE date = ?", (day.isoformat(),)).fetchone()
    return str(row[0]) if row else None


def write_day(conn: sqlite3.Connection, day: dt.date, url: str, result: FetchResult) -> None:
    year, doy = date_parts(day)
    fetched_at = utc_now()
    with conn:
        conn.execute(
            """
            INSERT INTO daily_listing (
                date, year, doy, listing_url, station_count, status,
                http_status, error, fetched_at, attempt_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                year = excluded.year,
                doy = excluded.doy,
                listing_url = excluded.listing_url,
                station_count = excluded.station_count,
                status = excluded.status,
                http_status = excluded.http_status,
                error = excluded.error,
                fetched_at = excluded.fetched_at,
                attempt_count = excluded.attempt_count
            """,
            (
                day.isoformat(),
                year,
                doy,
                url,
                len(result.stations),
                result.status,
                result.http_status,
                result.error,
                fetched_at,
                result.attempt_count,
            ),
        )
        if result.status == "OK":
            conn.execute("DELETE FROM station_day_availability WHERE date = ?", (day.isoformat(),))
            conn.executemany(
                """
                INSERT OR REPLACE INTO station_day_availability (
                    station, date, year, doy, has_1hz, source, listing_url, checked_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """,
                [
                    (station, day.isoformat(), year, doy, SOURCE, url, fetched_at)
                    for station in result.stations
                ],
            )


def get_token() -> str:
    result = subprocess.run(["es", "user", "get-access-token"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"failed to obtain EarthScope token: {result.stderr.strip()}")
    return result.stdout.strip()


def http_status_name(status: int) -> str:
    if status == 401:
        return "HTTP_401"
    if status == 429:
        return "HTTP_429"
    if 500 <= status <= 599:
        return "HTTP_5XX"
    return f"HTTP_{status}"


def parse_stations(text: str) -> list[str]:
    stations = set()
    for raw in text.splitlines():
        line = raw.strip().rstrip("/")
        if not line:
            continue
        station = line.rsplit("/", 1)[-1].strip().upper()
        if station:
            stations.add(station)
    return sorted(stations)


def fetch_listing(day: dt.date, token: str, args: argparse.Namespace) -> tuple[FetchResult, str]:
    url = listing_url(day)
    current_token = token
    token_refreshed = False
    attempts = max(1, args.max_retries + 1)
    for attempt in range(1, attempts + 1):
        request = Request(url, headers={"Authorization": f"Bearer {current_token}", "User-Agent": "gnss-eq-availability/0.1"})
        try:
            with urlopen(request, timeout=args.timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
            return FetchResult("OK", parse_stations(text), 200, attempt_count=attempt, token_refreshed=token_refreshed), current_token
        except HTTPError as exc:
            status = int(exc.code)
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:  # noqa: BLE001
                body = ""
            if status == 401 and attempt < attempts:
                current_token = get_token()
                token_refreshed = True
                continue
            if status in {429} or 500 <= status <= 599:
                if attempt < attempts:
                    time.sleep(args.retry_delay * attempt)
                    continue
            return FetchResult(http_status_name(status), http_status=status, error=body or str(exc), attempt_count=attempt, token_refreshed=token_refreshed), current_token
        except TimeoutError as exc:
            if attempt < attempts:
                time.sleep(args.retry_delay * attempt)
                continue
            return FetchResult("TIMEOUT", error=str(exc), attempt_count=attempt, token_refreshed=token_refreshed), current_token
        except URLError as exc:
            reason = str(getattr(exc, "reason", exc))
            if attempt < attempts:
                time.sleep(args.retry_delay * attempt)
                continue
            return FetchResult("FAIL", error=reason, attempt_count=attempt, token_refreshed=token_refreshed), current_token
    return FetchResult("FAIL", error="unreachable retry state", attempt_count=attempts, token_refreshed=token_refreshed), current_token


def main() -> int:
    args = parse_args()
    days = iter_dates(args)
    db_path = Path(args.db)
    if args.dry_run:
        for day in days:
            print(f"{day.isoformat()}\t{listing_url(day)}")
        return 0

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    init_db(conn)

    token: str | None = None
    processed = 0
    skipped = 0
    failed = 0
    fetched_once = False
    try:
        for day in days:
            status = existing_status(conn, day)
            if status == "OK" and not args.force:
                skipped += 1
                print(f"SKIP\t{day.isoformat()}\tstatus=OK")
                continue
            if fetched_once and args.delay > 0:
                time.sleep(args.delay)
            if token is None:
                token = get_token()
            url = listing_url(day)
            result, token = fetch_listing(day, token, args)
            fetched_once = True
            write_day(conn, day, url, result)
            processed += 1
            if result.status != "OK":
                failed += 1
            refresh_note = "\ttoken=refreshed" if result.token_refreshed else ""
            print(
                f"{result.status}\t{day.isoformat()}\tstations={len(result.stations)}"
                f"\tattempts={result.attempt_count}{refresh_note}\t{url}"
            )
    except KeyboardInterrupt:
        print("Interrupted; completed days are already committed.", file=sys.stderr)
        return 130
    finally:
        conn.close()

    print(f"DB\t{db_path}")
    print(f"SUMMARY\tprocessed={processed}\tskipped={skipped}\tfailed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
