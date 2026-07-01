#!/usr/bin/env python3
"""Update CDDIS station metadata from downloaded RINEX headers."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import math
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "cddis_highrate" / "cddis_highrate.sqlite"
DEFAULT_FILES_ROOT = ROOT / "data" / "cddis_highrate"
DEFAULT_SAMPLE_ROOT = ROOT / "data" / "cddis_highrate" / "station_metadata_samples"
WGS84_A_M = 6378137.0
WGS84_F = 1 / 298.257223563
WGS84_B_M = WGS84_A_M * (1 - WGS84_F)
WGS84_E2 = WGS84_F * (2 - WGS84_F)
WGS84_EP2 = (WGS84_A_M**2 - WGS84_B_M**2) / WGS84_B_M**2


@dataclass(frozen=True)
class RinexStationMetadata:
    station4: str
    station9: str
    marker_name: str
    marker_number: str
    receiver_type: str
    antenna_type: str
    x_m: float
    y_m: float
    z_m: float
    latitude: float
    longitude: float
    elevation_m: float
    source_file: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--files-root", default=str(DEFAULT_FILES_ROOT), help="Root containing downloaded CDDIS .gz/.Z files")
    parser.add_argument("--file", action="append", help="Specific downloaded RINEX file to parse; may be repeated")
    parser.add_argument("--from-availability", action="store_true", help="Download one representative available file per missing station before parsing")
    parser.add_argument("--sample-root", default=str(DEFAULT_SAMPLE_ROOT))
    parser.add_argument("--cookie-file", default=str(Path.home() / ".urs_cookies"))
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--limit", type=int, default=0, help="Maximum files or availability samples to parse, 0 means no limit")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_station(value: str) -> str:
    return value.strip().upper()[:4]


def station9_from_filename(path: Path) -> str:
    first = path.name.split(".", 1)[0].split("_", 1)[0].upper()
    return first[:9] if len(first) >= 9 else ""


def open_rinex_text(path: Path):
    suffixes = [suffix.lower() for suffix in path.suffixes]
    if suffixes and suffixes[-1] == ".gz":
        return gzip.open(path, "rt", encoding="ascii", errors="replace")
    return path.open("rt", encoding="ascii", errors="replace")


def ecef_to_geodetic(x_m: float, y_m: float, z_m: float) -> tuple[float, float, float]:
    lon = math.atan2(y_m, x_m)
    p = math.hypot(x_m, y_m)
    theta = math.atan2(z_m * WGS84_A_M, p * WGS84_B_M)
    lat = math.atan2(
        z_m + WGS84_EP2 * WGS84_B_M * math.sin(theta) ** 3,
        p - WGS84_E2 * WGS84_A_M * math.cos(theta) ** 3,
    )
    sin_lat = math.sin(lat)
    n = WGS84_A_M / math.sqrt(1 - WGS84_E2 * sin_lat * sin_lat)
    elevation = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), elevation


def parse_rinex_header(path: Path) -> RinexStationMetadata | None:
    marker_name = ""
    marker_number = ""
    receiver_type = ""
    antenna_type = ""
    xyz: tuple[float, float, float] | None = None
    with open_rinex_text(path) as handle:
        for line in handle:
            label = line[60:].strip() if len(line) >= 60 else ""
            body = line[:60]
            if label == "MARKER NAME":
                marker_name = body.strip()
            elif label == "MARKER NUMBER":
                marker_number = body.strip()
            elif label == "REC # / TYPE / VERS":
                receiver_type = body[20:40].strip() or body.strip()
            elif label == "ANT # / TYPE":
                antenna_type = body[20:40].strip() or body.strip()
            elif label == "APPROX POSITION XYZ":
                parts = body.split()
                if len(parts) >= 3:
                    xyz = (float(parts[0]), float(parts[1]), float(parts[2]))
            elif label == "END OF HEADER":
                break
    if xyz is None:
        return None
    station4 = normalize_station(marker_name) or normalize_station(path.name)
    station9 = station9_from_filename(path)
    lat, lon, elevation = ecef_to_geodetic(*xyz)
    return RinexStationMetadata(
        station4=station4,
        station9=station9,
        marker_name=marker_name,
        marker_number=marker_number,
        receiver_type=receiver_type,
        antenna_type=antenna_type,
        x_m=xyz[0],
        y_m=xyz[1],
        z_m=xyz[2],
        latitude=lat,
        longitude=lon,
        elevation_m=elevation,
        source_file=str(path),
    )


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cddis_stations (
            station4 TEXT PRIMARY KEY,
            station9 TEXT NOT NULL,
            marker_name TEXT NOT NULL,
            marker_number TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            elevation_m REAL NOT NULL,
            x_m REAL NOT NULL,
            y_m REAL NOT NULL,
            z_m REAL NOT NULL,
            receiver_type TEXT NOT NULL,
            antenna_type TEXT NOT NULL,
            source_file TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cddis_stations_lat_lon ON cddis_stations(latitude, longitude)")


def discover_files(args: argparse.Namespace) -> list[Path]:
    if args.file:
        return [Path(value).expanduser() for value in args.file]
    root = Path(args.files_root).expanduser()
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.name.lower().endswith((".gz", ".z")))
    return files[: args.limit] if args.limit > 0 else files


def availability_samples(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    sql = """
        SELECT station4, filename, url
        FROM (
            SELECT f.station4,
                   f.filename,
                   f.url,
                   ROW_NUMBER() OVER (
                       PARTITION BY f.station4
                       ORDER BY CASE WHEN f.filename LIKE '%.crx.gz' THEN 0 ELSE 1 END,
                                f.start_time_utc DESC,
                                f.filename
                   ) AS rn
            FROM cddis_highrate_files f
            LEFT JOIN cddis_stations s ON s.station4 = f.station4
            WHERE s.station4 IS NULL
        )
        WHERE rn = 1
        ORDER BY station4
    """
    if limit > 0:
        sql += " LIMIT ?"
        return list(conn.execute(sql, (limit,)))
    return list(conn.execute(sql))


def download_sample(row: sqlite3.Row, sample_root: Path, cookie_file: Path, timeout: int, overwrite: bool = False) -> Path:
    sample_root.mkdir(parents=True, exist_ok=True)
    filename = Path(str(row["filename"])).name
    target = sample_root / filename
    if target.exists() and target.stat().st_size > 0 and not overwrite:
        return target
    part = target.with_suffix(target.suffix + ".part")
    command = [
        "curl",
        "-L",
        "-n",
        "-b",
        str(cookie_file),
        "-c",
        str(cookie_file),
        "--fail",
        "--silent",
        "--show-error",
        "--connect-timeout",
        str(min(timeout, 60)),
        "--max-time",
        str(timeout),
        "-o",
        str(part),
        str(row["url"]),
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        part.unlink(missing_ok=True)
        detail = next((line.strip() for line in result.stderr.splitlines() if line.strip()), f"curl exited {result.returncode}")
        raise RuntimeError(detail)
    part.replace(target)
    return target


def discover_availability_files(args: argparse.Namespace) -> list[Path]:
    db_path = Path(args.db).expanduser()
    sample_root = Path(args.sample_root).expanduser()
    cookie_file = Path(args.cookie_file).expanduser()
    files: list[Path] = []
    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        rows = availability_samples(conn, args.limit)
    finally:
        conn.close()
    for row in rows:
        try:
            files.append(download_sample(row, sample_root, cookie_file, args.timeout))
        except Exception as exc:  # noqa: BLE001
            print(f"DOWNLOAD_FAIL\t{row['station4']}\t{row['filename']}\t{exc}", file=sys.stderr)
    return files


def upsert_station(conn: sqlite3.Connection, metadata: RinexStationMetadata, updated_at: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO cddis_stations (
            station4, station9, marker_name, marker_number, latitude, longitude, elevation_m,
            x_m, y_m, z_m, receiver_type, antenna_type, source_file, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metadata.station4,
            metadata.station9,
            metadata.marker_name,
            metadata.marker_number,
            metadata.latitude,
            metadata.longitude,
            metadata.elevation_m,
            metadata.x_m,
            metadata.y_m,
            metadata.z_m,
            metadata.receiver_type,
            metadata.antenna_type,
            metadata.source_file,
            updated_at,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.limit < 0:
        raise SystemExit("--limit must be non-negative")
    if args.timeout < 1:
        raise SystemExit("--timeout must be positive")
    files = discover_availability_files(args) if args.from_availability else discover_files(args)
    updated_at = utc_now()
    parsed: list[RinexStationMetadata] = []
    failed = 0
    for path in files:
        try:
            metadata = parse_rinex_header(path)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL\t{path}\t{exc}", file=sys.stderr)
            continue
        if metadata is None:
            failed += 1
            print(f"MISSING_XYZ\t{path}", file=sys.stderr)
            continue
        parsed.append(metadata)

    if not args.dry_run:
        db_path = Path(args.db).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        try:
            init_db(conn)
            with conn:
                for metadata in parsed:
                    upsert_station(conn, metadata, updated_at)
        finally:
            conn.close()

    for metadata in parsed:
        print(
            f"STATION\t{metadata.station4}\t{metadata.latitude:.6f}\t{metadata.longitude:.6f}\t{metadata.elevation_m:.3f}\t{metadata.source_file}"
        )
    print(f"SUMMARY\tfiles={len(files)}\tstations={len(parsed)}\tfailed={failed}", file=sys.stderr)
    return 0 if parsed else 1


if __name__ == "__main__":
    raise SystemExit(main())
