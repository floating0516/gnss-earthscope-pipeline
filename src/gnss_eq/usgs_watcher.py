from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_DB = ROOT / "data" / "live" / "usgs_watcher.sqlite"
USGS_QUERY_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
USER_AGENT = "gnss-earthscope-pipeline/0.1"

WATCH_FIELDS = [
    "kind",
    "status",
    "event_id",
    "event_time_utc",
    "first_seen_utc",
    "magnitude",
    "latitude",
    "longitude",
    "depth_km",
    "mag_type",
    "region",
    "scope",
    "place",
    "title",
    "usgs_url",
    "detail",
]

QUERY_BOXES = [
    ("americas", "americas_main", -60.0, 75.0, -170.0, -30.0),
    ("americas", "americas_aleutians", 45.0, 75.0, 170.0, 180.0),
    ("nz", "new_zealand_west", -55.0, -25.0, 160.0, 180.0),
    ("nz", "new_zealand_east", -55.0, -25.0, -180.0, -170.0),
]

SCOPE_ALIASES = {
    "americas": "americas",
    "america": "americas",
    "nz": "nz",
    "new_zealand": "nz",
    "new-zealand": "nz",
}


FetchJson = Callable[[str, int], Any]
NowFunc = Callable[[], str]
SleepFunc = Callable[[int], Any]


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now() -> str:
    return _format_utc(datetime.now(timezone.utc))


def iso_utc_from_ms(value: int | float | None) -> str:
    if value is None:
        return ""
    return _format_utc(datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc))


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scope_tokens(scope: str) -> tuple[str, ...]:
    tokens = set()
    for raw_token in scope.split(","):
        raw_token = raw_token.strip().lower()
        if not raw_token:
            continue
        token = SCOPE_ALIASES.get(raw_token)
        if token is None:
            raise ValueError("scope must contain only: americas, nz")
        tokens.add(token)
    if not tokens:
        raise ValueError("scope must contain at least one region")
    return tuple(token for token in ("americas", "nz") if token in tokens)


def normalize_scope(scope: str) -> str:
    return ",".join(_scope_tokens(scope))


def build_usgs_urls(
    *,
    scope: str = "americas,nz",
    starttime: str,
    endtime: str,
    min_magnitude: float = 6.0,
    limit: int = 2000,
) -> list[str]:
    tokens = set(_scope_tokens(scope))
    urls = []
    for token, _, min_latitude, max_latitude, min_longitude, max_longitude in QUERY_BOXES:
        if token not in tokens:
            continue
        params = {
            "format": "geojson",
            "starttime": starttime,
            "endtime": endtime,
            "minmagnitude": min_magnitude,
            "minlatitude": min_latitude,
            "maxlatitude": max_latitude,
            "minlongitude": min_longitude,
            "maxlongitude": max_longitude,
            "orderby": "time-asc",
            "limit": limit,
        }
        urls.append(f"{USGS_QUERY_URL}?{urlencode(params)}")
    return urls


