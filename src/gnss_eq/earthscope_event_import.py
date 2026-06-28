from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gnss_eq import monitor, usgs_watcher

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_DB = usgs_watcher.DEFAULT_STATE_DB
DEFAULT_EARTHSCOPE_DB = monitor.DEFAULT_EARTHSCOPE_DB
DEFAULT_EARTHSCOPE_NONCONUS_DB = monitor.DEFAULT_EARTHSCOPE_NONCONUS_DB

EARTHSCOPE_TARGETS = {
    "usa": {
        "source": "earthscope",
        "table": "usgs_m6plus_events_usa",
    },
    "nonconus": {
        "source": "earthscope_nonconus",
        "table": "usgs_m6plus_events_earthscope_nonconus",
    },
}

IMPORT_FIELDS = [
    "kind",
    "ok",
    "target",
    "action",
    "event_id",
    "event_time_utc",
    "magnitude",
    "latitude",
    "longitude",
    "event_table",
    "db",
    "reason",
]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _connect_readonly(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    uri = f"file:{path.resolve(strict=False)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row is not None


def _coerce_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode()
    return value


def _coerce_row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: _coerce_value(row[key]) for key in row.keys()}


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _event_date_parts(event_time_utc: str) -> tuple[str, int, int]:
    event_time = _parse_utc(event_time_utc)
    return event_time.date().isoformat(), event_time.year, int(event_time.strftime("%j"))


def _normalize_longitude(longitude: float) -> float:
    while longitude > 180.0:
        longitude -= 360.0
    while longitude < -180.0:
        longitude += 360.0
    return longitude


def _is_usa_subset(latitude: float, longitude: float, place: str) -> bool:
    longitude = _normalize_longitude(longitude)
    if 24.0 <= latitude <= 50.0 and -130.0 <= longitude <= -60.0:
        return True
    if 45.0 <= latitude <= 72.0 and (-180.0 <= longitude <= -125.0 or 170.0 <= longitude <= 180.0):
        return True
    if 15.0 <= latitude <= 25.0 and -162.0 <= longitude <= -154.0:
        return True
    if 16.0 <= latitude <= 20.0 and -68.0 <= longitude <= -63.0:
        normalized_place = place.lower()
        return "puerto rico" in normalized_place or "virgin islands" in normalized_place
    return False


def _target_for_event(event: dict[str, Any], target: str) -> str:
    if target in {"usa", "nonconus"}:
        return target
    latitude = float(event["latitude"])
    longitude = float(event["longitude"])
    place = str(event.get("place") or "")
    return "usa" if _is_usa_subset(latitude, longitude, place) else "nonconus"


def _database_error(target: str, path: Path, code: str = "DATABASE_NOT_FOUND") -> dict[str, Any]:
    return {
        "kind": "ERROR",
        "ok": False,
        "target": target,
        "action": code,
        "db": _display_path(path),
        "reason": f"Database not found: {_display_path(path)}" if code == "DATABASE_NOT_FOUND" else f"Database unavailable: {_display_path(path)}",
    }


