#!/usr/bin/env python3
"""Refresh station file verification rows from EarthScope station listings."""

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
BASE_URL = "https://gage-data.earthscope.org/archive/gnss/highrate/1-Hz/rinex"


class VerifyResult:
    def __init__(
        self,
        status: str,
        urls: list[str] | None = None,
        http_status: int | None = None,
        error: str = "",
        attempt_count: int = 0,
        token_refreshed: bool = False,
    ) -> None:
        self.status = status
        self.urls = urls or []
        self.http_status = http_status
        self.error = error
        self.attempt_count = attempt_count
        self.token_refreshed = token_refreshed

    @property
    def obs_urls(self) -> list[str]:
        return [url for url in self.urls if is_obs_url(url)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--event-id", action="append", help="Limit refresh to one or more event ids.")
    parser.add_argument("--radius-km", type=float, action="append", help="Limit refresh to one or more radii.")
    parser.add_argument("--missing-only", action="store_true", help="Only fetch candidate rows missing verification records.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=30.0)
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def station_listing_url(year: int, doy: int, station: str) -> str:
    return f"{BASE_URL}/{year}/{doy:03d}/{station.lower()}/?list&uris"


def is_obs_url(url: str) -> bool:
    lower = url.lower()
    return lower.endswith("d.z") or lower.endswith(".crx.gz") or lower.endswith(".crx.z")


def parse_urls(text: str) -> list[str]:
    urls = []
    for raw in text.splitlines():
        line = raw.strip()
        if line:
            urls.append(line)
    return sorted(set(urls))


def get_token() -> str:
    result = subprocess.run(["es", "user", "get-access-token"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"failed to obtain EarthScope token: {result.stderr.strip()}")
    return result.stdout.strip()


def http_status_name(status: int) -> str:
    if status == 401:
        return "HTTP_401"
    if status == 404:
        return "HTTP_404"
    if status == 429:
        return "HTTP_429"
    if 500 <= status <= 599:
        return "HTTP_5XX"
    return f"HTTP_{status}"


def fetch_station_listing(url: str, token: str, args: argparse.Namespace) -> tuple[VerifyResult, str]:
    current_token = token
    token_refreshed = False
    attempts = max(1, args.max_retries + 1)
    for attempt in range(1, attempts + 1):
        request = Request(url, headers={"Authorization": f"Bearer {current_token}", "User-Agent": "gnss-eq-file-verify/0.1"})
        try:
            with urlopen(request, timeout=args.timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
            urls = parse_urls(text)
            obs_urls = [item for item in urls if is_obs_url(item)]
            status = "VERIFIED" if obs_urls else "NO_OBS"
            return VerifyResult(status, urls, 200, attempt_count=attempt, token_refreshed=token_refreshed), current_token
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
            return VerifyResult(http_status_name(status), http_status=status, error=body or str(exc), attempt_count=attempt, token_refreshed=token_refreshed), current_token
        except TimeoutError as exc:
            if attempt < attempts:
                time.sleep(args.retry_delay * attempt)
                continue
            return VerifyResult("TIMEOUT", error=str(exc), attempt_count=attempt, token_refreshed=token_refreshed), current_token
        except URLError as exc:
            reason = str(getattr(exc, "reason", exc))
            if attempt < attempts:
                time.sleep(args.retry_delay * attempt)
                continue
            return VerifyResult("FAIL", error=reason, attempt_count=attempt, token_refreshed=token_refreshed), current_token
    return VerifyResult("FAIL", error="unreachable retry state", attempt_count=attempts, token_refreshed=token_refreshed), current_token


def init_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_earthscope_station_verified_files (
            event_id TEXT NOT NULL,
            station TEXT NOT NULL,
            event_date TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            radius_km REAL NOT NULL,
            distance_km REAL NOT NULL,
            station_latitude REAL NOT NULL,
            station_longitude REAL NOT NULL,
            verified_status TEXT NOT NULL,
            file_count INTEGER NOT NULL DEFAULT 0,
            obs_file_count INTEGER NOT NULL DEFAULT 0,
            first_obs_url TEXT,
            listing_url TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            error TEXT,
            PRIMARY KEY (event_id, station, radius_km)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_verified_event ON event_earthscope_station_verified_files(event_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_event_verified_status ON event_earthscope_station_verified_files(verified_status)")
    conn.commit()


def read_candidate_groups(conn: sqlite3.Connection, args: argparse.Namespace) -> list[sqlite3.Row]:
    conditions = []
    params: list[object] = []
    if args.event_id:
        placeholders = ",".join("?" for _ in args.event_id)
        conditions.append(f"c.event_id IN ({placeholders})")
        params.extend(args.event_id)
    if args.radius_km:
        placeholders = ",".join("?" for _ in args.radius_km)
        conditions.append(f"c.radius_km IN ({placeholders})")
        params.extend(float(radius) for radius in args.radius_km)
    if args.missing_only:
        conditions.append(
            """
            NOT EXISTS (
              SELECT 1
              FROM event_earthscope_station_verified_files v
              WHERE v.event_id = c.event_id
                AND v.station = c.station
                AND v.radius_km = c.radius_km
            )
            """
        )
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    return list(
        conn.execute(
            f"""
            SELECT
              c.event_id,
              c.station,
              c.event_date,
              CAST(strftime('%Y', c.event_date) AS INTEGER) AS year,
              CAST(strftime('%j', c.event_date) AS INTEGER) AS doy,
              GROUP_CONCAT(c.radius_km) AS radii,
              COUNT(*) AS candidate_rows
            FROM event_earthscope_station_candidates c
            {where}
            GROUP BY c.event_id, c.station, c.event_date
            ORDER BY c.event_date, c.event_id, c.station
            """,
            params,
        )
    )


def candidate_rows_for_group(conn: sqlite3.Connection, event_id: str, station: str, event_date: str, args: argparse.Namespace) -> list[sqlite3.Row]:
    conditions = ["c.event_id = ?", "c.station = ?", "c.event_date = ?"]
    params: list[object] = [event_id, station, event_date]
    if args.radius_km:
        placeholders = ",".join("?" for _ in args.radius_km)
        conditions.append(f"c.radius_km IN ({placeholders})")
        params.extend(float(radius) for radius in args.radius_km)
    if args.missing_only:
        conditions.append(
            """
            NOT EXISTS (
              SELECT 1
              FROM event_earthscope_station_verified_files v
              WHERE v.event_id = c.event_id
                AND v.station = c.station
                AND v.radius_km = c.radius_km
            )
            """
        )
    return list(
        conn.execute(
            f"""
            SELECT *
            FROM event_earthscope_station_candidates c
            WHERE {" AND ".join(conditions)}
            ORDER BY c.radius_km
            """,
            params,
        )
    )


def write_group(conn: sqlite3.Connection, candidates: list[sqlite3.Row], result: VerifyResult, url: str) -> None:
    checked_at = utc_now()
    obs_urls = result.obs_urls
    first_obs_url = obs_urls[0] if obs_urls else None
    rows = []
    for candidate in candidates:
        year = int(dt.date.fromisoformat(str(candidate["event_date"])).strftime("%Y"))
        doy = int(dt.date.fromisoformat(str(candidate["event_date"])).strftime("%j"))
        rows.append(
            (
                candidate["event_id"],
                candidate["station"],
                candidate["event_date"],
                year,
                doy,
                candidate["radius_km"],
                candidate["distance_km"],
                candidate["station_latitude"],
                candidate["station_longitude"],
                result.status,
                len(result.urls),
                len(obs_urls),
                first_obs_url,
                url,
                checked_at,
                result.error,
            )
        )
    with conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO event_earthscope_station_verified_files (
                event_id, station, event_date, year, doy, radius_km, distance_km,
                station_latitude, station_longitude, verified_status, file_count,
                obs_file_count, first_obs_url, listing_url, checked_at, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def main() -> int:
    args = parse_args()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    init_table(conn)

    groups = read_candidate_groups(conn, args)
    if args.dry_run:
        print(f"DRY_RUN\tgroups={len(groups)}")
        for row in groups[:20]:
            print(f"{row['event_id']}\t{row['station']}\t{row['event_date']}\tradii={row['radii']}")
        if len(groups) > 20:
            print(f"... {len(groups) - 20} more groups")
        conn.close()
        return 0

    token: str | None = None
    processed = 0
    failed = 0
    status_counts: dict[str, int] = {}
    fetched_once = False
    try:
        for group in groups:
            if fetched_once and args.delay > 0:
                time.sleep(args.delay)
            if token is None:
                token = get_token()
            url = station_listing_url(int(group["year"]), int(group["doy"]), str(group["station"]))
            result, token = fetch_station_listing(url, token, args)
            fetched_once = True
            candidates = candidate_rows_for_group(
                conn,
                str(group["event_id"]),
                str(group["station"]),
                str(group["event_date"]),
                args,
            )
            write_group(conn, candidates, result, url)
            processed += len(candidates)
            status_counts[result.status] = status_counts.get(result.status, 0) + len(candidates)
            if result.status != "VERIFIED":
                failed += len(candidates)
            refresh_note = "\ttoken=refreshed" if result.token_refreshed else ""
            print(
                f"{result.status}\t{group['event_id']}\t{group['station']}\t{group['event_date']}"
                f"\tradii={group['radii']}\tfiles={len(result.urls)}\tobs={len(result.obs_urls)}"
                f"\tattempts={result.attempt_count}{refresh_note}\t{url}"
            )
    except KeyboardInterrupt:
        print("Interrupted; completed rows are already committed.", file=sys.stderr)
        return 130
    finally:
        conn.close()

    summary = " ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
    print(f"DB\t{args.db}")
    print(f"SUMMARY\tgroups={len(groups)}\trows={processed}\tfailed_rows={failed}\t{summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
