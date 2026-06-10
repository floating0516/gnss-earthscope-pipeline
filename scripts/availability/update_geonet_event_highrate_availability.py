#!/usr/bin/env python3
"""Update GeoNet event high-rate 1 Hz RINEX availability in the local dataset."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "geonet_availability" / "geonet_1hz.sqlite"
DEFAULT_SUMMARY_CSV = ROOT / "data" / "geonet_availability" / "geonet_event_highrate_m6plus_availability.csv"
DEFAULT_FILES_TSV = ROOT / "data" / "geonet_availability" / "geonet_event_highrate_m6plus_files.tsv"
DEFAULT_BATCH_CSV = ROOT / "data" / "geonet_batches" / "geonet_m6plus_nz_event_highrate_candidates_300km.csv"
S3_ROOT = "https://geonet-open-data.s3.amazonaws.com/"
EVENT_HIGHRATE_PREFIX = "gnss/event.highrate/1hz/rinex"
RINEX2_D_Z_RE = re.compile(r"^[A-Za-z0-9]{4}\d{3}0\.\d{2}d\.Z$")
RINEX2_O_GZ_RE = re.compile(r"^[A-Za-z0-9]{4}\d{3}0\.\d{2}o\.gz$")
RINEX3_RNX_GZ_RE = re.compile(r"^([A-Z0-9]{4})00[A-Z0-9]{3}_R_\d{11}_\d{2}H_01S_MO\.rnx\.gz$")


@dataclass(frozen=True)
class HighrateFile:
    station: str
    filename: str
    key: str
    url: str
    size_bytes: int
    last_modified: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out-summary-csv", default=str(DEFAULT_SUMMARY_CSV))
    parser.add_argument("--out-files-tsv", default=str(DEFAULT_FILES_TSV))
    parser.add_argument("--out-batch-csv", default=str(DEFAULT_BATCH_CSV))
    parser.add_argument("--batch-radius-km", type=float, default=300.0)
    parser.add_argument("--max-batch-stations", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def list_url(prefix: str, continuation_token: str | None = None) -> str:
    params = {"list-type": "2", "prefix": prefix}
    if continuation_token:
        params["continuation-token"] = continuation_token
    return S3_ROOT + "?" + urllib.parse.urlencode(params)


def fetch_xml(url: str, timeout: int) -> ET.Element:
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-earthscope-pipeline geonet-event-highrate"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return ET.fromstring(response.read())


def child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == name:
            return child.text or ""
    return ""


def iter_contents(root: ET.Element) -> list[ET.Element]:
    return [child for child in root if child.tag.rsplit("}", 1)[-1] == "Contents"]


def station_from_hatanaka_name(filename: str) -> str:
    # GeoNet event high-rate RINEX appears in multiple historical formats:
    # RINEX 2 Hatanaka (.d.Z), RINEX 2 observation gzip (.o.gz), and RINEX 3 gzip (.rnx.gz).
    if RINEX2_D_Z_RE.match(filename) or RINEX2_O_GZ_RE.match(filename):
        return filename[:4].upper()
    rinex3 = RINEX3_RNX_GZ_RE.match(filename)
    if rinex3:
        return rinex3.group(1).upper()
    return ""


def list_event_day_files(year: int, doy: int, timeout: int) -> tuple[list[HighrateFile], str]:
    prefix = f"{EVENT_HIGHRATE_PREFIX}/{year}/{doy:03d}/"
    first_url = list_url(prefix)
    token: str | None = None
    files: list[HighrateFile] = []
    while True:
        root = fetch_xml(list_url(prefix, token), timeout)
        for item in iter_contents(root):
            key = child_text(item, "Key")
            filename = Path(key).name
            if not (RINEX2_D_Z_RE.match(filename) or RINEX2_O_GZ_RE.match(filename) or RINEX3_RNX_GZ_RE.match(filename)):
                continue
            station = station_from_hatanaka_name(filename)
            if not station:
                continue
            size_text = child_text(item, "Size")
            files.append(
                HighrateFile(
                    station=station,
                    filename=filename,
                    key=key,
                    url=urllib.parse.urljoin(S3_ROOT, key),
                    size_bytes=int(size_text or "0"),
                    last_modified=child_text(item, "LastModified"),
                )
            )
        if child_text(root, "IsTruncated").lower() != "true":
            break
        token = child_text(root, "NextContinuationToken")
        if not token:
            break
    return sorted(files, key=lambda item: (item.station, item.filename)), first_url


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_highrate_day_availability (
            event_id TEXT PRIMARY KEY,
            event_date TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            has_1hz INTEGER NOT NULL,
            file_count INTEGER NOT NULL,
            station_count INTEGER NOT NULL,
            candidate_200km_station_count INTEGER NOT NULL,
            candidate_300km_station_count INTEGER NOT NULL,
            candidate_300km_with_data_count INTEGER NOT NULL,
            stations TEXT NOT NULL,
            source TEXT NOT NULL,
            listing_url TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES geonet_m6plus_events_nz(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_geonet_event_highrate_day_has_1hz "
        "ON event_highrate_day_availability(has_1hz, event_date)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_highrate_station_files (
            event_id TEXT NOT NULL,
            station TEXT NOT NULL,
            event_date TEXT NOT NULL,
            year INTEGER NOT NULL,
            doy INTEGER NOT NULL,
            filename TEXT NOT NULL,
            s3_key TEXT NOT NULL,
            url TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            last_modified TEXT NOT NULL,
            within_200km_candidate INTEGER NOT NULL,
            within_300km_candidate INTEGER NOT NULL,
            distance_300km_km REAL,
            checked_at TEXT NOT NULL,
            PRIMARY KEY(event_id, station, filename),
            FOREIGN KEY(event_id) REFERENCES geonet_m6plus_events_nz(event_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_geonet_event_highrate_station_event "
        "ON event_highrate_station_files(event_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_geonet_event_highrate_station_station "
        "ON event_highrate_station_files(station)"
    )


def read_events(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT event_id, time_utc, event_date, year, doy, magnitude, latitude, longitude, place
        FROM geonet_m6plus_events_nz
        ORDER BY event_date, event_id
        """
    ).fetchall()