def fetch_json(url: str, timeout: int) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_events(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = []
    features = payload.get("features", [])
    if not isinstance(features, list):
        return events
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        if not isinstance(props, Mapping) or not isinstance(geometry, Mapping):
            continue
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            continue
        longitude = _as_float(coordinates[0])
        latitude = _as_float(coordinates[1])
        if latitude is None or longitude is None:
            continue
        event_id = str(feature.get("id") or props.get("code") or "").strip()
        if not event_id:
            continue
        depth_km = _as_float(coordinates[2]) if len(coordinates) >= 3 else None
        events.append(
            {
                "event_id": event_id,
                "event_time_utc": iso_utc_from_ms(_as_float(props.get("time"))),
                "usgs_updated_utc": iso_utc_from_ms(_as_float(props.get("updated"))),
                "latitude": latitude,
                "longitude": longitude,
                "depth_km": depth_km,
                "magnitude": _as_float(props.get("mag")),
                "mag_type": str(props.get("magType") or ""),
                "place": str(props.get("place") or ""),
                "title": str(props.get("title") or ""),
                "usgs_url": str(props.get("url") or ""),
                "detail_url": str(props.get("detail") or ""),
                "raw_json": json.dumps(feature, ensure_ascii=False, sort_keys=True),
            }
        )
    return events


def _normalize_longitude(longitude: float) -> float:
    while longitude > 180.0:
        longitude -= 360.0
    while longitude < -180.0:
        longitude += 360.0
    return longitude


def classify_region(latitude: float, longitude: float) -> str | None:
    longitude = _normalize_longitude(longitude)
    if -55.0 <= latitude <= -25.0 and (160.0 <= longitude <= 180.0 or -180.0 <= longitude <= -170.0):
        return "new_zealand"
    if -60.0 <= latitude <= 75.0 and -170.0 <= longitude <= -30.0:
        return "americas"
    if 45.0 <= latitude <= 75.0 and 170.0 <= longitude <= 180.0:
        return "americas"
    return None


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS usgs_watcher_events (
            event_id TEXT PRIMARY KEY,
            event_time_utc TEXT NOT NULL,
            first_seen_utc TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL,
            usgs_updated_utc TEXT NOT NULL DEFAULT '',
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            depth_km REAL,
            magnitude REAL,
            mag_type TEXT NOT NULL DEFAULT '',
            place TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            usgs_url TEXT NOT NULL DEFAULT '',
            detail_url TEXT NOT NULL DEFAULT '',
            scope TEXT NOT NULL,
            region TEXT NOT NULL,
            raw_json TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS usgs_watcher_polls (
            poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_utc TEXT NOT NULL,
            finished_utc TEXT NOT NULL,
            status TEXT NOT NULL,
            url_count INTEGER NOT NULL,
            fetched_count INTEGER NOT NULL,
            new_count INTEGER NOT NULL,
            error TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS usgs_watcher_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_usgs_watcher_events_time ON usgs_watcher_events(event_time_utc);
        CREATE INDEX IF NOT EXISTS idx_usgs_watcher_events_first_seen ON usgs_watcher_events(first_seen_utc);
        CREATE INDEX IF NOT EXISTS idx_usgs_watcher_events_region ON usgs_watcher_events(region);
        CREATE INDEX IF NOT EXISTS idx_usgs_watcher_events_magnitude ON usgs_watcher_events(magnitude);
        """
    )
    conn.commit()


def _get_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM usgs_watcher_state WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row else None


def _set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO usgs_watcher_state(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def _record_poll(
    conn: sqlite3.Connection,
    *,
    started_utc: str,
    finished_utc: str,
    status: str,
    url_count: int,
    fetched_count: int,
    new_count: int,
    error: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO usgs_watcher_polls(
            started_utc, finished_utc, status, url_count, fetched_count, new_count, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (started_utc, finished_utc, status, url_count, fetched_count, new_count, error),
    )
    conn.commit()


def record_events(conn: sqlite3.Connection, events: list[dict[str, Any]], seen_at: str, scope: str) -> list[dict[str, Any]]:
    normalized_scope = normalize_scope(scope)
    new_events = []
    for event in events:
        existing = conn.execute(
            "SELECT first_seen_utc FROM usgs_watcher_events WHERE event_id = ?",
            (event.get("event_id"),),
        ).fetchone()
        values = {
            "event_id": event.get("event_id", ""),
            "event_time_utc": event.get("event_time_utc", ""),
            "last_seen_utc": seen_at,
            "usgs_updated_utc": event.get("usgs_updated_utc", ""),
            "latitude": event.get("latitude"),
            "longitude": event.get("longitude"),
            "depth_km": event.get("depth_km"),
            "magnitude": event.get("magnitude"),
            "mag_type": event.get("mag_type", ""),
            "place": event.get("place", ""),
            "title": event.get("title", ""),
            "usgs_url": event.get("usgs_url", ""),
            "detail_url": event.get("detail_url", ""),
            "scope": normalized_scope,
            "region": event.get("region", ""),
            "raw_json": event.get("raw_json", ""),
        }
        if existing is None:
            conn.execute(
                """
                INSERT INTO usgs_watcher_events(
                    event_id, event_time_utc, first_seen_utc, last_seen_utc, usgs_updated_utc,
                    latitude, longitude, depth_km, magnitude, mag_type, place, title, usgs_url,
                    detail_url, scope, region, raw_json
                ) VALUES (
                    :event_id, :event_time_utc, :first_seen_utc, :last_seen_utc, :usgs_updated_utc,
                    :latitude, :longitude, :depth_km, :magnitude, :mag_type, :place, :title,
                    :usgs_url, :detail_url, :scope, :region, :raw_json
                )
                """,
                {**values, "first_seen_utc": seen_at},
            )
            new_events.append({**event, "first_seen_utc": seen_at, "last_seen_utc": seen_at, "scope": normalized_scope})
        else:
            conn.execute(
                """
                UPDATE usgs_watcher_events
                   SET event_time_utc = :event_time_utc,
                       last_seen_utc = :last_seen_utc,
                       usgs_updated_utc = :usgs_updated_utc,
                       latitude = :latitude,
                       longitude = :longitude,
                       depth_km = :depth_km,
                       magnitude = :magnitude,
                       mag_type = :mag_type,
                       place = :place,
                       title = :title,
                       usgs_url = :usgs_url,
                       detail_url = :detail_url,
                       scope = :scope,
                       region = :region,
                       raw_json = :raw_json
                 WHERE event_id = :event_id
                """,
                values,
            )
    conn.commit()
    return new_events


def _query_window(
    conn: sqlite3.Connection,
    end_utc: str,
    lookback_minutes: int,
    overlap_minutes: int,
    ignore_state: bool,
) -> tuple[str, str]:
    last_finished = None if ignore_state else _get_state(conn, "last_poll_finished_utc")
    if last_finished:
        return _format_utc(_parse_utc(last_finished) - timedelta(minutes=overlap_minutes)), "overlap"
    return _format_utc(_parse_utc(end_utc) - timedelta(minutes=lookback_minutes)), "lookback"


def _filter_events_for_scope(events: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    tokens = set(_scope_tokens(scope))
    allowed_regions = set()
    if "americas" in tokens:
        allowed_regions.add("americas")
    if "nz" in tokens:
        allowed_regions.add("new_zealand")

    filtered_by_id = {}
    for event in events:
        region = classify_region(float(event["latitude"]), float(event["longitude"]))
        if region not in allowed_regions:
            continue
        event_id = str(event.get("event_id") or "")
        if event_id and event_id not in filtered_by_id:
            filtered_by_id[event_id] = {**event, "region": region}
    return sorted(filtered_by_id.values(), key=lambda event: (event.get("event_time_utc", ""), event.get("event_id", "")))


def _error_text(exc: BaseException) -> str:
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def poll_once(
    *,
    state_db: Path,
    scope: str = "americas,nz",
    min_magnitude: float = 6.0,
    lookback_minutes: int = 1440,
    overlap_minutes: int = 30,
    limit: int = 2000,
    timeout: int = 30,
    ignore_state: bool = False,
    fetcher: FetchJson = fetch_json,
    now: NowFunc = utc_now,
) -> dict[str, Any]:
    normalized_scope = normalize_scope(scope)
    started_utc = now()
    state_db = Path(state_db)
    state_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(state_db)
    try:
        init_db(conn)
        query_start_utc, query_mode = _query_window(conn, started_utc, lookback_minutes, overlap_minutes, ignore_state)
        query_end_utc = started_utc
        urls = build_usgs_urls(
            scope=normalized_scope,
            starttime=query_start_utc,
            endtime=query_end_utc,
            min_magnitude=min_magnitude,
            limit=limit,
        )
        fetched_events = []
        error = ""
        for url in urls:
            try:
                fetched_events.extend(parse_events(fetcher(url, timeout)))
            except Exception as exc:  # noqa: BLE001
                error = _error_text(exc)
                break

        if error:
            finished_utc = now()
            result = {
                "status": "ERROR",
                "started_utc": started_utc,
                "finished_utc": finished_utc,
                "query_start_utc": query_start_utc,
                "query_end_utc": query_end_utc,
                "query_mode": query_mode,
                "scope": normalized_scope,
                "url_count": len(urls),
                "fetched_count": len(fetched_events),
                "new_count": 0,
                "events": [],
                "error": error,
                "urls": urls,
            }
            _record_poll(
                conn,
                started_utc=started_utc,
                finished_utc=finished_utc,
                status="ERROR",
                url_count=len(urls),
                fetched_count=len(fetched_events),
                new_count=0,
                error=error,
            )
            return result

        filtered_events = _filter_events_for_scope(fetched_events, normalized_scope)
        finished_utc = now()
        new_events = record_events(conn, filtered_events, finished_utc, normalized_scope)
        _set_state(conn, "last_poll_started_utc", started_utc)
        _set_state(conn, "last_poll_finished_utc", finished_utc)
        _record_poll(
            conn,
            started_utc=started_utc,
            finished_utc=finished_utc,
            status="OK",
            url_count=len(urls),
            fetched_count=len(filtered_events),
            new_count=len(new_events),
        )
        return {
            "status": "OK",
            "started_utc": started_utc,
            "finished_utc": finished_utc,
            "query_start_utc": query_start_utc,
            "query_end_utc": query_end_utc,
            "query_mode": query_mode,
            "scope": normalized_scope,
            "url_count": len(urls),
            "fetched_count": len(filtered_events),
            "new_count": len(new_events),
            "events": new_events,
            "error": "",
            "urls": urls,
        }
    finally:
        conn.close()


def _tsv_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ")


def _write_tsv_row(row: dict[str, Any]) -> None:
    print("\t".join(_tsv_value(row.get(field, "")) for field in WATCH_FIELDS))


def _poll_detail(result: dict[str, Any]) -> str:
    if result.get("error"):
        return str(result.get("error"))
    return (
        f"mode={result.get('query_mode')} "
        f"window={result.get('query_start_utc')}..{result.get('query_end_utc')} "
        f"urls={result.get('url_count')} fetched={result.get('fetched_count')} new={result.get('new_count')}"
    )


def write_tsv(result: dict[str, Any], *, include_header: bool = True) -> None:
    if include_header:
        print("\t".join(WATCH_FIELDS))
    _write_tsv_row(
        {
            "kind": "POLL",
            "status": result.get("status"),
            "scope": result.get("scope"),
            "detail": _poll_detail(result),
        }
    )
    if result.get("status") != "OK":
        _write_tsv_row(
            {
                "kind": "ERROR",
                "status": result.get("status"),
                "scope": result.get("scope"),
                "detail": result.get("error"),
            }
        )
    for event in result.get("events", []):
        _write_tsv_row(
            {
                "kind": "EVENT",
                "status": result.get("status"),
                "event_id": event.get("event_id"),
                "event_time_utc": event.get("event_time_utc"),
                "first_seen_utc": event.get("first_seen_utc"),
                "magnitude": event.get("magnitude"),
                "latitude": event.get("latitude"),
                "longitude": event.get("longitude"),
                "depth_km": event.get("depth_km"),
                "mag_type": event.get("mag_type"),
                "region": event.get("region"),
                "scope": event.get("scope") or result.get("scope"),
                "place": event.get("place"),
                "title": event.get("title"),
                "usgs_url": event.get("usgs_url"),
                "detail": event.get("detail_url"),
            }
        )


def _public_event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in event.items() if key != "raw_json"}


def write_json_lines(result: dict[str, Any]) -> None:
    payload = {**result, "events": [_public_event(event) for event in result.get("events", [])]}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def run_watch_loop(
    args: argparse.Namespace,
    *,
    fetcher: FetchJson = fetch_json,
    sleeper: SleepFunc = time.sleep,
    now: NowFunc = utc_now,
) -> int:
    include_header = True
    try:
        while True:
            result = poll_once(
                state_db=Path(args.state_db),
                scope=args.scope,
                min_magnitude=args.min_magnitude,
                lookback_minutes=args.lookback_minutes,
                overlap_minutes=args.overlap_minutes,
                limit=args.limit,
                timeout=args.timeout,
                ignore_state=args.ignore_state,
                fetcher=fetcher,
                now=now,
            )
            if args.format == "jsonl":
                write_json_lines(result)
            else:
                write_tsv(result, include_header=include_header)
                include_header = False
            sys.stdout.flush()
            if args.once:
                return 0 if result.get("status") == "OK" else 1
            sleeper(args.interval)
    except KeyboardInterrupt:
        return 130
