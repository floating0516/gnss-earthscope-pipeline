#!/usr/bin/env python3
"""Populate station siting metadata for EarthScope and GeoNet SQLite databases."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gnss_eq.station_siting import ensure_station_siting_table, upsert_station_siting

DAI_URL = "https://www.unavco.org/data/gps-gnss/data-access-methods/dai1/perm_sta.php"
DEFAULT_EARTHSCOPE_DBS = [
    ROOT / "data" / "earthscope_availability" / "earthscope_1hz.sqlite",
    ROOT / "data" / "earthscope_availability" / "earthscope_nonconus_1hz.sqlite",
]
DEFAULT_GEONET_DB = ROOT / "data" / "geonet_availability" / "geonet_1hz.sqlite"


class HtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._stack: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._stack.append({"rows": [], "row": None, "cell": None})
        elif tag == "tr" and self._stack:
            self._stack[-1]["row"] = []
        elif tag in {"td", "th"} and self._stack and self._stack[-1].get("row") is not None:
            self._stack[-1]["cell"] = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._stack:
            return
        current = self._stack[-1]
        if tag in {"td", "th"} and current.get("cell") is not None and current.get("row") is not None:
            cell_values = current["cell"]
            row_values = current["row"]
            assert isinstance(cell_values, list)
            assert isinstance(row_values, list)
            text = re.sub(r"\s+", " ", "".join(cell_values)).strip()
            row_values.append(text)
            current["cell"] = None
        elif tag == "tr" and current.get("row") is not None:
            rows = current["rows"]
            row_values = current["row"]
            assert isinstance(rows, list)
            assert isinstance(row_values, list)
            if any(cell for cell in row_values):
                rows.append(row_values)
            current["row"] = None
        elif tag == "table":
            finished = self._stack.pop()
            rows = finished["rows"]
            assert isinstance(rows, list)
            if rows:
                self.tables.append(rows)

    def handle_data(self, data: str) -> None:
        if self._stack and self._stack[-1].get("cell") is not None:
            cell_values = self._stack[-1]["cell"]
            assert isinstance(cell_values, list)
            cell_values.append(data)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["earthscope", "geonet", "all"], default="all")
    parser.add_argument("--earthscope-db", action="append", type=Path, help="EarthScope SQLite DB; may be repeated")
    parser.add_argument("--geonet-db", type=Path, default=DEFAULT_GEONET_DB)
    parser.add_argument("--station", action="append", help="Limit EarthScope DAI sync to selected station code(s)")
    parser.add_argument("--batch-size", type=int, default=75)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def parse_float(value: str) -> float | None:
    text = str(value or "").strip().replace("°", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    if re.search(r"\b[WS]\b", text, re.IGNORECASE):
        number = -abs(number)
    return number


def parse_coordinate_pair(value: str) -> tuple[float | None, float | None]:
    text = str(value or "")
    matches = re.findall(r"([-+]?\d+(?:\.\d+)?)\s*°?\s*([NSEW])", text, flags=re.IGNORECASE)
    lat: float | None = None
    lon: float | None = None
    for number_text, direction in matches:
        number = float(number_text)
        direction = direction.upper()
        if direction in {"S", "W"}:
            number = -abs(number)
        if direction in {"N", "S"}:
            lat = number
        elif direction in {"E", "W"}:
            lon = number
    return lat, lon


def find_column(headers: list[str], *needles: str) -> int | None:
    normalized = [normalize_header(header) for header in headers]
    for needle in needles:
        target = normalize_header(needle)
        for idx, header in enumerate(normalized):
            if target and target in header:
                return idx
    return None


def cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def parse_dai_station_rows(html: str) -> dict[str, dict[str, object]]:
    parser = HtmlTableParser()
    parser.feed(html)
    result: dict[str, dict[str, object]] = {}
    for table in parser.tables:
        if len(table) < 2:
            continue
        header_index = None
        for index, possible_headers in enumerate(table[:-1]):
            station_idx = find_column(possible_headers, "station code", "station")
            monument_idx = find_column(possible_headers, "monument style", "attachment description")
            if station_idx is not None and monument_idx is not None:
                header_index = index
                break
        if header_index is None:
            continue
        headers = table[header_index]
        station_idx = find_column(headers, "station code", "station")
        monument_idx = find_column(headers, "monument style", "attachment description")
        if station_idx is None or monument_idx is None:
            continue
        lat_idx = find_column(headers, "latitude", "lat")
        lon_idx = find_column(headers, "longitude", "lon")
        name_idx = find_column(headers, "station name", "name")
        for row in table[header_index + 1 :]:
            station = cell(row, station_idx).upper()[:4]
            if not re.fullmatch(r"[A-Z0-9]{4}", station):
                continue
            if lat_idx is not None and lon_idx is not None and lat_idx == lon_idx:
                latitude, longitude = parse_coordinate_pair(cell(row, lat_idx))
            else:
                latitude = parse_float(cell(row, lat_idx))
                longitude = parse_float(cell(row, lon_idx))
            result[station] = {
                "station": station,
                "station_name": cell(row, name_idx),
                "latitude": latitude,
                "longitude": longitude,
                "monument_style": cell(row, monument_idx),
            }
    return result


def build_dai_url(stations: list[str], limit: int) -> str:
    params = [
        ("pview", "original"),
        ("filter_station_code", "checked"),
        ("station_code", " ".join(stations)),
        ("tabular", "Y"),
        ("limit", str(limit)),
        ("offset", "0"),
        ("sort_col", "permanent_station.station_code"),
        ("sort_order", "ASC"),
        (
            "column_list",
            "select permanent_station.station_code monument.lat monument.lon data "
            "permanent_station.station_name min_start max_end attachment_description.description log",
        ),
        ("column_list_count", "8"),
        ("view", "View Results"),
    ]
    return DAI_URL + "?" + urllib.parse.urlencode(params)


def fetch_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "gnss-earthscope-pipeline station-siting-sync"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row is not None


def collect_earthscope_station_codes(conn: sqlite3.Connection) -> list[str]:
    tables = [
        ("station_day_availability", "station"),
        ("event_earthscope_station_candidates", "station"),
        ("event_earthscope_station_verified_files", "station"),
    ]
    codes: set[str] = set()
    for table, column in tables:
        if not table_exists(conn, table):
            continue
        for row in conn.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL"):
            station = str(row[0] or "").strip().upper()[:4]
            if station:
                codes.add(station)
    return sorted(codes)


def chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def sync_earthscope_station_siting(
    conn: sqlite3.Connection,
    *,
    stations: list[str] | None,
    updated_at: str,
    batch_size: int,
    timeout: int,
    dry_run: bool = False,
) -> int:
    ensure_station_siting_table(conn)
    station_codes = sorted({str(station).strip().upper()[:4] for station in (stations or collect_earthscope_station_codes(conn)) if station})
    if dry_run:
        print(f"EARTHSCOPE_DRY_RUN\tstations={len(station_codes)}")
        return len(station_codes)

    written = 0
    for batch in chunks(station_codes, batch_size):
        url = build_dai_url(batch, max(500, len(batch) * 5))
        rows = parse_dai_station_rows(fetch_text(url, timeout))
        with conn:
            for station in batch:
                metadata = rows.get(station, {})
                upsert_station_siting(
                    conn,
                    provider="EarthScope",
                    station=station,
                    monument_style=metadata.get("monument_style") or "UNKNOWN",
                    station_name=metadata.get("station_name") or "",
                    latitude=metadata.get("latitude") if isinstance(metadata.get("latitude"), float) else None,
                    longitude=metadata.get("longitude") if isinstance(metadata.get("longitude"), float) else None,
                    siting_source="EarthScope DAI",
                    source_url=url,
                    raw_metadata=metadata,
                    updated_at=updated_at,
                )
                written += 1
    return written


def sync_geonet_station_siting(conn: sqlite3.Connection, updated_at: str, dry_run: bool = False) -> int:
    if not table_exists(conn, "geonet_gnss_stations"):
        raise RuntimeError("geonet_gnss_stations table not found")
    rows = conn.execute(
        """
        SELECT station, station9, name, latitude, longitude
        FROM geonet_gnss_stations
        WHERE station IS NOT NULL
        ORDER BY station
        """
    ).fetchall()
    if dry_run:
        print(f"GEONET_DRY_RUN\tstations={len(rows)}")
        return len(rows)

    ensure_station_siting_table(conn)
    with conn:
        for row in rows:
            values = dict(row) if isinstance(row, sqlite3.Row) else {
                "station": row[0],
                "station9": row[1],
                "name": row[2],
                "latitude": row[3],
                "longitude": row[4],
            }
            upsert_station_siting(
                conn,
                provider="GeoNet",
                station=values.get("station") or "",
                station9=values.get("station9") or "",
                station_name=values.get("name") or "",
                latitude=float(values["latitude"]) if values.get("latitude") is not None else None,
                longitude=float(values["longitude"]) if values.get("longitude") is not None else None,
                monument_style="UNKNOWN",
                siting_source="GeoNet station inventory",
                raw_metadata=values,
                updated_at=updated_at,
            )
    return len(rows)


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    updated_at = utc_now()
    total = 0

    if args.source in {"earthscope", "all"}:
        earthscope_dbs = args.earthscope_db or [path for path in DEFAULT_EARTHSCOPE_DBS if path.exists()]
        for db_path in earthscope_dbs:
            conn = connect(db_path)
            try:
                count = sync_earthscope_station_siting(
                    conn,
                    stations=args.station,
                    updated_at=updated_at,
                    batch_size=args.batch_size,
                    timeout=args.timeout,
                    dry_run=args.dry_run,
                )
                total += count
                print(f"EARTHSCOPE\t{db_path}\tstations={count}")
            finally:
                conn.close()

    if args.source in {"geonet", "all"} and args.geonet_db.exists():
        conn = connect(args.geonet_db)
        try:
            count = sync_geonet_station_siting(conn, updated_at, dry_run=args.dry_run)
            total += count
            print(f"GEONET\t{args.geonet_db}\tstations={count}")
        finally:
            conn.close()

    print(f"SUMMARY\tstation_siting_rows_processed={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