def _list_watcher_events(
    state_db: Path,
    *,
    event_ids: list[str],
    min_magnitude: float,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    conn = _connect_readonly(state_db)
    if conn is None:
        return [], [_database_error("watcher", state_db)]
    try:
        if not _table_exists(conn, "usgs_watcher_events"):
            return [], [
                {
                    "kind": "ERROR",
                    "ok": False,
                    "target": "watcher",
                    "action": "TABLE_NOT_FOUND",
                    "db": _display_path(state_db),
                    "reason": "usgs_watcher_events table not found",
                }
            ]
        conditions = ["region = 'americas'", "COALESCE(magnitude, 0) >= ?"]
        params: list[Any] = [min_magnitude]
        if event_ids:
            placeholders = ",".join("?" for _ in event_ids)
            conditions.append(f"event_id IN ({placeholders})")
            params.extend(event_ids)
        sql = f"""
            SELECT event_id,
                   event_time_utc,
                   first_seen_utc,
                   last_seen_utc,
                   usgs_updated_utc,
                   latitude,
                   longitude,
                   depth_km,
                   magnitude,
                   mag_type,
                   place,
                   title,
                   usgs_url,
                   detail_url,
                   scope,
                   region
              FROM usgs_watcher_events
             WHERE {' AND '.join(conditions)}
             ORDER BY first_seen_utc DESC, event_time_utc DESC, event_id DESC
             LIMIT ?
        """
        rows = conn.execute(sql, (*params, limit)).fetchall()
        return [_coerce_row(row) for row in rows], []
    finally:
        conn.close()


def _upsert_event(
    conn: sqlite3.Connection,
    table: str,
    event: dict[str, Any],
    *,
    min_magnitude: float,
    dry_run: bool,
    update_existing: bool,
) -> str:
    existing = conn.execute(f"SELECT 1 FROM {table} WHERE event_id = ?", (event["event_id"],)).fetchone()
    if existing and not update_existing:
        return "WOULD_SKIP_EXISTS" if dry_run else "SKIPPED_EXISTS"
    action = "UPDATE" if existing else "INSERT"
    if dry_run:
        return f"WOULD_{action}"

    event_date, year, doy = _event_date_parts(str(event["event_time_utc"]))
    updated_at = _utc_now()
    values = {
        "event_id": str(event["event_id"]),
        "title": str(event.get("title") or f"M{float(event['magnitude']):.1f} - {event.get('place') or ''}"),
        "time_utc": str(event["event_time_utc"]),
        "event_date": event_date,
        "year": year,
        "doy": doy,
        "magnitude": float(event["magnitude"]),
        "longitude": float(event["longitude"]),
        "latitude": float(event["latitude"]),
        "depth_km": event.get("depth_km"),
        "place": str(event.get("place") or ""),
        "usgs_url": str(event.get("usgs_url") or ""),
        "query_start": str(event.get("first_seen_utc") or event["event_time_utc"]),
        "query_end": str(event.get("last_seen_utc") or event["event_time_utc"]),
        "min_magnitude": min_magnitude,
        "region_filter": "usgs_watcher_americas",
        "updated_at": updated_at,
    }
    conn.execute(
        f"""
        INSERT INTO {table} (
            event_id, title, time_utc, event_date, year, doy, magnitude,
            longitude, latitude, depth_km, place, usgs_url, query_start,
            query_end, min_magnitude, region_filter, updated_at
        ) VALUES (
            :event_id, :title, :time_utc, :event_date, :year, :doy, :magnitude,
            :longitude, :latitude, :depth_km, :place, :usgs_url, :query_start,
            :query_end, :min_magnitude, :region_filter, :updated_at
        )
        ON CONFLICT(event_id) DO UPDATE SET
            title = excluded.title,
            time_utc = excluded.time_utc,
            event_date = excluded.event_date,
            year = excluded.year,
            doy = excluded.doy,
            magnitude = excluded.magnitude,
            longitude = excluded.longitude,
            latitude = excluded.latitude,
            depth_km = excluded.depth_km,
            place = excluded.place,
            usgs_url = excluded.usgs_url,
            query_start = excluded.query_start,
            query_end = excluded.query_end,
            min_magnitude = excluded.min_magnitude,
            region_filter = excluded.region_filter,
            updated_at = excluded.updated_at
        """,
        values,
    )
    return action


def _import_event_to_target(
    event: dict[str, Any],
    *,
    target: str,
    db_path: Path,
    min_magnitude: float,
    dry_run: bool,
    update_existing: bool,
) -> tuple[dict[str, Any], dict[str, int]]:
    config = EARTHSCOPE_TARGETS[target]
    table = str(config["table"])
    counts = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
    if not db_path.exists():
        counts["errors"] += 1
        return _database_error(target, db_path), counts

    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, table):
            counts["errors"] += 1
            return (
                {
                    "kind": "ERROR",
                    "ok": False,
                    "target": target,
                    "action": "TABLE_NOT_FOUND",
                    "event_id": event.get("event_id"),
                    "event_table": table,
                    "db": _display_path(db_path),
                    "reason": f"{table} table not found",
                },
                counts,
            )
        with conn:
            action = _upsert_event(
                conn,
                table,
                event,
                min_magnitude=min_magnitude,
                dry_run=dry_run,
                update_existing=update_existing,
            )
    finally:
        conn.close()

    if action.endswith("INSERT"):
        counts["inserted"] += 1
    elif action.endswith("UPDATE"):
        counts["updated"] += 1
    elif action in {"SKIPPED_EXISTS", "WOULD_SKIP_EXISTS"}:
        counts["skipped"] += 1
    row = {
        "kind": "EVENT",
        "ok": True,
        "target": target,
        "action": action,
        "event_id": event.get("event_id"),
        "event_time_utc": event.get("event_time_utc"),
        "magnitude": event.get("magnitude"),
        "latitude": event.get("latitude"),
        "longitude": event.get("longitude"),
        "event_table": table,
        "db": _display_path(db_path),
        "reason": "dry run" if dry_run else "imported from USGS watcher state",
    }
    return row, counts