def candidate_stations(conn: sqlite3.Connection, event_id: str, radius_km: float) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT station, distance_km
        FROM event_geonet_station_candidates
        WHERE event_id = ? AND radius_km = ?
        ORDER BY distance_km, station
        """,
        (event_id, radius_km),
    ).fetchall()
    return {row["station"].upper(): float(row["distance_km"]) for row in rows}


def write_csvs(
    conn: sqlite3.Connection,
    summary_path: Path,
    files_path: Path,
    batch_path: Path,
    batch_radius_km: float,
    max_batch_stations: int,
) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    files_path.parent.mkdir(parents=True, exist_ok=True)
    batch_path.parent.mkdir(parents=True, exist_ok=True)

    summary_rows = conn.execute(
        """
        SELECT e.event_id, e.time_utc, e.magnitude, e.latitude, e.longitude, e.place,
               a.event_date, a.year, a.doy, a.has_1hz, a.file_count, a.station_count,
               a.candidate_200km_station_count, a.candidate_300km_station_count,
               a.candidate_300km_with_data_count, a.stations, a.listing_url, a.checked_at
        FROM geonet_m6plus_events_nz e
        JOIN event_highrate_day_availability a USING(event_id)
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
            "file_count",
            "station_count",
            "candidate_200km_station_count",
            "candidate_300km_station_count",
            "candidate_300km_with_data_count",
            "stations",
            "listing_url",
            "checked_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(dict(row) for row in summary_rows)

    file_rows = conn.execute(
        """
        SELECT event_id, station, event_date, year, doy, filename, s3_key, url, size_bytes,
               last_modified, within_200km_candidate, within_300km_candidate, distance_300km_km,
               checked_at
        FROM event_highrate_station_files
        ORDER BY event_date, event_id, station, filename
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
            "s3_key",
            "url",
            "size_bytes",
            "last_modified",
            "within_200km_candidate",
            "within_300km_candidate",
            "distance_300km_km",
            "checked_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(dict(row) for row in file_rows)

    batch_events = conn.execute(
        """
        SELECT e.event_id, e.time_utc, e.latitude, e.longitude, e.magnitude
        FROM geonet_m6plus_events_nz e
        JOIN event_highrate_day_availability a USING(event_id)
        WHERE a.has_1hz = 1
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
                SELECT f.station
                FROM event_highrate_station_files f
                JOIN event_geonet_station_candidates c
                  ON c.event_id = f.event_id
                 AND c.station = f.station
                 AND c.radius_km = ?
                WHERE f.event_id = ?
                ORDER BY c.distance_km, f.station
                """,
                (batch_radius_km, event["event_id"]),
            ).fetchall()
            stations = [row["station"] for row in rows]
            written_stations = stations[:max_batch_stations] if max_batch_stations > 0 else stations
            writer.writerow(
                {
                    "event_id": event["event_id"],
                    "event_time": event["time_utc"],
                    "latitude": event["latitude"],
                    "longitude": event["longitude"],
                    "magnitude": event["magnitude"],
                    "radius_km": batch_radius_km,
                    "stations": " ".join(written_stations),
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
            raise RuntimeError(f"No GeoNet events found in {db_path}")

        with conn:
            conn.execute("DELETE FROM event_highrate_station_files")
            conn.execute("DELETE FROM event_highrate_day_availability")

        available_events = 0
        total_files = 0
        total_stations: set[str] = set()
        for index, event in enumerate(events, start=1):
            files, listing_url = list_event_day_files(int(event["year"]), int(event["doy"]), args.timeout)
            stations = sorted({item.station for item in files})
            candidates_200 = candidate_stations(conn, event["event_id"], 200.0)
            candidates_300 = candidate_stations(conn, event["event_id"], 300.0)
            candidate_300_with_data = [station for station in stations if station in candidates_300]
            if files:
                available_events += 1
                total_files += len(files)
                total_stations.update(stations)

            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO event_highrate_day_availability (
                        event_id, event_date, year, doy, has_1hz, file_count, station_count,
                        candidate_200km_station_count, candidate_300km_station_count,
                        candidate_300km_with_data_count, stations, source, listing_url, checked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["event_id"],
                        event["event_date"],
                        event["year"],
                        event["doy"],
                        1 if files else 0,
                        len(files),
                        len(stations),
                        len([station for station in stations if station in candidates_200]),
                        len(candidates_300),
                        len(candidate_300_with_data),
                        " ".join(stations),
                        "GeoNet event.highrate 1hz/rinex",
                        listing_url,
                        checked_at,
                    ),
                )
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO event_highrate_station_files (
                        event_id, station, event_date, year, doy, filename, s3_key, url,
                        size_bytes, last_modified, within_200km_candidate,
                        within_300km_candidate, distance_300km_km, checked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            event["event_id"],
                            item.station,
                            event["event_date"],
                            event["year"],
                            event["doy"],
                            item.filename,
                            item.key,
                            item.url,
                            item.size_bytes,
                            item.last_modified,
                            1 if item.station in candidates_200 else 0,
                            1 if item.station in candidates_300 else 0,
                            candidates_300.get(item.station),
                            checked_at,
                        )
                        for item in files
                    ],
                )
            print(
                f"[{index:02d}/{len(events)}] {event['event_id']} {event['event_date']} "
                f"{len(files)} files, {len(stations)} stations, "
                f"{len(candidate_300_with_data)} available 300 km candidates",
                file=sys.stderr,
            )

        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO build_metadata(key, value) VALUES (?, ?)",
                [
                    ("event_highrate_source", "GeoNet event.highrate 1hz/rinex"),
                    ("event_highrate_available_events", str(available_events)),
                    ("event_highrate_total_events_checked", str(len(events))),
                    ("event_highrate_file_rows", str(total_files)),
                    ("event_highrate_unique_stations", str(len(total_stations))),
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

    print(f"Wrote event high-rate availability to {db_path}")
    print(f"Wrote summary CSV: {args.out_summary_csv}")
    print(f"Wrote files TSV: {args.out_files_tsv}")
    print(f"Wrote high-rate batch CSV: {args.out_batch_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