def import_watched_events(
    *,
    state_db: Path = DEFAULT_STATE_DB,
    target: str = "auto",
    event_ids: list[str] | None = None,
    min_magnitude: float = 6.0,
    limit: int = 20,
    earthscope_db: Path = DEFAULT_EARTHSCOPE_DB,
    earthscope_nonconus_db: Path = DEFAULT_EARTHSCOPE_NONCONUS_DB,
    dry_run: bool = False,
    update_existing: bool = False,
) -> dict[str, Any]:
    if target not in {"auto", "usa", "nonconus"}:
        raise ValueError("target must be one of: auto, usa, nonconus")
    if limit < 1:
        raise ValueError("limit must be a positive integer")

    event_ids = event_ids or []
    state_db = Path(state_db)
    events, errors = _list_watcher_events(state_db, event_ids=event_ids, min_magnitude=min_magnitude, limit=limit)
    counts = {"total": len(events), "inserted": 0, "updated": 0, "skipped": 0, "errors": len(errors)}
    rows: list[dict[str, Any]] = []
    target_paths = {
        "usa": Path(earthscope_db),
        "nonconus": Path(earthscope_nonconus_db),
    }

    for event in events:
        event_target = _target_for_event(event, target)
        row, current_counts = _import_event_to_target(
            event,
            target=event_target,
            db_path=target_paths[event_target],
            min_magnitude=min_magnitude,
            dry_run=dry_run,
            update_existing=update_existing,
        )
        rows.append(row)
        counts["inserted"] += current_counts["inserted"]
        counts["updated"] += current_counts["updated"]
        counts["skipped"] += current_counts["skipped"]
        counts["errors"] += current_counts["errors"]

    return {
        "ok": counts["errors"] == 0,
        "dry_run": dry_run,
        "state_db": _display_path(state_db),
        "target": target,
        "limit": limit,
        "min_magnitude": min_magnitude,
        "earthscope_db": _display_path(Path(earthscope_db)),
        "earthscope_nonconus_db": _display_path(Path(earthscope_nonconus_db)),
        "counts": counts,
        "events": rows,
        "errors": errors,
    }


def _tsv_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\n", " ")


def _write_tsv_row(row: dict[str, Any]) -> None:
    print("\t".join(_tsv_value(row.get(field, "")) for field in IMPORT_FIELDS))


def write_import_tsv(report: dict[str, Any]) -> None:
    print("\t".join(IMPORT_FIELDS))
    counts = report.get("counts", {})
    _write_tsv_row(
        {
            "kind": "SUMMARY",
            "ok": report.get("ok"),
            "target": report.get("target"),
            "action": "DRY_RUN" if report.get("dry_run") else "IMPORT",
            "reason": (
                f"total={counts.get('total', 0)} inserted={counts.get('inserted', 0)} "
                f"updated={counts.get('updated', 0)} skipped={counts.get('skipped', 0)} errors={counts.get('errors', 0)}"
            ),
        }
    )
    for error in report.get("errors", []):
        _write_tsv_row(error)
    for event in report.get("events", []):
        _write_tsv_row(event)


def write_import_json(report: dict[str, Any]) -> None:
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()
